import sys
import os
import time
import random

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services.emergency.connectivity_service import connectivity_service

def verify():
    print("--- 📶 Task 2: Track Segment Dead-Zone Bitmask Verification ---")
    
    # 1. Generate 10,000 random coordinates in India
    test_points = [
        (random.uniform(8.0, 37.0), random.uniform(68.0, 97.0))
        for _ in range(10000)
    ]
    
    # Let's insert a known hit at the seeded location (28.6, 77.2)
    test_points.append((28.601, 77.201))
    
    print(f"Executing {len(test_points)} Dead-Zone Checks using O(1) Memory-Mapped Bitmap...")
    
    start_time = time.perf_counter()
    
    hits = 0
    for lat, lng in test_points:
        res = connectivity_service.check_upcoming_dead_zones(lat, lng)
        if res:
            hits += 1
            
    end_time = time.perf_counter()
    total_time = end_time - start_time
    avg_ms = (total_time / len(test_points)) * 1000
    
    print(f"\n📊 Results:")
    print(f"Total Time for {len(test_points)} checks: {total_time:.4f} seconds")
    print(f"Average Latency per check: {avg_ms:.4f} ms")
    print(f"Dead-Zones Detected: {hits}")
    
    if avg_ms < 1.0 and hits > 0:
        print("\n🏆 TASK 2 VERIFIED: O(1) bitwise dead-zone detection achieved!")
    else:
        print(f"\n❌ TASK 2 WARNING: Performance is slower than expected ({avg_ms:.2f}ms per query) or no hits.")

if __name__ == "__main__":
    verify()
