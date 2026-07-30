import time
import asyncio
import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger("routemaster.middleware.control")

class TokenBucket:
    """Task 3.2: Thread-safe, weighted Token Bucket algorithm."""
    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = asyncio.Lock()

    async def consume(self, tokens: float = 1.0) -> bool:
        async with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def _refill(self):
        now = time.time()
        delta = now - self.last_refill
        new_tokens = delta * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now

    def adjust(self, capacity: float, refill_rate: float):
        """Task 3.5: Dynamic adjustment of bucket parameters."""
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = min(self.tokens, capacity)

class TrafficPredictor:
    """Task 3.4: Simple ML-lite Prediction using EWMA."""
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.current_count = 0
        self.predicted_load = 0.0
        self.surge_mode = False
        self.window_start = time.time()
        self.history = []

    def report_request(self):
        self.current_count += 1

    def step(self):
        """Should be called every 10-60 seconds to update prediction."""
        now = time.time()
        duration = now - self.window_start
        if duration < 1.0: return
        
        rps = self.current_count / duration
        
        # EWMA update: Load = alpha * new + (1-alpha) * old
        if self.predicted_load == 0:
            self.predicted_load = rps
        else:
            self.predicted_load = (self.alpha * rps) + ((1 - self.alpha) * self.predicted_load)
            
        # Surge Detection (> 50% above prediction)
        self.surge_mode = rps > (self.predicted_load * 1.5) and rps > 5.0
        
        # Reset window
        self.current_count = 0
        self.window_start = now
        
        return self.predicted_load, self.surge_mode

# Global Instance Proxy [Task 3.9]
_middleware_instance: Optional[Any] = None

def register_middleware(instance: Any):
    global _middleware_instance
    _middleware_instance = instance
    logger.info("🔗 Adaptive Control: Middleware instance registered.")

class ControlLoop:
    """Task 3.9: Real-time feedback loop between metrics and control."""
    def __init__(self):
        self.predictor = TrafficPredictor()
        self.is_running = False

    async def run(self):
        self.is_running = True
        logger.info("📡 Adaptive Load Control: Feedback Loop Started.")
        while self.is_running:
            try:
                if not _middleware_instance:
                    await asyncio.sleep(5)
                    continue

                # 1. Update Prediction
                load, is_surge = self.predictor.step() or (0, False)
                
                # 2. Get System Health
                from core.infrastructure.system_monitor import system_monitor, SystemState
                state = system_monitor.current_state
                
                # 3. Adjust Buckets [Task 3.5 & 3.10]
                # Default Base: 100 RPS capacity, 50 RPS refill
                base_cap = 200.0
                base_rate = 100.0
                
                if state == SystemState.CRITICAL:
                    base_cap *= 0.3
                    base_rate *= 0.3
                elif state == SystemState.WARNING or is_surge:
                    base_cap *= 0.6
                    base_rate *= 0.6
                
                _middleware_instance.bucket.adjust(base_cap, base_rate)
                
                if is_surge:
                    logger.warning(f"⚡ SURGE DETECTED: Next Load Predicted: {load:.2f} RPS. Throttling applied.")
                
                await asyncio.sleep(10) # 10s decision cycle
            except Exception as e:
                logger.error(f"Control Loop Error: {e}")
                await asyncio.sleep(60)

traffic_control = ControlLoop()
