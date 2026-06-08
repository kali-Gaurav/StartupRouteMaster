import os
import sys
from pathlib import Path
import asyncio

# Add backend to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from core.infrastructure.redis_manager import async_redis_client, verify_redis_connection
import logging

logging.basicConfig(level=logging.INFO)

async def test_redis():
    print("Testing Redis Connection...")
    # Test sync connection
    sync_ok = verify_redis_connection()
    print(f"Sync Connection: {'OK' if sync_ok else 'FAILED'}")
    
    # Test async connection
    try:
        ping_ok = await async_redis_client.ping()
        print(f"Async Ping: {'OK' if ping_ok else 'FAILED'}")
    except Exception as e:
        print(f"Async Connection Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_redis())
