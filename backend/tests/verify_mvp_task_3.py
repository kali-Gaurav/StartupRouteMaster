import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.route_engine.scoring import RouteScorer
from core.route_engine.constraints_engine import ConstraintsEngine
from core.data_utils.structures import Route, RouteSegment, TransferConnection

async def verify_task_3():
    print("\n>>> STARTING VERIFICATION: MVP TASK 3 (SMART TRANSFER WEIGHTS)")
    
    # 1. Setup Constraints
    c = ConstraintsEngine.initialize_constraints("comfort", datetime.now().date())
    
    def create_route_with_transfer(wait_mins):
        r = Route()
        s1 = RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                          departure_time=datetime.now(), arrival_time=datetime.now() + timedelta(hours=2),
                          duration_minutes=120, distance_km=100.0, train_number="T1")
        s2 = RouteSegment(trip_id=2, departure_stop_id=2, arrival_stop_id=3, 
                          departure_time=s1.arrival_time + timedelta(minutes=wait_mins),
                          arrival_time=s1.arrival_time + timedelta(minutes=wait_mins+120),
                          duration_minutes=120, distance_km=100.0, train_number="T2")
        r.add_segment(s1)
        r.add_segment(s2)
        tc = TransferConnection(station_id=2, arrival_time=s1.arrival_time, 
                                departure_time=s2.departure_time, duration_minutes=wait_mins,
                                station_name="HUB")
        r.add_transfer(tc)
        r.total_cost = 1000.0
        return r

    # 2. Create Test Routes
    route_ideal = create_route_with_transfer(45)  # Safe
    route_tight = create_route_with_transfer(15)  # Risky
    route_long = create_route_with_transfer(480) # 8 hours - Exhausting

    # 3. Score them
    score_ideal = await RouteScorer.score_route(route_ideal, c)
    score_tight = await RouteScorer.score_route(route_tight, c)
    score_long = await RouteScorer.score_route(route_long, c)

    print(f"\n  Scores:")
    print(f"    Ideal (45m): {score_ideal:.2f}")
    print(f"    Tight (15m): {score_tight:.2f} (Diff: {score_tight - score_ideal:.2f})")
    print(f"    Long (8h):   {score_long:.2f} (Diff: {score_long - score_ideal:.2f})")

    # 4. Assertions
    # Ideal should be best
    assert score_ideal < score_tight
    assert score_ideal < score_long
    
    # Tight should have quadratic penalty: (30-15)^2 * 10 = 15^2 * 10 = 225 * 10 = 2250
    # Long should have linear penalty: ((480-360)/60) * 200 = 2 * 200 = 400
    
    print("\n  Verifying Metadata Breakdown...")
    print(f"    Tight Penalty: {route_tight.metadata['breakdown']['smart_transfer_penalty']}")
    print(f"    Long Penalty:  {route_long.metadata['breakdown']['smart_transfer_penalty']}")
    
    assert route_tight.metadata['breakdown']['smart_transfer_penalty'] == 2250
    assert route_long.metadata['breakdown']['smart_transfer_penalty'] == 400
    
    # 5. Verify UI Labels
    print("\n  Verifying UI Reasons...")
    print(f"    Ideal Reasons: {route_ideal.metadata['ui_reasons']}")
    print(f"    Tight Reasons: {route_tight.metadata['ui_reasons']}")
    print(f"    Long Reasons:  {route_long.metadata['ui_reasons']}")
    
    assert "Tight Connection" in route_tight.metadata['ui_reasons']
    assert "Long Wait" in route_long.metadata['ui_reasons']
    assert "Tight Connection" not in route_ideal.metadata['ui_reasons']

    print("\n✅ ALL MVP TASK 3 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_3())
