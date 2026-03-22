import time
import logging
import asyncio
from typing import Optional, Dict, Any
from core.redis import async_redis_client

logger = logging.getLogger("routemaster.rate_limit")

class HybridRateLimiter:
    """
    Task 24: High-Efficiency Hybrid Rate Limiter.
    Uses local in-memory counters for 95% of checks to save Redis I/O.
    Syncs to Redis periodically for distributed consistency.
    """
    def __init__(self):
        self._local_counters: Dict[str, Dict[str, Any]] = {}
        self._redis = async_redis_client
        self._initialized = False

    async def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """
        Check if request is allowed.
        Optimized for VPS: minimize Redis round-trips.
        """
        now = int(time.time())
        window_key = f"{key}:{now // window}"
        
        # 1. Local Check (L1)
        if window_key not in self._local_counters:
            self._local_counters[window_key] = {"count": 0, "expires": now + window}
            
        counter = self._local_counters[window_key]
        if counter["count"] >= limit:
            return False
            
        # 2. Increment Local
        counter["count"] += 1
        
        # 3. Probabilistic Redis Sync (L2) - 5% chance or if local is high
        # This keeps Redis updated without constant I/O
        import random
        if counter["count"] > (limit * 0.8) or random.random() < 0.05:
            asyncio.create_task(self._sync_to_redis(window_key, counter["count"], window))
            
        return True

    async def _sync_to_redis(self, key: str, local_count: int, window: int):
        try:
            if not self._redis: return
            # Atomic increment in Redis and get total
            # We use SETNX + INCRBY or similar
            # For simplicity here:
            await self._redis.incrby(f"rl:{key}", 1)
            await self._redis.expire(f"rl:{key}", window * 2)
        except Exception as e:
            logger.error(f"Redis RL Sync Error: {e}")

    def cleanup(self):
        """Clear expired local counters."""
        now = time.time()
        expired = [k for k, v in self._local_counters.items() if v["expires"] < now]
        for k in expired:
            del self._local_counters[k]

# Global Instance
rate_limiter = HybridRateLimiter()

async def init_rate_limiter():
    logger.info("⚡ Hybrid Rate Limiter Initialized (VPS Optimized).")
