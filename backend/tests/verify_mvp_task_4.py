import asyncio
import sys
import os
import numpy as np
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.route_engine.categorization import CategorizationEngine
from core.data_structures import Route, RouteSegment, Persona

def create_mock_route(jid, duration, cost, prob=0.9):
    r = Route()
    s = RouteSegment(trip_id=jid, departure_stop_id=1, arrival_stop_id=2, 
                      departure_time=datetime.now(), arrival_time=datetime.now() + timedelta(minutes=duration),
                      duration_minutes=duration, distance_km=100.0, train_number=f"T{jid}")
    r.add_segment(s)
    r.total_cost = float(cost)
    r.total_duration = duration
    r.availability_probability = prob
    r.score = float(duration + cost/10.0) # Simple score
    return r

async def verify_task_4():
    print("\n>>> STARTING VERIFICATION: MVP TASK 4 (CATEGORY NORMALIZATION)")
    
    # 1. Create 50 diverse routes
    routes = []
    # Regular routes
    for i in range(40):
        # Duration 300-600, Cost 500-1500
        dur = 300 + (i * 7)
        cost = 500 + (i * 25)
        routes.append(create_mock_route(f"R{i}", dur, cost))
    
    # [4.6] Add Outliers
    # Outlier 1: Very Expensive, not faster
    routes.append(create_mock_route("OUTLIER_RICH", 500, 10000)) 
    # Outlier 2: Very Slow, regular cost
    routes.append(create_mock_route("OUTLIER_SLOW", 2000, 800))
    # Expensive but fast (should NOT be pruned)
    routes.append(create_mock_route("FAST_EXPENSIVE", 150, 2000))

    print(f"  Total Input Routes: {len(routes)}")
    
    # 2. Categorize
    categories = CategorizationEngine.categorize(routes, Persona.BUDGET)
    
    # 3. Verify Pruning (Subtask 4.6)
    print("\n[4.6] Verifying Outlier Pruning...")
    all_cat_ids = []
    for cat in categories.values():
        all_cat_ids.extend([r["journey_id"] for r in cat])
    
    unique_ids = set(all_cat_ids)
    print(f"  Total Unique Routes in Categories: {len(unique_ids)}")
    
    # Check if any ID contains the mock strings
    has_rich = any("OUTLIER_RICH" in jid for jid in unique_ids)
    has_fast = any("FAST_EXPENSIVE" in jid for jid in unique_ids)
    
    assert has_rich is False
    assert has_fast is True
    print("  SUCCESS: Outliers correctly pruned.")

    # 4. Verify Pricing Bounds (Subtask 4.2)
    print("\n[4.2] Verifying Cheapest category bounds...")
    min_cost = min(r.total_cost for r in routes)
    costs = np.array([r.total_cost for r in routes])
    std_cost = np.std(costs)
    bound = min_cost + 1.5 * std_cost
    
    print(f"  Min Cost: {min_cost}, Bound: {bound:.2f}")
    for rd in categories["cheapest"]:
        print(f"    - Journey {rd['journey_id']}: ₹{rd['total_fare']}")
        assert rd["total_fare"] <= bound
    print("  SUCCESS: Cheapest routes within statistical bounds.")

    # 5. Verify Best Value (Subtask 4.5)
    print("\n[4.5] Verifying Best Value category...")
    assert len(categories["best_value"]) > 0
    first_val = categories["best_value"][0]
    print(f"  Top Value Route: {first_val['journey_id']} (Value Score: {first_val['value_score']:.4f})")
    assert "value_score" in first_val
    print("  SUCCESS: Best Value logic implemented.")

    # 6. Verify Diversification (Subtask 4.8)
    print("\n[4.8] Verifying Category Diversification...")
    cheapest_top = categories["cheapest"][0]["journey_id"]
    fastest_top = categories["fastest"][0]["journey_id"]
    print(f"  Top Cheapest: {cheapest_top}")
    print(f"  Top Fastest:  {fastest_top}")
    
    # In our mock data, R0 is cheapest (300m, ₹500) and FAST_EXPENSIVE is fastest (150m, ₹2000)
    # So they should be different
    assert cheapest_top != fastest_top
    print("  SUCCESS: Main categories have distinct winners.")

    print("\n✅ ALL MVP TASK 4 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_4())
