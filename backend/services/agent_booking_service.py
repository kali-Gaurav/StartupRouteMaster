"""
Agent Booking Service - Production Version
Handles manual agent fulfillment requests and state enforcement.
With circuit breaker protection, retry logic, and comprehensive error handling.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from dataclasses import dataclass, field
from collections import deque
from contextlib import asynccontextmanager

from database.models import Booking, EscrowStatus, PassengerDetails, AuditLog
from core.data_structures import Passenger
from core.resilience import circuit_breaker_manager, CircuitBreakerState
from core.retry import retry_sync, RetryPolicy
from services.cache_service import cache_service

logger = logging.getLogger(__name__)


@dataclass
class AgentBookingConfig:
    """Configuration for agent booking service."""
    agent_fee: float = 10.0
    cache_ttl_seconds: int = 300
    retry_policy: RetryPolicy = field(default_factory=lambda: RetryPolicy(
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0,
        retry_on_exceptions=(TimeoutError, ConnectionError, OSError)
    ))
    circuit_failure_threshold: int = 5
    circuit_recovery_seconds: int = 60


@dataclass
class AgentBookingResult:
    """Result of agent booking operation."""
    success: bool
    booking_id: Optional[str]
    user_id: str
    route_id: str
    total_amount: float
    ticket_fare: float
    agent_fee: float
    message: str
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "booking_id": self.booking_id,
            "user_id": self.user_id,
            "route_id": self.route_id,
            "total_amount": self.total_amount,
            "ticket_fare": self.ticket_fare,
            "agent_fee": self.agent_fee,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp
        }


@dataclass
class AgentClaimResult:
    """Result of agent claiming a booking."""
    success: bool
    booking_id: str
    agent_id: str
    commission_amount: float
    message: str
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "booking_id": self.booking_id,
            "agent_id": self.agent_id,
            "commission_amount": self.commission_amount,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp
        }


class AgentBookingService:
    """
    Agent Booking Service - Phase 5 Monetization
    Handles manual agent fulfillment requests and state enforcement.
    With circuit breaker protection and retry logic.
    """
    
    def __init__(self, config: Optional[AgentBookingConfig] = None):
        self.config = config or AgentBookingConfig()
        
        # Circuit breaker for database operations
        self._breaker = circuit_breaker_manager.get_breaker("agent_booking")
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = None
        
        logger.info("AgentBookingService initialized with resilience patterns")

    def _get_cache_key(self, booking_id: str) -> str:
        """Generate cache key for booking status."""
        return f"agent_booking:{booking_id}"

    def _get_cached_booking(self, booking_id: str) -> Optional[Dict]:
        """Get cached booking data."""
        cache_key = self._get_cache_key(booking_id)
        return cache_service.get(cache_key)

    def _cache_booking(self, booking_id: str, data: Dict):
        """Cache booking data."""
        cache_key = self._get_cache_key(booking_id)
        cache_service.set(cache_key, data, ttl_seconds=self.config.cache_ttl_seconds)

    @circuit_breaker_manager.get_breaker("agent_booking").decorate
    @retry_sync
    def create_booking_request(
        self,
        db: Session, 
        user_id: str, 
        route_id: str, 
        passengers: List[Passenger],
        ticket_fare: float
    ) -> AgentBookingResult:
        """
        Subtask 42.3 & 42.4: Create a manual agent booking request.
        ENFORCEMENT: Checks if route was unlocked by the user.
        
        Args:
            db: Database session
            user_id: User ID
            route_id: Route ID
            passengers: List of passenger details
            ticket_fare: Base ticket fare
            
        Returns:
            AgentBookingResult with booking details
        """
        try:
            # [42.4] State Machine Enforcement: Must be unlocked
            unlock_exists = db.query(Booking).filter(
                Booking.user_id == user_id,
                Booking.route_id == route_id,
                Booking.service_type == "UNLOCK",
                Booking.is_unlocked == True
            ).first()
            
            if not unlock_exists:
                return AgentBookingResult(
                    success=False,
                    booking_id=None,
                    user_id=user_id,
                    route_id=route_id,
                    total_amount=0.0,
                    ticket_fare=ticket_fare,
                    agent_fee=0.0,
                    message="Route must be unlocked (₹49) before requesting agent booking.",
                    error="ROUTE_NOT_UNLOCKED"
                )

            # [42.7] & [3.1] Fee Aggregation with strict rounding
            agent_fee = self.config.agent_fee
            total_amount = round(float(ticket_fare) + agent_fee, 2)
            
            # [27.3] Tatkal Auto-Priority
            from utils.geo_utils import is_tatkal_window
            priority = 0 if is_tatkal_window() else 10
            
            booking = Booking(
                user_id=user_id,
                route_id=route_id,
                amount_paid=total_amount,
                service_type="AGENT_BOOKING",
                escrow_status=EscrowStatus.CREATED,
                priority=priority,
                escrow_message="Agent booking requested. Awaiting payment verification.",
                booking_details={
                    "ticket_fare": round(float(ticket_fare), 2),
                    "agent_fee": round(agent_fee, 2),
                    "total_checkout": total_amount,
                    "locked_at": datetime.utcnow().isoformat()
                }
            )
            db.add(booking)
            db.flush()
            
            # Add Passengers
            for p in passengers:
                pd = PassengerDetails(
                    booking_id=booking.id,
                    full_name=p.name,
                    age=p.age,
                    gender=p.gender
                )
                db.add(pd)
                
            # [42.9] Transactional Integrity
            audit = AuditLog(
                entity_type="Booking",
                entity_id=booking.id,
                action="AGENT_BOOKING_REQUESTED",
                new_value="CREATED",
                performed_by=user_id,
                reason=f"User requested booking for {len(passengers)} passengers."
            )
            db.add(audit)
            
            db.commit()
            db.refresh(booking)
            
            # Record metrics
            self._record_metric("create_booking_request", True, route_id)
            
            logger.info(f"Agent booking request created: {booking.id} for user {user_id}")
            
            return AgentBookingResult(
                success=True,
                booking_id=booking.id,
                user_id=user_id,
                route_id=route_id,
                total_amount=total_amount,
                ticket_fare=ticket_fare,
                agent_fee=agent_fee,
                message="Agent booking request created successfully"
            )
            
        except Exception as e:
            logger.error(f"Failed to create agent booking request: {e}")
            db.rollback()
            
            # Record metrics
            self._record_metric("create_booking_request", False, route_id)
            
            return AgentBookingResult(
                success=False,
                booking_id=None,
                user_id=user_id,
                route_id=route_id,
                total_amount=0.0,
                ticket_fare=ticket_fare,
                agent_fee=0.0,
                message="Failed to create agent booking request",
                error=str(e)
            )

    @circuit_breaker_manager.get_breaker("agent_booking").decorate
    @retry_sync
    def claim_booking(
        self,
        db: Session,
        booking_id: str,
        agent_id: str
    ) -> AgentClaimResult:
        """
        Subtask 42.8, 44.2 & 47.2: Agent claims a booking with atomic locking.
        
        Args:
            db: Database session
            booking_id: Booking ID to claim
            agent_id: Agent ID claiming the booking
            
        Returns:
            AgentClaimResult with claim details
        """
        try:
            # [47.2] Atomic SELECT FOR UPDATE to prevent double-claiming
            booking = db.query(Booking).filter(Booking.id == booking_id).with_for_update().first()
            if not booking:
                return AgentClaimResult(
                    success=False,
                    booking_id=booking_id,
                    agent_id=agent_id,
                    commission_amount=0.0,
                    message="Booking not found",
                    error="BOOKING_NOT_FOUND"
                )
            
            # [47.1] Check if already claimed
            if booking.agent_id and booking.agent_id != agent_id:
                logger.warning(f"Booking {booking_id} already claimed by {booking.agent_id}")
                return AgentClaimResult(
                    success=False,
                    booking_id=booking_id,
                    agent_id=agent_id,
                    commission_amount=0.0,
                    message=f"Booking already claimed by agent {booking.agent_id}",
                    error="ALREADY_CLAIMED"
                )
            
            # [44.2] Commission Service: Record ₹10 fee
            from services.commission_service import commission_service
            commission_amount = commission_service.record_commission(db, booking_id, agent_id)
                
            booking.agent_id = agent_id
            booking.escrow_status = EscrowStatus.BOOKING_INITIATED
            booking.escrow_message = f"Agent {agent_id} is processing your booking."
            
            audit = AuditLog(
                entity_type="Booking",
                entity_id=booking.id,
                action="AGENT_CLAIMED",
                old_value="VERIFIED",
                new_value="BOOKING_INITIATED",
                performed_by=agent_id,
                reason="Agent claimed booking for fulfillment (Atomic Lock)."
            )
            db.add(audit)
            db.commit()
            
            # Invalidate cache
            self._invalidate_cache(booking_id)
            
            # Record metrics
            self._record_metric("claim_booking", True, booking.route_id)
            
            logger.info(f"Booking {booking_id} claimed by agent {agent_id}")
            
            return AgentClaimResult(
                success=True,
                booking_id=booking_id,
                agent_id=agent_id,
                commission_amount=commission_amount,
                message="Booking claimed successfully"
            )
            
        except Exception as e:
            logger.error(f"Error claiming booking: {e}")
            db.rollback()
            
            # Record metrics
            self._record_metric("claim_booking", False, "")
            
            return AgentClaimResult(
                success=False,
                booking_id=booking_id,
                agent_id=agent_id,
                commission_amount=0.0,
                message="Failed to claim booking",
                error=str(e)
            )

    def _invalidate_cache(self, booking_id: str):
        """Invalidate cached booking data."""
        cache_key = self._get_cache_key(booking_id)
        cache_service.delete(cache_key)
        logger.debug(f"Cache invalidated for {cache_key}")

    def _record_metric(self, operation: str, success: bool, route_id: str):
        """Record operation metric."""
        if self._metrics_lock is None:
            import asyncio
            self._metrics_lock = asyncio.Lock()
        
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self._record_metric_async(operation, success, route_id))

    async def _record_metric_async(self, operation: str, success: bool, route_id: str):
        """Record operation metric (async)."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": operation,
                "success": success,
                "route_id": route_id
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        
        operations = {}
        for m in self._metrics:
            op = m["operation"]
            if op not in operations:
                operations[op] = {"total": 0, "success": 0}
            operations[op]["total"] += 1
            if m["success"]:
                operations[op]["success"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": operations,
            "circuit_breaker_state": self._breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "config": {
                "agent_fee": self.config.agent_fee,
                "cache_ttl_seconds": self.config.cache_ttl_seconds
            },
            "circuit_breaker": self._breaker.get_state().value,
            "metrics": self.get_metrics()
        }
