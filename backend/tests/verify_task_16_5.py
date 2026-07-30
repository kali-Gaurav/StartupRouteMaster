import sys
import os
import numpy as np
import time

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.algo_utils import find_pareto_frontier

def verify_task_16_5():
    print("\n>>> Verifying Task 16.5: Pareto Frontier in Numpy")
    
    # 1. Simple Manual Test
    # Points: (5, 10), (10, 5), (10, 10), (7, 7)
    # Pareto: (5, 10), (10, 5), (7, 7)
    # (10, 10) is dominated by all.
    pts = np.array([
        [5, 10],
        [10, 5],
        [10, 10],
        [7, 7]
    ], dtype=np.float32)
    
    mask = find_pareto_frontier(pts)
    print(f"  Points: {pts.tolist()}")
    print(f"  Pareto Mask: {mask}")
    
    if not np.array_equal(mask, [True, True, False, True]):
        print("❌ FAILURE: Pareto frontier incorrect for manual test.")
        return False
        
    # 2. Benchmark with 1000 points
    num_pts = 1000
    random_pts = np.random.uniform(1, 100, (num_pts, 2))
    
    start = time.perf_counter()
    frontier_mask = find_pareto_frontier(random_pts)
    latency = (time.perf_counter() - start) * 1000
    
    num_on_frontier = np.sum(frontier_mask)
    print(f"  Benchmark: {num_pts} points processed in {latency:.2f}ms")
    print(f"  Frontier size: {num_on_frontier}")
    
    if latency > 50.0: # Pareto can be slow if not carefully implemented, but 1k should be fast
        print(f"⚠️ WARNING: Pareto filtering took {latency:.2f}ms.")

    print("\n✅ TASK 16.5 VERIFIED: find_pareto_frontier is logically correct.")
    return True

if __name__ == "__main__":
    verify_task_16_5()
