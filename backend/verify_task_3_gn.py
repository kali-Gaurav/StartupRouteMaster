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

async def verify_task_3_gn():
    print("=== Verifying Task 3: Partial GN Compromise ===")
    
    # 1. Setup Mock Graph
    # S1 -> S2 (Overnight Leg, CNF)
    # S2 -> S3 (Short Leg, ONLY GN AVAILABLE)
    
    s1, s2, s3 = MockStop(1, "S1"), MockStop(2, "S2"), MockStop(3, "S3")
    dep_time = datetime(2026, 3, 9, 10, 0)
    
    # Leg 1: S1 -> S2 (Confirmed, 10 hours)
    seg1 = RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                        departure_time=dep_time, arrival_time=dep_time + timedelta(hours=10),
                        duration_minutes=600, distance_km=500.0, service_mask=127)
    
    next_dep = dep_time + timedelta(hours=11)
    # Leg 2: S2 -> S3 (GN Only, 2 hours)
    seg2_gn = RouteSegment(trip_id=2, departure_stop_id=2, arrival_stop_id=3,
                           departure_time=next_dep, arrival_time=next_dep + timedelta(hours=2),
                           duration_minutes=120, distance_km=100.0, service_mask=127,
                           is_unconfirmed_allowed=True) # Task 3

    tr = TransferConnection(2, dep_time + timedelta(hours=10), next_dep, 60, "S2", 5.0, 5.0)

    sti = defaultdict(lambda: [[] for _ in range(24)])
    sti[1][dep_time.hour].append((dep_time, 1))
    sti[2][next_dep.hour].append((next_dep, 2))

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={1: [(dep_time, 1)], 2: [(next_dep, 2)]},
        trip_segments={1: [seg1], 2: [seg2_gn]},
        transfer_graph={2: [tr]},
        stop_cache={1: s1, 2: s2, 3: s3},
        stop_index={1: 0, 2: 1, 3: 2},
        station_time_index=sti
    )
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    graph.trip_segments = mock_snapshot.trip_segments
    graph.transfer_graph = mock_snapshot.transfer_graph
    
    raptor = OptimizedRAPTOR(max_transfers=1)

    # 2. Test COMFORT Persona (Should find 0 routes because it blocks GN)
    print("Searching with COMFORT persona...")
    c_comfort = RouteConstraints(persona=Persona.COMFORT)
    res_comfort = await raptor.find_routes(1, 3, dep_time, c_comfort, graph)
    
    print(f"Comfort results found: {len(res_comfort)}")
    assert len(res_comfort) == 0, "Comfort persona should block unconfirmed segments"

    # 3. Test EMERGENCY Persona (Should accept the 2-hour GN leg)
    print("Searching with EMERGENCY persona...")
    c_emergency = RouteConstraints(persona=Persona.EMERGENCY)
    res_emergency = await raptor.find_routes(1, 3, dep_time, c_emergency, graph)
    
    print(f"Emergency results found: {len(res_emergency)}")
    assert len(res_emergency) > 0, "Emergency persona should allow unconfirmed segments"
    print(f"Emergency Score: {res_emergency[0].score}")
    
    print("[OK] Partial GN Compromise correctly integrated into Persona scoring.")
    print("=== Task 3 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_3_gn())
