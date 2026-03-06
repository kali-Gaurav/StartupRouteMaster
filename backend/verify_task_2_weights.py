import sys
import os
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.data_structures import RouteSegment, TransferConnection, Route
from core.route_engine.constraints import RouteConstraints, Persona
from core.route_engine.graph import TimeDependentGraph, StaticGraphSnapshot

class MockStop:
    def __init__(self, id, code):
        self.id = id
        self.code = code
        self.latitude, self.longitude = 0.0, 0.0
        self.name = code

async def verify_task_2_weights():
    print("=== Verifying Task 2: Dynamic Weighting Engine ===")
    
    # Setup Mock Graph
    # Route A: FAST but EXPENSIVE (2 hours, ₹1000)
    # Route B: SLOW but CHEAP (5 hours, ₹200)
    
    s1, s2 = MockStop(1, "S1"), MockStop(2, "S2")
    dep_time = datetime(2026, 3, 9, 10, 0)
    
    seg_a = RouteSegment(trip_id=101, departure_stop_id=1, arrival_stop_id=2,
                         departure_time=dep_time, arrival_time=dep_time + timedelta(hours=2),
                         duration_minutes=120, distance_km=100.0, service_mask=127,
                         fare=1000.0)
    
    seg_b = RouteSegment(trip_id=102, departure_stop_id=1, arrival_stop_id=2,
                         departure_time=dep_time, arrival_time=dep_time + timedelta(hours=5),
                         duration_minutes=300, distance_km=100.0, service_mask=127,
                         fare=200.0)

    sti = defaultdict(lambda: [[] for _ in range(24)])
    sti[1][dep_time.hour].append((dep_time, 101))
    sti[1][dep_time.hour].append((dep_time, 102))

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={1: [(dep_time, 101), (dep_time, 102)]},
        trip_segments={101: [seg_a], 102: [seg_b]},
        transfer_graph={},
        stop_cache={1: s1, 2: s2},
        stop_index={1: 0, 2: 1},
        station_time_index=sti
    )
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    graph.trip_segments = mock_snapshot.trip_segments
    
    raptor = OptimizedRAPTOR(max_transfers=0)

    # 1. Test COMFORT with high time_priority (Should pick FAST route)
    print("Searching COMFORT + High Time Priority...")
    c_time = RouteConstraints(persona=Persona.COMFORT, time_priority=1.0, cost_priority=0.1)
    res_time = await raptor.find_routes(1, 2, dep_time, c_time, graph)
    
    print(f"Top choice Trip ID: {res_time[0].segments[0].trip_id}")
    assert res_time[0].segments[0].trip_id == 101

    # 2. Test COMFORT with high cost_priority (Should pick CHEAP route)
    print("Searching COMFORT + High Cost Priority...")
    c_cost = RouteConstraints(persona=Persona.COMFORT, time_priority=0.1, cost_priority=1.0)
    res_cost = await raptor.find_routes(1, 2, dep_time, c_cost, graph)
    
    print(f"Top choice Trip ID: {res_cost[0].segments[0].trip_id}")
    assert res_cost[0].segments[0].trip_id == 102

    print("[OK] Dynamic weighting correctly shifted rankings based on priority overrides.")
    print("=== Task 2 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_2_weights())
