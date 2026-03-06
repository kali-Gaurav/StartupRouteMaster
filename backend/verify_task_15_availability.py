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

async def verify_task_15_availability():
    print("=== Verifying Task 15: ML Availability Heuristic Edge Scoring ===")
    
    # 1. Setup Mock Graph
    # Route 1 (Trip 101): FAST but high demand (12626) -> Low Availability Score
    # Route 2 (Trip 102): SLOW but normal train -> High Availability Score
    
    s1 = MockStop(1, "S1")
    s2 = MockStop(2, "S2")

    dep_time = datetime(2026, 3, 9, 10, 0)
    
    # Fast Trip (12626 is penalized in heuristic)
    seg_fast = RouteSegment(trip_id=101, departure_stop_id=1, arrival_stop_id=2, 
                            departure_time=dep_time, arrival_time=dep_time + timedelta(hours=2),
                            duration_minutes=120, distance_km=100.0, service_mask=127,
                            train_number="12626")
    
    # Slow Trip (Higher duration, but higher availability score)
    seg_slow = RouteSegment(trip_id=102, departure_stop_id=1, arrival_stop_id=2,
                            departure_time=dep_time, arrival_time=dep_time + timedelta(hours=5),
                            duration_minutes=300, distance_km=100.0, service_mask=127,
                            train_number="99999")

    sti = defaultdict(lambda: [[] for _ in range(24)])
    sti[1][dep_time.hour].append((dep_time, 101))
    sti[1][dep_time.hour].append((dep_time, 102))

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={1: [(dep_time, 101), (dep_time, 102)]},
        trip_segments={101: [seg_fast], 102: [seg_slow]},
        transfer_graph={},
        stop_cache={1: s1, 2: s2},
        stop_index={1: 0, 2: 1},
        station_time_index=sti
    )
    
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    graph.trip_segments = mock_snapshot.trip_segments
    graph.stop_cache = mock_snapshot.stop_cache
    
    raptor = OptimizedRAPTOR(max_transfers=1)
    constraints = RouteConstraints(max_results=10)

    # 2. Run Search
    print("Running Search...")
    routes = await raptor.find_routes(1, 2, dep_time, constraints, graph)
    
    # 3. Verify Order
    print(f"Found {len(routes)} routes.")
    for idx, r in enumerate(routes):
        train = r.segments[0].train_number
        cnf_prob = r.metadata.get("predicted_cnf_probability", 0)
        print(f"Rank {idx+1}: Train {train}, Duration {r.total_duration}m, Score {r.score:.2f}, CNF Prob {cnf_prob:.2f}")

    # Standard duration scoring would favor Train 101 (120m vs 300m).
    # But Task 15 adds a penalty: (1.0 - cnf_prob) * 1000.
    # Train 101 (12626) has much lower prob, so it should be ranked lower.
    
    assert routes[0].segments[0].trip_id == 102, "Slow but available train should be ranked #1"
    
    print("[OK] Engine correctly prioritized the route with higher availability probability.")
    print("=== Task 15 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_15_availability())
