import json
import logging
from core.redis_client import async_redis_client # Switch to async
from cachetools import TTLCache
from datetime import datetime
from collections import deque
import asyncio

logger = logging.getLogger(__name__)

# Upgrade 5: In-Memory L1 Cache (5000 journeys, 15 min TTL)
_l1_journey_cache = TTLCache(maxsize=5000, ttl=900)

class JourneyCacheMetrics:
    """Metrics tracking for journey cache service."""
    
    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
    
    async def record_access(self, operation: str, success: bool, hit: bool = False):
        """Record cache access metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": operation,
                "success": success,
                "cache_hit": hit
            })
    
    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0, "cache_hits": 0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        cache_hits = sum(1 for m in self._metrics if m.get("cache_hit", False))
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "cache_hits": cache_hits,
            "cache_hit_rate": cache_hits / total if total > 0 else 0.0,
            "l1_cache_size": len(_l1_journey_cache)
        }

# Global metrics instance
_journey_cache_metrics = JourneyCacheMetrics()

async def save_journey(journey_id: str, journey_data: dict, ttl: int = 900) -> bool:
    """
    Saves a full journey object to L1 (RAM) and L2 (Redis) asynchronously.
    """
    try:
        # Save to RAM (Synchronous but near-instant)
        _l1_journey_cache[journey_id] = journey_data
        
        # Save to Redis (Asynchronous)
        await async_redis_client.setex(
            f"journey_state:{journey_id}",
            ttl,
            json.dumps(journey_data)
        )
        
        await _journey_cache_metrics.record_access("save", True)
        return True
    except Exception as e:
        logger.error(f"Failed to cache journey state: {e}")
        await _journey_cache_metrics.record_access("save", False)
        return False

async def get_journey(journey_id: str) -> dict | None:
    """
    Retrieves a cached journey object from L1 (fastest) or L2 (Redis) asynchronously.
    """
    try:
        # 1. Check L1 Cache
        if journey_id in _l1_journey_cache:
            await _journey_cache_metrics.record_access("get", True, hit=True)
            return _l1_journey_cache[journey_id]
            
        # 2. Check L2 Cache (Redis)
        data = await async_redis_client.get(f"journey_state:{journey_id}")
        if data:
            journey = json.loads(data)
            # Re-populate L1
            _l1_journey_cache[journey_id] = journey
            await _journey_cache_metrics.record_access("get", True, hit=True)
            return journey
            
        await _journey_cache_metrics.record_access("get", True, hit=False)
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve journey state: {e}")
        await _journey_cache_metrics.record_access("get", False)
        return None

def get_cache_metrics() -> dict:
    """Get journey cache metrics."""
    return _journey_cache_metrics.get_metrics()

def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "l1_cache_size": len(_l1_journey_cache),
        "metrics": _journey_cache_metrics.get_metrics()
    }
