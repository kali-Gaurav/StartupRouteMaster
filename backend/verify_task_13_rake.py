import sys
import os
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.data_structures import RouteSegment, TransferConnection, Route
from core.route_engine.constraints import RouteConstraints
from core.route_engine.graph import TimeDependentGraph, StaticGraphSnapshot

class MockStop:
    def __init__(self, id, code):
        self.id = id
        self.code = code
        self.latitude = 0.0
        self.longitude = 0.0
        self.name = code

async def verify_task_13_rake():
    print("=== Verifying Task 13: Rake Linkage Awareness ===")
    
    # 1. Setup Mock Graph with a Rake Linkage
    # Trip 1001: S1 -> S50
    # Trip 1002: S50 -> S3
    # Linkage: (1001, 1002, 50) is SAME RAKE
    
    s1 = MockStop(1, "S1")
    s50 = MockStop(50, "S50")
    s3 = MockStop(3, "S3")

    dep_time = datetime(2026, 3, 9, 10, 0)
    arr_t_leg1 = dep_time + timedelta(hours=2)
    # Standard transfer needs 30m buffer (arr + 30m = 12:30)
    # We will mock departure at 12:05 (Only 5m buffer) -> should only work if Rake Linkage detected
    rake_dep_t = dep_time + timedelta(hours=2, minutes=5) 
    
    seg1 = RouteSegment(trip_id=1001, departure_stop_id=1, arrival_stop_id=50, 
                        departure_time=dep_time, arrival_time=arr_t_leg1,
                        duration_minutes=120, distance_km=100.0, service_mask=127)
    
    seg2 = RouteSegment(trip_id=1002, departure_stop_id=50, arrival_stop_id=3,
                        departure_time=rake_dep_t, arrival_time=rake_dep_t + timedelta(hours=2),
                        duration_minutes=120, distance_km=100.0, service_mask=127)

    sti = defaultdict(lambda: [[] for _ in range(24)])
    sti[1][dep_time.hour].append((dep_time, 1001))
    sti[50][rake_dep_t.hour].append((rake_dep_t, 1002))

    # Transfer at S50
    tr = TransferConnection(50, arr_t_leg1, rake_dep_t, 5, "S50", 5.0, 5.0)

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={
            1: [(dep_time, 1001)],
            50: [(rake_dep_t, 1002)]
        },
        trip_segments={1001: [seg1], 1002: [seg2]},
        transfer_graph={50: [tr]},
        stop_cache={1: s1, 50: s50, 3: s3},
        stop_index={1: 0, 50: 1, 3: 2},
        station_time_index=sti
    )
    
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    graph.trip_segments = mock_snapshot.trip_segments
    graph.stop_cache = mock_snapshot.stop_cache
    graph.transfer_graph = mock_snapshot.transfer_graph
    
    raptor = OptimizedRAPTOR(max_transfers=1)
    constraints = RouteConstraints(max_results=10)

    # 2. Run Search
    print("Running Search with 5-minute transfer window...")
    # Standard RAPTOR with 30m min buffer would fail this.
    # Our updated logic should allow it because rl_manager.is_same_rake returns True for (1001, 1002, 50).
    routes = await raptor._search_single_departure(graph, 1, 3, dep_time, constraints)
    
    # 3. Verify
    print(f"Found {len(routes)} routes.")
    # In my current implementation of _process_route_transfers, I still check graph.get_transfers_from_stop
    # which enforces strict_min. To make Task 13 truly work, I need to either:
    # a) Modify get_transfers_from_stop to allow rake-links OR
    # b) Update tr.duration_minutes dynamically.
    
    # Let's see if it found it.
    assert len(routes) > 0, "Rake linkage was not prioritized/allowed!"
    print("[OK] Rake linkage correctly allowed an 'impossible' 5-minute transfer.")
    print("=== Task 13 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_13_rake())
