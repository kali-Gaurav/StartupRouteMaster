import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.route_engine.buffer_logic import buffer_optimizer

class MockStop:
    def __init__(self, id, is_major):
        self.id = id
        self.is_major_junction = is_major

def verify_task_7():
    print("=== Verifying Task 7: Layover Buffer Optimization ===")
    
    # 1. Setup Mock Cache
    s_normal = MockStop(1, False)
    s_hub = MockStop(2, True)
    cache = {1: s_normal, 2: s_hub}
    
    travel_date = datetime(2026, 6, 15) # Summer
    
    # 2. Test Normal Station
    buf_normal = buffer_optimizer.calculate_required_buffer(1, cache, travel_date)
    print(f"Normal Station Buffer: {buf_normal} mins")
    assert buf_normal == 30
    
    # 3. Test Major Hub
    buf_hub = buffer_optimizer.calculate_required_buffer(2, cache, travel_date)
    print(f"Major Hub Buffer: {buf_hub} mins")
    # Base (30) + Hub Bonus (60) = 90
    assert buf_hub == 90
    
    # 4. Test Winter Fog Factor
    winter_date = datetime(2026, 1, 15)
    buf_winter = buffer_optimizer.calculate_required_buffer(2, cache, winter_date)
    print(f"Winter Hub Buffer: {buf_winter} mins")
    # Base (30) + Hub (60) + Winter (45) = 135
    assert buf_winter == 135
    
    print("[OK] Dynamic buffers correctly calculated based on station and season.")
    print("=== Task 7 Verification Complete ===")

if __name__ == "__main__":
    verify_task_7()
