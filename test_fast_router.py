
import asyncio
import logging
from datetime import datetime, date
import sys
import os

# Ensure backend is in path
sys.path.insert(0, os.path.abspath("backend"))

from database.session import init_db
from core.route_engine.fast_router import FastPathRouter # Assuming this is the next engine
from core.route_engine.constraints import RouteConstraints

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_fast_router")

async def test_fast_router_yield():
    # 0. Initialize DB
    await init_db()
    
    # 1. Setup
    travel_date = datetime(2026, 4, 2)
    source_code = "NDLS"
    dest_code = "MMCT"

    print(f"Testing FastPathRouter from {source_code} to {dest_code} on {travel_date.date()}")
    
    router = FastPathRouter()
    
    # 2. Run Search
    start = datetime.now()
    results = await router.find_routes(source_code, dest_code, travel_date, limit=20)
    end = datetime.now()
    
    print(f"Search took: {(end-start).total_seconds():.2f}s")
    print(f"Routes found: {len(results)}")
    
    for i, r in enumerate(results):
        print(f"--- Route {i+1} ---")
        print(f"  Engine: {r.metadata.get('engine')}")
        print(f"  Duration: {r.total_duration} mins")
        for j, seg in enumerate(r.segments):
            print(f"    Leg {j+1}: {seg.train_number} from {seg.departure_code} @ {seg.departure_time} -> {seg.arrival_code} @ {seg.arrival_time}")
        if r.transfers:
            for t in r.transfers:
                print(f"    Transfer at {t.station_code} for {t.duration_minutes} mins")

if __name__ == "__main__":
    asyncio.run(test_fast_router_yield())
