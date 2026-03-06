import sys
import os
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.data_structures import RouteSegment
from core.route_engine.constraints import RouteConstraints
from core.route_engine.graph import TimeDependentGraph, StaticGraphSnapshot
from core.route_engine.direct_index import DirectRouteManager

class MockStop:
    def __init__(self, id, code, is_major):
        self.id = id
        self.code = code
        self.is_major_junction = is_major
        self.latitude, self.longitude = 0.0, 0.0
        self.name = code

async def verify_task_16():
    print("=== Verifying Task 16: Hidden Quota Exploitation ===")
    
    route_engine_instance = RailwayRouteEngine()
    dep_time = datetime(2026, 3, 9, 10, 0)
    
    # 1. Setup Mock Graph
    # Trip 101: S1 (Major) -> S2 (User Source) -> S3 (Destination)
    s1 = MockStop(1, "MAJ", True)
    s2 = MockStop(2, "SRC", False)
    s3 = MockStop(3, "DST", False)
    
    seg1 = RouteSegment(trip_id=101, departure_stop_id=1, arrival_stop_id=2,
                        departure_time=dep_time, arrival_time=dep_time + timedelta(hours=1),
                        duration_minutes=60, distance_km=50.0, service_mask=127,
                        departure_code="MAJ", arrival_code="SRC")
    
    seg2 = RouteSegment(trip_id=101, departure_stop_id=2, arrival_stop_id=3,
                        departure_time=dep_time + timedelta(hours=1, minutes=10), 
                        arrival_time=dep_time + timedelta(hours=3),
                        duration_minutes=110, distance_km=100.0, service_mask=127,
                        departure_code="SRC", arrival_code="DST")

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={1: [(dep_time, 101)], 2: [(dep_time + timedelta(hours=1, minutes=10), 101)]},
        trip_segments={101: [seg1, seg2]},
        transfer_graph={},
        stop_cache={1: s1, 2: s2, 3: s3},
        stop_index={1: 0, 2: 1, 3: 2},
        station_time_index=defaultdict(lambda: [[] for _ in range(24)])
    )
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    graph.trip_segments = mock_snapshot.trip_segments
    graph.stop_cache = mock_snapshot.stop_cache
    
    # Mock Direct Index
    from core.route_engine import engine as engine_mod
    mock_direct = DirectRouteManager(None)
    mock_direct._index[(2, 3)].add(101) # SRC -> DST
    
    def mock_get_manager(*args): return mock_direct
    engine_mod.get_direct_manager = mock_get_manager
    
    # Mock Station Resolver
    import utils.station_utils as su
    def mock_resolve(db, s, d):
        if s == "SRC": return s2, s3
        return None, None
    su.resolve_stations = mock_resolve

    # 2. Run Search from SRC to DST
    print("Running search from SRC to DST...")
    # Inject our mock graph into the engine instance
    route_engine_instance.current_graph = graph
    route_engine_instance.current_snapshot = mock_snapshot
    
    constraints = RouteConstraints()
    routes = await route_engine_instance.search("SRC", "DST", dep_time, constraints)
    
    # 3. Verify
    print(f"Results found: {len(routes)}")
    for r in routes:
        meta = getattr(r, 'metadata', {})
        print(f"Route: {r.segments[0].departure_code} -> {r.segments[-1].arrival_code}, Trick={meta.get('boarding_point_trick', False)}")
        
    # We expect 2 routes: 
    # 1. SRC -> DST (Normal)
    # 2. MAJ -> DST (Boarding Point Trick)
    assert len(routes) >= 2
    assert any(r.metadata.get("boarding_point_trick") for r in routes)
    
    print("[OK] Hidden Quota Exploitation correctly suggested a virtual route from the previous major station.")
    print("=== Task 16 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_16())
