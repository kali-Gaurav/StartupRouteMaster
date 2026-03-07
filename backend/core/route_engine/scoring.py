from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import numpy as np
from core.data_structures import Route, RouteSegment
from .constraints import RouteConstraints, Persona

class RouteScorer:
    """
    Unified Intelligence Branch - Phase 3.
    Decouples all business logic and persona-based ranking from the search engines.
    """
    
    @staticmethod
    async def score_route(route: Route, constraints: RouteConstraints, reliability_scores: Dict = None) -> float:
        w = constraints.weights
        reliability_scores = reliability_scores or {}
        
        # 1. Base Components (Time & Cost)
        time_score = route.total_duration * w.time
        cost_score = route.total_cost * w.cost
        
        # 2. Transfer Penalty
        transfer_penalty = (len(route.transfers) ** 1.5) * w.transfer
        
        # 3. Comfort & Safety Intelligence
        comfort_adjustments = 0
        for tr in route.transfers:
            if RouteScorer.is_night_time(tr.arrival_time):
                penalty_val = 1000 if constraints.persona != Persona.EMERGENCY else 200
                comfort_adjustments += penalty_val
        
        if route.total_duration > 600:
            pantry_count = sum(1 for seg in route.segments if getattr(seg, 'has_pantry', False))
            comfort_adjustments -= (pantry_count * 60)
            
        # 4. Confirmation Risk
        gn_penalty = 0
        for seg in route.segments:
            if getattr(seg, 'is_unconfirmed_allowed', False):
                if constraints.persona == Persona.EMERGENCY:
                    gn_penalty += 200
                else:
                    gn_penalty += 5000
        
        # 5. Connection Survival
        survival_prob = RouteScorer.estimate_survival(route, reliability_scores)
        survival_penalty = (1.0 - survival_prob) * 1000
        
        final_score = time_score + cost_score + transfer_penalty + comfort_adjustments + gn_penalty + survival_penalty
        
        if not hasattr(route, 'metadata') or route.metadata is None:
            route.metadata = {}
            
        route.metadata["breakdown"] = {
            "time_mins": route.total_duration,
            "cost_val": route.total_cost,
            "transfers": len(route.transfers),
            "survival_prob": round(survival_prob, 2),
            "comfort_penalty": comfort_adjustments,
            "risk_penalty": gn_penalty
        }
        
        return float(final_score)

    @staticmethod
    def score_routes_batch(routes: List[Route], constraints: RouteConstraints) -> List[Route]:
        """Task 16.4: Fast vectorized base scoring for large result sets."""
        if not routes: return []
        
        durations = np.array([r.total_duration for r in routes], dtype=np.float32)
        costs = np.array([r.total_cost for r in routes], dtype=np.float32)
        transfers = np.array([len(r.transfers) for r in routes], dtype=np.float32)
        
        w = constraints.weights
        # Vectorized base score
        batch_scores = (durations * w.time) + (costs * w.cost) + (np.power(transfers, 1.5) * w.transfer)
        
        for i, r in enumerate(routes):
            r.score = float(batch_scores[i])
            
        return routes

    @staticmethod
    def is_night_time(dt: datetime) -> bool:
        """Window: 23:30 to 05:00."""
        h, m = dt.hour, dt.minute
        return (h == 23 and m >= 30) or (h < 5)

    @staticmethod
    def estimate_survival(route: Route, scores: Dict) -> float:
        if not route.transfers: return 1.0
        prob = 1.0
        for i, tr in enumerate(route.transfers):
            trip_id = route.segments[i].trip_id
            score = scores.get((trip_id, tr.station_id), 0.95)
            buffer_boost = min(1.0, tr.duration_minutes / 120.0)
            adjusted_prob = score + ((1.0 - score) * buffer_boost)
            prob *= adjusted_prob
        return prob
