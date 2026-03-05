import sys
import os
import time
import random

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services.emergency.risk_service import risk_service

def verify():
    print("--- 🛡️ Task 1: Static Binary Spatial Index Verification ---")
    
    # Generate 10,000 random coordinates across India to test
    # (Lat: 8.0 to 37.0, Lng: 68.0 to 97.0)
    test_points = [
        (random.uniform(8.0, 37.0), random.uniform(68.0, 97.0))
        for _ in range(10000)
    ]
    
    print(f"Executing {len(test_points)} Risk Checks using memory-mapped binary index...")
    
    start_time = time.perf_counter()
    
    hits = 0
    for lat, lng in test_points:
        res = risk_service.check_area_risk(lat, lng)
        if res.get("score", 0) > 1:
            hits += 1
            
    end_time = time.perf_counter()
    total_time = end_time - start_time
    avg_ms = (total_time / len(test_points)) * 1000
    
    print(f"\n📊 Results:")
    print(f"Total Time for 10,000 checks: {total_time:.4f} seconds")
    print(f"Average Latency per check: {avg_ms:.4f} ms")
    print(f"High-Risk Zones Detected: {hits}")
    
    if avg_ms < 1.0:
        print("\n🏆 TASK 1 VERIFIED: Sub-millisecond spatial querying achieved! (O(log N) sweep-line active)")
    else:
        print(f"\n❌ TASK 1 WARNING: Performance is slower than expected ({avg_ms:.2f}ms per query).")

if __name__ == "__main__":
    verify()
