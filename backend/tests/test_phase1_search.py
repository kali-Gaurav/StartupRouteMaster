import asyncio
from datetime import datetime
from backend.core.route_engine.engine import RailwayRouteEngine

async def test_search_ndls_mmct():
    engine = RailwayRouteEngine()
    # Search for NDLS to MMCT on 2026-03-15
    search_date = datetime(2026, 3, 15, 16, 55)
    # ensure previous static graph snapshot doesn't interfere
    import os
    snapshot_path = os.path.join(os.getcwd(), 'snapshots', f'graph_snapshot_{search_date.strftime("%Y%m%d")}.pkl')
    print(f"Deleting snapshot at {snapshot_path} if exists")
    if os.path.exists(snapshot_path):
        try:
            os.remove(snapshot_path)
            print("Snapshot removed")
        except Exception as e:
            print(f"Failed to remove snapshot: {e}")
    print(f"Exists after deletion? {os.path.exists(snapshot_path)}")

    print(f"\n🔍 Searching for NDLS -> MMCT on {search_date}...")
    routes = await engine.search_routes("NDLS", "MMCT", search_date)
    
    print(f"Found {len(routes)} routes.")
    for i, route in enumerate(routes):
        print(f"Route {i+1}:")
        print(f"  Segments: {len(route.segments)}")
        print(f"  Duration: {route.total_duration} mins")
        print(f"  Cost: {route.total_cost}")
        print(f"  Reliability: {route.reliability}")
        for seg in route.segments:
            print(f"  - Train {seg.train_number} ({seg.departure_stop_id} -> {seg.arrival_stop_id})")
            print(f"    Departure: {seg.departure_time}, Arrival: {seg.arrival_time}")
            print(f"    Duration: {seg.duration_minutes} mins")
    
    if len(routes) > 0:
        print("\n✅ Search successful!")
    else:
        print("\n❌ Search failed: No routes found.")

if __name__ == "__main__":
    asyncio.run(test_search_ndls_mmct())
