"""
Sovereign A/B Testing & Optimization Engine
===========================================
Patent Innovation #4: Autonomous optimization of behavioral nudges.

This engine determines which "variant" of a nudge (tone, incentive, copy)
performs best for specific user segments and corridors. It uses a 
Multi-Armed Bandit (MAB) strategy to maximize network redistribution.
"""

import logging
import random
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

from core.sovereign.edr_algorithm import NudgeType

logger = logging.getLogger("sovereign.ab_engine")

class ExperimentVariant(str, Enum):
    CONTROL = "CONTROL"
    VARIANT_A = "VARIANT_A"  # Focus on Financial Savings (Incentives)
    VARIANT_B = "VARIANT_B"  # Focus on Comfort & Safety (NPC Pressure)
    VARIANT_C = "VARIANT_C"  # Focus on Time & Efficiency (Quickest Route)

class SovereignABEngine:
    """
    Autonomous optimization engine for EDR nudges and Shadow-Guide guidance.
    """

    def __init__(self):
        self.experiments = {
            "nudge_tone_optimization": {
                "variants": [ExperimentVariant.VARIANT_A, ExperimentVariant.VARIANT_B, ExperimentVariant.VARIANT_C],
                "weights": [0.33, 0.33, 0.34],
                "active": True
            },
            "incentive_elasticity_test": {
                "variants": ["BASE", "BOOST_20", "BOOST_50"],
                "weights": [0.5, 0.25, 0.25],
                "active": True
            }
        }
        logger.info("[AB_ENGINE] Sovereign A/B Engine initialized")

    def get_user_variant(self, user_id: str, experiment_id: str) -> str:
        """
        Deterministically assigns a user to a variant using hashing.
        Ensures consistent experience for the same user.
        """
        if experiment_id not in self.experiments or not self.experiments[experiment_id]["active"]:
            return ExperimentVariant.CONTROL.value

        exp = self.experiments[experiment_id]
        variants = exp["variants"]
        weights = exp["weights"]

        # Hash user_id + experiment_id to get a stable float [0.0, 1.0)
        hash_val = hashlib.md5(f"{user_id}:{experiment_id}".encode()).hexdigest()
        normalized_hash = int(hash_val, 16) % 100 / 100.0

        # Select variant based on cumulative weights
        cumulative_weight = 0.0
        for i, weight in enumerate(weights):
            cumulative_weight += weight
            if normalized_hash < cumulative_weight:
                return variants[i]

        return variants[0]

    def optimize_nudge(self, user_id: str, nudge: Any) -> Any:
        """
        Adjusts nudge parameters based on the assigned A/B variant.
        """
        variant = self.get_user_variant(user_id, "nudge_tone_optimization")
        
        # Initialize metadata if not present
        if not hasattr(nudge, "metadata") or nudge.metadata is None:
            nudge.metadata = {}

        if variant == ExperimentVariant.VARIANT_A:
            # Variant A: Financial. Boost headline with incentive amount.
            nudge.headline = f"Get ₹{int(nudge.incentive_value)} Cashback Now!"
            nudge.metadata["ab_variant"] = "FINANCIAL"
        elif variant == ExperimentVariant.VARIANT_B:
            # Variant B: Comfort. Focus on pressure delta.
            nudge.headline = "Escape the Crowds: Comfort Option"
            nudge.description = "Travel in peace. This train is significantly less crowded."
            nudge.metadata["ab_variant"] = "COMFORT"
        elif variant == ExperimentVariant.VARIANT_C:
            # Variant C: Time.
            nudge.headline = "Fast-Track Your Journey"
            nudge.metadata["ab_variant"] = "EFFICIENCY"
            
        return nudge

    async def record_conversion(self, user_id: str, experiment_id: str, variant: str, goal: str):
        """
        Records a successful conversion (e.g. nudge click or booking).
        This data feeds back into the weight optimization (Multi-Armed Bandit).
        """
        logger.info(f"[AB_ENGINE] Conversion recorded: {user_id} | {experiment_id} | {variant} | {goal}")
        
        try:
            from services.multi_layer_cache import multi_layer_cache
            if multi_layer_cache.redis:
                key = f"ab:metrics:{experiment_id}:{variant}"
                await multi_layer_cache.redis.hincrby(key, goal, 1)
                await multi_layer_cache.redis.hincrby(key, "total_hits", 1)
                
                # Periodically trigger weight rebalancing (e.g. every 10 conversions)
                total_conversions = await multi_layer_cache.redis.get(f"ab:total_conversions:{experiment_id}") or 0
                total_conversions = int(total_conversions) + 1
                await multi_layer_cache.redis.set(f"ab:total_conversions:{experiment_id}", total_conversions)
                
                if total_conversions % 10 == 0:
                    await self.rebalance_weights(experiment_id)
        except Exception as e:
            logger.error(f"[AB_ENGINE] Failed to record metrics: {e}")

    async def rebalance_weights(self, experiment_id: str):
        """
        [MAB] Updates experiment weights based on performance using Epsilon-Greedy.
        """
        if experiment_id not in self.experiments:
            return

        from services.multi_layer_cache import multi_layer_cache
        if not multi_layer_cache.redis:
            return

        exp = self.experiments[experiment_id]
        variants = exp["variants"]
        
        performance = {}
        for variant in variants:
            key = f"ab:metrics:{experiment_id}:{variant}"
            metrics = await multi_layer_cache.redis.hgetall(key)
            if metrics:
                hits = int(metrics.get(b"total_hits", 1))
                conversions = int(metrics.get(b"conversion", 0))
                performance[variant] = conversions / hits
            else:
                performance[variant] = 0.0

        # Epsilon-Greedy Logic: 20% exploration, 80% exploitation
        epsilon = 0.2
        best_variant = max(performance, key=performance.get)
        
        new_weights = []
        num_variants = len(variants)
        for variant in variants:
            if variant == best_variant:
                weight = (1 - epsilon) + (epsilon / num_variants)
            else:
                weight = epsilon / num_variants
            new_weights.append(round(weight, 3))

        exp["weights"] = new_weights
        logger.info(f"🔄 [AB_ENGINE] Rebalanced Weights for {experiment_id}: {new_weights} (Best: {best_variant})")

# Singleton
ab_engine = SovereignABEngine()
