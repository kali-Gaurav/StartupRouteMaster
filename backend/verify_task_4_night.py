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

async def verify_task_4_night():
    print("=== Verifying Task 4: Night-Transfer Penalty ===")
    
    # 1. Setup Mock Graph
    s1, s2, s3 = MockStop(1, "S1"), MockStop(2, "S2"), MockStop(3, "S3")
    dep_time = datetime(2026, 3, 9, 10, 0)
    
    # Route 1: NIGHT TRANSFER (2 AM)
    # Leg 1 arrives at 01:30 AM next day
    arr_night = dep_time + timedelta(hours=15, minutes=30)
    seg1_night = RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                              departure_time=dep_time, arrival_time=arr_night,
                              duration_minutes=930, distance_km=500.0, service_mask=127)
    
    dep_onward_night = arr_night + timedelta(minutes=60) # 02:30 AM
    seg2_night = RouteSegment(trip_id=2, departure_stop_id=2, arrival_stop_id=3,
                              departure_time=dep_onward_night, arrival_time=dep_onward_night + timedelta(hours=2),
                              duration_minutes=120, distance_km=100.0, service_mask=127)

    tr_night = TransferConnection(2, arr_night, dep_onward_night, 60, "S2", 5.0, 5.0)

    # Route 2: DAY TRANSFER (10 AM) - Slower total duration
    # Leg 1 arrives at 09:00 AM next day
    arr_day = dep_time + timedelta(hours=23)
    seg1_day = RouteSegment(trip_id=3, departure_stop_id=1, arrival_stop_id=2, 
                            departure_time=dep_time, arrival_time=arr_day,
                            duration_minutes=1380, distance_km=500.0, service_mask=127)
    
    dep_onward_day = arr_day + timedelta(minutes=60) # 10:00 AM
    seg2_day = RouteSegment(trip_id=4, departure_stop_id=2, arrival_stop_id=3,
                            departure_time=dep_onward_day, arrival_time=dep_onward_day + timedelta(hours=2),
                            duration_minutes=120, distance_km=100.0, service_mask=127)

    tr_day = TransferConnection(2, arr_day, dep_onward_day, 60, "S2", 5.0, 5.0)

    sti = defaultdict(lambda: [[] for _ in range(24)])
    sti[1][dep_time.hour].append((dep_time, 1))
    sti[1][dep_time.hour].append((dep_time, 3))
    sti[2][dep_onward_night.hour].append((dep_onward_night, 2))
    sti[2][dep_onward_day.hour].append((dep_onward_day, 4))

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={1: [(dep_time, 1), (dep_time, 3)], 2: [(dep_onward_night, 2), (dep_onward_day, 4)]},
        trip_segments={1: [seg1_night], 2: [seg2_night], 3: [seg1_day], 4: [seg2_day]},
        transfer_graph={2: [tr_night, tr_day]},
        stop_cache={1: s1, 2: s2, 3: s3},
        stop_index={1: 0, 2: 1, 3: 2},
        station_time_index=sti
    )
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    graph.trip_segments = mock_snapshot.trip_segments
    graph.transfer_graph = mock_snapshot.transfer_graph
    
    raptor = OptimizedRAPTOR(max_transfers=1)

    # 2. Test COMFORT persona (Should favor the slower DAY transfer)
    print("Searching with COMFORT persona...")
    c_comfort = RouteConstraints(persona=Persona.COMFORT)
    res_comfort = await raptor.find_routes(1, 3, dep_time, c_comfort, graph)
    
    found_trains = [r.segments[0].trip_id for r in res_comfort]
    print(f"Comfort Order (Trip IDs): {found_trains}")
    # Route with Trip 3 arrives at 10 AM (day), Route with Trip 1 arrives at 2 AM (night).
    # Comfort should pick Trip 3 first despite being ~8 hours slower.
    assert found_trains[0] == 3
    print("[OK] Comfort persona correctly penalized the night transfer.")

    # 3. Test EMERGENCY persona (Should favor the faster NIGHT transfer)
    print("Searching with EMERGENCY persona...")
    c_emergency = RouteConstraints(persona=Persona.EMERGENCY)
    res_emergency = await raptor.find_routes(1, 3, dep_time, c_emergency, graph)
    
    found_trains_em = [r.segments[0].trip_id for r in res_emergency]
    print(f"Emergency Order (Trip IDs): {found_trains_em}")
    assert found_trains_em[0] == 1
    print("[OK] Emergency persona correctly prioritized speed over night-transfer comfort.")

    print("=== Task 4 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_4_night())
