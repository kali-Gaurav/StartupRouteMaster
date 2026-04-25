import logging
from typing import Optional
from datetime import datetime
from collections import deque
from sqlalchemy.orm import Session
from database.session import SessionUser
from database.models import User, FraudAlert
from services.ledger_service import ledger_service
from services.fraud_service import fraud_service
from core.resilience import circuit_breaker_manager, CircuitConfig
from core.retry import RetryPolicy

logger = logging.getLogger("ledger-reconciliation")

class LedgerReconciliationJob:
    """
    [Task 49.4 & 49.8] Nightly Audit Job.
    Compares Walllet Balance vs Ledger Parity.
    """
    
    def __init__(self):
        # Circuit breaker for ledger service operations
        self._ledger_breaker = circuit_breaker_manager.get_or_create(
            "ledger_reconciliation_ledger",
            CircuitConfig(
                failure_threshold=3,
                timeout_seconds=300.0,
                success_threshold=2
            )
        )
        
        # Circuit breaker for fraud service operations
        self._fraud_breaker = circuit_breaker_manager.get_or_create(
            "ledger_reconciliation_fraud",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=60.0,
                success_threshold=3
            )
        )
        
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "ledger_reconciliation_db",
            CircuitConfig(
                failure_threshold=3,
                timeout_seconds=180.0,
                success_threshold=2
            )
        )
        
        # Retry policy for reconciliation operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=2.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "deadlock" in str(e).lower(),
                lambda e: "integrity" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = __import__('asyncio').Lock()
        
        logger.info("LedgerReconciliationJob initialized with resilience patterns")
    
    async def _record_metrics(self, operation_type: str, success: bool, error: str = None):
        """Record metrics for reconciliation operations."""
        try:
            async with self._metrics_lock:
                self._metrics.append({
                    "timestamp": datetime.utcnow(),
                    "operation_type": operation_type,
                    "success": success,
                    "error": error
                })
        except Exception:
            pass  # Metrics recording should not block main operations
    
    def get_metrics(self) -> dict:
        """Get job metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_type = {}
        for m in self._metrics:
            op_type = m.get("operation_type", "unknown")
            if op_type not in by_type:
                by_type[op_type] = {"total": 0, "success": 0}
            by_type[op_type]["total"] += 1
            if m["success"]:
                by_type[op_type]["success"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_type,
            "circuit_breaker_ledger_state": self._ledger_breaker.get_state().value,
            "circuit_breaker_fraud_state": self._fraud_breaker.get_state().value,
            "circuit_breaker_db_state": self._db_breaker.get_state().value
        }
    
    def health_check(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "ledger": {
                    "state": self._ledger_breaker.get_state().value,
                    "failure_count": self._ledger_breaker.failure_count,
                    "success_count": self._ledger_breaker.success_count
                },
                "fraud": {
                    "state": self._fraud_breaker.get_state().value,
                    "failure_count": self._fraud_breaker.failure_count,
                    "success_count": self._fraud_breaker.success_count
                },
                "db": {
                    "state": self._db_breaker.get_state().value,
                    "failure_count": self._db_breaker.failure_count,
                    "success_count": self._db_breaker.success_count
                }
            },
            "metrics": self.get_metrics()
        }
    
    def reset_circuit_breakers(self):
        """Reset circuit breakers."""
        self._ledger_breaker.reset()
        self._fraud_breaker.reset()
        self._db_breaker.reset()
        logger.info("Circuit breakers reset for ledger_reconciliation_job")
    
    def run_recon(self, db: Session):
        """
        [Task 49.4 & 49.8] Nightly Audit Job.
        Compares Wallet Balance vs Ledger Parity.
        """
        logger.info("🕵️ Starting Platform-Wide Financial Reconciliation...")
        
        # 1. Integrity Check [49.9]
        if not ledger_service.verify_ledger_integrity(db):
            logger.critical("🛑 LEDGER INTEGRITY FAILURE! Halting and Alerting Admins.")
            # Trigger Global System Fraud Alert
            fraud_service.create_alert(db, None, "LEDGER_TAMPER_DETECTED", "CRITICAL", {"reason": "Hash Chain Break"})
            return
            
        # 2. Per-User Parity [49.4]
        users = db.query(User).filter(User.is_active == True).all()
        variance_count = 0
        
        for u in users:
            # Note: Credits to INR conversion logic needed for production parity
            # Assume 1 Credit = ₹39.9
            ledger_balance_inr = ledger_service.get_account_balance(db, "USER_WALLET", user_id=u.id)
            wallet_credits = u.credits or 0
            wallet_value_inr = wallet_credits * 39.9
            
            variance = abs(ledger_balance_inr - wallet_value_inr)
            
            if variance > 0.1: # Allow for tiny float rounding [49.8]
                logger.warning(f"🚨 Variance Detected for {u.email}: ₹{variance:.2f}")
                fraud_service.create_alert(
                    db, u.id, "FINANCIAL_VARIANCE", "HIGH", 
                    {"ledger": ledger_balance_inr, "wallet_value": wallet_value_inr}
                )
                variance_count += 1
                
        logger.info(f"✅ Recon Finished. Total Variance Alerts: {variance_count}")

recon_job = LedgerReconciliationJob()
