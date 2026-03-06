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

async def verify_task_5_split():
    print("=== Verifying Task 5: Split-Class Routing ===")
    
    # 1. Setup Mock Graph
    # Leg 1: S1 -> S2 (Class: CC, Fare: 400)
    # Leg 2: S2 -> S3 (Class: 3A, Fare: 800)
    # Total should be 1200
    
    s1, s2, s3 = MockStop(1, "S1"), MockStop(2, "S2"), MockStop(3, "S3")
    dep_time = datetime(2026, 3, 9, 10, 0)
    
    seg1 = RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                        departure_time=dep_time, arrival_time=dep_time + timedelta(hours=4),
                        duration_minutes=240, distance_km=200.0, service_mask=127,
                        fare=400.0, train_name="Day Shatabdi")
    
    next_dep = dep_time + timedelta(hours=5)
    seg2 = RouteSegment(trip_id=2, departure_stop_id=2, arrival_stop_id=3,
                        departure_time=next_dep, arrival_time=next_dep + timedelta(hours=10),
                        duration_minutes=600, distance_km=600.0, service_mask=127,
                        fare=800.0, train_name="Overnight Exp")

    tr = TransferConnection(2, dep_time + timedelta(hours=4), next_dep, 60, "S2", 5.0, 5.0)

    sti = defaultdict(lambda: [[] for _ in range(24)])
    sti[1][dep_time.hour].append((dep_time, 1))
    sti[2][next_dep.hour].append((next_dep, 2))

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={1: [(dep_time, 1)], 2: [(next_dep, 2)]},
        trip_segments={1: [seg1], 2: [seg2]},
        transfer_graph={2: [tr]},
        stop_cache={1: s1, 2: s2, 3: s3},
        stop_index={1: 0, 2: 1, 3: 2},
        station_time_index=sti
    )
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    graph.trip_segments = mock_snapshot.trip_segments
    graph.transfer_graph = mock_snapshot.transfer_graph
    
    raptor = OptimizedRAPTOR(max_transfers=1)
    constraints = RouteConstraints()

    # 2. Run Search
    print("Running Search for split-class journey...")
    routes = await raptor._search_single_departure(graph, 1, 3, dep_time, constraints)
    
    # 3. Verify
    assert len(routes) > 0
    r = routes[0]
    print(f"Total Cost: {r.total_cost}")
    assert r.total_cost == 1200.0, f"Expected 1200.0, got {r.total_cost}"
    assert len(r.segments) == 2
    
    print("[OK] Split-class journey correctly combined and cost calculated.")
    print("=== Task 5 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_5_split())
