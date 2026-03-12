import asyncio
import logging
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.multi_layer_cache import MultiLayerCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-3.1")

async def test_dynamic_l1_capacity():
    cache_svc = MultiLayerCache()
    
    # 1. Test Low RAM Scenario (< 200MB)
    logger.info("Testing Low RAM Scenario (Limit should be 500)...")
    mock_mem = MagicMock()
    mock_mem.available = 100 * 1024 * 1024 # 100MB
    
    with patch('psutil.virtual_memory', return_value=mock_mem):
        # Fill cache with 1000 items
        for i in range(1000):
            await cache_svc.put(f"low_key_{i}", {"data": i})
        
        lru_size = len(cache_svc.lru.cache)
        logger.info(f"L1 Size under Low RAM: {lru_size}")
        assert lru_size == 500
        logger.info("✅ Low RAM limit verified.")

    cache_svc.lru.clear()

    # 2. Test High RAM Scenario (> 1GB)
    logger.info("Testing High RAM Scenario (Limit should be 5000)...")
    mock_mem.available = 2048 * 1024 * 1024 # 2GB
    
    with patch('psutil.virtual_memory', return_value=mock_mem):
        # Fill cache with 6000 items
        for i in range(6000):
            await cache_svc.put(f"high_key_{i}", {"data": i})
        
        lru_size = len(cache_svc.lru.cache)
        logger.info(f"L1 Size under High RAM: {lru_size}")
        assert lru_size == 5000
        logger.info("✅ High RAM limit verified.")

    logger.info("✅ Subtask 3.1: Dynamic L1 Capping Verified.")

if __name__ == "__main__":
    asyncio.run(test_dynamic_l1_capacity())
