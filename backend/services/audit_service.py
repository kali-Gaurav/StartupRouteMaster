import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from database.models import AuditLog
from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy, retry
from collections import deque
import asyncio

logger = logging.getLogger(__name__)


class AuditService:
    """
    Audit Log Service for tracking all system changes.
    
    Records an immutable audit trail for financial and booking status changes.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self):
        """Initialize audit service with resilience patterns."""
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "audit_service_db",
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
            max_delay=2.0,
            conditions=[
                lambda e: "deadlock" in str(e).lower(),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Audit history
        self._audit_history: deque = deque(maxlen=1000)
        self._history_lock = asyncio.Lock()
        
        logger.info("AuditService initialized with resilience patterns")

    @retry(
        max_attempts=3,
        initial_delay=0.1,
        max_delay=2.0,
        conditions=[
            lambda e: "deadlock" in str(e).lower(),
            lambda e: "timeout" in str(e).lower()
        ]
    )
    async def log_audit(
        self,
        db: Session,
        entity_type: str,
        entity_id: str,
        action: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        performed_by: str = "SYSTEM",
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """
        Task 17: Audit Log for Status Changes.
        Records an immutable audit trail for financial and booking status changes.
        
        Args:
            db: Database session
            entity_type: Type of entity being audited
            entity_id: Entity identifier
            action: Action performed
            old_value: Previous value
            new_value: New value
            performed_by: Who performed the action
            reason: Reason for the change
            metadata: Additional metadata
            
        Returns:
            AuditLog entry
            
        Protected by circuit breaker and retry logic.
        """
        try:
            log_entry = AuditLog(
                id=str(uuid.uuid4()),
                entity_type=entity_type,
                entity_id=str(entity_id),
                action=action,
                old_value=str(old_value) if old_value is not None else None,
                new_value=str(new_value) if new_value is not None else None,
                performed_by=performed_by,
                reason=reason,
                metadata_json=metadata or {},
                timestamp=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
            
            # Record metrics
            await self._record_metrics("audit_logged", True, entity_type)
            
            # Add to history
            await self._add_to_history(log_entry)
            
            logger.info(
                f"Audit Log: {entity_type} {entity_id} {action} by {performed_by}"
            )
            
            return log_entry
            
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
            db.rollback()
            await self._record_metrics("audit_logged", False, entity_type)
            raise

    async def get_audit_logs(
        self,
        db: Session,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        performed_by: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> list:
        """
        Query audit logs with filters.
        
        Args:
            db: Database session
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            action: Filter by action
            performed_by: Filter by performer
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum results
            
        Returns:
            List of AuditLog entries
        """
        query = db.query(AuditLog)
        
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        if entity_id:
            query = query.filter(AuditLog.entity_id == entity_id)
        if action:
            query = query.filter(AuditLog.action == action)
        if performed_by:
            query = query.filter(AuditLog.performed_by == performed_by)
        if start_time:
            query = query.filter(AuditLog.timestamp >= start_time)
        if end_time:
            query = query.filter(AuditLog.timestamp <= end_time)
        
        return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

    async def get_entity_history(
        self,
        db: Session,
        entity_type: str,
        entity_id: str,
        limit: int = 50
    ) -> list:
        """
        Get full history for an entity.
        
        Args:
            db: Database session
            entity_type: Entity type
            entity_id: Entity ID
            limit: Maximum results
            
        Returns:
            List of AuditLog entries
        """
        return await self.get_audit_logs(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit
        )

    async def get_action_counts(
        self,
        db: Session,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Get counts of actions within time range.
        
        Args:
            db: Database session
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            Dict of action to count
        """
        query = db.query(AuditLog.action, db.func.count(AuditLog.id))
        
        if start_time:
            query = query.filter(AuditLog.timestamp >= start_time)
        if end_time:
            query = query.filter(AuditLog.timestamp <= end_time)
        
        results = query.group_by(AuditLog.action).all()
        
        return {action: count for action, count in results}

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        operation_type: str,
        success: bool,
        entity_type: str = ""
    ):
        """Record operation metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "entity_type": entity_type
            })

    async def _add_to_history(self, log_entry: AuditLog):
        """Add log to history."""
        async with self._history_lock:
            self._audit_history.append({
                "id": log_entry.id,
                "entity_type": log_entry.entity_type,
                "entity_id": log_entry.entity_id,
                "action": log_entry.action,
                "performed_by": log_entry.performed_by,
                "timestamp": log_entry.timestamp.isoformat()
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_type = {}
        for m in self._metrics:
            e_type = m.get("entity_type", "unknown")
            by_type[e_type] = by_type.get(e_type, 0) + 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "entity_type_breakdown": by_type,
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
        logger.info("Circuit breaker reset for audit service")

    def get_audit_history(self, limit: int = 50) -> list:
        """Get recent audit history."""
        return list(self._audit_history)[-limit:]


# Global instance
audit_service = AuditService()
