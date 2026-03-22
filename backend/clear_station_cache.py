import asyncio
from services.cache_service import cache_service

async def clear_cache():
    if not cache_service.is_available():
        print("Redis not available.")
        return
        
    # v1:station_resolve:NDLS
    keys = cache_service.redis.keys("v1:station_resolve:*")
    print(f"Clearing {len(keys)} cached station resolution keys...")
    for key in keys:
        # Remove 'v1:' from the key before passing to delete()
        clean_key = key.replace("v1:", "")
        cache_service.delete(clean_key)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(clear_cache())
