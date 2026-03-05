import sys
import os
from pathlib import Path

# Add backend to sys.path
backend_path = Path("backend").resolve()
sys.path.append(str(backend_path))

import redis
from database.config import Config

def test_redis():
    print(f"Testing Redis with URL length: {len(Config.REDIS_URL)}")
    if not Config.REDIS_URL:
        print("REDIS_URL is empty!")
        return

    try:
        client = redis.from_url(
            Config.REDIS_URL,
            decode_responses=True,
            ssl_cert_reqs=None,
            socket_timeout=5.0,
            socket_connect_timeout=5.0
        )
        client.ping()
        print("✅ Redis connection SUCCESSFUL!")
    except Exception as e:
        print(f"❌ Redis connection FAILED: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    test_redis()
