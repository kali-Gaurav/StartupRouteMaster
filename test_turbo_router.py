
import asyncio
import logging
from datetime import datetime, date
import sys
import os

# Ensure backend is in path
sys.path.insert(0, os.path.abspath("backend"))

from database.session import init_db
from core.route_engine.turbo_router import TurboRouter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_turbo")

async def test_turbo_direct_yield():
    # 0. Initialize DB
    await init_db()
    
    # 1. Setup
    travel_date = datetime(2026, 4, 2)
    source_code = "NDLS"
    dest_code = "MMCT"

    print(f"Testing TurboRouter (Direct) from {source_code} to {dest_code} on {travel_date.date()}")
    
    router = TurboRouter()
    
    # 2. Run Search
    start = datetime.now()
    results = await router.find_routes(source_code, dest_code, travel_date, limit=20)
    end = datetime.now()
    
    print(f"Search took: {(end-start).total_seconds():.2f}s")
    print(f"Routes found: {len(results)}")
    
    for i, r in enumerate(results):
        print(f"--- Route {i+1} ---") # Fixed newline character here
        print(f"  Type: {r.get('type')}, Phase: {r.get('phase_found')}")
        print(f"  Duration: {r.get('duration')} mins")
        print(f"  Legs: {len(r.get('legs', []))}")
        # Note: TurboRouter returns dicts, not Route objects, need to adjust print
        if r.get('type') == 'direct':
            print(f"    Train: {r['train_no']} from {source_code} @ {r['dep']} -> {dest_code} @ {r['arr']}")

if __name__ == "__main__":
    asyncio.run(test_turbo_direct_yield())
