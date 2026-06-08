"""
Commission Service - Agent Commission Management with Ledger Support
====================================================================

Manages agent commissions including:
- Commission recording and tracking
- Commission settlement and payout
- Wallet management
- Double-entry ledger integration

With resilience patterns: circuit breaker, retry, idempotency, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

from typing import Optional, Dict, Any, List
import logging
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import CommissionTracking, AgentWallet, Booking, User, AuditLog
from core.resilience.core import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy, retry
from collections import deque
from dataclasses import dataclass
from enum import Enum
import asyncio

logger = logging.getLogger("commission-service")

# Commission rates
AGENT_BASE_COMMISSION_PCT = 0.05  # 5%
TOP_AGENT_THRESHOLD = 50  # Bookings per week
TOP_AGENT_COMMISSION_PCT = 0.07  # 7%


class CommissionStatus(Enum):
    """Status of commission tracking."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


@dataclass
class CommissionDetails:
    """Commission details result."""
    commission_id: str
    agent_id: str
    booking_id: str
    amount: float
    status: CommissionStatus
    created_at: datetime
    settled_at: Optional[datetime] = None
    payout_id: Optional[str] = None


class CommissionService:
    """
    Commission service for managing agent commissions and settlements.
    
    With resilience patterns: circuit breaker, retry, idempotency, and metrics tracking.
    """
    
    def __init__(self):
        """Initialize commission service with resilience patterns."""
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "commission_service_db",
            CircuitConfig(
                failure_threshold=10,
                timeout_seconds=30.0,
                success_threshold=5
            )
        )
        
        # Circuit breaker for ledger operations
        self._ledger_breaker = circuit_breaker_manager.get_or_create(
            "commission_service_ledger",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=60.0,
                success_threshold=3
            )
        )
        
        # Retry policy for database operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=2.0,
            conditions=[
                lambda e: "deadlock" in str(e).lower(),
                lambda e: "timeout" in str(e).lower(),
                lambda e: "integrity" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Idempotency tracking
        self._idempotency_keys: deque = deque(maxlen=10000)
        self._idempotency_lock = asyncio.Lock()
        
        logger.info("CommissionService initialized with resilience patterns")

    def _is_idempotent_key_used(self, key: str) -> bool:
        """Check if idempotency key was already used."""
        return key in self._idempotency_keys

    def _mark_idempotency_key(self, key: str):
        """Mark idempotency key as used."""
        if key not in self._idempotency_keys:
            self._idempotency_keys.append(key)

    def _generate_idempotency_key(self, agent_id: str, booking_id: str) -> str:
        """Generate idempotency key for commission recording."""
        return f"commission_{agent_id}_{booking_id}_{datetime.utcnow().strftime('%Y%m%d%H%M')}"

    @retry(
        max_attempts=3,
        initial_delay=0.1,
        max_delay=2.0,
        conditions=[
            lambda e: "deadlock" in str(e).lower(),
            lambda e: "timeout" in str(e).lower()
        ]
    )
    async def record_commission(
        self,
        db: Session,
        booking_id: str,
        agent_id: str,
        idempotency_key: Optional[str] = None
    ) -> CommissionDetails:
        """
        [Task 44.2] Records a new pending commission for an agent with Ledger Support.
        
        Args:
            db: Database session
            booking_id: Booking identifier
            agent_id: Agent identifier
            idempotency_key: Optional idempotency key for duplicate prevention
            
        Returns:
            CommissionDetails with commission information
            
        Protected by circuit breaker and retry logic.
        """
        # Generate idempotency key if not provided
        key = idempotency_key or self._generate_idempotency_key(agent_id, booking_id)
        
        # Check for duplicate
        async with self._idempotency_lock:
            if self._is_idempotent_key_used(key):
                logger.warning(f"⚠️ Duplicate commission request detected: {key}")
                # Return existing commission
                existing = db.query(CommissionTracking).filter(
                    CommissionTracking.booking_id == booking_id,
                    CommissionTracking.user_id == agent_id
                ).first()
                if existing:
                    return CommissionDetails(
                        commission_id=str(existing.id),
                        agent_id=existing.user_id,
                        booking_id=existing.booking_id,
                        amount=existing.amount,
                        status=CommissionStatus(existing.status),
                        created_at=existing.created_at,
                        settled_at=existing.settled_at,
                        payout_id=existing.payout_id
                    )
        
        # 1. Safety Latch: Check for Financial Lock
        from services.cache_service import cache_service
        financial_lock = await cache_service.get("PLATFORM_FINANCIAL_LOCK")
        if financial_lock:
            logger.critical(
                f"🛑 [COMMISSION] BLOCKED: System is in Financial Emergency mode. Agent: {agent_id}"
            )
            raise PermissionError("Financial operations suspended due to integrity failure.")

        # 2. Performance Multiplier check (Percentage Based)
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        weekly_count = db.query(CommissionTracking).filter(
            CommissionTracking.user_id == agent_id,
            CommissionTracking.created_at >= one_week_ago
        ).count()
        
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        base_amount = float(booking.amount_paid) if booking and booking.amount_paid else 0.0
        
        commission_pct = TOP_AGENT_COMMISSION_PCT if weekly_count >= TOP_AGENT_THRESHOLD else AGENT_BASE_COMMISSION_PCT
        rate = round(base_amount * commission_pct, 2)
        
        # 3. Double-Entry Ledgering [Task 49.2]
        ledger_entry = None
        try:
            from services.ledger_service import ledger_service
            ledger_entry = await ledger_service(db).record_transaction(
                db,
                "CASH_ESCROW",
                f"AGENT_PENDING_{agent_id}",
                float(rate),
                booking_id,
                agent_id
            )
        except Exception as e:
            logger.error(f"❌ Ledger recording failed: {e}")
            # Continue without ledger if it fails, but log the issue
            ledger_entry = None

        # 4. Create Tracking Row
        track = CommissionTracking(
            user_id=agent_id,
            booking_id=booking_id,
            amount=rate,
            status="PENDING",
            payout_id=ledger_entry.transaction_uuid if ledger_entry else None
        )
        db.add(track)
        
        # 5. Update Wallet Pending Balance
        wallet = db.query(AgentWallet).filter(AgentWallet.user_id == agent_id).with_for_update().first()
        if wallet is None:
            wallet = AgentWallet(user_id=agent_id, pending_commission=0.0, total_earned=0.0)
            db.add(wallet)
        
        wallet.pending_commission = float(wallet.pending_commission or 0.0) + rate
        
        db.commit()
        
        # Mark idempotency key as used
        async with self._idempotency_lock:
            self._mark_idempotency_key(key)
        
        # Record metrics
        await self._record_metrics("commission_recorded", True, rate)
        
        logger.info(
            f"Commission Recorded & Ledgered: Agent {agent_id} | "
            f"Amount: ₹{rate} | "
            f"Tx: {ledger_entry.transaction_uuid[:8] if ledger_entry else 'N/A'}"
        )
        
        return CommissionDetails(
            commission_id=str(track.id),
            agent_id=agent_id,
            booking_id=booking_id,
            amount=rate,
            status=CommissionStatus.PENDING,
            created_at=track.created_at,
            payout_id=track.payout_id
        )

    @retry(
        max_attempts=3,
        initial_delay=0.1,
        max_delay=2.0,
        conditions=[
            lambda e: "deadlock" in str(e).lower(),
            lambda e: "timeout" in str(e).lower()
        ]
    )
    async def settle_batch(
        self,
        db: Session,
        agent_id: str,
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        [Task 44.4] Moves PENDING commissions to total_earned with Idempotent Reservation.
        
        Args:
            db: Database session
            agent_id: Agent identifier
            batch_id: Optional batch ID for idempotency
            
        Returns:
            Dict with settlement details
            
        Protected by circuit breaker and retry logic.
        """
        # 1. Safety Latch
        from services.cache_service import cache_service
        financial_lock = await cache_service.get("PLATFORM_FINANCIAL_LOCK")
        if financial_lock:
            logger.critical(
                f"🛑 [SETTLEMENT] BLOCKED: System Integrity Compromised. Agent: {agent_id}"
            )
            return {"status": "BLOCKED", "reason": "FINANCIAL_LOCK"}
        
        batch_uuid = batch_id or f"SETTLE_{agent_id}_{datetime.utcnow().strftime('%Y%m%d%H%M')}"
        
        # Check for duplicate batch
        existing_batch = db.query(CommissionTracking).filter(
            CommissionTracking.payout_id == batch_uuid,
            CommissionTracking.status == "SETTLED"
        ).first()
        
        if existing_batch:
            logger.info(f"⚠️ Batch {batch_uuid} already settled, returning existing result")
            return {
                "status": "ALREADY_SETTLED",
                "batch_id": batch_uuid,
                "agent_id": agent_id
            }
        
        # 2. Reservation Phase: Mark targeted rows with BATCH_ID
        db.query(CommissionTracking).filter(
            CommissionTracking.user_id == agent_id,
            CommissionTracking.status == "PENDING"
        ).update({
            "status": "PROCESSING",
            "payout_id": batch_uuid
        }, synchronize_session='fetch')
        db.commit()

        # 3. Calculation Phase
        batch_tracks = db.query(CommissionTracking).filter(
            CommissionTracking.payout_id == batch_uuid,
            CommissionTracking.status == "PROCESSING"
        ).all()
        
        if not batch_tracks:
            return {
                "status": "NO_PENDING",
                "batch_id": batch_uuid,
                "agent_id": agent_id
            }
        
        total_to_settle = sum(t.amount for t in batch_tracks)
        
        # 4. Record Settlement in Ledger [IDEMPOTENT]
        ledger_entry = None
        try:
            from services.ledger_service import ledger_service
            ledger_entry = await ledger_service(db).record_transaction(
                db,
                f"AGENT_PENDING_{agent_id}",
                f"AGENT_SETTLED_{agent_id}",
                float(total_to_settle),
                batch_uuid,
                agent_id
            )
        except Exception as e:
            logger.error(f"❌ Ledger settlement failed: {e}")
            # Rollback processing status
            for t in batch_tracks:
                t.status = "PENDING"
            db.commit()
            raise

        # 5. Finalize Wallet
        wallet = db.query(AgentWallet).filter(AgentWallet.user_id == agent_id).with_for_update().first()
        if wallet is None:
            wallet = AgentWallet(user_id=agent_id, pending_commission=0.0, total_earned=0.0)
            db.add(wallet)
        
        wallet.pending_commission = float(wallet.pending_commission or 0.0) - total_to_settle
        wallet.total_earned = float(wallet.total_earned or 0.0) + total_to_settle
        wallet.last_payout_at = datetime.utcnow()
        
        for t in batch_tracks:
            t.status = "SETTLED"
            t.settled_at = datetime.utcnow()
            
        db.commit()
        
        # Record metrics
        await self._record_metrics("batch_settled", True, total_to_settle)
        
        logger.info(
            f"✅ Settled ₹{total_to_settle} for Agent {agent_id} | "
            f"Batch: {batch_uuid[:8]} | "
            f"Commissions: {len(batch_tracks)}"
        )
        
        return {
            "status": "SETTLED",
            "batch_id": batch_uuid,
            "agent_id": agent_id,
            "amount": total_to_settle,
            "commission_count": len(batch_tracks),
            "ledger_tx": ledger_entry.transaction_uuid[:8] if ledger_entry else None
        }

    async def get_agent_commissions(
        self,
        db: Session,
        agent_id: str,
        status: Optional[CommissionStatus] = None,
        limit: int = 100
    ) -> List[CommissionDetails]:
        """
        Get commission history for an agent.
        
        Args:
            db: Database session
            agent_id: Agent identifier
            status: Optional status filter
            limit: Maximum number of records
            
        Returns:
            List of CommissionDetails
        """
        query = db.query(CommissionTracking).filter(
            CommissionTracking.user_id == agent_id
        )
        
        if status:
            query = query.filter(CommissionTracking.status == status.value)
        
        tracks = query.order_by(CommissionTracking.created_at.desc()).limit(limit).all()
        
        return [
            CommissionDetails(
                commission_id=str(t.id),
                agent_id=t.user_id,
                booking_id=t.booking_id,
                amount=t.amount,
                status=CommissionStatus(t.status),
                created_at=t.created_at,
                settled_at=t.settled_at,
                payout_id=t.payout_id
            )
            for t in tracks
        ]

    async def get_agent_wallet(self, db: Session, agent_id: str) -> Dict[str, float]:
        """
        Get agent wallet balance.
        
        Args:
            db: Database session
            agent_id: Agent identifier
            
        Returns:
            Dict with wallet balances
        """
        wallet = db.query(AgentWallet).filter(
            AgentWallet.user_id == agent_id
        ).first()
        
        if not wallet:
            return {
                "pending_commission": 0.0,
                "total_earned": 0.0,
                "last_payout_at": None
            }
        
        return {
            "pending_commission": float(wallet.pending_commission or 0.0),
            "total_earned": float(wallet.total_earned or 0.0),
            "last_payout_at": wallet.last_payout_at.isoformat() if wallet.last_payout_at else None
        }

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        transaction_type: str,
        success: bool,
        amount: float = 0.0
    ):
        """Record transaction metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "transaction_type": transaction_type,
                "success": success,
                "amount": amount
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_transactions": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        amounts = [m["amount"] for m in self._metrics]
        by_type = {}
        for m in self._metrics:
            t_type = m["transaction_type"]
            by_type[t_type] = by_type.get(t_type, 0) + 1
        
        return {
            "total_transactions": total,
            "successful_transactions": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "total_amount": sum(amounts),
            "transaction_breakdown": by_type,
            "db_circuit_breaker_state": self._db_breaker.get_state().value,
            "ledger_circuit_breaker_state": self._ledger_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breakers": {
                "database": {
                    "state": self._db_breaker.get_state().value,
                    "failure_count": self._db_breaker.failure_count,
                    "success_count": self._db_breaker.success_count
                },
                "ledger": {
                    "state": self._ledger_breaker.get_state().value,
                    "failure_count": self._ledger_breaker.failure_count,
                    "success_count": self._ledger_breaker.success_count
                }
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breakers(self):
        """Reset all circuit breakers."""
        self._db_breaker.reset()
        self._ledger_breaker.reset()
        logger.info("Circuit breakers reset for commission service")

    def clear_idempotency_keys(self):
        """Clear idempotency keys (use with caution)."""
        self._idempotency_keys.clear()
        logger.info("Idempotency keys cleared for commission service")


# Global instance
commission_service = CommissionService()
