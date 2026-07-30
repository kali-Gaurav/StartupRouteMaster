"""
⚖️ PARETO OPTIMIZER — Multi-Objective Selection Engine (V2 - Diversity Aware)
Finds the non-dominated set of routes across competing objectives:
  1. Time (Total Duration)
  2. Cost (Total Fare)
  3. Comfort (Coach Class + Transfers)
  4. Reliability (Historical Data)
  5. Safety (Real-time Hazard scores)

REFACTORED: Now includes a Protection Layer to ensure Diversity.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass

from core.data_utils.structures import Route, Persona
from core.knowledge.graph_store import knowledge_graph

logger = logging.getLogger(__name__)

class ParetoOptimizer:
    """
    Filters and labels routes based on the Pareto Frontier.
    Ensures users are presented with distinct, optimal choices.
    """

    def __init__(self):
        self.objectives = ["time", "cost", "comfort", "reliability", "safety"]

    def find_frontier(self, routes: List[Route], discovery_model: Optional[Any] = None) -> List[Route]:
        """
        Implements an O(N^2) filter with dynamic Epsilon-Dominance.
        """
        if not routes: return []
        
        # [Task 12.6] Elastic Slack Calculation
        # OMNISCIENT mode wants more visibility, so we use 15% slack.
        # Standard mode uses 5%.
        from .constraints import DiscoveryModel
        slack = 0.05
        if discovery_model == DiscoveryModel.OMNISCIENT:
            slack = 5.0 # Very high slack to allow high-yield discovery results
        
        # 1. Identify "Global Best" and "Best in Tier" (Protection Layer)
        protected_ids: Set[str] = set()
        
        # --- Global Bests ---
        # Fastest
        f_best = min(routes, key=lambda x: x.total_duration)
        protected_ids.add(f_best.journey_id)
        f_best.metadata.setdefault("persona_tags", []).append("FASTEST")
        
        # Cheapest
        c_best = min(routes, key=lambda x: x.total_cost)
        protected_ids.add(c_best.journey_id)
        c_best.metadata.setdefault("persona_tags", []).append("CHEAPEST")
        
        # --- Tier Protection (Ensures 0T, 1T, 2T, 3T representation) ---
        # We protect the best route (by duration) for each transfer bucket
        tiers = {0: [], 1: [], 2: [], 3: []}
        for r in routes:
            t_count = len(r.transfers)
            if t_count in tiers: tiers[t_count].append(r)
            elif t_count > 3: tiers[3].append(r)
            
        for t_val, t_routes in tiers.items():
            if t_routes:
                t_best = min(t_routes, key=lambda x: x.total_duration)
                protected_ids.add(t_best.journey_id)
                t_best.metadata.setdefault("persona_tags", []).append(f"BEST_{t_val}T")
        
        # Safest
        s_best = max(routes, key=lambda x: getattr(x, 'safety_score', 0.5))
        protected_ids.add(s_best.journey_id)
        s_best.metadata.setdefault("persona_tags", []).append("SAFEST")
        
        # Most Comfortable
        m_best = max(routes, key=lambda x: x.score or 0)
        protected_ids.add(m_best.journey_id)
        m_best.metadata.setdefault("persona_tags", []).append("LUXURY")

        # 2. Pareto Dominance Pass
        frontier = []
        for r1 in routes:
            if r1.journey_id in protected_ids:
                frontier.append(r1)
                continue
                
            is_dominated = False
            for r2 in routes:
                if r1 == r2: continue
                if self._dominates(r2, r1, slack=slack):
                    is_dominated = True
                    break
            
            if not is_dominated:
                frontier.append(r1)
        
        # 3. Intelligent "Smart Choice" Tagging
        self._tag_smart_choice(frontier)
        
        logger.info(f"⚖️ [PARETO:V2] Yield: {len(routes)} -> {len(frontier)} (Slack: {slack*100}%, Protected: {len(protected_ids)})")
        return frontier

    def _dominates(self, r1: Route, r2: Route, slack: float = 0.05) -> bool:
        """
        Returns True if r1 is strictly better than r2 with a slack (Epsilon-Dominance).
        Slack prevents a route that is only 1% better from pruning a perfectly valid alternative.
        """
        o1 = self._get_objective_vector(r1)
        o2 = self._get_objective_vector(r2)
        
        better_in_any = False
        for v1, v2 in zip(o1, o2):
            # Epsilon Check: Is r1 significantly worse? (Adding slack to r2's limit)
            # For minimization, r1 must be <= r2 * (1 + slack) to NOT be dominated
            if v1 > v2 * (1.0 + slack):
                return False
            if v1 < v2 * (1.0 - slack):
                better_in_any = True
                
        return better_in_any

    def _get_objective_vector(self, r: Route) -> Tuple[float, ...]:
        time_val = float(r.total_duration)
        cost_val = float(r.total_cost)
        
        # Transfers: minimize transfers
        transfers = float(len(r.transfers))
        
        # Reliability: minimize unreliability
        unreliability = 1.0 - (r.reliability or 1.0)
        
        # Safety: minimize hazard (1.0 - safety_score)
        hazard = 1.0 - getattr(r, 'safety_score', 0.5)
        
        return (time_val, cost_val, transfers, unreliability, hazard)

    def _tag_smart_choice(self, frontier: List[Route]):
        if not frontier: return
        
        # Smart Choice: Weighted blend (Persona-agnostic here, but favors balance)
        # We look for a route that is in the top 20% of multiple categories
        smart_choice = min(frontier, key=lambda r: self._calculate_composite_score(r))
        smart_choice.metadata.setdefault("persona_tags", []).append("SMART_CHOICE")

    def _calculate_composite_score(self, r: Route) -> float:
        """Calculates a normalized composite score (lower is better)."""
        o = self._get_objective_vector(r)
        # Normalized Weights: Time=0.3, Cost=0.3, Comfort=0.2, Safety=0.15, Reliability=0.05
        return (o[0] * 0.3) + (o[1] * 0.3) + (o[2] * 0.2) + (o[4] * 0.15) + (o[3] * 0.05)

# Singleton
pareto_optimizer = ParetoOptimizer()
