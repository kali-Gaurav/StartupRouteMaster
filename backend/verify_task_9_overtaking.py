import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.data_structures import Route, RouteSegment

def verify_task_9_overtaking():
    print("=== Verifying Task 9: Overtaking Train Pruning ===")
    
    raptor = OptimizedRAPTOR()
    
    # 1. Setup Mock Routes
    # Route A: Departs 10:00, Arrives 14:00 (Duration 4h)
    # Route B: Departs 11:00, Arrives 13:30 (Duration 2.5h) - DOMINATES A
    # Route C: Departs 12:00, Arrives 15:00 (Duration 3h) - Non-dominated vs B
    
    r_a = Route(segments=[
        RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                      departure_time=datetime(2026, 3, 9, 10, 0), arrival_time=datetime(2026, 3, 9, 14, 0), 
                      duration_minutes=240, distance_km=100.0)
    ])
    
    r_b = Route(segments=[
        RouteSegment(trip_id=2, departure_stop_id=1, arrival_stop_id=2, 
                      departure_time=datetime(2026, 3, 9, 11, 0), arrival_time=datetime(2026, 3, 9, 13, 30), 
                      duration_minutes=150, distance_km=100.0)
    ])
    
    r_c = Route(segments=[
        RouteSegment(trip_id=3, departure_stop_id=1, arrival_stop_id=2, 
                      departure_time=datetime(2026, 3, 9, 12, 0), arrival_time=datetime(2026, 3, 9, 15, 0), 
                      duration_minutes=180, distance_km=100.0)
    ])

    routes = [r_a, r_b, r_c]
    
    # 2. Run Pruning
    print("Running Overtaking Pruning...")
    filtered = raptor._deduplicate_routes(routes)
    
    found_ids = [r.segments[0].trip_id for r in filtered]
    print(f"Remaining trips: {found_ids}")
    
    # Trip 1 (A) should be removed because Trip 2 (B) leaves LATER and arrives EARLIER.
    assert 1 not in found_ids
    assert 2 in found_ids
    assert 3 in found_ids
    
    print("[OK] Overtaken train (Trip 1) was correctly pruned.")
    print("=== Task 9 Verification Complete ===")

if __name__ == "__main__":
    verify_task_9_overtaking()
