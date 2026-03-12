import asyncio
import json
import logging
import time
from typing import Any, Optional, Dict, List
from collections import deque
from core.metrics import jit_metrics

logger = logging.getLogger("cache-warmup")

class CacheWarmupOrchestrator:
    """
    Subtask 6.1 & 6.3 (FIXED): Event Sourcing & Hierarchical Warmup.
    [Subtask 3.5] Load-Aware Adaptive Warmup.
    """
    def __init__(self, cache_instance):
        self.cache = cache_instance
        self.miss_queue = deque(maxlen=1000)
        self._lock = asyncio.Lock()

    def record_miss(self, key: str):
        self.miss_queue.append((key, time.time()))
        logger.debug(f"📉 Cache Miss Event: {key}")

    def is_off_peak(self) -> bool:
        """Checks if current time is 2AM - 5AM UTC."""
        current_hour = time.gmtime().tm_hour
        return 2 <= current_hour <= 5

    def is_system_busy(self) -> bool:
        """Checks if VPS is currently under high load."""
        return jit_metrics.cpu_usage_percent > 70 or jit_metrics.event_loop_latency_ms > 50

    async def trigger_warmup(self, key: str, data: Any, priority: str = "L2"):
        """
        Hierarchical Hydration Logic with Load Protection.
        """
        if self.is_system_busy():
            logger.info(f"⏩ Skipping warmup for {key} due to high system load.")
            return

        async with self._lock:
            # Subtask 6.3: L1 Hydration using existing LRU object
            if priority == "L1":
                self.cache.lru.put(key, data)
                logger.info(f"❄️  L1 Hydrated (RAM): {key}")
            
            # Always ensure L2 (Redis) is populated if available
            await self.cache.put(key, data)
            logger.debug(f"📦 L2 Hydrated (Redis): {key}")

    async def run_trending_analyzer(self):
        """
        Analyzes cache misses to identify trending keys.
        [Subtask 3.5] Respects system load before analyzing.
        """
        while True:
            await asyncio.sleep(30)
            if self.is_system_busy():
                continue

            if not self.miss_queue: continue
            
            counts = {}
            for key, ts in list(self.miss_queue):
                counts[key] = counts.get(key, 0) + 1
            
            for key, count in counts.items():
                if count >= 3:
                    logger.info(f"📈 Trending Key identified: {key} ({count} misses).")
                    # In production, this would trigger background pre-warm
