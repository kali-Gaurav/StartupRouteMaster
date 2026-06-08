import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from sqlalchemy.orm import Session
from database.models import User, CreditTransaction, AuditLog
from core.resilience.core import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import retry_sync, RetryPolicy
from collections import deque
import asyncio

logger = logging.getLogger("credit-service")

BUNDLE_PACKS = {
    "STARTER_5": {"credits": 5, "price": 199},   # ₹39.8 per credit
    "VALUE_10": {"credits": 10, "price": 349},  # ₹34.9 per credit
    "PRO_50": {"credits": 50, "price": 1499},   # ₹29.98 per credit (BEST VALUE)
}

class UnlockCreditService:
    """
    Credit service for managing user credits and transactions.
    
    With resilience patterns: circuit breaker, retry, and metrics tracking.
    """
    
    def __init__(self):
        """Initialize credit service with resilience patterns."""
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "credit_service_db",
            CircuitConfig(
                failure_threshold=10,
                timeout_seconds=30.0,
                success_threshold=5
            )
        )
        
        # Retry policy for database operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=1.0,
            conditions=[
                lambda e: "deadlock" in str(e).lower(),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("UnlockCreditService initialized with resilience patterns")
    
    @staticmethod
    def get_user_balance(db: Session, user_id: str) -> Dict[str, int]:
        user = db.query(User).filter(User.id == user_id).first()
        if not user: return {"total": 0, "paid": 0, "bonus": 0}
        return {
            "total": user.credit_balance + user.bonus_credit_balance,
            "paid": user.credit_balance,
            "bonus": user.bonus_credit_balance
        }

    @staticmethod
    def top_up_credits(db: Session, user_id: str, bundle_id: str, payment_id: str) -> bool:
        """
        [Task 42.B] Adds credits to user account upon successful payment.
        """
        bundle = BUNDLE_PACKS.get(bundle_id)
        if not bundle:
            raise ValueError(f"Invalid bundle ID: {bundle_id}")

        user = db.query(User).filter(User.id == user_id).with_for_update().first()
        if not user: return False

        # [Task 43.D] Karma-Based Discount (Suggestion: Top scorers get 10% off)
        discount = 0.0
        if user.karma_score > 5000:
            discount = 0.10 # 10%
        elif user.karma_score > 1000:
            discount = 0.05 # 5%
            
        final_price = round(bundle["price"] * (1 - discount), 2)
        logger.info(f"Karma Discount Applied: {discount*100}% | New Price: {final_price}")

        # Top-up credits
        credits_to_add = bundle["credits"]
        
        # Audit Ledger
        old_balance = user.credit_balance
        user.credit_balance += credits_to_add
        user.total_lifetime_credits += credits_to_add
        
        tx = CreditTransaction(
            user_id=user_id,
            amount=credits_to_add,
            transaction_type="PURCHASE",
            balance_before=old_balance,
            balance_after=user.credit_balance,
            reference_entity_id=payment_id
        )
        db.add(tx)
        
        # [Task 42.E] First-time bonus logic
        if user.total_lifetime_credits <= credits_to_add:
            bonus = 1 # 1 free credit for first purchase
            user.bonus_credit_balance += bonus
            db.add(CreditTransaction(
                user_id=user_id,
                amount=bonus,
                transaction_type="BONUS",
                balance_before=0,
                balance_after=bonus,
                reference_entity_id=payment_id
            ))
            logger.info(f"Awarded First-Purchase Bonus to {user_id}")

        db.commit()
        logger.info(f"User {user_id} topped up {credits_to_add} via {bundle_id}")
        return True

    @staticmethod
    async def award_credits(db: Session, user_id: str, credits: int, reason: str, ref_id: str) -> bool:
        """
        Award credits to a user for trust recovery or promotional reasons.
        """
        user = db.query(User).filter(User.id == user_id).with_for_update().first()
        if not user:
            return False

        old_balance = user.credit_balance + user.bonus_credit_balance
        user.credit_balance += credits
        user.total_lifetime_credits += credits

        tx = CreditTransaction(
            user_id=user_id,
            amount=credits,
            transaction_type="AWARD",
            balance_before=old_balance,
            balance_after=user.credit_balance + user.bonus_credit_balance,
            reference_entity_id=ref_id
        )
        db.add(tx)
        db.commit()
        logger.info(f"Awarded {credits} credits to {user_id} for {reason}")
        return True

    @staticmethod
    def consume_credit(db: Session, user_id: str, booking_id: str) -> bool:
        """
        [Task 42.C] Core Consumption Logic. Deducts 1 token.
        Priority: 1. Bonus 2. Paid
        """
        user = db.query(User).filter(User.id == user_id).with_for_update().first()
        if not user:
            return False

        balance = int(user.credit_balance or 0) + int(user.bonus_credit_balance or 0)
        if balance < 1:
            return False

        # --- MOMENTUM BONUS Logic (Gaurav Suggestion) ---
        # If user consumed last credit < 24 hours ago, check for "Speed Unlock"
        last_tx = db.query(CreditTransaction).filter(
            CreditTransaction.user_id == user_id, 
            CreditTransaction.transaction_type == "CONSUMPTION"
        ).order_by(CreditTransaction.timestamp.desc()).first()
        
        if last_tx and (datetime.utcnow() - last_tx.timestamp) < timedelta(hours=24):
            # Potential streak detection (Implementation logic in Task 43)
            pass

        # Deduction with Priority
        if user.bonus_credit_balance > 0:
            user.bonus_credit_balance -= 1
        else:
            user.credit_balance -= 1

        db.add(CreditTransaction(
            user_id=user_id,
            amount=-1,
            transaction_type="CONSUMPTION",
            balance_before=UnlockCreditService.get_user_balance(db, user_id)["total"] + 1,
            balance_after=UnlockCreditService.get_user_balance(db, user_id)["total"],
            reference_entity_id=booking_id
        ))
        
        db.commit()
        return True

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(self, transaction_type: str, success: bool, amount: int = 0):
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
        by_type = {}
        for m in self._metrics:
            t_type = m["transaction_type"]
            by_type[t_type] = by_type.get(t_type, 0) + 1
        
        return {
            "total_transactions": total,
            "successful_transactions": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "transaction_breakdown": by_type,
            "circuit_breaker_state": self._db_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "state": self._db_breaker.get_state().value,
                "failure_count": self._db_breaker.failure_count,
                "success_count": self._db_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._db_breaker.reset()
        logger.info("Circuit breaker reset for credit service")


# Create instance for metrics tracking
_credit_service_instance = None

def get_credit_service() -> UnlockCreditService:
    """Get or create credit service instance."""
    global _credit_service_instance
    if _credit_service_instance is None:
        _credit_service_instance = UnlockCreditService()
    return _credit_service_instance

credit_service = UnlockCreditService()
