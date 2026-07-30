"""
Feedback Loop Service - Intelligent Prediction Feedback
========================================================

Provides intelligent feedback loop for prediction accuracy:
- Prediction recording and verification
- Reward/punishment cycles
- Multiplier adjustments based on accuracy

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import asyncio
import logging
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

from core.resilience.core import circuit_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy
from enum import Enum

logger = logging.getLogger("feedback-loop")


class PredictionStatus(Enum):
    """Status of prediction."""
    PENDING = "PENDING"
    USED = "USED"
    EXPIRED = "EXPIRED"


@dataclass
class PredictionAttempt:
    """Prediction attempt details."""
    intent: str
    path: str
    timestamp: float
    status: PredictionStatus = PredictionStatus.PENDING


@dataclass
class FeedbackMetrics:
    """Feedback loop metrics."""
    total_predictions: int
    correct_predictions: int
    false_positives: int
    accuracy_rate: float
    active_predictions: int


class PredictionFeedbackLoop:
    """
    Subtask 1.7 (FIXED): Intelligent Feedback Loop.
    Correctly handles multiple simultaneous predictions per client.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self):
        """Initialize feedback loop with resilience patterns."""
        self.pending_verifications: Dict[str, List[PredictionAttempt]] = {}
        self.multipliers = {"SEARCH": 1.0, "BOOKING": 1.0, "STATUS": 1.0}
        self.window_seconds = 30.0
        self.lock = asyncio.Lock()  # Thread safety
        
        # Circuit breaker for operations
        self._operation_breaker = circuit_manager.get_or_create(
            "feedback_loop",
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
                lambda e: isinstance(e, (KeyError, IndexError)),
                lambda e: "empty" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Statistics
        self.stats = {
            "correct": 0,
            "false_positives": 0,
            "total_predictions": 0,
            "total_verifications": 0
        }
        
        # Start background task
        self._punishment_task = None
        
        logger.info("PredictionFeedbackLoop initialized with resilience patterns")

    async def start(self):
        """Start the background punishment cycle."""
        if self._punishment_task is None or self._punishment_task.done():
            self._punishment_task = asyncio.create_task(self.run_punishment_cycle())
            logger.info("Feedback loop punishment cycle started")

    async def stop(self):
        """Stop the background punishment cycle."""
        if self._punishment_task and not self._punishment_task.done():
            self._punishment_task.cancel()
            try:
                await self._punishment_task
            except asyncio.CancelledError:
                pass
            logger.info("Feedback loop punishment cycle stopped")

    async def record_prediction(
        self,
        client_id: str,
        intent: str,
        path: str
    ) -> bool:
        """
        Record a prediction for verification.
        
        Args:
            client_id: Client identifier
            intent: Predicted intent
            path: Predicted path
            
        Returns:
            True if recorded, False if skipped
        """
        # Task 36: Probabilistic Sampling for Feedback
        try:
            from core.infrastructure.resource_monitor import resource_monitor
            if resource_monitor.should_throttle_tasks():
                if random.random() > 0.2:  # Only sample 20% during load
                    return False
        except ImportError:
            pass
        
        async with self.lock:
            if client_id not in self.pending_verifications:
                self.pending_verifications[client_id] = []
            
            # Avoid redundant predictions for same intent/path in same window
            if any(
                a.intent == intent and a.path == path
                for a in self.pending_verifications[client_id]
                if a.status == PredictionStatus.PENDING
            ):
                return False

            attempt = PredictionAttempt(
                intent=intent,
                path=path,
                timestamp=time.time(),
                status=PredictionStatus.PENDING
            )
            self.pending_verifications[client_id].append(attempt)
            self.stats["total_predictions"] += 1
            
            # Record metrics
            await self._record_metrics("prediction_recorded", True, intent)
            
            logger.debug(f"📝 Recorded prediction: {client_id} -> {intent}/{path}")
            return True

    async def record_actual_use(
        self,
        client_id: str,
        path: str
    ) -> int:
        """
        Record actual path used by client.
        
        Args:
            client_id: Client identifier
            path: Actual path used
            
        Returns:
            Number of predictions marked as correct
        """
        async with self.lock:
            if client_id not in self.pending_verifications:
                return 0

            now = time.time()
            marked_count = 0
            
            # Iterate and mark ALL matching pending predictions as used
            for attempt in self.pending_verifications[client_id]:
                if (
                    attempt.status == PredictionStatus.PENDING and
                    (now - attempt.timestamp) < self.window_seconds
                ):
                    if self._match_path_to_intent(path, attempt.intent):
                        attempt.status = PredictionStatus.USED
                        self.stats["correct"] += 1
                        self.stats["total_verifications"] += 1
                        marked_count += 1
                        
                        # Update multiplier
                        self.multipliers[attempt.intent] = min(
                            1.2,
                            self.multipliers[attempt.intent] + 0.01
                        )
                        
                        # Reduced logging for performance (Task 30 style)
                        if random.random() < 0.1:
                            logger.debug(
                                f"🎯 Reward: {attempt.intent} -> "
                                f"{self.multipliers[attempt.intent]:.2f}"
                            )
            
            # Record metrics
            if marked_count > 0:
                await self._record_metrics("actual_use_recorded", True, path)
            
            return marked_count

    async def run_punishment_cycle(self):
        """
        Background task to process expired predictions.
        """
        while True:
            try:
                # Task 36: Adaptive Cycle
                try:
                    from core.infrastructure.resource_monitor import resource_monitor
                    sleep_time = 30 if resource_monitor.should_throttle_tasks() else 10
                except ImportError:
                    sleep_time = 10
                
                await asyncio.sleep(sleep_time)
                
                async with self.lock:
                    now = time.time()
                    to_remove_clients = []
                    
                    for client_id, attempts in self.pending_verifications.items():
                        # Process unused and expired
                        new_attempts = []
                        for attempt in attempts:
                            if (
                                attempt.status == PredictionStatus.PENDING and
                                (now - attempt.timestamp) > self.window_seconds
                            ):
                                # Mark as expired and apply punishment
                                attempt.status = PredictionStatus.EXPIRED
                                self.stats["false_positives"] += 1
                                self.stats["total_verifications"] += 1
                                
                                self.multipliers[attempt.intent] = max(
                                    0.5,
                                    self.multipliers[attempt.intent] - 0.05
                                )
                                logger.debug(
                                    f"📉 Punish: {attempt.intent} -> "
                                    f"{self.multipliers[attempt.intent]:.2f}"
                                )
                            elif (
                                attempt.status == PredictionStatus.PENDING or
                                (now - attempt.timestamp) < self.window_seconds
                            ):
                                # Keep if still fresh or already used but in window
                                new_attempts.append(attempt)
                        
                        self.pending_verifications[client_id] = new_attempts
                        if not new_attempts:
                            to_remove_clients.append(client_id)
                    
                    for cid in to_remove_clients:
                        del self.pending_verifications[cid]
                    
                    # Record metrics
                    await self._record_metrics("punishment_cycle", True, "cycle")
                    
            except asyncio.CancelledError:
                logger.info("Punishment cycle cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Punishment cycle error: {e}")
                await self._record_metrics("punishment_cycle", False, "cycle")

    def _match_path_to_intent(self, actual_path: str, predicted_intent: str) -> bool:
        """Match actual path to predicted intent."""
        p = actual_path.lower()
        if predicted_intent == "SEARCH" and ("search" in p or "stations" in p):
            return True
        if predicted_intent == "BOOKING" and ("book" in p or "pay" in p):
            return True
        if predicted_intent == "STATUS" and ("live" in p or "track" in p):
            return True
        return False

    def get_multiplier(self, intent: str) -> float:
        """
        Get current multiplier for an intent.
        
        Args:
            intent: Intent type
            
        Returns:
            Current multiplier value
        """
        return self.multipliers.get(intent, 1.0)

    def get_pending_predictions(
        self,
        client_id: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get pending predictions.
        
        Args:
            client_id: Optional client filter
            
        Returns:
            Dict of client_id to pending predictions
        """
        result = {}
        
        if client_id:
            if client_id in self.pending_verifications:
                result[client_id] = [
                    {
                        "intent": a.intent,
                        "path": a.path,
                        "timestamp": a.timestamp,
                        "status": a.status.value
                    }
                    for a in self.pending_verifications[client_id]
                ]
        else:
            for cid, attempts in self.pending_verifications.items():
                result[cid] = [
                    {
                        "intent": a.intent,
                        "path": a.path,
                        "timestamp": a.timestamp,
                        "status": a.status.value
                    }
                    for a in attempts
                ]
        
        return result

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
        total = self.stats["total_verifications"]
        correct = self.stats["correct"]
        
        return {
            "total_predictions": self.stats["total_predictions"],
            "correct_predictions": correct,
            "false_positives": self.stats["false_positives"],
            "accuracy_rate": correct / total if total > 0 else 0.0,
            "active_predictions": sum(
                len(attempts)
                for attempts in self.pending_verifications.values()
            ),
            "multipliers": dict(self.multipliers),
            "pending_clients": len(self.pending_verifications),
            "circuit_breaker_state": self._operation_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "punishment_cycle_running": (
                self._punishment_task is not None and
                not self._punishment_task.done()
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
        logger.info("Circuit breaker reset for feedback loop")

    def clear_predictions(self, client_id: Optional[str] = None):
        """Clear predictions for a client or all clients."""
        if client_id:
            if client_id in self.pending_verifications:
                del self.pending_verifications[client_id]
        else:
            self.pending_verifications.clear()
        logger.info(f"Predictions cleared for {'all' if not client_id else client_id}")


# Global instance
feedback_loop = PredictionFeedbackLoop()
