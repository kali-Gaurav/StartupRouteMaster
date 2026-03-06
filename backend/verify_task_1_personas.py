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

async def verify_task_1_personas():
    print("=== Verifying Task 1: Persona-Driven Routing ===")
    
    # Setup Mock Graph
    # Route 1: Direct but SLOW (6 hours)
    # Route 2: 1-Transfer but FAST (3 hours total)
    
    s1, s2, s3 = MockStop(1, "S1"), MockStop(2, "S2"), MockStop(3, "S3")
    dep_time = datetime(2026, 3, 9, 10, 0)
    
    # Route 1: S1 -> S3 (Direct, 360m)
    seg_direct = RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=3,
                              departure_time=dep_time, arrival_time=dep_time + timedelta(hours=6),
                              duration_minutes=360, distance_km=200.0, service_mask=127)
    
    # Route 2: S1 -> S2 (Leg 1, 90m) + S2 -> S3 (Leg 2, 90m)
    seg_leg1 = RouteSegment(trip_id=2, departure_stop_id=1, arrival_stop_id=2,
                            departure_time=dep_time, arrival_time=dep_time + timedelta(minutes=90),
                            duration_minutes=90, distance_km=100.0, service_mask=127)
    
    next_dep = dep_time + timedelta(minutes=150) # 1h transfer
    seg_leg2 = RouteSegment(trip_id=3, departure_stop_id=2, arrival_stop_id=3,
                            departure_time=next_dep, arrival_time=next_dep + timedelta(minutes=90),
                            duration_minutes=90, distance_km=100.0, service_mask=127)

    tr = TransferConnection(2, dep_time + timedelta(minutes=90), next_dep, 60, "S2", 5.0, 5.0)

    sti = defaultdict(lambda: [[] for _ in range(24)])
    sti[1][dep_time.hour].append((dep_time, 1))
    sti[1][dep_time.hour].append((dep_time, 2))
    sti[2][next_dep.hour].append((next_dep, 3))

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={1: [(dep_time, 1), (dep_time, 2)], 2: [(next_dep, 3)]},
        trip_segments={1: [seg_direct], 2: [seg_leg1], 3: [seg_leg2]},
        transfer_graph={2: [tr]},
        stop_cache={1: s1, 2: s2, 3: s3},
        stop_index={1: 0, 2: 1, 3: 2},
        station_time_index=sti
    )
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    graph.trip_segments = mock_snapshot.trip_segments
    graph.transfer_graph = mock_snapshot.transfer_graph
    
    raptor = OptimizedRAPTOR(max_transfers=1)

    # 1. Test COMFORT Persona (Should favor Direct route due to high transfer penalty)
    print("Searching with COMFORT persona...")
    c_comfort = RouteConstraints(persona=Persona.COMFORT)
    res_comfort = await raptor.find_routes(1, 3, dep_time, c_comfort, graph)
    
    print(f"Comfort results: {[('Direct' if len(r.transfers)==0 else 'Transfer') for r in res_comfort]}")
    assert len(res_comfort[0].transfers) == 0, "Comfort persona should prioritize direct route"

    # 2. Test EMERGENCY Persona (Should favor Transfer route due to lower total time)
    print("Searching with EMERGENCY persona...")
    c_emergency = RouteConstraints(persona=Persona.EMERGENCY)
    res_emergency = await raptor.find_routes(1, 3, dep_time, c_emergency, graph)
    
    print(f"Emergency results: {[('Direct' if len(r.transfers)==0 else 'Transfer') for r in res_emergency]}")
    # Total time for Transfer is 240m vs Direct 360m. 
    # With time weight 2.0, Transfer should win easily.
    assert len(res_emergency[0].transfers) == 1, "Emergency persona should prioritize fastest route regardless of transfers"

    print("[OK] Routing Personas correctly influenced result ranking.")
    print("=== Task 1 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_1_personas())
