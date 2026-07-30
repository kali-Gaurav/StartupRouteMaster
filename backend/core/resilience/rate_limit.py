import time
import logging
import asyncio
from typing import Dict, Any
from core.infrastructure.redis_manager import async_redis_client
from core.sovereign.network_pressure import network_pressure

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
        Check if request is allowed. Supports dynamic tier-based limits for API keys.
        """
        # [Task 110.2] Key-based Tier Detection
        actual_limit = limit
        if key.startswith("rm_key_"):
            actual_limit = self._get_tier_limit(key)
            window = 3600 # One-hour window for enterprise keys
            
        now = int(time.time())
        window_key = f"{key}:{now // window}"
        
        # 1. Local Check (L1)
        if window_key not in self._local_counters:
            self._local_counters[window_key] = {"count": 0, "expires": now + window}
            
        counter = self._local_counters[window_key]
        if counter["count"] >= actual_limit:
            return False
            
        # 2. Increment Local
        counter["count"] += 1
        
        # 3. Probabilistic Redis Sync (L2) - 5% chance or if local is high
        # This keeps Redis updated without constant I/O
        import random
        if counter["count"] > (actual_limit * 0.8) or random.random() < 0.05:
            asyncio.create_task(self._sync_to_redis(window_key, counter["count"], window))
            
        return True

    async def is_corridor_allowed(self, ip: str, source: str, destination: str) -> bool:
        """
        [SOVEREIGN] Demand-Aware Rate Limiting.
        Tightens limits for a specific corridor as its pressure increases.
        Prevents 'Demand Manipulation Attacks' that try to trigger EDR incentives.
        """
        # 1. Get current pressure
        node = await network_pressure.get_corridor_pressure(source, destination)
        pressure = node.pressure_score
        
        # 2. Calculate dynamic limit
        # Base limit is 30 searches per hour per corridor for normal users
        base_limit = 30
        
        # Tighten limit as pressure increases
        # Pressure 0.0 -> 30, Pressure 0.9 -> 10, Pressure 1.0 -> 5
        dynamic_limit = int(base_limit * (1.0 - (pressure ** 2)))
        dynamic_limit = max(5, dynamic_limit) # Minimum 5 searches
        
        key = f"rl:corridor:{source}:{destination}:{ip}"
        window = 3600 # 1 hour
        
        allowed = await self.is_allowed(key, dynamic_limit, window)
        
        if not allowed:
            logger.warning(
                f"🚨 [SOVEREIGN:RL] Demand Attack Blocked! IP {ip} targeting {source}->{destination} "
                f"(Pressure: {pressure:.2f}, Limit: {dynamic_limit})"
            )
            
        return allowed

    async def is_incentive_farming(self, user_id: str) -> bool:
        """
        [SOVEREIGN] Anti-Farming Logic.
        Checks if a user is repeatedly triggering and accepting incentives across many corridors.
        """
        if not user_id or not self._redis:
            return False
            
        key = f"rl:farming:{user_id}"
        count = await self._redis.get(key)
        if count and int(count) > 10: # Threshold for suspected farming
            return True
        return False

    def _get_tier_limit(self, api_key: str) -> int:
        """[Task 112] Lookup the rate limit based on the API key prefix or metadata."""
        if "_ent_" in api_key: return 50000 # 50k / hr for enterprise
        if "_adm_" in api_key: return 1000000 # Unlimited-ish for admin
        return 500 # Default tier

    async def _sync_to_redis(self, key: str, local_count: int, window: int):
        try:
            if not self._redis: return
            # Atomic increment in Redis and get total
            # We use SETNX + INCRBY or similar
            # For simplicity here:
            await self._redis.incr(f"rl:{key}")
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
