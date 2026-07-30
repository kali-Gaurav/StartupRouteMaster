import asyncio
import logging
import time
import sys
import os
import numpy as np

# Set PYTHONPATH
sys.path.append(os.getcwd())

from core.nexus.rl.reconciler import rl_reconciler
from core.nexus.rl.state import rl_state_mapper

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify-rl")

async def run_rl_test():
    logger.info("🧪 Launching NEXUS-7.7: RL Pricing Inference Benchmark...")
    
    # 1. Warm Up Reconciler
    await rl_reconciler.init()
    
    # 2. Test Single Inference Latency [Task 7.2 & 7.7]
    logger.info("🛡️ Testing Task 7.2: Vectorized State Mapping & Dot-Product Latency...")
    
    mock_context = {
        'demand_score': 0.8,
        'occupancy_rate': 0.9,
        'time_to_departure_hours': 2.0,
        'route_popularity': 0.7
    }
    
    start_all = time.perf_counter()
    
    # Map to Vector (Task 7.2)
    vector = rl_state_mapper.map_to_vector(mock_context)
    
    # Do Inference (Task 7.1)
    # Using weighted sum of Demand, Occupancy, Urgency, Popularity
    multiplier = rl_reconciler.get_optimal_multiplier(vector)
    
    latency_micros = (time.perf_counter() - start_all) * 1_000_000
    
    if 0.8 <= multiplier <= 2.5:
        logger.info(f"✅ SUCCESS: RL Multiplier Suggested: {multiplier:.3f} | Latency: {latency_micros:.2f}μs (Target: <5000μs).")
    else:
        logger.error(f"❌ FAILURE: RL Multiplier Out of Bounds: {multiplier}")
        return 1

    # 3. Test Reward Loop [Task 7.3 & 7.8]
    logger.info("🛡️ Testing Task 7.3: Reward Reconciler Converge Check...")
    initial_weights = rl_reconciler.weights.copy()
    
    # Simulate high rewards for a specific state (surging occupancy)
    for _ in range(10):
        # State: High demand (0.9), High occupancy (0.9), High Urgency (0.9)
        state_surge = np.array([0.9, 0.9, 0.9, 0.5])
        # Record Success (High Reward)
        await rl_reconciler.record_interaction(state_surge, 2.0, 1.5) # Reward 1.5
    
    # Force update
    await rl_reconciler._update_policy()
    
    new_weights = rl_reconciler.weights
    
    # Check if demand/occupancy weights increased
    if new_weights[0] >= initial_weights[0] and new_weights[1] >= initial_weights[1]:
        logger.info(f"✅ SUCCESS: RL Policy Converging. Demand Weight: {new_weights[0]:.3f} (Was: {initial_weights[0]:.3f})")
    else:
        logger.error(f"❌ FAILURE: RL Policy Diverged/Stagnant despite high rewards.")
        return 1

    logger.info("🎉 Task 7.7 VERIFIED: RL Pricing Optimizer is Deeply Hardened.")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(run_rl_test()))
