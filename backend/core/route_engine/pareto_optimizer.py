"""
⚖️ PARETO OPTIMIZER — Multi-Objective Selection Engine
Finds the non-dominated set of routes across competing objectives:
  1. Time (Total Duration)
  2. Cost (Total Fare)
  3. Comfort (Coach Class + Transfers)
  4. Reliability (Knowledge Graph historical data)
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from core.data_structures import Route
from core.knowledge.graph_store import knowledge_graph

logger = logging.getLogger(__name__)

@dataclass
class ParetoObjective:
    name: str
    value: float
    minimize: bool = True

class ParetoOptimizer:
    """
    Filters and labels routes based on the Pareto Frontier.
    Ensures users are presented with distinct, optimal choices.
    """

    def __init__(self):
        self.objectives = ["time", "cost", "comfort", "reliability"]

    def find_frontier(self, routes: List[Route]) -> List[Route]:
        """
        Implements a simple O(N^2) filter for non-dominated routes.
        For small N (typical route count < 100), this is extremely fast.
        """
        if not routes: return []
        
        frontier = []
        for r1 in routes:
            is_dominated = False
            for r2 in routes:
                if r1 == r2: continue
                if self._dominates(r2, r1):
                    is_dominated = True
                    break
            
            if not is_dominated:
                frontier.append(r1)
        
        # Add special 'Persona' tags to frontier routes
        self._tag_frontier(frontier)
        
        logger.info(f"⚖️ [PARETO] Reduced {len(routes)} routes to {len(frontier)} frontier options.")
        return frontier

    def _dominates(self, r1: Route, r2: Route) -> bool:
        """Returns True if r1 is strictly better than r2 in at least one objective and not worse in any."""
        # Objectives (normalized: lower is better)
        # 1. Time (minutes)
        # 2. Cost (fare)
        # 3. Discomfort (transfers * 100 + class_penalty)
        # 4. Unreliability (1.0 - knowledge_graph_score)
        
        o1 = self._get_objective_vector(r1)
        o2 = self._get_objective_vector(r2)
        
        better_in_any = False
        for v1, v2 in zip(o1, o2):
            if v1 > v2: # r1 is worse in this objective
                return False
            if v1 < v2: # r1 is strictly better
                better_in_any = True
                
        return better_in_any

    def _get_objective_vector(self, r: Route) -> Tuple[float, ...]:
        time_val = float(r.total_duration)
        cost_val = float(r.total_cost)
        
        # Comfort: Higher score in Route object means MORE comfort. 
        # We need to minimize DIScomfort.
        discomfort = 100.0 - (r.score or 50.0)
        
        # Reliability: Use Knowledge Graph + Route's existing score
        rel_score = knowledge_graph.get_station_reliability(r.segments[0].departure_code)
        unreliability = 1.0 - rel_score
        
        return (time_val, cost_val, discomfort, unreliability)

    def _tag_frontier(self, frontier: List[Route]):
        """Identifies 'Best in Class' for specific personas."""
        if not frontier: return
        
        # 1. Fastest
        fastest = min(frontier, key=lambda x: x.total_duration)
        if "persona_tags" not in fastest.metadata: fastest.metadata["persona_tags"] = []
        fastest.metadata["persona_tags"].append("FASTEST")
        
        # 2. Cheapest
        cheapest = min(frontier, key=lambda x: x.total_cost)
        if "persona_tags" not in cheapest.metadata: cheapest.metadata["persona_tags"] = []
        cheapest.metadata["persona_tags"].append("CHEAPEST")
        
        # 3. Most Comfortable
        most_comfy = max(frontier, key=lambda x: x.score or 0)
        if "persona_tags" not in most_comfy.metadata: most_comfy.metadata["persona_tags"] = []
        most_comfy.metadata["persona_tags"].append("LUXURY")
        
        # 4. Smart Choice (Weighted blend)
        # Often a route that isn't the best in any one thing but great overall.
        pass

# Singleton
pareto_optimizer = ParetoOptimizer()
