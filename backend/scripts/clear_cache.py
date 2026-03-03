import asyncio
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.multi_layer_cache import multi_layer_cache

async def clear():
    await multi_layer_cache.initialize()
    if multi_layer_cache.redis:
        await multi_layer_cache.redis.flushall()
        print("Cache cleared successfully.")
    else:
        print("Redis not connected.")

if __name__ == "__main__":
    asyncio.run(clear())
