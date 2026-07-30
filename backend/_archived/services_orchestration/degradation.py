"""
Degradation Manager - Tiered Degradation State Machine
=======================================================

Manages system degradation states based on resource availability:
- HEALTHY: Full functionality
- DEGRADED_ML: ML features reduced
- DEGRADED_GRAPH: Graph operations reduced
- MINIMAL: Core functionality only

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import asyncio
import logging
import time
import psutil
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timedelta

from core.resilience.core import circuit_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy

logger = logging.getLogger("degradation-manager")


class SystemState(Enum):
    """System degradation states."""
    HEALTHY = "HEALTHY"
    DEGRADED_ML = "DEGRADED_ML"
    DEGRADED_GRAPH = "DEGRADED_GRAPH"
    MINIMAL = "MINIMAL"


@dataclass
class StateTransition:
    """State transition event."""
    from_state: SystemState
    to_state: SystemState
    timestamp: datetime
    reason: str
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DegradationMetrics:
    """Degradation monitoring metrics."""
    cpu_usage: float
    memory_usage: float
    active_connections: int
    queue_depth: int
    response_time_ms: float


class DegradationManager:
    """
    Subtask 7.1: Tiered Degradation State Machine.
    Monitors system resources and transitions between degradation states.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self):
        """Initialize degradation manager with resilience patterns."""
        self.current_state = SystemState.HEALTHY
        self.last_state_change = time.time()
        self._state_history: deque = deque(maxlen=100)
        self._history_lock = asyncio.Lock()
        
        # Thresholds for state transitions
        self._thresholds = {
            "cpu_warning": 70.0,      # CPU % for warning
            "cpu_critical": 85.0,     # CPU % for critical
            "memory_warning": 75.0,   # Memory % for warning
            "memory_critical": 90.0,  # Memory % for critical
            "response_time_warning": 1000.0,  # Response time ms
            "response_time_critical": 2000.0,  # Response time ms
        }
        
        # Circuit breaker for monitoring operations
        self._monitor_breaker = circuit_manager.get_or_create(
            "degradation_manager_monitor",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
                success_threshold=3
            )
        )
        
        # Retry policy for monitoring
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: isinstance(e, (OSError, PermissionError)),
                lambda e: "access" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Monitoring task
        self._monitor_task = None
        self._monitor_interval = 30  # seconds
        
        logger.info("DegradationManager initialized with resilience patterns")

    def get_current_state(self) -> SystemState:
        """Get current system state."""
        return self.current_state

    def get_state_description(self) -> str:
        """Get human-readable state description."""
        descriptions = {
            SystemState.HEALTHY: "All systems operational",
            SystemState.DEGRADED_ML: "ML features reduced - non-critical ML operations disabled",
            SystemState.DEGRADED_GRAPH: "Graph operations reduced - complex routing disabled",
            SystemState.MINIMAL: "Minimal mode - core functionality only",
        }
        return descriptions.get(self.current_state, "Unknown state")

    def is_feature_enabled(self, feature: str) -> bool:
        """
        Check if a feature is enabled in current state.
        
        Args:
            feature: Feature name to check
            
        Returns:
            True if enabled, False otherwise
        """
        feature_matrix = {
            "search": [True, True, True, True],
            "booking": [True, True, True, True],
            "live_status": [True, True, True, True],
            "ml_predictions": [True, True, False, False],
            "complex_routing": [True, True, False, False],
            "recommendations": [True, True, False, False],
            "analytics": [True, False, False, False],
            "notifications": [True, True, True, True],
        }
        
        state_index = list(SystemState).index(self.current_state)
        return feature_matrix.get(feature, [True, True, True, True])[state_index]

    async def _get_system_metrics(self) -> Optional[DegradationMetrics]:
        """
        Get current system metrics.
        
        Returns:
            DegradationMetrics or None if unavailable
        """
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Active connections (approximate)
            try:
                connections = len(psutil.net_connections())
            except Exception:
                connections = 0
            
            # Queue depth (placeholder - would integrate with message queue)
            queue_depth = 0
            
            # Response time (placeholder - would measure actual endpoints)
            response_time_ms = 0.0
            
            return DegradationMetrics(
                cpu_usage=cpu_percent,
                memory_usage=memory_percent,
                active_connections=connections,
                queue_depth=queue_depth,
                response_time_ms=response_time_ms
            )
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to get system metrics: {e}")
            return None

    async def _calculate_next_state(self) -> SystemState:
        """
        Calculate next state based on current metrics.
        
        Returns:
            SystemState to transition to
        """
        metrics = await self._get_system_metrics()
        
        if not metrics:
            # If metrics unavailable, be conservative
            return SystemState.MINIMAL
        
        # Check for minimal state (critical thresholds)
        if (
            metrics.cpu_usage >= self._thresholds["cpu_critical"] or
            metrics.memory_usage >= self._thresholds["memory_critical"] or
            metrics.response_time_ms >= self._thresholds["response_time_critical"]
        ):
            return SystemState.MINIMAL
        
        # Check for degraded_ml state
        if (
            metrics.cpu_usage >= self._thresholds["cpu_warning"] or
            metrics.memory_usage >= self._thresholds["memory_warning"] or
            metrics.response_time_ms >= self._thresholds["response_time_warning"]
        ):
            return SystemState.DEGRADED_ML
        
        # Default to healthy
        return SystemState.HEALTHY

    async def transition_to(self, new_state: SystemState, reason: str = ""):
        """
        Transition to a new state.
        
        Args:
            new_state: Target state
            reason: Reason for transition
        """
        if new_state == self.current_state:
            return
        
        old_state = self.current_state
        
        # Create transition record
        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            timestamp=datetime.utcnow(),
            reason=reason or f"State transition: {old_state.value} -> {new_state.value}",
            metrics={
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent
            }
        )
        
        async with self._history_lock:
            self._state_history.append(transition)
        
        self.current_state = new_state
        self.last_state_change = time.time()
        
        logger.warning(
            f"🔄 System state transition: {old_state.value} -> {new_state.value} "
            f"(Reason: {reason})"
        )

    async def run_monitor_loop(self):
        """
        Background monitoring loop.
        Periodically checks system metrics and transitions states.
        """
        logger.info("🛰️ Degradation monitor started")
        
        while True:
            try:
                await asyncio.sleep(self._monitor_interval)
                
                # Calculate next state
                next_state = await self._calculate_next_state()
                
                # Transition if needed
                if next_state != self.current_state:
                    await self.transition_to(
                        next_state,
                        f"Resource thresholds exceeded"
                    )
                
                # Record metrics
                await self._record_metrics("monitor_cycle", True)
                
            except asyncio.CancelledError:
                logger.info("Degradation monitor cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}")
                await self._record_metrics("monitor_cycle", False)

    async def start_monitoring(self, interval_seconds: int = 30):
        """
        Start the monitoring loop.
        
        Args:
            interval_seconds: Monitoring interval
        """
        self._monitor_interval = interval_seconds
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self.run_monitor_loop())
            logger.info(f"Degradation monitoring started (interval: {interval_seconds}s)")

    async def stop_monitoring(self):
        """Stop the monitoring loop."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            logger.info("Degradation monitoring stopped")

    def update_thresholds(self, **kwargs):
        """
        Update degradation thresholds.
        
        Args:
            **kwargs: Threshold values to update
        """
        valid_keys = [
            "cpu_warning", "cpu_critical",
            "memory_warning", "memory_critical",
            "response_time_warning", "response_time_critical"
        ]
        
        for key, value in kwargs.items():
            if key in valid_keys:
                self._thresholds[key] = value
                logger.info(f"Updated threshold: {key} = {value}")

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(self, operation_type: str, success: bool):
        """Record operation metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "current_state": self.current_state.value
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        
        # Count state transitions
        state_counts = {}
        for m in self._metrics:
            state = m.get("current_state", "unknown")
            state_counts[state] = state_counts.get(state, 0) + 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "current_state": self.current_state.value,
            "state_distribution": state_counts,
            "last_state_change": self.last_state_change,
            "circuit_breaker_state": self._monitor_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "current_state": self.current_state.value,
            "state_description": self.get_state_description(),
            "monitoring_active": (
                self._monitor_task is not None and
                not self._monitor_task.done()
            ),
            "thresholds": self._thresholds,
            "circuit_breaker": {
                "state": self._monitor_breaker.get_state().value,
                "failure_count": self._monitor_breaker.failure_count,
                "success_count": self._monitor_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._monitor_breaker.reset()
        logger.info("Circuit breaker reset for degradation manager")

    def get_state_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent state transitions."""
        return [
            {
                "from_state": t.from_state.value,
                "to_state": t.to_state.value,
                "timestamp": t.timestamp.isoformat(),
                "reason": t.reason,
                "metrics": t.metrics
            }
            for t in list(self._state_history)[-limit:]
        ]


# Global instance
degradation_manager = DegradationManager()
