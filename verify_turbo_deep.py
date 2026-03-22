
import asyncio
import logging
import time
from datetime import datetime
import sys
import os

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("turbo-deep-audit")

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.turbo_router import TurboRouter
from database.session import SessionTransit

async def audit_turbo_deep():
    print("--- TURBO ENGINE DEEP AUDIT ---")
    
    # 1. Initialize DB
    await container.get('db')
    await container.get('search') # To init overlay
    
    db = SessionTransit()
    router = TurboRouter()
    
    # Test Case 1: NDLS -> MMCT (Long Haul)
    # Expected: Direct trains like 12952 should be found.
    # Check: Duration calculation for trains arriving next day.
    
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    
    print("\n>>> Case 1: NDLS -> MMCT (Long Haul)")
    start_ts = time.perf_counter()
    routes = router.find_routes("NDLS", "MMCT", departure_date, limit=20)
    latency = (time.perf_counter() - start_ts) * 1000
    
    print(f"Yield: {len(routes)} routes in {latency:.2f}ms")
    for i, r in enumerate(routes[:3]):
        if r['type'] == 'direct':
            print(f"  [{i}] Direct Train {r['train_no']}: {r['dep']} -> {r['arr']} (Dur: {r['duration']}m, Dist: {r['distance']}km)")
        else:
            print(f"  [{i}] 1-T Hub {r['hub']}: {r['legs'][0]['train']} -> {r['legs'][1]['train']} (Dur: {r.get('duration')}m)")

    # Test Case 2: MS -> MAS (Ultra Short terminal cluster)
    print("\n>>> Case 2: MS -> MAS (Metropolitan Cluster)")
    start_ts = time.perf_counter()
    routes = router.find_routes("MS", "MAS", departure_date, limit=20)
    latency = (time.perf_counter() - start_ts) * 1000
    print(f"Yield: {len(routes)} routes in {latency:.2f}ms")
    # We expect high yield here due to cluster expansion
    
    # Test Case 3: BPL -> RKMP (Very Short)
    print("\n>>> Case 3: BPL -> RKMP")
    start_ts = time.perf_counter()
    routes = router.find_routes("BPL", "RKMP", departure_date, limit=20)
    print(f"Yield: {len(routes)} routes in {(time.perf_counter() - start_ts)*1000:.2f}ms")

    db.close()
    await container.shutdown_all()

if __name__ == "__main__":
    asyncio.run(audit_turbo_deep())
