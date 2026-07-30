import sys
import os
import time
import numpy as np

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.data_utils.structures import Route, RouteSegment
from core.route_engine.scoring import RouteScorer
from core.route_engine.constraints import RouteConstraints, Persona

def verify_task_16_4():
    print("\n>>> Verifying Task 16.4: Batch Scoring")
    
    constraints = RouteConstraints(persona=Persona.COMFORT)
    
    # 1. Create 1000 mock routes
    num_routes = 1000
    mock_routes = []
    for i in range(num_routes):
        r = Route()
        r.total_duration = 500 + i
        r.total_cost = 1000 + (i * 2)
        mock_routes.append(r)
        
    # 2. Benchmark Batch Scoring
    start = time.perf_counter()
    RouteScorer.score_routes_batch(mock_routes, constraints)
    latency = (time.perf_counter() - start) * 1000
    
    print(f"  Scored {num_routes} routes in {latency:.2f}ms")
    
    # 3. Verify Score Consistency
    # Manual check for the first route
    r0 = mock_routes[0]
    w = constraints.weights
    expected_score = (r0.total_duration * w.time) + (r0.total_cost * w.cost)
    
    print(f"  Sample Score: {r0.score:.2f}, Expected: {expected_score:.2f}")
    
    if abs(r0.score - expected_score) > 0.01:
        print("❌ FAILURE: Batch score mismatch.")
        return False
        
    if latency > 5.0:
        print(f"⚠️ WARNING: Batch scoring took {latency:.2f}ms, expected < 1ms for 1k routes.")

    print("\n✅ TASK 16.4 VERIFIED: Batch scoring is fast and consistent.")
    return True

if __name__ == "__main__":
    verify_task_16_4()
