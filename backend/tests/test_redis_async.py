import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import redis.asyncio as aioredis

async def test_async_redis():
    # Load .env
    env_path = Path(__file__).resolve().parent / '.env'
    load_dotenv(dotenv_path=env_path)

    redis_url = os.getenv("REDIS_URL")
    print(f"Testing Async Redis URL: {redis_url[:20]}...{redis_url[-20:]}")

    try:
        client = aioredis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None)
        pong = await client.ping()
        print(f"Async Redis Ping: {pong}")
        await client.close()
    except Exception as e:
        print(f"Async Redis Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_async_redis())
