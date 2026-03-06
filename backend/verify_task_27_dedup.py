import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.data_structures import Route, RouteSegment

def verify_task_27():
    print("=== Verifying Task 27: Universal Engine Deduplicator ===")
    
    engine = RailwayRouteEngine()
    dep_time = datetime(2026, 3, 9, 10, 0)
    
    # 1. Setup Mock Routes (Identical journey found by two sources)
    seg = RouteSegment(trip_id=101, departure_stop_id=1, arrival_stop_id=2, 
                       departure_time=dep_time, arrival_time=dep_time, 
                       duration_minutes=60, distance_km=100.0)
    
    # Source A (Direct Index): higher score (worse)
    r_a = Route(segments=[seg], score=500.0)
    
    # Source B (RAPTOR): lower score (better)
    r_b = Route(segments=[seg], score=450.0)
    
    # Route C: Different trip
    seg_c = RouteSegment(trip_id=102, departure_stop_id=1, arrival_stop_id=2, 
                         departure_time=dep_time, arrival_time=dep_time, 
                         duration_minutes=60, distance_km=100.0)
    r_c = Route(segments=[seg_c], score=400.0)

    routes = [r_a, r_b, r_c]
    
    # 2. Run Deduplication
    print("Running Universal Deduplication...")
    deduplicated = engine._merge_and_deduplicate(routes)
    
    print(f"Routes remaining: {len(deduplicated)}")
    for i, r in enumerate(deduplicated):
        print(f"Route {i+1}: Trip {r.segments[0].trip_id}, Score {r.score}")
        
    assert len(deduplicated) == 2 # 101 merged, 102 kept
    # Ensure Trip 101 kept the better score (450.0)
    r101 = next(r for r in deduplicated if r.segments[0].trip_id == 101)
    assert r101.score == 450.0
    
    print("[OK] Identical routes merged accurately, keeping the best metadata/score.")
    print("=== Task 27 Verification Complete ===")

if __name__ == "__main__":
    verify_task_27()
