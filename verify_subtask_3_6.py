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
logger = logging.getLogger("verify-3.6")

async def test_swr_logic():
    cache_svc = MultiLayerCache()
    cache_svc._xfetch_beta = 100.0 # Force XFetch to trigger very aggressively
    
    key = "swr_test_key"
    val = {"test": "data_original"}
    
    # Define a refresh callback
    refresh_called = False
    async def mock_refresh():
        nonlocal refresh_called
        refresh_called = True
        logger.info("Background refresh callback executed!")

    logger.info("1. Putting item...")
    await cache_svc.put(key, val, ttl=10)
    
    # Manually fix delta because local imports bypass mocks
    envelope = cache_svc.lru.get(key)
    envelope['xf_delta'] = 10.0 
    
    # 2. Simulate Near-Expiry
    logger.info(f"2. Simulating near-expiry (xf_delta={envelope['xf_delta']})...")
    expiry = envelope['xf_expiry']
    
    with patch('time.time', return_value=expiry - 0.1): # 0.1s before expiry
        with patch('random.random', return_value=0.999): # Force XFetch trigger
            res = await cache_svc.get(key, refresh_callback=mock_refresh)
            
            # SWR Check: Should return STALE value AND trigger background task
            assert res == val
            logger.info("✅ SWR returned stale value correctly.")
            
            # Wait a tiny bit for the async task to run
            await asyncio.sleep(0.1)
            assert refresh_called is True
            logger.info("✅ SWR triggered background refresh correctly.")

    logger.info("✅ Subtask 3.6: Stale-While-Revalidate Verified.")

if __name__ == "__main__":
    asyncio.run(test_swr_logic())
