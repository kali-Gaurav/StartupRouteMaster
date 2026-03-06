import sys
import os
import asyncio
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.data_structures import RouteSegment, TransferConnection
from core.route_engine.constraints import RouteConstraints
from core.route_engine.graph import TimeDependentGraph, StaticGraphSnapshot

class MockStop:
    def __init__(self, id, code, lat, lon):
        self.id = id
        self.code = code
        self.latitude = lat
        self.longitude = lon
        self.name = code

async def verify_task_10_directional():
    print("=== Verifying Task 10: Directional Consistency Check ===")
    
    # 1. Setup Mock Stations (Geographic coordinates)
    # Source: Bangalore (12.97, 77.59)
    # Destination: Chennai (13.08, 80.27)
    # Transfer A (Consistent): Katpadi (12.94, 79.13) - roughly on the way
    # Transfer B (Zig-Zag): Mysore (12.29, 76.63) - complete opposite direction
    
    s_blr = MockStop(1, "SBC", 12.97, 77.59)
    s_chn = MockStop(2, "MAS", 13.08, 80.27)
    s_kat = MockStop(3, "KPD", 12.94, 79.13)
    s_mys = MockStop(4, "MYS", 12.29, 76.63)

    # 2. Setup Mock Graph
    dep_time = datetime(2026, 3, 9, 10, 0)
    
    # Leg 1 from BLR
    seg_kat = RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=3, 
                           departure_time=dep_time, arrival_time=datetime(2026, 3, 9, 13, 0),
                           duration_minutes=180, distance_km=200.0)
    
    seg_mys = RouteSegment(trip_id=2, departure_stop_id=1, arrival_stop_id=4,
                           departure_time=dep_time, arrival_time=datetime(2026, 3, 9, 12, 0),
                           duration_minutes=120, distance_km=140.0)

    # Transfer at Katpadi (Leg 2 onward)
    tr_kat = TransferConnection(3, datetime(2026, 3, 9, 13, 0), datetime(2026, 3, 9, 14, 0), 
                                60, "Katpadi", 5.0, 5.0)
    
    # Transfer at Mysore (Leg 2 onward)
    tr_mys = TransferConnection(4, datetime(2026, 3, 9, 12, 0), datetime(2026, 3, 9, 13, 0), 
                                60, "Mysore", 5.0, 5.0)

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={
            1: [(dep_time, 1), (dep_time, 2)],
            3: [(datetime(2026, 3, 9, 14, 0), 101)], # Onward from Katpadi
            4: [(datetime(2026, 3, 9, 13, 0), 102)]  # Onward from Mysore
        },
        trip_segments={
            1: [seg_kat], 
            2: [seg_mys],
            101: [RouteSegment(101, 3, 2, datetime(2026, 3, 9, 14, 0), datetime(2026, 3, 9, 16, 0), 120, 100.0)],
            102: [RouteSegment(102, 4, 2, datetime(2026, 3, 9, 13, 0), datetime(2026, 3, 9, 18, 0), 300, 400.0)]
        },
        transfer_graph={
            3: [tr_kat],
            4: [tr_mys]
        },
        stop_cache={1: s_blr, 2: s_chn, 3: s_kat, 4: s_mys},
        stop_index={1: 0, 2: 1, 3: 2, 4: 3}
    )
    graph = TimeDependentGraph(snapshot=mock_snapshot)
    
    raptor = OptimizedRAPTOR(max_transfers=1)
    constraints = RouteConstraints(max_results=10)

    # 3. Run Search
    print("Running Search from SBC to MAS...")
    routes = await raptor.find_routes(1, 2, dep_time, constraints, graph)
    
    # Check which transfers were kept
    transfer_stations = []
    for r in routes:
        if r.transfers:
            transfer_stations.append(r.transfers[0].station_id)
            
    print(f"Transfer stations kept: {transfer_stations}")
    
    # Station 3 (Katpadi) should be present.
    # Station 4 (Mysore) should be pruned because it's further from MAS than SBC is.
    assert 3 in transfer_stations
    assert 4 not in transfer_stations
    
    print("[OK] Zig-zag route via Mysore correctly pruned.")
    print("=== Task 10 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_10_directional())
