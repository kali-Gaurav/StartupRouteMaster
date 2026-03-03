import asyncio
import sys
import os
from datetime import datetime

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.search_service import SearchService
from database.session import SessionTransit, SessionUser
from services.multi_layer_cache import multi_layer_cache

async def verify():
    # 1. Initialize
    await multi_layer_cache.initialize()
    if not multi_layer_cache.redis:
        print("Redis not connected")
        return

    # Clear previous metrics for clean test
    today = datetime.utcnow().date().isoformat()
    await multi_layer_cache.redis.delete(f"metrics:engine_usage:{today}")
    await multi_layer_cache.redis.delete(f"metrics:engine_success:{today}")

    # 2. Run Search via Service
    print(f"Running search for NDLS -> BCT on {today}...")
    session = SessionTransit()
    search_svc = SearchService(session)
    
    # Use a guaranteed corridor
    result = await search_svc.search_routes("NDLS", "BCT", today)
    found_count = len(result.get('journeys', []))
    print(f"Search Finished. Found {found_count} journeys.")

    # 3. Verify Redis Metrics
    print("\nRedis Metrics Audit:")
    
    usage = await multi_layer_cache.redis.hgetall(f"metrics:engine_usage:{today}")
    success = await multi_layer_cache.redis.hgetall(f"metrics:engine_success:{today}")
    
    print(f"Engine Usage: {usage}")
    print(f"Engine Success: {success}")
    
    if usage:
        print("🎉 SUCCESS: Observability metrics correctly recorded in Redis.")
    else:
        print("❌ ERROR: Metrics missing.")

    session.close()

if __name__ == "__main__":
    asyncio.run(verify())
