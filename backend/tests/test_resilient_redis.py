import asyncio
import logging
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parent))

from core.redis_client import async_redis_client, verify_redis_connection

async def test_resilient_redis():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("test.redis")
    
    logger.info("Starting Resilient Redis Test...")
    
    # Test 1: Sync Verification
    sync_ok = verify_redis_connection()
    logger.info(f"Sync Verification: {sync_ok}")
    
    # Test 2: Async Ping
    ping_ok = await async_redis_client.ping()
    logger.info(f"Async Ping: {ping_ok}")
    
    # Test 3: Set/Get
    test_key = "nexus:test:resiliency"
    await async_redis_client.setex(test_key, 60, "ACTIVE")
    val = await async_redis_client.get(test_key)
    logger.info(f"Async Get (Expected: ACTIVE): {val}")
    
    if val == "ACTIVE":
        logger.info("✅ Resilient Redis Test PASSED.")
    else:
        logger.error("❌ Resilient Redis Test FAILED.")

if __name__ == "__main__":
    asyncio.run(test_resilient_redis())
