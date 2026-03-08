import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.ml.availability_heuristic import availability_heuristic

async def verify_task_16():
    print("\n>>> STARTING VERIFICATION: MVP TASK 16 (ML HEURISTIC)")
    
    # 1. Test Proximity Advantage (Long term + 1AC)
    print("\n[16.1 & 16.2] Testing Long-term 1AC (High prob)...")
    date_long = datetime.now() + timedelta(days=70)
    prob_long = availability_heuristic.estimate_confirmation_chance("12625", "1A", date_long)
    print(f"  70 days away, 1AC: {prob_long:.4f}")
    # 0.65 + 0.25 (1A) + 0.15 (>60d) = 1.05 -> clamped to 0.99
    assert prob_long > 0.9
    
    # 2. Test Last Minute Penalty (Tomorrow + Sleeper)
    print("\n[16.2 & 16.3] Testing Last-minute Sleeper (Low prob)...")
    date_near = datetime.now() + timedelta(days=1)
    prob_near = availability_heuristic.estimate_confirmation_chance("12625", "SL", date_near)
    print(f"  1 day away, SL: {prob_near:.4f}")
    # 0.65 - 0.2 (SL) - 0.4 (<2d) + some buffer check
    assert prob_near <= 0.25
    
    # 3. Test Multi-leg Complexity Penalty (Subtask 16.4)
    print("\n[16.4] Testing Multi-leg Complexity Penalty...")
    
    class MockSeg:
        def __init__(self, tno, dt):
            self.train_number = tno
            self.departure_time = dt
            self.metadata = {"class_type": "3A"}

    date_fixed = datetime.now() + timedelta(days=10)
    seg1 = MockSeg("12625", date_fixed)
    seg2 = MockSeg("12626", date_fixed + timedelta(hours=10))
    
    score_direct = availability_heuristic.get_route_availability_score([seg1])
    score_multi = availability_heuristic.get_route_availability_score([seg1, seg2])
    
    print(f"  Direct Score: {score_direct:.4f}")
    print(f"  Multi-leg Score: {score_multi:.4f}")
    
    # Multi-leg should be lower due to product AND the 10% penalty
    # seg1 prob: 0.65 + 0.05 (3A) = 0.7
    # multi should be: (0.7 * 0.7) * 0.9 = 0.441
    assert score_multi < (score_direct * score_direct)
    print(f"  SUCCESS: Multi-leg penalty verified (ratio: {score_multi / (score_direct*score_direct):.2f})")

    print("\n✅ ALL MVP TASK 16 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_16())
