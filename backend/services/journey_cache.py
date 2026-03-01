import json
import logging
from core.redis import async_redis_client # Switch to async
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Upgrade 5: In-Memory L1 Cache (5000 journeys, 15 min TTL)
_l1_journey_cache = TTLCache(maxsize=5000, ttl=900)

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
        return True
    except Exception as e:
        logger.error(f"Failed to cache journey state: {e}")
        return False

async def get_journey(journey_id: str) -> dict | None:
    """
    Retrieves a cached journey object from L1 (fastest) or L2 (Redis) asynchronously.
    """
    try:
        # 1. Check L1 Cache
        if journey_id in _l1_journey_cache:
            return _l1_journey_cache[journey_id]
            
        # 2. Check L2 Cache (Redis)
        data = await async_redis_client.get(f"journey_state:{journey_id}")
        if data:
            journey = json.loads(data)
            # Re-populate L1
            _l1_journey_cache[journey_id] = journey
            return journey
            
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve journey state: {e}")
        return None
