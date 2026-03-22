import asyncio
import json
import logging
import time
from typing import Any, Optional, Dict, List, Tuple
from collections import deque, Counter
from core.metrics import jit_metrics

logger = logging.getLogger("cache-warmup")

class CacheWarmupOrchestrator:
    """
    Hierarchical Warmup & Adaptive Hydration Engine.
    [Subtask 3.5] Load-Aware Adaptive Warmup.
    [Subtask 6.1] Event-Driven Trending Analysis.
    """
    def __init__(self, cache_instance):
        self.cache = cache_instance
        self.miss_queue = deque(maxlen=2000)
        self._lock = asyncio.Lock()
        self._trending_task = None
        self._is_running = False
        self._batch_size = 5
        self._hydration_semaphore = asyncio.Semaphore(10) # Limit concurrent hydration

    def record_miss(self, key: str):
        """Records a cache miss event for trending analysis."""
        self.miss_queue.append((key, time.time()))
        
    def is_off_peak(self) -> bool:
        """Checks if current time is off-peak (2AM - 5AM UTC)."""
        current_hour = time.gmtime().tm_hour
        return 2 <= current_hour <= 5

    def get_load_throttle_delay(self) -> float:
        """Returns a dynamic delay based on system load to prevent starvation."""
        if jit_metrics.cpu_usage_percent > 85: return 2.0
        if jit_metrics.cpu_usage_percent > 70: return 0.5
        return 0.0

    async def trigger_warmup(self, key: str, data: Any, priority: str = "L2"):
        """
        Hierarchical Hydration Logic with Load Protection.
        """
        if jit_metrics.is_overloaded:
            logger.info(f"⏩ Critical Load: Skipping warmup for {key}")
            return

        delay = self.get_load_throttle_delay()
        if delay > 0: await asyncio.sleep(delay)

        async with self._hydration_semaphore:
            # L1 Hydration (Fast RAM)
            if priority == "L1":
                self.cache.lru.put(key, data)
            
            # L2 Hydration (Redis)
            if self.cache.redis:
                await self.cache.put(key, data)
                logger.debug(f"📦 L2 Hydrated: {key}")

    async def run_trending_analyzer(self):
        """
        Analyzes recent cache misses to identify and pre-warm trending keys.
        """
        self._is_running = True
        logger.info("📈 Cache Trending Analyzer Started.")
        
        while self._is_running:
            try:
                await asyncio.sleep(60) # Analyze every minute
                
                if jit_metrics.is_overloaded or not self.miss_queue:
                    continue

                # 1. Identify trending keys (threshold: 5 misses in 5 minutes)
                now = time.time()
                recent_misses = [k for k, t in list(self.miss_queue) if now - t < 300]
                
                if not recent_misses: continue
                
                counts = Counter(recent_misses)
                trending_keys = [k for k, c in counts.items() if c >= 5]
                
                if not trending_keys: continue

                logger.info(f"🔥 Identified {len(trending_keys)} trending keys for pre-warm.")
                
                # 2. Trigger intelligent pre-warm
                for key in trending_keys[:self._batch_size]:
                    await self._smart_prewarm(key)
                    await asyncio.sleep(0.1) # Yield to event loop

            except Exception as e:
                logger.error(f"Trending Analyzer Error: {e}")
                await asyncio.sleep(10)

    async def _smart_prewarm(self, key: str):
        """Logic to fetch fresh data for a trending key and hydrate layers."""
        # Implementation depends on key type (e.g., station_meta, popular_route)
        # For now, we log and trigger a placeholder hydration
        logger.debug(f"⚡ Smart Pre-warm triggered for {key}")
        # In a real scenario, this would call specific service loaders
        pass

    def stop(self):
        self._is_running = False
