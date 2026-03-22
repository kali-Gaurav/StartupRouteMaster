import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("feedback-loop")

@dataclass
class PredictionAttempt:
    intent: str
    path: str
    timestamp: float
    used: bool = False

class PredictionFeedbackLoop:
    """
    Subtask 1.7 (FIXED): Intelligent Feedback Loop.
    Correctly handles multiple simultaneous predictions per client.
    """
    def __init__(self):
        self.pending_verifications: Dict[str, List[PredictionAttempt]] = {}
        self.stats = {"correct": 0, "false_positives": 0}
        self.multipliers = {"SEARCH": 1.0, "BOOKING": 1.0, "STATUS": 1.0}
        self.window_seconds = 30.0
        self.lock = asyncio.Lock() # Thread safety

    async def record_prediction(self, client_id: str, intent: str, path: str):
        # Task 36: Probabilistic Sampling for Feedback
        from core.resource_monitor import resource_monitor
        if resource_monitor.should_throttle_tasks():
            import random
            if random.random() > 0.2: # Only sample 20% during load
                return

        async with self.lock:
            if client_id not in self.pending_verifications:
                self.pending_verifications[client_id] = []
            
            # Avoid redundant predictions for same intent/path in same window
            if any(a.intent == intent and a.path == path for a in self.pending_verifications[client_id]):
                return

            attempt = PredictionAttempt(intent=intent, path=path, timestamp=time.time())
            self.pending_verifications[client_id].append(attempt)

    async def record_actual_use(self, client_id: str, path: str):
        async with self.lock:
            if client_id not in self.pending_verifications:
                return

            now = time.time()
            # Iterate and mark ALL matching pending predictions as used
            for attempt in self.pending_verifications[client_id]:
                if not attempt.used and (now - attempt.timestamp) < self.window_seconds:
                    if self._match_path_to_intent(path, attempt.intent):
                        attempt.used = True
                        self.stats["correct"] += 1
                        from core.metrics import jit_metrics
                        jit_metrics.correct_predictions += 1
                        self.multipliers[attempt.intent] = min(1.2, self.multipliers[attempt.intent] + 0.01)
                        # Reduced logging for performance (Task 30 style)
                        if random.random() < 0.1:
                            logger.debug(f"🎯 Reward: {attempt.intent} -> {self.multipliers[attempt.intent]:.2f}")

    async def run_punishment_cycle(self):
        while True:
            # Task 36: Adaptive Cycle
            from core.resource_monitor import resource_monitor
            sleep_time = 30 if resource_monitor.should_throttle_tasks() else 10
            await asyncio.sleep(sleep_time)
            
            async with self.lock:
                now = time.time()
                to_remove_clients = []
                
                for client_id, attempts in self.pending_verifications.items():
                    # Process unused and expired
                    new_attempts = []
                    for attempt in attempts:
                        if not attempt.used and (now - attempt.timestamp) > self.window_seconds:
                            self.stats["false_positives"] += 1
                            from core.metrics import jit_metrics
                            jit_metrics.false_positives += 1
                            self.multipliers[attempt.intent] = max(0.5, self.multipliers[attempt.intent] - 0.05)
                            logger.warning(f"📉 Punish: {attempt.intent} -> {self.multipliers[attempt.intent]:.2f}")
                        elif not attempt.used or (now - attempt.timestamp) < self.window_seconds:
                            # Keep if still fresh or already used but in window
                            new_attempts.append(attempt)
                    
                    self.pending_verifications[client_id] = new_attempts
                    if not new_attempts:
                        to_remove_clients.append(client_id)
                
                for cid in to_remove_clients:
                    del self.pending_verifications[cid]

    def _match_path_to_intent(self, actual_path: str, predicted_intent: str) -> bool:
        p = actual_path.lower()
        if predicted_intent == "SEARCH" and ("search" in p or "stations" in p): return True
        if predicted_intent == "BOOKING" and ("book" in p or "pay" in p): return True
        if predicted_intent == "STATUS" and ("live" in p or "track" in p): return True
        return False

feedback_loop = PredictionFeedbackLoop()
