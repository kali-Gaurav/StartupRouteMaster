import asyncio
import logging
import time
from unittest.mock import MagicMock, AsyncMock, patch
import os
import sys

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.services.multi_layer_cache import MultiLayerCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-3.3")

async def test_xfetch_logic():
    cache_svc = MultiLayerCache()
    # Ensure L2 is bypassed for simplicity in this logic test
    cache_svc._xfetch_beta = 5.0 # Increase beta to trigger more easily
    
    key = "xfetch_test_key"
    val = {"test": "data"}
    ttl = 2 # 2 seconds TTL
    
    logger.info(f"Putting item with {ttl}s TTL...")
    await cache_svc.put(key, val, ttl=ttl)
    
    # 1. Immediate Get (Should always be HIT)
    res = await cache_svc.get(key)
    assert res == val
    logger.info("✅ Immediate hit confirmed.")

    # 2. Near Expiry Get (Trigger probabilistic miss)
    logger.info("Simulating near-expiry state...")
    
    miss_found = False
    # Mock current time to be past the point where xfetch might trigger
    future_time = time.time() + 1.9
    with patch('time.time', return_value=future_time):
        with patch('random.random', return_value=0.999): # High random forces miss
            res = await cache_svc.get(key)
            if res is None:
                miss_found = True
                logger.info("✅ XFetch Probabilistic Miss triggered successfully!")
            else:
                # Debug why no miss
                item = cache_svc.lru.get(key)
                logger.info(f"Item expiry: {item['xf_expiry']}, current mocked time: {future_time}")
                logger.info(f"Diff: {item['xf_expiry'] - future_time}")

    if not miss_found:
        logger.warning("❌ XFetch did not trigger a miss. Check beta/math logic.")
        assert False

if __name__ == "__main__":
    asyncio.run(test_xfetch_logic())
