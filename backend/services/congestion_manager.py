import asyncio
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class CongestionManager:
    """
    [Task 139] Tracks search volume and crowd trends for trips.
    Uses Redis to store dynamic 'Congestion Ranks'.
    """
    PREFIX = "nexus:congestion:v1:"

    async def _get_redis(self):
        try:
            from services.multi_layer_cache import multi_layer_cache
            return multi_layer_cache.redis
        except: return None

    async def increment_surge(self, trip_ids: List[int]):
        """Increment search counters for the given trips (Search-Aware Surge)."""
        r = await self._get_redis()
        if not r: return
        
        try:
            # Avoid hammering Redis for every tiny background search
            if not trip_ids: return
            
            async with r.pipeline(transaction=False) as pipe:
                for tid in trip_ids:
                    # Surge counts expire after 2 hours
                    key = f"{self.PREFIX}{tid}"
                    await pipe.incr(key)
                    await pipe.expire(key, 7200) 
                await pipe.execute()
        except Exception as e:
            logger.debug(f"Congestion Surge Update Failed: {e}")

    async def get_congestion_ranks(self, trip_ids: List[int]) -> Dict[int, float]:
        """Fetch normalized congestion ranks (0.0=Empty, 1.0=Popular, 2.0=Extreme)."""
        r = await self._get_redis()
        if not r or not trip_ids: 
            return {tid: 0.0 for tid in trip_ids}
            
        try:
            keys = [f"{self.PREFIX}{tid}" for tid in trip_ids]
            counts = await r.mget(keys)
            
            ranks = {}
            for i, tid in enumerate(trip_ids):
                count_str = counts[i]
                count = int(count_str) if count_str else 0
                
                # Normalization Heuristic:
                # - 0 to 10 searches/hr: Quiet (0.0 to 0.2)
                # - 50 searches/hr: Popular (1.0)
                # - 100+ searches/hr: Overcrowded (2.0)
                rank = min(2.0, count / 50.0) 
                ranks[tid] = round(rank, 2)
            return ranks
        except Exception as e:
            logger.debug(f"Congestion Rank Fetch Failed: {e}")
            return {tid: 0.0 for tid in trip_ids}

congestion_manager = CongestionManager()
