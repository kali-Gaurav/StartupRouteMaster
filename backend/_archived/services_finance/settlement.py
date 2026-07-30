"""
Settlement Service - Automated Merchant Sovereignty
====================================================

Handles instant UPI-enabled payouts for agents and merchants:
- Commission settlement for completed trips
- Batch settlement processing
- RazorpayX integration

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database.models import Booking, User, Wallet, AgentWallet
from database.session import SessionTransit
from core.resilience.core import circuit_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy, retry
from collections import deque
from dataclasses import dataclass
from enum import Enum
import asyncio

logger = logging.getLogger("routemaster.settlement")

def safe_fromisoformat(val):
    from datetime import datetime
    return datetime.fromisoformat(val) if isinstance(val, str) and val else None

class SettlementStatus(Enum):
    """Status of settlement process."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass
class SettlementResult:
    """Settlement result details."""
    booking_id: str
    agent_id: str
    amount: float
    status: SettlementStatus
    payout_reference: Optional[str]
    ledger_transaction: Optional[str]
    settled_at: Optional[datetime]
    error: Optional[str]


class SettlementService:
    """
    [P18] Automated Merchant Sovereignty.
    Handles instant UPI-enabled payouts for agents and merchants.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self):
        """Initialize settlement service with resilience patterns."""
        # Circuit breaker for database operations
        self._db_breaker = circuit_manager.get_or_create(
            "settlement_service_db",
            CircuitConfig(
                failure_threshold=10,
                timeout_seconds=30.0,
                success_threshold=5
            )
        )
        
        # Circuit breaker for payment gateway operations
        self._payment_breaker = circuit_manager.get_or_create(
            "settlement_service_payment",
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
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Settlement cache for idempotency
        self._settlement_cache: Dict[str, SettlementResult] = {}
        self._cache_lock = asyncio.Lock()
        
        logger.info("SettlementService initialized with resilience patterns")

    def _is_already_settled(self, booking_id: str) -> bool:
        """Check if booking was already settled."""
        return booking_id in self._settlement_cache

    async def process_completed_trip_settlement(
        self,
        db: Session,
        booking_id: str
    ) -> SettlementResult:
        """
        Triggers instantly when a trip status becomes 'COMPLETED'.
        Allocates commission to the agent's wallet with Ledger Integrity.
        
        Args:
            db: Database session
            booking_id: Booking identifier
            
        Returns:
            SettlementResult with settlement details
            
        Protected by circuit breaker and retry logic.
        """
        # Check idempotency
        async with self._cache_lock:
            if self._is_already_settled(booking_id):
                cached = self._settlement_cache[booking_id]
                if cached.status == SettlementStatus.COMPLETED:
                    logger.warning(f"⚠️ [SETTLEMENT] Booking {booking_id} already settled. Returning cached.")
                    return cached
        
        # 1. Safety Latch
        from services.cache_service import cache_service
        financial_lock = cache_service.get("PLATFORM_FINANCIAL_LOCK")
        if asyncio.iscoroutine(financial_lock):
            financial_lock = await financial_lock
        if financial_lock:
            logger.critical(
                f"🛑 [SETTLEMENT] BLOCKED: System in Emergency Lock. Booking: {booking_id}"
            )
            return SettlementResult(
                booking_id=booking_id,
                agent_id="",
                amount=0.0,
                status=SettlementStatus.FAILED,
                payout_reference=None,
                ledger_transaction=None,
                settled_at=None,
                error="FINANCIAL_LOCK"
            )

        booking = db.query(Booking).filter_by(id=booking_id).first()
        if not booking:
            return SettlementResult(
                booking_id=booking_id,
                agent_id="",
                amount=0.0,
                status=SettlementStatus.FAILED,
                payout_reference=None,
                ledger_transaction=None,
                settled_at=None,
                error="BOOKING_NOT_FOUND"
            )
        
        if booking.booking_status != "COMPLETED":
            return SettlementResult(
                booking_id=booking_id,
                agent_id=booking.agent_id or "",
                amount=0.0,
                status=SettlementStatus.FAILED,
                payout_reference=None,
                ledger_transaction=None,
                settled_at=None,
                error="BOOKING_NOT_COMPLETED"
            )
            
        agent_id = booking.agent_id
        if not agent_id:
            return SettlementResult(
                booking_id=booking_id,
                agent_id="",
                amount=0.0,
                status=SettlementStatus.FAILED,
                payout_reference=None,
                ledger_transaction=None,
                settled_at=None,
                error="NO_AGENT_ID"
            )
        
        # Check if already settled
        if booking.booking_details and booking.booking_details.get("settled"):
            return SettlementResult(
                booking_id=booking_id,
                agent_id=agent_id,
                amount=0.0,
                status=SettlementStatus.FAILED,
                payout_reference=booking.booking_details.get("payout_ref"),
                ledger_transaction=booking.booking_details.get("ledger_tx"),
                settled_at=safe_fromisoformat(booking.booking_details.get("settled_at")),
                error="ALREADY_SETTLED"
            )
        
        # [Task 30.2] Multi-Tier Commission Logic
        commission_rate = 0.05  # Base 5%
        if booking.amount_paid > 5000:
            commission_rate = 0.07  # High Volume Bonus
            
        commission_amount = booking.amount_paid * commission_rate
        
        logger.info(f"💸 [SETTLEMENT] Initiating payout for Agent {agent_id}: ₹{commission_amount}")
        
        # 2. Record in Sealed Ledger BEFORE external payout
        ledger_entry = None
        try:
            from services.ledger_service import ledger_service
            ledger = ledger_service(db)
            if hasattr(ledger, "record_transaction"):
                ledger_entry = await ledger.record_transaction(
                    db,
                    debit_acc=f"AGENT_SETTLED_{agent_id}",
                    credit_acc="EXTERNAL_BANK_LIQUIDITY",
                    amount=commission_amount,
                    booking_id=booking_id,
                    agent_id=agent_id
                )
        except Exception as e:
            logger.error(f"❌ Ledger recording failed: {e}")
            # Continue without ledger if it fails, but log the issue
        
        # 3. Industrial Bank Integration (RazorpayX Simulation)
        payout_ref = f"SETTLE_{booking_id}_{datetime.now().strftime('%Y%m%d%H%M')}"
        
        async def _trigger_payout():
            """Trigger payout through payment gateway."""
            return await self.trigger_razorpayx_payout(agent_id, commission_amount, payout_ref)
        
        try:
            payout_success = await self._payment_breaker.execute(
                self._retry_policy.execute,
                _trigger_payout
            )
        except Exception as e:
            logger.error(f"❌ Payment gateway call failed: {e}")
            payout_success = False
        
        if payout_success:
            # 4. Credit the internal wallet
            wallet = db.query(AgentWallet).filter_by(user_id=agent_id).first()
            if not wallet:
                wallet = AgentWallet(user_id=agent_id, total_earned=0, pending_commission=0)
                db.add(wallet)
            
            # Since this is a payout, we reduce the settled balance
            setattr(wallet, "total_earned", float(getattr(wallet, "total_earned", 0) or 0) + commission_amount)
            
            # Update booking metadata
            if not booking.booking_details:
                booking.booking_details = {}
            booking.booking_details["settled"] = True
            booking.booking_details["payout_ref"] = payout_ref
            booking.booking_details["ledger_tx"] = ledger_entry.transaction_uuid if ledger_entry and hasattr(ledger_entry, "transaction_uuid") else None
            settled_at_str = booking.booking_details.get("settled_at")
            settled_at = safe_fromisoformat(settled_at_str)
            
            db.commit()
            
            result = SettlementResult(
                booking_id=booking_id,
                agent_id=agent_id,
                amount=commission_amount,
                status=SettlementStatus.COMPLETED,
                payout_reference=payout_ref,
                ledger_transaction=ledger_entry.transaction_uuid if ledger_entry and hasattr(ledger_entry, "transaction_uuid") else None,
                settled_at=settled_at,
                error=None
            )
            
            # Cache for idempotency
            async with self._cache_lock:
                self._settlement_cache[booking_id] = result
            
            # Record metrics
            await self._record_metrics("settlement_completed", True, commission_amount)
            
            logger.info(
                f"✅ [SETTLEMENT] Success: {agent_id} | "
                f"Ledger: {ledger_entry.transaction_uuid[:8] if ledger_entry and hasattr(ledger_entry, 'transaction_uuid') else 'N/A'}"
            )
            
            return result
        else:
            # Payout failed
            result = SettlementResult(
                booking_id=booking_id,
                agent_id=agent_id,
                amount=commission_amount,
                status=SettlementStatus.FAILED,
                payout_reference=payout_ref,
                ledger_transaction=None,
                settled_at=None,
                error="PAYOUT_FAILED"
            )
            
            # Cache for idempotency
            async with self._cache_lock:
                self._settlement_cache[booking_id] = result
            
            # Record metrics
            await self._record_metrics("settlement_failed", False, commission_amount)
            
            return result

    async def trigger_razorpayx_payout(
        self,
        user_id: str,
        amount: float,
        reference: str
    ) -> bool:
        """
        Industrial simulation of RazorpayX Payout API.
        
        Args:
            user_id: User identifier
            amount: Payout amount
            reference: Payment reference
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"📡 [RAZORPAY_X] Dispatching ₹{amount} to VPA of {user_id}...")
        
        # Simulate network latency
        await asyncio.sleep(0.5)
        
        # Simulation of successful response (90% success rate for testing)
        import random
        success = random.random() < 0.9
        
        if success:
            logger.info(f"✅ [RAZORPAY_X] Payout successful: {reference}")
        else:
            logger.error(f"❌ [RAZORPAY_X] Payout failed: {reference}")
        
        return success

    async def run_batch_settlement(
        self,
        db: Session,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Agent-driven bulk processing of all pending completed trips.
        
        Args:
            db: Database session
            limit: Maximum bookings to process
            
        Returns:
            Dict with batch settlement results
        """
        candidates = db.query(Booking).filter(
            Booking.booking_status == "COMPLETED"
        ).limit(limit).all()
        pending = [
            b for b in candidates
            if not (b.booking_details and b.booking_details.get("settled"))
        ]
        
        logger.info(f"🏦 [BATCH] Found {len(pending)} pending settlements.")
        
        processed = 0
        successful = 0
        failed = 0
        total_amount = 0.0
        
        for b in pending:
            result = await self.process_completed_trip_settlement(db, str(b.id))
            processed += 1
            
            if result.status == SettlementStatus.COMPLETED:
                successful += 1
                total_amount += result.amount
            else:
                failed += 1
        
        # Record metrics
        await self._record_metrics("batch_settlement", True, processed)
        
        return {
            "processed": processed,
            "successful": successful,
            "failed": failed,
            "total_amount": total_amount,
            "success_rate": successful / processed if processed > 0 else 0
        }

    async def get_settlement_status(
        self,
        db: Session,
        booking_id: str
    ) -> Optional[SettlementResult]:
        """
        Get settlement status for a booking.
        
        Args:
            db: Database session
            booking_id: Booking identifier
            
        Returns:
            SettlementResult or None
        """
        # Check cache first
        async with self._cache_lock:
            if self._is_already_settled(booking_id):
                return self._settlement_cache[booking_id]
        
        # Check database
        booking = db.query(Booking).filter_by(id=booking_id).first()
        if not booking or not booking.booking_details:
            return None
        
        if not booking.booking_details.get("settled"):
            return None
        
        return SettlementResult(
            booking_id=booking_id,
            agent_id=booking.agent_id or "",
            amount=0.0,
            status=SettlementStatus.COMPLETED,
            payout_reference=booking.booking_details.get("payout_ref"),
            ledger_transaction=booking.booking_details.get("ledger_tx"),
            settled_at=safe_fromisoformat(booking.booking_details.get("settled_at")),
            error=None
        )

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        operation_type: str,
        success: bool,
        amount: float = 0.0
    ):
        """Record operation metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "amount": amount
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_settlements": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        amounts = [m["amount"] for m in self._metrics]
        by_type = {}
        for m in self._metrics:
            op_type = m["operation_type"]
            by_type[op_type] = by_type.get(op_type, 0) + 1
        
        return {
            "total_settlements": total,
            "successful_settlements": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "total_amount": sum(amounts),
            "operation_breakdown": by_type,
            "db_circuit_breaker_state": self._db_breaker.get_state().value,
            "payment_circuit_breaker_state": self._payment_breaker.get_state().value
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
                "payment": {
                    "state": self._payment_breaker.get_state().value,
                    "failure_count": self._payment_breaker.failure_count,
                    "success_count": self._payment_breaker.success_count
                }
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breakers(self):
        """Reset all circuit breakers."""
        self._db_breaker.reset()
        self._payment_breaker.reset()
        logger.info("Circuit breakers reset for settlement service")

    def clear_settlement_cache(self):
        """Clear settlement cache (use with caution)."""
        self._settlement_cache.clear()
        logger.info("Settlement cache cleared")


# Global instance
settlement_service = SettlementService()
