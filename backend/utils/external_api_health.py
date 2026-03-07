import time
import logging
from collections import deque
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ExternalAPIHealth:
    """
    Task 25.1 & 29.1: Singleton to track health of external API providers.
    Implements simple circuit breaker metrics and latency tracking.
    """
    def __init__(self, window_size: int = 20, failure_threshold: float = 0.5):
        self.window_size = window_size
        self.failure_threshold = failure_threshold
        
        # history of bool (True=success, False=failure)
        self.history = deque(maxlen=window_size)
        # history of floats (ms)
        self.latencies = deque(maxlen=window_size)
        
        self.is_disabled = False
        self.disabled_until = 0.0
        
        self.total_calls = 0
        self.total_success = 0
        self.total_failure = 0
        self.last_error = None

    def record_success(self, latency_ms: float = 0.0):
        self.total_calls += 1
        self.total_success += 1
        self.history.append(True)
        if latency_ms > 0:
            self.latencies.append(latency_ms)
        self._check_circuit()

    def record_failure(self, error: str = None):
        self.total_calls += 1
        self.total_failure += 1
        self.history.append(False)
        self.last_error = error
        self._check_circuit()

    def _check_circuit(self):
        if len(self.history) < self.window_size:
            return

        failure_count = self.history.count(False)
        failure_rate = failure_count / len(self.history)
        
        avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0

        # Auto-disable on high latency (> 10s) or failure rate
        if (failure_rate >= self.failure_threshold or avg_latency > 10000) and not self.is_disabled:
            logger.error(f"🚨 CIRCUIT BREAKER TRIPPED: Failure rate={failure_rate*100:.1f}%, Avg Latency={avg_latency:.0f}ms")
            self.is_disabled = True
            self.disabled_until = time.time() + 300 

    def is_available(self) -> bool:
        if self.is_disabled:
            if time.time() > self.disabled_until:
                # Attempt recovery
                logger.info("♻️ CIRCUIT BREAKER: Cooling period over, attempting recovery...")
                self.is_disabled = False
                self.history.clear()
                self.latencies.clear()
                return True
            return False
        return True

    def get_status(self) -> Dict[str, Any]:
        avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0
        return {
            "available": self.is_available(),
            "total_calls": self.total_calls,
            "success_rate": (self.total_success / self.total_calls * 100) if self.total_calls else 0,
            "failure_rate": (self.history.count(False) / len(self.history)) if self.history else 0.0,
            "avg_latency_ms": round(avg_latency, 2),
            "is_disabled": self.is_disabled,
            "last_error": self.last_error
        }

# Global instance
api_health = ExternalAPIHealth()
