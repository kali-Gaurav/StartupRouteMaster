import sys
import os
import asyncio
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.data_structures import Route, RouteSegment

def verify_task_28_pareto():
    print("=== Verifying Task 28: Dominance Filtering (Pareto Optimality) ===")
    
    raptor = OptimizedRAPTOR()
    
    # 1. Setup Mock Routes
    # Route A: 10h, ₹500
    # Route B: 8h,  ₹400 (DOMINATES A - faster and cheaper)
    # Route C: 12h, ₹300 (PARETO-OPTIMAL vs B - slower but cheaper)
    
    dep = datetime(2026, 3, 9, 10, 0)
    
    r_a = Route(segments=[RouteSegment(1, 1, 2, dep, dep + timedelta(hours=10), 600, 100.0, fare=500.0)])
    r_b = Route(segments=[RouteSegment(2, 1, 2, dep, dep + timedelta(hours=8), 480, 100.0, fare=400.0)])
    r_c = Route(segments=[RouteSegment(3, 1, 2, dep, dep + timedelta(hours=12), 720, 100.0, fare=300.0)])

    routes = [r_a, r_b, r_c]
    
    # 2. Run Pareto Filtering
    print("Running Pareto filtering...")
    filtered = raptor._deduplicate_routes(routes)
    
    found_ids = [r.segments[0].trip_id for r in filtered]
    print(f"Remaining trips: {found_ids}")
    
    # Trip 1 (A) should be removed because Trip 2 (B) is better in both time and cost.
    assert 1 not in found_ids
    assert 2 in found_ids
    assert 3 in found_ids
    
    print("[OK] Pareto Dominance correctly filtered inferior routes while keeping distinct optimal choices.")
    print("=== Task 28 Verification Complete ===")

if __name__ == "__main__":
    verify_task_28_pareto()
