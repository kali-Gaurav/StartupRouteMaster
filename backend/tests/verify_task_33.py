import numpy as np
import time
from utils.algo_utils import find_pareto_frontier

def verify_task_33_logic():
    print("\n>>> VERIFYING TASK 33: DOMINANCE FILTERING TUNING")
    
    # 1. Setup synthetic routes
    # Dim 0: Arrival (lower is better)
    # Dim 1: Score (lower is better)
    # Dim 2: Cost (lower is better)
    # Dim 3: Transfers (lower is better)
    
    routes = np.array([
        [100, 50, 1000, 0], # A: Fast, Low Score, Expensive, Direct
        [200, 40, 200, 1],  # B: Slower, Lower Score, Cheap, 1-T
        [150, 60, 500, 1],  # C: Mid Speed, Mid Score, Mid Price, 1-T
        [100, 50, 1000, 0], # D: Duplicate of A
        [300, 80, 100, 2],  # E: Very Slow, High Score, Very Cheap, 2-T
        [100, 55, 1100, 0], # F: Dominated by A (Slower/More Expensive)
    ], dtype=np.float64)
    
    # 2. Run Pareto
    start = time.perf_counter()
    mask = find_pareto_frontier(routes)
    latency = (time.perf_counter() - start) * 1000
    
    print(f"  Processed {len(routes)} points in {latency:.4f}ms")
    
    # Indices that should be kept:
    # 0 (A) - Fast
    # 1 (B) - Cheap/Optimal
    # 2 (C) - Maybe? Arrival 150 < 200 (B), but Cost 500 > 200 (B). YES, it's optimal vs B on time.
    # 4 (E) - Very Cheap
    # 5 (F) - NO, dominated by A in Score and Cost
    
    kept_indices = np.where(mask)[0]
    print(f"  Indices kept: {kept_indices}")
    
    assert 0 in kept_indices
    assert 1 in kept_indices
    assert 2 in kept_indices
    assert 4 in kept_indices
    assert 5 not in kept_indices
    
    print("✅ TASK 33 LOGIC VERIFIED: Multi-dimensional variety preserved.")

if __name__ == "__main__":
    verify_task_33_logic()
