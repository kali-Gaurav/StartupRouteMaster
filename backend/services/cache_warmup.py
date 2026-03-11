import asyncio
import json
import logging
import time
from typing import Any, Optional, Dict, List
from collections import deque

logger = logging.getLogger("cache-warmup")

class CacheWarmupOrchestrator:
    """
    Subtask 6.1 & 6.3 (FIXED): Event Sourcing & Hierarchical Warmup.
    Maps correctly to MultiLayerCache.lru for L1 operations.
    """
    def __init__(self, cache_instance):
        self.cache = cache_instance
        self.miss_queue = deque(maxlen=1000)
        self._lock = asyncio.Lock()

    def record_miss(self, key: str):
        self.miss_queue.append((key, time.time()))
        logger.debug(f"📉 Cache Miss Event: {key}")

    async def trigger_warmup(self, key: str, data: Any, priority: str = "L2"):
        """
        Hierarchical Hydration Logic.
        """
        async with self._lock:
            # Subtask 6.3: L1 Hydration using existing LRU object
            if priority == "L1":
                self.cache.lru.put(key, data)
                logger.info(f"❄️  L1 Hydrated (RAM): {key}")
            
            # Always ensure L2 (Redis) is populated if available
            await self.cache.put(key, data)
            logger.debug(f"📦 L2 Hydrated (Redis): {key}")

    async def run_trending_analyzer(self):
        while True:
            await asyncio.sleep(30)
            if not self.miss_queue: continue
            
            counts = {}
            for key, ts in list(self.miss_queue):
                counts[key] = counts.get(key, 0) + 1
            
            for key, count in counts.items():
                if count >= 3:
                    logger.info(f"📈 Trending Key: {key} ({count} misses).")
                    # (In production, this triggers background fetch)
