import logging
import asyncio
from typing import Optional
from datetime import datetime
from collections import deque
from sqlalchemy.orm import Session
from database.session import SessionLocal
from database.models import User, CommissionTracking
from services.commission_service import commission_service
from core.resilience import circuit_breaker_manager, CircuitConfig
from core.retry import RetryPolicy

logger = logging.getLogger("settlement-job")

class CommissionSettlementJob:
    """
    [Task 44.5] Daily Cron to settle all pending agent commissions.
    """
    
    def __init__(self):
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "commission_settlement_db",
            CircuitConfig(
                failure_threshold=3,
                timeout_seconds=180.0,
                success_threshold=2
            )
        )
        
        # Circuit breaker for commission service operations
        self._service_breaker = circuit_breaker_manager.get_or_create(
            "commission_settlement_service",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=120.0,
                success_threshold=3
            )
        )
        
        # Retry policy for settlement operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=2.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "deadlock" in str(e).lower(),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("CommissionSettlementJob initialized with resilience patterns")
    
    async def _record_metrics(self, operation_type: str, success: bool, error: str = None):
        """Record metrics for settlement operations."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "error": error
            })
    
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
            "circuit_breaker_db_state": self._db_breaker.get_state().value,
            "circuit_breaker_service_state": self._service_breaker.get_state().value
        }
    
    def health_check(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "db": {
                    "state": self._db_breaker.get_state().value,
                    "failure_count": self._db_breaker.failure_count,
                    "success_count": self._db_breaker.success_count
                },
                "service": {
                    "state": self._service_breaker.get_state().value,
                    "failure_count": self._service_breaker.failure_count,
                    "success_count": self._service_breaker.success_count
                }
            },
            "metrics": self.get_metrics()
        }
    
    def reset_circuit_breakers(self):
        """Reset circuit breakers."""
        self._db_breaker.reset()
        self._service_breaker.reset()
        logger.info("Circuit breakers reset for commission_settlement_job")

# Global job instance
settlement_job = CommissionSettlementJob()

async def run_settlement_cycle():
    """
    [Task 44.5] Daily Cron to settle all pending agent commissions.
    """
    logger.info("📅 Starting Daily Commission Settlement Cycle...")
    db = SessionLocal()
    try:
        # Find all agents with pending commissions
        agents = db.query(CommissionTracking.user_id).filter(
            CommissionTracking.status == "PENDING"
        ).distinct().all()
        
        agent_ids = [a.user_id for a in agents]
        logger.info(f"Found {len(agent_ids)} agents with pending earnings.")
        
        for agent_id in agent_ids:
            try:
                commission_service.settle_batch(db, agent_id)
            except Exception as e:
                logger.error(f"❌ Failed to settle for agent {agent_id}: {e}")
                db.rollback()
                
        logger.info("✅ Settlement Cycle Completed Successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_settlement_cycle())
