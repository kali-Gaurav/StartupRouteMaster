import time
import asyncio
import logging
from typing import Dict, List, Optional
from collections import deque
from datetime import datetime, timedelta

from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy
from dataclasses import dataclass, field

logger = logging.getLogger("behavior-tracker")


@dataclass
class UserBehaviorState:
    """Tracks a sliding window of a single user's actions."""
    def __init__(self, window_size: int = 5):
        self.history = deque(maxlen=window_size)
        self.last_action_time = time.time()

    def add_action(self, path: str):
        self.history.append(path)
        self.last_action_time = time.time()

    def get_recent_paths(self) -> List[str]:
        """Get list of recent paths."""
        return list(self.history)


class HeuristicIntentTrigger:
    """
    Subtask 1.9: Advanced Behavioral Heuristics.
    Identifies high-confidence intent based on action sequences.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self):
        """Initialize behavior tracker with resilience patterns."""
        self.user_states: Dict[str, UserBehaviorState] = {}
        self.lock = asyncio.Lock()
        
        # Circuit breaker for operations
        self._operation_breaker = circuit_breaker_manager.get_or_create(
            "behavior_tracker",
            CircuitConfig(
                failure_threshold=10,
                timeout_seconds=60.0,
                success_threshold=5
            )
        )
        
        # Retry policy for operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=1.0,
            conditions=[
                lambda e: isinstance(e, (KeyError, IndexError))
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Heuristic statistics
        self._heuristic_stats: Dict[str, int] = {
            "SEARCH_DEEP": 0,
            "BOOKING_PREP": 0,
            "STATUS_ACTIVE": 0
        }
        
        # Background cleanup task
        self._cleanup_task = None
        
        logger.info("HeuristicIntentTrigger initialized with resilience patterns")

    async def start(self):
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self.cleanup_idle_states())
            logger.info("Behavior tracker cleanup task started")

    async def stop(self):
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Behavior tracker cleanup task stopped")

    async def analyze_sequence(
        self,
        client_id: str,
        current_path: str
    ) -> Optional[str]:
        """
        Analyzes the last few actions to detect complex intent.
        Returns upgraded intent if a heuristic is triggered.
        
        Args:
            client_id: Client identifier
            current_path: Current path accessed
            
        Returns:
            Detected intent or None
        """
        async with self.lock:
            if client_id not in self.user_states:
                self.user_states[client_id] = UserBehaviorState()
            
            state = self.user_states[client_id]
            state.add_action(current_path)
            
            history = state.get_recent_paths()
            
            # Heuristic 1: "Deep Station Explorer" -> SEARCH Intent
            station_hits = [p for p in history if "/stations/" in p or "/search/" in p]
            if len(set(station_hits)) >= 3:
                self._heuristic_stats["SEARCH_DEEP"] += 1
                logger.debug(f"🔥 Heuristic Triggered: Deep Station Explorer ({client_id})")
                await self._record_metrics("heuristic_detected", True, "SEARCH_DEEP")
                return "SEARCH_DEEP"

            # Heuristic 2: "Ready to Book" -> BOOKING Intent
            if any("search" in p for p in history) and any("availability" in p or "fare" in p for p in history):
                self._heuristic_stats["BOOKING_PREP"] += 1
                logger.debug(f"🔥 Heuristic Triggered: Ready to Book ({client_id})")
                await self._record_metrics("heuristic_detected", True, "BOOKING_PREP")
                return "BOOKING_PREP"

            # Heuristic 3: "Active Traveler" -> STATUS Intent
            live_hits = [p for p in history if "live" in p or "track" in p]
            if len(live_hits) >= 2:
                self._heuristic_stats["STATUS_ACTIVE"] += 1
                logger.debug(f"🔥 Heuristic Triggered: Active Traveler ({client_id})")
                await self._record_metrics("heuristic_detected", True, "STATUS_ACTIVE")
                return "STATUS_ACTIVE"
        
        return None

    async def cleanup_idle_states(self):
        """Reclaim memory for inactive users."""
        while True:
            try:
                await asyncio.sleep(60)
                
                async with self.lock:
                    now = time.time()
                    idle_ids = [
                        cid for cid, s in self.user_states.items()
                        if (now - s.last_action_time) > 300
                    ]
                    
                    for cid in idle_ids:
                        del self.user_states[cid]
                    
                    if idle_ids:
                        logger.debug(f"Cleaned up {len(idle_ids)} idle user states")
                    
                    await self._record_metrics("cleanup_cycle", True, str(len(idle_ids)))
                    
            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Cleanup error: {e}")
                await self._record_metrics("cleanup_cycle", False, "error")

    def get_user_state(self, client_id: str) -> Optional[UserBehaviorState]:
        """Get state for a specific user."""
        return self.user_states.get(client_id)

    def get_all_user_states(self) -> Dict[str, Dict[str, Any]]:
        """Get all user states (for debugging/monitoring)."""
        return {
            cid: {
                "history": list(state.history),
                "last_action_time": state.last_action_time
            }
            for cid, state in self.user_states.items()
        }

    def get_heuristic_stats(self) -> Dict[str, int]:
        """Get heuristic detection statistics."""
        return dict(self._heuristic_stats)

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        operation_type: str,
        success: bool,
        detail: str = ""
    ):
        """Record operation metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "detail": detail
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "active_users": len(self.user_states),
            "heuristic_stats": self.get_heuristic_stats(),
            "circuit_breaker_state": self._operation_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "cleanup_task_running": (
                self._cleanup_task is not None and
                not self._cleanup_task.done()
            ),
            "circuit_breaker": {
                "state": self._operation_breaker.get_state().value,
                "failure_count": self._operation_breaker.failure_count,
                "success_count": self._operation_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._operation_breaker.reset()
        logger.info("Circuit breaker reset for behavior tracker")

    def clear_user_states(self, client_id: Optional[str] = None):
        """Clear user states for a specific client or all clients."""
        if client_id:
            if client_id in self.user_states:
                del self.user_states[client_id]
        else:
            self.user_states.clear()
        logger.info(f"User states cleared for {'all' if not client_id else client_id}")


# Global instance
behavior_tracker = HeuristicIntentTrigger()
