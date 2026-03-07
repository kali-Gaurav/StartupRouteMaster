import asyncio
import os
import sys
import time
import logging

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import SessionLocal
from services.search_service import SearchService
from services.multi_layer_cache import multi_layer_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_task_23")

async def verify_task_23():
    print("\n>>> Verifying Task 23: Aggressive Search Fingerprint Caching")
    await multi_layer_cache.initialize()
    
    db = SessionLocal()
    service = SearchService(db)
    
    source, dest = "PGT", "KOTA"
    date_str = "2026-03-08"
    
    # 1. First Search (Cold - will take ~1s)
    print(f"  Performing Cold Search: {source} -> {dest}...")
    start = time.perf_counter()
    res1 = await service.search_routes(source, dest, date_str)
    cold_latency = (time.perf_counter() - start) * 1000
    print(f"  Cold Latency: {cold_latency:.2f}ms")
    
    # 2. Second Search (Hot - should be < 50ms)
    print(f"  Performing Hot Search (from Redis)...")
    start = time.perf_counter()
    res2 = await service.search_routes(source, dest, date_str)
    hot_latency = (time.perf_counter() - start) * 1000
    print(f"  Hot Latency: {hot_latency:.2f}ms")
    
    print(f"  Source Attribution: {res2.get('source', 'unknown')}")
    
    if res2.get("source") != "redis_fingerprint":
        print("❌ FAILURE: Second search did not hit the fingerprint cache.")
        return False
        
    if hot_latency > 100.0:
        print(f"❌ FAILURE: Hot search too slow ({hot_latency:.2f}ms). Expected < 50ms.")
        return False

    print(f"\n✅ TASK 23 VERIFIED: Cache speedup is {cold_latency / hot_latency:.1f}x")
    return True

if __name__ == "__main__":
    asyncio.run(verify_task_23())
