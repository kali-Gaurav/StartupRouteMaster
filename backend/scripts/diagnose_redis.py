import asyncio
import os
from dotenv import load_dotenv
import redis.asyncio as redis
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("diagnose-redis")

async def test_redis_connection(url, name):
    logger.info(f"Testing {name}: {url.split('@')[-1]}")
    try:
        r = redis.Redis.from_url(
            url,
            decode_responses=True,
            ssl_cert_reqs=None,
            socket_connect_timeout=5.0
        )
        await r.ping()
        logger.info(f"✅ Success with {name}")
        await r.close()
        return True
    except Exception as e:
        logger.error(f"❌ Failed with {name}: {e}")
        return False

async def main():
    # Load .env
    env_path = os.path.join(os.getcwd(), 'backend', '.env')
    if not os.path.exists(env_path):
        env_path = '.env'
    load_dotenv(env_path)
    
    current_url = os.getenv("REDIS_URL")
    if not current_url:
        logger.error("REDIS_URL not found in environment")
        return

    logger.info(f"Current REDIS_URL from .env: {current_url.split('@')[-1]}")
    
    # Try current
    await test_redis_connection(current_url, "Current .env URL")
    
    # Try variations
    # 1. Without 'default' username (Upstash style often :PASSWORD)
    if 'default:' in current_url:
        variation1 = current_url.replace('default:', ':')
        await test_redis_connection(variation1, "URL without 'default' username")
    
    # 2. Without username/password separator if 'default' is not used
    # 3. Check for trailing whitespace
    if current_url.strip() != current_url:
        logger.info("Current URL has trailing/leading whitespace!")
        await test_redis_connection(current_url.strip(), "Trimmed URL")

if __name__ == "__main__":
    asyncio.run(main())
