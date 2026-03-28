import asyncio
import sys
from pathlib import Path

# Add backend to sys.path
backend_path = Path("backend").resolve()
sys.path.append(str(backend_path))

from redis.asyncio import from_url
from database.config import Config

async def test_redis_async():
    print(f"Testing Async Redis with URL length: {len(Config.REDIS_URL)}")
    if not Config.REDIS_URL:
        print("REDIS_URL is empty!")
        return

    try:
        # Try without ssl_cert_reqs=None first (like the app)
        print("Attempt 1: Standard connection...")
        client = await from_url(Config.REDIS_URL, decode_responses=False)
        await client.ping()
        print("✅ Attempt 1: SUCCESSFUL!")
        await client.aclose()
    except Exception as e:
        print(f"❌ Attempt 1: FAILED: {type(e).__name__}: {str(e)}")
        
        try:
            # Try WITH ssl_cert_reqs=None
            print("\nAttempt 2: Connection with ssl_cert_reqs=None...")
            client = await from_url(Config.REDIS_URL, decode_responses=False, ssl_cert_reqs=None)
            await client.ping()
            print("✅ Attempt 2: SUCCESSFUL!")
            await client.aclose()
        except Exception as e2:
            print(f"❌ Attempt 2: FAILED: {type(e2).__name__}: {str(e2)}")

if __name__ == "__main__":
    asyncio.run(test_redis_async())
