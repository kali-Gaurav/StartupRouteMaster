import asyncio
import os
import sys

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.redis import async_redis_client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_redis():
    logger.info("Testing Redis connection...")
    try:
        # Ping returns True on success
        pong = await async_redis_client.ping()
        if pong:
            logger.info("✓ Redis connection successful!")
            return True
        else:
            logger.error("✗ Redis ping failed (returned False).")
            return False
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        return False
    finally:
        await async_redis_client.close()

if __name__ == "__main__":
    success = asyncio.run(test_redis())
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
