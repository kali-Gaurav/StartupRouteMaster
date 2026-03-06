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

async def verify_task_6_pantry():
    print("=== Verifying Task 6: Pantry Car Priority ===")
    
    s1, s2 = MockStop(1, "S1"), MockStop(2, "S2")
    dep_time = datetime(2026, 3, 9, 10, 0)
    
    # 1. Setup Mock Graph
    # Both trips are 12 hours (720 mins)
    # Trip 101: HAS PANTRY
    # Trip 102: NO PANTRY
    
    seg_pantry = RouteSegment(trip_id=101, departure_stop_id=1, arrival_stop_id=2,
                              departure_time=dep_time, arrival_time=dep_time + timedelta(hours=12),
                              duration_minutes=720, distance_km=800.0, service_mask=127,
                              has_pantry=True)
    
    seg_no_pantry = RouteSegment(trip_id=102, departure_stop_id=1, arrival_stop_id=2,
                                 departure_time=dep_time, arrival_time=dep_time + timedelta(hours=12),
                                 duration_minutes=720, distance_km=800.0, service_mask=127,
                                 has_pantry=False)

    sti = defaultdict(lambda: [[] for _ in range(24)])
    sti[1][dep_time.hour].extend([(dep_time, 101), (dep_time, 102)])

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={1: [(dep_time, 101), (dep_time, 102)]},
        trip_segments={101: [seg_pantry], 102: [seg_no_pantry]},
        transfer_graph={},
        stop_cache={1: s1, 2: s2},
        stop_index={1: 0, 2: 1},
        station_time_index=sti
    )
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    graph.trip_segments = mock_snapshot.trip_segments
    
    raptor = OptimizedRAPTOR(max_transfers=0)
    constraints = RouteConstraints(persona=Persona.COMFORT)

    # 2. Run Search
    print("Searching for long-distance trains (12h)...")
    routes = await raptor.find_routes(1, 2, dep_time, constraints, graph)
    
    # 3. Verify
    print(f"Results found: {len(routes)}")
    for r in routes:
        tid = r.segments[0].trip_id
        pantry = r.segments[0].has_pantry
        print(f"Trip {tid}: Pantry={pantry}, Score={r.score:.2f}")
        
    assert routes[0].segments[0].trip_id == 101, "Train with Pantry should be ranked first"
    assert routes[0].score < routes[1].score
    
    print("[OK] Pantry Car Priority correctly improved the route score.")
    print("=== Task 6 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_6_pantry())
