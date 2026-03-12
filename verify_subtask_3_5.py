import asyncio
import logging
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.services.multi_layer_cache import MultiLayerCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-3.5")

async def test_load_aware_warmup():
    cache_svc = MultiLayerCache()
    warmup = cache_svc.warmup
    
    # 1. Test System Busy Scenario
    logger.info("Testing System Busy Scenario (Should skip warmup)...")
    mock_metrics = MagicMock()
    mock_metrics.cpu_usage_percent = 95.0
    mock_metrics.event_loop_latency_ms = 10.0
    
    with patch('backend.services.cache_warmup.jit_metrics', mock_metrics):
        # Trigger a warmup
        await warmup.trigger_warmup("test_busy_key", {"data": 1})
        res = await cache_svc.get("test_busy_key")
        assert res is None
        logger.info("✅ Warmup correctly skipped during high load.")

    # 2. Test System Idle Scenario
    logger.info("Testing System Idle Scenario (Should proceed)...")
    mock_metrics.cpu_usage_percent = 10.0
    mock_metrics.event_loop_latency_ms = 1.0
    
    with patch('backend.services.cache_warmup.jit_metrics', mock_metrics):
        await warmup.trigger_warmup("test_idle_key", {"data": 2})
        res = await cache_svc.get("test_idle_key")
        assert res == {"data": 2}
        logger.info("✅ Warmup correctly proceeded during low load.")

    logger.info("✅ Subtask 3.5: Load-Aware Warmup Verified.")

if __name__ == "__main__":
    asyncio.run(test_load_aware_warmup())
