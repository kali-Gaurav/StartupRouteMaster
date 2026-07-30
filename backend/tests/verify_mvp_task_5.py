import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.route_utils import RouteDedupFilter
from core.data_utils.structures import Route, RouteSegment

def create_mock_route(jid, departure_time, score):
    r = Route()
    s = RouteSegment(trip_id=jid, departure_stop_id=1, arrival_stop_id=2, 
                      departure_time=departure_time, arrival_time=departure_time + timedelta(hours=2),
                      duration_minutes=120, distance_km=100.0, train_number="T12625") # Same train number
    r.add_segment(s)
    r.score = float(score)
    return r

async def verify_task_5():
    print("\n>>> STARTING VERIFICATION: MVP TASK 5 (STRICT DEDUPLICATION)")
    
    base_time = datetime(2026, 3, 8, 10, 0)
    
    # 1. Prepare Routes
    # Route 1: 10:00 AM, score 500
    r1 = create_mock_route("R1", base_time, 500)
    # Route 2: 10:30 AM, score 400 (Better score, should win over R1)
    r2 = create_mock_route("R2", base_time + timedelta(minutes=30), 400)
    # Route 3: 2:00 PM, score 600 (Beyond 2h window, should stay)
    r3 = create_mock_route("R3", base_time + timedelta(hours=4), 600)
    
    routes = [r1, r2, r3]
    print(f"  Input Routes: {len(routes)}")
    
    # 2. Apply Dedup
    print("  Applying strict deduplication...")
    deduped = RouteDedupFilter.apply_strict_dedup(routes)
    
    # 3. Verify Results
    print(f"  Deduped Count: {len(deduped)}")
    
    # Expected: R2 (wins over R1) and R3 (distinct window)
    assert len(deduped) == 2
    
    dep_times = sorted([r.segments[0].departure_time for r in deduped])
    print(f"  Departure Times: {[t.strftime('%H:%M') for t in dep_times]}")
    
    assert dep_times[0] == base_time + timedelta(minutes=30) # R2 won
    assert dep_times[1] == base_time + timedelta(hours=4) # R3 stayed
    
    # Verify score winner
    scores = [r.score for r in deduped]
    print(f"  Remaining Scores: {scores}")
    assert 400.0 in scores
    assert 600.0 in scores
    assert 500.0 not in scores
    
    print("\n✅ ALL MVP TASK 5 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_5())
