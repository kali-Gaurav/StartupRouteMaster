import time
from datetime import datetime, timedelta
from core.data_structures import DynamicWaitConfig
from core.dynamic_logic import is_valid_transfer

def benchmark_is_valid_transfer():
    config = DynamicWaitConfig()
    arr = 600 # 10:00 AM
    dep = 720 # 12:00 PM
    journey = 300 # 5 hours
    
    start = time.time()
    iterations = 100000
    for _ in range(iterations):
        is_valid_transfer(arr, dep, journey, config, "NDLS")
    end = time.time()
    
    avg_ms = (end - start) * 1000 / iterations
    print(f"Benchmark: {iterations} iterations took {end-start:.4f}s")
    print(f"Average time per check: {avg_ms:.6f} ms")
    assert avg_ms < 0.1 # Should be well under 2ms

def verify_scenarios():
    config = DynamicWaitConfig(min_wait_minutes=15, max_wait_minutes=240, beta=0.5)
    
    # Scenario 1: Hub station NDLS (1.5x max wait)
    # Short journey (120 min) -> base max_w ~= 67 min. With NDLS -> 67 * 1.5 ~= 100 min.
    assert is_valid_transfer(600, 680, 120, config, "NDLS") is True
    assert is_valid_transfer(600, 710, 120, config, "NDLS") is False # 110 min wait > 100
    print("Scenario 1 (Hub): OK")
    
    # Scenario 2: High Waiting Ratio
    # Journey 30 min, Wait 120 min -> ratio = 120/150 = 0.8 > 0.4.
    assert is_valid_transfer(600, 720, 30, config) is False
    print("Scenario 2 (Ratio): OK")
    
    # Scenario 3: Midnight Crossing
    # Arr 23:00 (1380), Dep 01:00 (60) -> 120 min wait.
    # Journey 600 min -> max_w ~= 154 min.
    assert is_valid_transfer(1380, 60, 600, config) is True
    print("Scenario 3 (Midnight): OK")

if __name__ == "__main__":
    verify_scenarios()
    benchmark_is_valid_transfer()
    print("TASK 1 VERIFICATION COMPLETE")
