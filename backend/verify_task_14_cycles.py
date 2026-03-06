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

async def verify_task_14_cycles():
    print("=== Verifying Task 14: Circular Route Prevention ===")
    
    # 1. Setup Mock Graph with a Cycle
    # S1(0,0) -> S2(1,1) -> S3(2,2)
    s1 = MockStop(1, "S1")
    s1.latitude, s1.longitude = 0.0, 0.0
    s2 = MockStop(2, "S2")
    s2.latitude, s2.longitude = 1.0, 1.0
    s3 = MockStop(3, "S3")
    s3.latitude, s3.longitude = 2.0, 2.0

    dep_time = datetime(2026, 3, 9, 10, 0)
    arr_t_leg1 = dep_time + timedelta(hours=2)
    next_dep_t = dep_time + timedelta(hours=2, minutes=45) 
    
    # Leg 1: S1 -> S2
    seg1 = RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                        departure_time=dep_time, arrival_time=arr_t_leg1,
                        duration_minutes=120, distance_km=100.0, service_mask=127)
    
    # Potential Leg 2 (Cycle): S2 -> S1
    seg_cycle = RouteSegment(trip_id=2, departure_stop_id=2, arrival_stop_id=1,
                             departure_time=next_dep_t, arrival_time=next_dep_t + timedelta(hours=2),
                             duration_minutes=120, distance_km=100.0, service_mask=127)
                             
    # Potential Leg 2 (Progress): S2 -> S3
    seg_progress = RouteSegment(trip_id=3, departure_stop_id=2, arrival_stop_id=3,
                                departure_time=next_dep_t, arrival_time=next_dep_t + timedelta(hours=2),
                                duration_minutes=120, distance_km=100.0, service_mask=127)

    # station_time_index: stop_id -> hour -> list of (dt, trip_id)
    sti = defaultdict(lambda: [[] for _ in range(24)])
    sti[1][dep_time.hour].append((dep_time, 1))
    sti[2][next_dep_t.hour].append((next_dep_t, 2))
    sti[2][next_dep_t.hour].append((next_dep_t, 3))

    # Transfer at S2
    # tr2 covers arr_t_leg1 and has departure after it
    tr2 = TransferConnection(2, arr_t_leg1, next_dep_t, 
                             45, "S2", 5.0, 5.0)

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={
            1: [(dep_time, 1)],
            2: [(next_dep_t, 2), (next_dep_t, 3)]
        },
        trip_segments={1: [seg1], 2: [seg_cycle], 3: [seg_progress]},
        transfer_graph={2: [tr2]},
        stop_cache={1: s1, 2: s2, 3: s3},
        stop_index={1: 0, 2: 1, 3: 2},
        station_time_index=sti
    )
    
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    graph.trip_segments = mock_snapshot.trip_segments
    graph.stop_cache = mock_snapshot.stop_cache
    graph.transfer_graph = mock_snapshot.transfer_graph
    
    raptor = OptimizedRAPTOR(max_transfers=2)
    constraints = RouteConstraints(max_results=10)
    constraints.lookahead_minutes = 1440

    # 2. Run Search
    print("Running Search from S1 to S3...")
    routes = await raptor._search_single_departure(graph, 1, 3, dep_time, constraints)
    
    # 3. Verify
    print(f"Found {len(routes)} raw candidate routes.")
    assert len(routes) > 0, "No routes found!"
    
    for idx, r in enumerate(routes):
        stations = [s.departure_stop_id for s in r.segments] + [r.segments[-1].arrival_stop_id]
        print(f"Route {idx+1} stations: {stations}")
        # Ensure no station is repeated
        assert len(stations) == len(set(stations)), f"Cycle detected in route: {stations}"
    
    print("[OK] No circular routes were generated.")
    print("=== Task 14 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_14_cycles())
