import sys
import os
import asyncio
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.data_structures import RouteSegment
from core.route_engine.constraints import RouteConstraints
from core.route_engine.graph import TimeDependentGraph, StaticGraphSnapshot

async def verify_task_8_calendar():
    print("=== Verifying Task 8: Strict Bitmask Calendar Validation ===")
    
    # 1. Setup Mock Graph
    # Trip 1: Runs ONLY on Mondays (bit 0 = 1)
    # Trip 2: Runs ONLY on Wednesdays (bit 2 = 4)
    # Trip 3: Runs EVERY day (bits 0-6 = 127)
    
    s1 = RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                      departure_time=datetime(2026, 3, 9, 10, 0), arrival_time=datetime(2026, 3, 9, 12, 0), 
                      duration_minutes=120, distance_km=100.0, service_mask=1) # Mon only
                      
    s2 = RouteSegment(trip_id=2, departure_stop_id=1, arrival_stop_id=2, 
                      departure_time=datetime(2026, 3, 11, 10, 0), arrival_time=datetime(2026, 3, 11, 12, 0), 
                      duration_minutes=120, distance_km=100.0, service_mask=4) # Wed only
                      
    s3_mon = RouteSegment(trip_id=3, departure_stop_id=1, arrival_stop_id=2, 
                      departure_time=datetime(2026, 3, 9, 14, 0), arrival_time=datetime(2026, 3, 9, 16, 0), 
                      duration_minutes=120, distance_km=100.0, service_mask=127) # Daily
                      
    s3_wed = RouteSegment(trip_id=3, departure_stop_id=1, arrival_stop_id=2, 
                      departure_time=datetime(2026, 3, 11, 14, 0), arrival_time=datetime(2026, 3, 11, 16, 0), 
                      duration_minutes=120, distance_km=100.0, service_mask=127) # Daily

    mock_snapshot = StaticGraphSnapshot(
        date=datetime(2026, 3, 9),
        departures_by_stop={1: [
            (s1.departure_time, 1), 
            (s3_mon.departure_time, 3),
            (s2.departure_time, 2), 
            (s3_wed.departure_time, 3)
        ]},
        arrivals_by_stop={2: [
            (s1.arrival_time, 1), 
            (s3_mon.arrival_time, 3),
            (s2.arrival_time, 2), 
            (s3_wed.arrival_time, 3)
        ]},
        trip_segments={1: [s1], 2: [s2], 3: [s3_mon]}, # Note: trip_segments lookup uses mask from first seg
        transfer_graph={},
        stop_cache={1: None, 2: None},
        station_schedule={},
        train_path={},
        route_patterns={},
        stop_index={1: 0, 2: 1}
    )
    graph_mon = TimeDependentGraph(snapshot=mock_snapshot)
    graph_mon.trip_segments = {1: [s1], 2: [s2], 3: [s3_mon]}
    
    raptor = OptimizedRAPTOR(max_transfers=0)
    constraints = RouteConstraints(max_results=10)

    # 2. Test Monday (2026-03-09 is a Monday)
    print("Testing Monday Search...")
    monday_dt = datetime(2026, 3, 9, 8, 0)
    res_mon = await raptor._search_single_departure(graph_mon, 1, 2, monday_dt, constraints)
    found_trips_mon = [r.segments[0].trip_id for r in res_mon if r.segments]
    print(f"Monday found: {found_trips_mon}")
    assert 1 in found_trips_mon
    assert 3 in found_trips_mon
    assert 2 not in found_trips_mon
    print("[OK] Monday search correctly filtered Trip 2 (Wed only)")

    # 3. Test Wednesday (2026-03-11 is a Wednesday)
    print("Testing Wednesday Search...")
    graph_wed = TimeDependentGraph(snapshot=mock_snapshot)
    graph_wed.trip_segments = {1: [s1], 2: [s2], 3: [s3_wed]}
    
    wed_dt = datetime(2026, 3, 11, 8, 0)
    res_wed = await raptor._search_single_departure(graph_wed, 1, 2, wed_dt, constraints)
    found_trips_wed = [r.segments[0].trip_id for r in res_wed if r.segments]
    print(f"Wednesday found: {found_trips_wed}")
    assert 2 in found_trips_wed
    assert 3 in found_trips_wed
    assert 1 not in found_trips_wed
    print("[OK] Wednesday search correctly filtered Trip 1 (Mon only)")

    print("=== Task 8 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_8_calendar())
