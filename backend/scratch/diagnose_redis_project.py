
import sys
import os
import asyncio
import logging

# Add backend to path
sys.path.append(os.getcwd())

from core.redis_client import async_redis_client, URL, OPTS

async def diagnose_redis():
    print(f"Diagnosing Redis with URL: {URL.split('@')[-1]}")
    print(f"Options: {OPTS}")
    
    logging.basicConfig(level=logging.INFO)
    
    # Test Sync Client first (since it's a singleton in redis_client.py)
    from core.redis_client import redis_client
    try:
        print("Testing Sync Redis Client...")
        redis_client.ping()
        print("Sync Redis: OK")
    except Exception as e:
        print(f"Sync Redis Error: {type(e).__name__}: {e}")

    # Test Async Client
    try:
        print("\nTesting Async Redis Client...")
        res = await async_redis_client.ping()
        if res:
            print("Async Redis: OK")
        else:
            print("Async Redis: Ping failed (returned False)")
            
        # Try a direct operation
        await async_redis_client.set("diag_key", "test_val")
        val = await async_redis_client.get("diag_key")
        print(f"Async GET result: {val}")
        
    except Exception as e:
        print(f"Async Redis Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose_redis())
