"""
Recovery Service - Resilient Smart-Retry Hub
=============================================

Handles failed payments and PNR lookups with:
- Exponential backoff with jitter
- Failure queue for manual intervention
- Automatic escalation to admin review

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import logging
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, Optional, List
from sqlalchemy.orm import Session
from database.models import AuditLog
from core.resilience.core import circuit_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy, retry
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import time

logger = logging.getLogger("routemaster.recovery")


class RetryStatus(Enum):
    """Status of retry operation."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


@dataclass
class RetryTask:
    """Retry task details."""
    task_id: str
    function_name: str
    status: RetryStatus
    retry_count: int
    max_retries: int
    last_attempt: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    escalated_at: Optional[datetime] = None


class SmartRetryHub:
    """
    [Group 4] Resilient Smart-Retry Hub.
    Handles failed payments and PNR lookups with exponential backoff and jitter.
    Includes a 'Failure Queue' for manual intervention.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self):
        """Initialize smart retry hub with resilience patterns."""
        self.retry_registry: Dict[str, RetryTask] = {}
        self.MAX_RETRIES = 5
        
        # Circuit breaker for retry operations
        self._retry_breaker = circuit_manager.get_or_create(
            "smart_retry_hub",
            CircuitConfig(
                failure_threshold=10,
                timeout_seconds=60.0,
                success_threshold=5
            )
        )
        
        # Retry policy for operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=10.0,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "timeout" in str(e).lower(),
                lambda e: "temporary" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Task history
        self._task_history: deque = deque(maxlen=1000)
        self._history_lock = asyncio.Lock()
        
        logger.info("SmartRetryHub initialized with resilience patterns")

    def _calculate_backoff(self, retry_count: int) -> float:
        """
        Calculate exponential backoff with jitter.
        
        Delay = 2^retry * 0.5s + jitter (0.1-0.5s)
        """
        base_delay = (2 ** retry_count) * 0.5
        jitter = random.uniform(0.1, 0.5)
        return base_delay + jitter

    async def execute_with_retry(
        self,
        task_id: str,
        func: Callable,
        db: Session,
        *args,
        max_retries: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Executes a mission-critical function with autonomous recovery logic.
        
        Args:
            task_id: Unique task identifier
            func: Async function to execute
            db: Database session
            *args: Positional arguments for func
            max_retries: Optional max retries override
            **kwargs: Keyword arguments for func
            
        Returns:
            Dict with result or failure information
            
        Protected by circuit breaker and retry logic.
        """
        max_attempts = max_retries or self.MAX_RETRIES
        
        # Get or create task
        if task_id not in self.retry_registry:
            self.retry_registry[task_id] = RetryTask(
                task_id=task_id,
                function_name=func.__name__,
                status=RetryStatus.IN_PROGRESS,
                retry_count=0,
                max_retries=max_attempts,
                last_attempt=None,
                last_error=None,
                created_at=datetime.utcnow()
            )
        
        task = self.retry_registry[task_id]
        
        async def _execute_with_breaker():
            """Execute function through circuit breaker."""
            return await func(*args, **kwargs)
        
        try:
            # 1. Attempt Execution
            result = await self._retry_breaker.execute(
                self._retry_policy.execute,
                _execute_with_breaker
            )
            
            # Clean up on success
            task.status = RetryStatus.SUCCESS
            task.last_attempt = datetime.utcnow()
            
            if task_id in self.retry_registry:
                del self.retry_registry[task_id]
            
            # Record metrics
            await self._record_metrics("retry_success", True, task.retry_count)
            
            # Add to history
            await self._add_to_history(task)
            
            return {
                "status": "SUCCESS",
                "task_id": task_id,
                "result": result,
                "retry_count": task.retry_count
            }

        except Exception as e:
            # 2. Increment and Evaluate
            task.retry_count += 1
            task.last_attempt = datetime.utcnow()
            task.last_error = str(e)
            
            logger.warning(
                f"🔁 [RECOVERY] Task {task_id} failed "
                f"(Attempt {task.retry_count}/{max_attempts}): {e}"
            )

            if task.retry_count >= max_attempts:
                # Move to admin queue
                return await self._move_to_admin_queue(task, str(e), db)

            # 3. Calculate Exponential Backoff with Jitter
            delay = self._calculate_backoff(task.retry_count)
            logger.info(f"⏳ [RECOVERY] Backing off for {delay:.2f}s...")
            
            await asyncio.sleep(delay)
            
            # Recursive Retry
            return await self.execute_with_retry(
                task_id, func, db, *args,
                max_retries=max_attempts,
                **kwargs
            )

    async def _move_to_admin_queue(
        self,
        task: RetryTask,
        error: str,
        db: Session
    ) -> Dict[str, Any]:
        """Escalates a persistent failure to the admin audit queue."""
        logger.error(
            f"🚨 [RECOVERY] Task {task.task_id} reached MAX_RETRIES. "
            f"Escalating to Admin."
        )
        
        task.status = RetryStatus.ESCALATED
        task.escalated_at = datetime.utcnow()
        
        try:
            audit = AuditLog(
                entity_type="SYSTEM_RECOVERY",
                entity_id=task.task_id,
                action="RETRY_EXHAUSTED",
                new_value="ADMIN_INTERVENTION_REQUIRED",
                performed_by="SYSTEM_RECOVERY_HUB",
                reason=f"Failed after {task.max_retries} attempts. Last Error: {error}"
            )
            db.add(audit)
            db.commit()
        except Exception as e:
            logger.error(f"❌ Failed to create audit log: {e}")
        
        # Add to history
        await self._add_to_history(task)
        
        # Remove from active registry
        if task.task_id in self.retry_registry:
            del self.retry_registry[task.task_id]
        
        # Record metrics
        await self._record_metrics("retry_escalated", True, task.retry_count)
        
        return {
            "status": "FAILED_ESCALATED",
            "task_id": task.task_id,
            "error": error,
            "retry_count": task.retry_count,
            "escalated_at": task.escalated_at.isoformat()
        }

    async def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get all pending retry tasks."""
        return [
            {
                "task_id": task.task_id,
                "function_name": task.function_name,
                "status": task.status.value,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "last_attempt": task.last_attempt.isoformat() if task.last_attempt else None,
                "last_error": task.last_error,
                "created_at": task.created_at.isoformat()
            }
            for task in self.retry_registry.values()
        ]

    async def cancel_task(self, task_id: str, reason: str = "USER_CANCELLED") -> bool:
        """
        Cancel a pending retry task.
        
        Args:
            task_id: Task identifier
            reason: Cancellation reason
            
        Returns:
            True if cancelled, False if not found
        """
        if task_id in self.retry_registry:
            task = self.retry_registry[task_id]
            task.status = RetryStatus.FAILED
            task.last_error = reason
            
            await self._add_to_history(task)
            del self.retry_registry[task_id]
            
            logger.info(f"⚠️ [RECOVERY] Task {task_id} cancelled: {reason}")
            return True
        
        return False

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        operation_type: str,
        success: bool,
        retry_count: int = 0
    ):
        """Record operation metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "retry_count": retry_count
            })

    async def _add_to_history(self, task: RetryTask):
        """Add task to history."""
        async with self._history_lock:
            self._task_history.append({
                "task_id": task.task_id,
                "function_name": task.function_name,
                "status": task.status.value,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "last_error": task.last_error,
                "created_at": task.created_at.isoformat(),
                "completed_at": datetime.utcnow().isoformat()
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        escalated = sum(1 for m in self._metrics if m["operation_type"] == "retry_escalated")
        avg_retries = sum(m["retry_count"] for m in self._metrics) / total if total > 0 else 0
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "escalated_operations": escalated,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_retry_count": avg_retries,
            "pending_tasks": len(self.retry_registry),
            "circuit_breaker_state": self._retry_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "pending_tasks": len(self.retry_registry),
            "circuit_breaker": {
                "state": self._retry_breaker.get_state().value,
                "failure_count": self._retry_breaker.failure_count,
                "success_count": self._retry_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._retry_breaker.reset()
        logger.info("Circuit breaker reset for smart retry hub")

    def get_task_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent task history."""
        return list(self._task_history)[-limit:]


# Global singleton
smart_retry_hub = SmartRetryHub()
