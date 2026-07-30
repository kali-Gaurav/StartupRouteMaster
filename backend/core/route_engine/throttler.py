import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class EngineThrottler:
    """
    [Task 41.1] Predictive Latency-Based Throttler.
    Uses EWMA (Exponentially Weighted Moving Average) to track engine latency
    and dynamically scale discovery limits to prevent system-wide lag.
    Designed for high-concurrency VPS environments.
    """
    def __init__(
        self, 
        engine_id: str, 
        target_latency_ms: float,
        alpha: float = 0.3  # Smoothing factor (higher = more reactive to spikes)
    ):
        self.engine_id = engine_id
        self.target_latency = target_latency_ms
        self.alpha = alpha
        
        self.current_ewma = target_latency_ms  # Seed with target
        self.last_update = time.time()
        
        # Scaling thresholds
        self.limit_scale = 1.0  # Percentage of the requested limit to allow (1.0 = 100%)
        self.min_scale = 0.1    # Never drop below 10% of requested limit
        
        # Critical thresholds (reduced from 3.0x to 2.0x for higher availability)
        # 3x was too aggressive, prevented recovery during normal peak spikes
        self.critical_latency = target_latency_ms * 2.0

    def record_latency(self, latency_ms: float):
        """Update EWMA with new results and adjust throttle scale."""
        self.current_ewma = (self.alpha * latency_ms) + (1.0 - self.alpha) * self.current_ewma
        self.last_update = time.time()
        
        # Recalculate scaling factor
        if self.current_ewma > self.target_latency:
            # Linear scaling down. E.g., if latency is 2x target, scale is 0.5.
            self.limit_scale = max(self.min_scale, self.target_latency / self.current_ewma)
            
            if self.limit_scale < 0.7:
                logger.warning(
                    f"⚠️ [THROTTLER:{self.engine_id}] Latency spike detected! "
                    f"EWMA: {self.current_ewma:.0f}ms (Target: {self.target_latency:.0f}ms). "
                    f"Throttling results to {self.limit_scale*100:.1f}%."
                )
        else:
            # Recovery phase: Smoothly move back to 100%
            self.limit_scale = min(1.0, self.limit_scale + 0.1)

    def get_effective_limit(self, requested_limit: int) -> int:
        """Returns the discovery limit allowed by the throttler."""
        return max(1, int(requested_limit * self.limit_scale))

    def should_skip(self, is_premium: bool = False) -> bool:
        """Hard skip if latency is critical and user isn't premium."""
        if is_premium: return False
        return self.current_ewma > self.critical_latency

    def get_stats(self) -> Dict[str, Any]:
        return {
            "ewma_latency": round(self.current_ewma, 1),
            "throttle_factor": round(self.limit_scale, 2),
            "is_throttled": self.limit_scale < 1.0,
            "is_critical": self.current_ewma > self.critical_latency
        }
