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
        self.latitude, self.longitude = 0.0, 0.0
        self.name = code

async def verify_task_12_walk():
    print("=== Verifying Task 12: Walkable Transfer Logic ===")
    
    # S1 -> S2 (Train)
    # S2 -> S3 (Walk)
    # S3 -> S4 (Train)
    
    s1, s2, s3, s4 = MockStop(1, "S1"), MockStop(2, "S2"), MockStop(3, "S3"), MockStop(4, "S4")
    # Coordinates for S2 and S3 (nearby)
    s2.latitude, s2.longitude = 12.97, 77.59
    s3.latitude, s3.longitude = 12.98, 77.60 
    
    dep_time = datetime(2026, 3, 9, 10, 0)
    arr_t_s2 = dep_time + timedelta(hours=1)
    
    # Leg 1: S1 -> S2
    seg1 = RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                        departure_time=dep_time, arrival_time=arr_t_s2,
                        duration_minutes=60, distance_km=50.0, service_mask=127)
    
    # 30 min walk buffer
    walk_dep_s3 = arr_t_s2 + timedelta(minutes=45) 
    
    # Leg 2: S3 -> S4
    seg2 = RouteSegment(trip_id=2, departure_stop_id=3, arrival_stop_id=4,
                        departure_time=walk_dep_s3, arrival_time=walk_dep_s3 + timedelta(hours=1),
                        duration_minutes=60, distance_km=50.0, service_mask=127)

    # Cross-terminal transfer S2 -> S3
    tr_walk = TransferConnection(3, arr_t_s2, walk_dep_s3, 45, "S2-S3 Walk", 5.0, 5.0)

    sti = defaultdict(lambda: [[] for _ in range(24)])
    sti[1][dep_time.hour].append((dep_time, 1))
    sti[3][walk_dep_s3.hour].append((walk_dep_s3, 2))

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={1: [(dep_time, 1)], 3: [(walk_dep_s3, 2)]},
        trip_segments={1: [seg1], 2: [seg2]},
        transfer_graph={2: [tr_walk]}, # tr_walk station_id is 3 (target)
        stop_cache={1: s1, 2: s2, 3: s3, 4: s4},
        stop_index={1: 0, 2: 1, 3: 2, 4: 3},
        station_time_index=sti
    )
    
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    graph.trip_segments = mock_snapshot.trip_segments
    graph.transfer_graph = mock_snapshot.transfer_graph
    
    raptor = OptimizedRAPTOR(max_transfers=1)
    constraints = RouteConstraints(max_results=10)

    # 2. Run Search
    print("Running Search requiring walking transfer...")
    routes = await raptor._search_single_departure(graph, 1, 4, dep_time, constraints)
    
    # 3. Verify
    print(f"Found {len(routes)} routes.")
    assert len(routes) > 0
    
    r = routes[0]
    print(f"Route Metadata: {r.metadata}")
    assert "walking_transfers" in r.metadata
    assert r.metadata["walking_transfers"][0]["from"] == 2
    assert r.metadata["walking_transfers"][0]["to"] == 3
    
    print("[OK] Walkable transfer correctly identified and flagged in metadata.")
    print("=== Task 12 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_12_walk())
