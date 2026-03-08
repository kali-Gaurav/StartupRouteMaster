import asyncio
import sys
import os
import time
from datetime import datetime

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.geo_utils import station_geo_index
from database.session import SessionTransit

async def verify_task_7():
    print("\n>>> STARTING VERIFICATION: MVP TASK 7 (GEO-SPATIAL UPGRADES)")
    
    db = SessionTransit()
    
    # 1. Initialize Index
    print("  Initializing StationGeoIndex from Transit DB...")
    start_init = time.perf_counter()
    station_geo_index.initialize(db)
    init_duration = (time.perf_counter() - start_init) * 1000
    print(f"    Loaded {len(station_geo_index.station_codes)} stations in {init_duration:.2f}ms")
    
    assert len(station_geo_index.station_codes) > 5000
    
    # 2. Sub-ms Proximity Search Benchmark (Subtask 7.3 & 7.10)
    print("\n[7.3] Benchmarking Proximity Search near NDLS...")
    # NDLS Coords: 28.6422, 77.2187
    lat, lon = 28.6422, 77.2187
    
    # Warmup
    station_geo_index.find_nearby_stations(lat, lon, 20.0)
    
    search_times = []
    for _ in range(100):
        s_start = time.perf_counter()
        results = station_geo_index.find_nearby_stations(lat, lon, 20.0)
        search_times.append((time.perf_counter() - s_start) * 1000)
    
    avg_search = sum(search_times) / len(search_times)
    print(f"    Average Search Time (8k stations): {avg_search:.4f}ms")
    
    assert avg_search < 5.0 # Should be MUCH less than 5ms
    print("    SUCCESS: Sub-5ms proximity search proven.")
    
    # 3. Precision Check
    print("\n[7.7] Checking Precision and Sorting...")
    print(f"    Nearby Stations found: {len(results)}")
    
    top_result = results[0]
    print(f"    Closest: {top_result['code']} at {top_result['distance']:.4f}km")
    
    assert top_result['code'] == 'NDLS'
    assert top_result['distance'] < 0.1 # Should be virtually 0
    
    # 4. Filter Check
    # Find stations within 50km
    results_50 = station_geo_index.find_nearby_stations(lat, lon, 50.0)
    print(f"    Stations within 50km: {len(results_50)}")
    assert len(results_50) > 10
    
    # Check that all are within 50km
    for r in results_50:
        assert r['distance'] <= 50.0

    print("\n✅ ALL MVP TASK 7 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_7())
