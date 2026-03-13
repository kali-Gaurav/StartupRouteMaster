import asyncio
import logging
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.core.metrics import TelemetryMetrics, SurgeLevel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-4.2")

async def test_surge_level_transitions():
    metrics = TelemetryMetrics()
    
    # 1. Normal State
    metrics.cpu_usage_percent = 10.0
    logger.info(f"Test 1: CPU {metrics.cpu_usage_percent}% -> Surge Level: {metrics.surge_level.name}")
    assert metrics.surge_level == SurgeLevel.NORMAL

    # 2. Transition to ELEVATED (Threshold 70%)
    metrics.cpu_usage_percent = 75.0
    logger.info(f"Test 2: CPU {metrics.cpu_usage_percent}% -> Surge Level: {metrics.surge_level.name}")
    assert metrics.surge_level == SurgeLevel.ELEVATED

    # 3. Transition to HIGH (Threshold 85%)
    metrics.cpu_usage_percent = 88.0
    logger.info(f"Test 3: CPU {metrics.cpu_usage_percent}% -> Surge Level: {metrics.surge_level.name}")
    assert metrics.surge_level == SurgeLevel.HIGH

    # 4. Hysteresis Test (Falling load)
    # Target: 88% -> 82% (Threshold for HIGH is 85%, Hysteresis buffer is 5%, so should drop below 80% to downgrade)
    metrics.cpu_usage_percent = 82.0
    logger.info(f"Test 4 (Hysteresis): CPU {metrics.cpu_usage_percent}% (Prev: HIGH) -> Surge Level: {metrics.surge_level.name}")
    assert metrics.surge_level == SurgeLevel.HIGH # Should NOT downgrade yet
    
    # 5. Drop below Hysteresis (Threshold 80%)
    metrics.cpu_usage_percent = 78.0
    logger.info(f"Test 5 (Hysteresis): CPU {metrics.cpu_usage_percent}% -> Surge Level: {metrics.surge_level.name}")
    assert metrics.surge_level == SurgeLevel.ELEVATED # Should downgrade now

    # 6. CRITICAL (Threshold 95% or Latency > 200)
    metrics.event_loop_latency_ms = 250.0
    logger.info(f"Test 6: Latency {metrics.event_loop_latency_ms}ms -> Surge Level: {metrics.surge_level.name}")
    assert metrics.surge_level == SurgeLevel.CRITICAL

    logger.info("✅ Subtask 4.2: Surge Levels & Hysteresis logic Verified.")

if __name__ == "__main__":
    asyncio.run(test_surge_level_transitions())
