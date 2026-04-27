"""
Unlock Service - Production Version
Handles the logic for locking/unlocking journey details and masking sensitive data.
With circuit breaker protection, retry logic, and comprehensive error handling.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
from contextlib import asynccontextmanager

from database.models import Booking, EscrowStatus, UnlockedRoute
from core.data_structures import Route, RouteSegment
from core.resilience import circuit_breaker_manager, CircuitBreakerState
from core.retry import retry_sync, RetryPolicy
from services.cache_service import cache_service

logger = logging.getLogger(__name__)


@dataclass
class UnlockServiceConfig:
    """Configuration for unlock service."""
    unlock_fee: float = 49.0
    cache_ttl_seconds: int = 3600  # 1 hour
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
class UnlockRequestResult:
    """Result of unlock request creation."""
    success: bool
    booking_id: str
    route_id: str
    user_id: str
    amount: float
    session_code: str
    message: str
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "booking_id": self.booking_id,
            "route_id": self.route_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "session_code": self.session_code,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp
        }


@dataclass
class UnlockStatusResult:
    """Result of unlock status check."""
    is_unlocked: bool
    booking_id: Optional[str]
    route_id: str
    user_id: str
    unlock_timestamp: Optional[str]
    message: str
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_unlocked": self.is_unlocked,
            "booking_id": self.booking_id,
            "route_id": self.route_id,
            "user_id": self.user_id,
            "unlock_timestamp": self.unlock_timestamp,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp
        }


class UnlockService:
    """
    Unlock Service - Phase 5 Monetization
    Handles the logic for locking/unlocking journey details and masking sensitive data.
    With circuit breaker protection and retry logic.
    """
    
    def __init__(self, config: Optional[UnlockServiceConfig] = None):
        self.config = config or UnlockServiceConfig()
        
        # Circuit breaker for database operations
        self._breaker = circuit_breaker_manager.get_breaker("unlock_service")
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = None
        
        logger.info("UnlockService initialized with resilience patterns")

    def _get_cache_key(self, user_id: str, route_id: str) -> str:
        """Generate cache key for unlock status."""
        return f"unlock_status:{user_id}:{route_id}"

    def _get_cached_status(self, user_id: str, route_id: str) -> Optional[UnlockStatusResult]:
        """Get cached unlock status."""
        cache_key = self._get_cache_key(user_id, route_id)
        cached = cache_service.get(cache_key)
        if cached:
            result = UnlockStatusResult(**cached)
            return result
        return None

    def _cache_status(self, user_id: str, route_id: str, result: UnlockStatusResult):
        """Cache unlock status."""
        cache_key = self._get_cache_key(user_id, route_id)
        cache_service.set(cache_key, result.to_dict(), ttl_seconds=self.config.cache_ttl_seconds)

    @staticmethod
    def mask_route(route_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Subtask 41.5: Mask sensitive train details for locked routes.
        Hides Train Number, Train Name, and Platforms.
        """
        masked = route_dict.copy()
        masked["is_locked"] = True
        
        # Mask Segments
        for seg in masked.get("segments", []):
            seg["train_number"] = "XXXXX"
            seg["train_name"] = "Hidden Train"
            seg["departure_platform"] = "X"
            seg["arrival_platform"] = "X"
            if "trip_id" in seg:
                seg["trip_id"] = "hidden"
            
        # [Task 22.4] Add descriptive CTA for UI
        masked["unlock_fee"] = self.config.unlock_fee
        masked["unlock_currency"] = "INR"
        masked["cta_text"] = f"Unlock for ₹{self.config.unlock_fee:,.0f}"
        masked["cta_message"] = "Get full train numbers, platform info and real-time safety status."
        masked["cta_action"] = "UNLOCK_JOURNEY"
        
        # Also mask 'legs' if present
        for leg in masked.get("legs", []):
            leg["train_number"] = "XXXXX"
            leg["train_name"] = "Hidden Train"
            leg["departure_platform"] = "X"
            leg["arrival_platform"] = "X"

        return masked

    @circuit_breaker_manager.get_breaker("unlock_service").decorate
    @retry_sync
    def create_unlock_request(
        self,
        db: Session,
        user_id: str,
        route_id: str,
        amount: Optional[float] = None
    ) -> UnlockRequestResult:
        """
        Subtask 41.3 & 41.4: Initiate an unlock request.
        
        Args:
            db: Database session
            user_id: User ID
            route_id: Route ID to unlock
            amount: Unlock fee (defaults to config value)
            
        Returns:
            UnlockRequestResult with request details
        """
        unlock_amount = amount or self.config.unlock_fee
        import secrets
        
        try:
            unlock_booking = Booking(
                user_id=user_id,
                route_id=route_id,
                amount_paid=unlock_amount,
                service_type="UNLOCK",
                escrow_status=EscrowStatus.CREATED,
                escrow_message="Payment pending for route unlock.",
                is_unlocked=False,
                booking_details={}  # Satisfy NOT NULL
            )
            db.add(unlock_booking)
            db.flush()  # Get ID
            
            # [41.4] Payment Integration: Create a PaymentSession record
            from database.models import PaymentSession
            pay_session = PaymentSession(
                user_id=user_id,
                route_id=route_id,
                amount=unlock_amount,
                session_code=f"UNL-{secrets.token_hex(4).upper()}",
                status="PENDING"
            )
            db.add(pay_session)
            
            # [41.9] Audit Log
            from database.models import AuditLog
            audit = AuditLog(
                entity_type="Booking",
                entity_id=unlock_booking.id,
                action="UNLOCK_INITIATED",
                new_value="CREATED",
                performed_by=user_id,
                reason="User initiated ₹49 unlock flow."
            )
            db.add(audit)
            
            db.commit()
            
            # Record metrics
            self._record_metric("create_unlock_request", True, route_id)
            
            logger.info(f"Unlock request created: Booking {unlock_booking.id} for user {user_id}")
            
            return UnlockRequestResult(
                success=True,
                booking_id=unlock_booking.id,
                route_id=route_id,
                user_id=user_id,
                amount=unlock_amount,
                session_code=pay_session.session_code,
                message="Unlock request created successfully"
            )
            
        except Exception as e:
            logger.error(f"Failed to create unlock request: {e}")
            db.rollback()
            
            # Record metrics
            self._record_metric("create_unlock_request", False, route_id)
            
            return UnlockRequestResult(
                success=False,
                booking_id="",
                route_id=route_id,
                user_id=user_id,
                amount=unlock_amount,
                session_code="",
                message="Failed to create unlock request",
                error=str(e)
            )

    @circuit_breaker_manager.get_breaker("unlock_service").decorate
    @retry_sync
    def fulfill_unlock(
        self,
        db: Session,
        booking_id: str
    ) -> Dict[str, Any]:
        """
        Subtask 41.7: Set route as unlocked upon payment verification.
        
        Args:
            db: Database session
            booking_id: Booking ID to fulfill
            
        Returns:
            Dictionary with fulfillment result
        """
        try:
            booking = db.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                return {
                    "success": False,
                    "message": "Booking not found",
                    "error": f"Booking {booking_id} not found"
                }
            
            # Update booking status
            booking.is_unlocked = True
            booking.escrow_status = EscrowStatus.COMPLETED
            booking.escrow_message = "Route successfully unlocked."
            
            # Record in UnlockedRoute for persistent access
            from database.models import UnlockedRoute
            unlocked = UnlockedRoute(
                user_id=booking.user_id,
                route_id=booking.route_id,
                booking_id=booking.id,
                unlocked_at=datetime.utcnow()
            )
            db.add(unlocked)
            
            # [Point 15.2] NIS Conversion: Log Unlock
            try:
                from services.intelligence_service import IntelligenceService
                intel_svc = IntelligenceService(db)
                import asyncio
                asyncio.run(
                    intel_svc.record_conversion(
                        str(booking.route_id),
                        "UNLOCK",
                        float(booking.amount_paid)
                    )
                )
            except Exception as e:
                logger.error(f"Failed to log NIS conversion: {e}")

            # [41.9] Audit Log
            from database.models import AuditLog
            audit = AuditLog(
                entity_type="Booking",
                entity_id=booking.id,
                action="UNLOCK_COMPLETED",
                old_value="CREATED",
                new_value="COMPLETED",
                performed_by="SYSTEM_PAYMENT",
                reason="Payment verified. Details revealed."
            )
            db.add(audit)
            
            db.commit()
            
            # Invalidate cache
            self._invalidate_cache(booking.user_id, booking.route_id)
            
            # Record metrics
            self._record_metric("fulfill_unlock", True, booking.route_id)
            
            logger.info(f"Unlock fulfilled: Booking {booking_id} for user {booking.user_id}")
            
            return {
                "success": True,
                "message": "Route successfully unlocked",
                "booking_id": booking_id,
                "route_id": booking.route_id
            }
            
        except Exception as e:
            logger.error(f"Failed to fulfill unlock: {e}")
            db.rollback()
            
            # Record metrics
            self._record_metric("fulfill_unlock", False, "")
            
            return {
                "success": False,
                "message": "Failed to fulfill unlock",
                "error": str(e)
            }

    @retry_sync
    def is_route_unlocked(
        self,
        db: Session,
        user_id: str,
        route_id: str,
        bypass_cache: bool = False
    ) -> UnlockStatusResult:
        """
        Check if a route is unlocked for a user.
        
        Args:
            db: Database session
            user_id: User ID
            route_id: Route ID
            bypass_cache: Skip cache and fetch fresh data
            
        Returns:
            UnlockStatusResult with unlock status
        """
        # Check cache first
        if not bypass_cache:
            cached = self._get_cached_status(user_id, route_id)
            if cached:
                return cached
        
        try:
            booking = db.query(Booking).filter(
                Booking.user_id == user_id,
                Booking.route_id == route_id,
                Booking.service_type == "UNLOCK",
                Booking.is_unlocked == True
            ).first()
            
            is_unlocked = booking is not None
            
            result = UnlockStatusResult(
                is_unlocked=is_unlocked,
                booking_id=booking.id if booking else None,
                route_id=route_id,
                user_id=user_id,
                unlock_timestamp=booking.created_at.isoformat() if booking and booking.created_at else None,
                message="Route is unlocked" if is_unlocked else "Route is not unlocked"
            )
            
            # Cache the result
            self._cache_status(user_id, route_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to check unlock status: {e}")
            
            return UnlockStatusResult(
                is_unlocked=False,
                booking_id=None,
                route_id=route_id,
                user_id=user_id,
                unlock_timestamp=None,
                message="Failed to check unlock status",
                error=str(e)
            )

    def _invalidate_cache(self, user_id: str, route_id: str):
        """Invalidate cached unlock status."""
        cache_key = self._get_cache_key(user_id, route_id)
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
                "unlock_fee": self.config.unlock_fee,
                "cache_ttl_seconds": self.config.cache_ttl_seconds
            },
            "circuit_breaker": self._breaker.get_state().value,
            "metrics": self.get_metrics()
        }


def apply_route_locks(
    db: Session,
    routes: List[Dict[str, Any]],
    user_id: Optional[str],
    departure_date: str,
    plan_tier: str,
    preview_count: int = 1,
) -> List[Dict[str, Any]]:
    """
    Apply monetization locks to route payloads.

    A small preview can remain visible; everything else is masked.
    """
    locked_routes: List[Dict[str, Any]] = []
    for index, route in enumerate(routes):
        route_payload = route.copy()
        if index < preview_count:
            route_payload["is_locked"] = False
        else:
            route_payload = UnlockService.mask_route(route_payload)
        locked_routes.append(route_payload)
    return locked_routes
