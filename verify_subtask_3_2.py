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
logger = logging.getLogger("verify-3.2")

async def test_l2_latency_bypass():
    cache_svc = MultiLayerCache()
    cache_svc.redis = AsyncMock()
    
    # 1. Normal Latency
    logger.info("Testing Normal Latency (L2 should be enabled)...")
    cache_svc.redis.ping.return_value = True
    
    # Mock time.perf_counter to simulate fast response
    with patch('time.perf_counter', side_effect=[0, 0.01]): 
        await cache_svc._measure_l2_latency()
        
    logger.info(f"Measured Latency: {cache_svc._l2_latency_ms:.2f}ms")
    assert cache_svc._is_l2_available() is True
    logger.info("✅ Normal latency check passed.")

    # 2. High Latency (> 50ms)
    logger.info("Testing High Latency (L2 should be disabled)...")
    # Simulate 100ms latency multiple times to push the moving average
    for _ in range(10):
        with patch('time.perf_counter', side_effect=[0, 0.1]):
            await cache_svc._measure_l2_latency()
        
    logger.info(f"Final Average Latency: {cache_svc._l2_latency_ms:.2f}ms")
    assert cache_svc._is_l2_available() is False
    logger.info("✅ High latency bypass verified.")

    # 3. Verify bypass affects 'get'
    logger.info("Verifying 'get' skips Redis during bypass...")
    cache_svc.redis.get = AsyncMock()
    await cache_svc.get("some_key")
    # Should NOT have called redis.get because it's disabled
    cache_svc.redis.get.assert_not_called()
    logger.info("✅ 'get' correctly bypassed L2.")

if __name__ == "__main__":
    asyncio.run(test_l2_latency_bypass())
