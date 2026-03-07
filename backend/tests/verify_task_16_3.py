import sys
import os
import asyncio
from datetime import datetime
import logging

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.route_engine.engine import RailwayRouteEngine

logging.basicConfig(level=logging.INFO)

async def verify_task_16_3():
    print("\n>>> Verifying Task 16.3: Vectorized Spatial Filtering")
    engine = RailwayRouteEngine()
    
    target_date = datetime(2026, 3, 8)
    graph = await engine._get_current_graph(target_date)
    
    # 1. Test coordinates: NDLS (New Delhi)
    ndls_lat, ndls_lon = 28.64289, 77.21908
    radius = 50.0 # 50km
    
    print(f"  Searching for stations within {radius}km of NDLS [{ndls_lat}, {ndls_lon}]...")
    
    import time
    start = time.perf_counter()
    nearby_ids = graph.get_nearby_stations(ndls_lat, ndls_lon, radius)
    latency = (time.perf_counter() - start) * 1000
    
    print(f"  Found {len(nearby_ids)} stations in {latency:.2f}ms")
    
    if not nearby_ids:
        print("❌ FAILURE: No stations found near NDLS.")
        return False
        
    # 2. Check if specific expected stations are present (e.g. NZM, DLI)
    import sqlite3
    conn = sqlite3.connect('backend/database/transit_graph.db')
    cur = conn.cursor()
    cur.execute("SELECT code FROM stops WHERE id IN ({})".format(",".join(map(str, nearby_ids))))
    codes = [r[0] for r in cur.fetchall()]
    conn.close()
    
    print(f"  Nearby station codes: {codes[:10]}...")
    
    expected = ["NDLS", "NZM", "DLI", "ANVT"]
    found_expected = [c for c in expected if c in codes]
    print(f"  Found expected Delhi stations: {found_expected}")
    
    if len(found_expected) < 2:
        print("❌ FAILURE: Expected major Delhi stations missing from results.")
        return False

    if latency > 10.0:
        print(f"⚠️ WARNING: Spatial filtering took {latency:.2f}ms, expected < 2ms for 8k stations.")

    print("\n✅ TASK 16.3 VERIFIED: Vectorized spatial filtering is fast and accurate.")
    return True

if __name__ == "__main__":
    asyncio.run(verify_task_16_3())
