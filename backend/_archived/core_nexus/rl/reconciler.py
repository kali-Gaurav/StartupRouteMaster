import logging
import numpy as np
import asyncio
import time
from typing import Dict, List, Optional
from core.nexus.bootstrapper import nexus_boot
from core.nexus.state import SystemState

logger = logging.getLogger("nexus.rl.reconciler")

class RLPricingReconciler:
    """[Task 7.1 & 7.3] Online Learning Reconciler for Dynamic Pricing.
    Adjusts 'exploration' and 'exploitation' weights based on revenue delta.
    """
    
    def __init__(self):
        # Weights for [Demand, Occupancy, Time, Popularity]
        self.weights = np.array([0.7, 0.5, 0.25, 0.25])
        self.learning_rate = 0.01
        self.epsilon = 0.1 # Exploration rate
        self._history: List[Dict] = []
        self._initialized = False

    async def init(self):
        """[Task 7.10] Register and start the Reconciliation Loop."""
        logger.info("🧠 [NEXUS:RL] Pricing Reconciler Node Initialized.")
        self._initialized = True
        asyncio.create_task(self._reconciliation_loop())

    async def _reconciliation_loop(self):
        """[Task 7.4] Periodic Policy-Update Sentinel."""
        while True:
            # [Task 21] Heartbeat
            from core.nexus.bootstrapper import nexus_boot
            nexus_boot.recovery.record_heartbeat("rl_pricing")
            
            await asyncio.sleep(300) # Reconcile every 5 minutes
            if not self._history:
                continue
            
            logger.info(f"🧠 [NEXUS:RL] Reconciling {len(self._history)} transactions...")
            await self._update_policy()
            self._history = []

    async def record_interaction(self, state: np.ndarray, action: float, reward: float):
        """[Task 7.3] Unified Reward Signal Consolidation."""
        self._history.append({
            "state": state,
            "action": action,
            "reward": reward,
            "timestamp": time.time()
        })

    async def _update_policy(self):
        """[Task 7.4] Stochastic Gradient Ascent for Reward Optimization."""
        # This is a simplified Online RL Update
        for entry in self._history:
            state = entry["state"]
            reward = entry["reward"]
            
            # Adjust weights proportionally to state-importance and reward
            # If reward is high, strengthen the features that were high in that state
            delta = self.learning_rate * reward * state
            self.weights = np.clip(self.weights + delta, 0.1, 2.0)
            
        logger.info(f"🧠 [NEXUS:RL] Policy Updated. New Weights: {self.weights}")

    def get_optimal_multiplier(self, state: np.ndarray) -> float:
        """[Task 7.2] High-Performance NumPy Vectorized Inference."""
        # Weighted Summer of State Features
        raw_multiplier = np.dot(state, self.weights)
        
        # Add Exploration (Epsilon-Greedy)
        if np.random.random() < self.epsilon:
            raw_multiplier *= (1.0 + (np.random.normal(0, 0.05)))
            
        return float(np.clip(raw_multiplier, 0.8, 2.5))

rl_reconciler = RLPricingReconciler()
