from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import numpy as np
from core.data_structures import Route, RouteSegment, Passenger
from .constraints import RouteConstraints, Persona

class RouteScorer:
    """
    Unified Intelligence Branch - Phase 3.
    Decouples all business logic and persona-based ranking from the search engines.
    """
    
    @staticmethod
    async def score_route(route: Route, constraints: RouteConstraints, reliability_scores: Dict = None, passengers: List[Passenger] = None) -> float:
        w = constraints.weights
        reliability_scores = reliability_scores or {}
        passengers = passengers or [Passenger()]
        
        # 1. Base Components (Time & Cost)
        time_score = route.total_duration * w.time
        cost_score = route.total_cost * w.cost
        
        # 2. Transfer Penalty
        base_transfer_p = (len(route.transfers) ** 1.5) * w.transfer
        
        # [39.2] Passenger Persona Adjustments
        has_senior = any(p.age >= 60 for p in passengers)
        has_infant = any(p.age < 5 for p in passengers)
        is_solo_female = len(passengers) == 1 and passengers[0].gender == "F"
        
        # Seniors and infants hate transfers
        if has_senior or has_infant:
            base_transfer_p *= 2.0 
            
        # Solo female Travelers priority safety/reliability
        safety_boost = 0
        if is_solo_female:
            # Penalty for night arrivals or night transfers
            for tr in route.transfers:
                if RouteScorer.is_night_time(tr.arrival_time) or RouteScorer.is_night_time(tr.departure_time):
                    safety_boost += 2000 # High penalty for risky transfers
            
            if route.segments and RouteScorer.is_night_time(route.segments[-1].arrival_time):
                safety_boost += 1000 # Penalty for late night arrival

        transfer_penalty = base_transfer_p + safety_boost
        
        # 3. Comfort & Safety Intelligence
        comfort_adjustments = 0
        pantry_count = sum(1 for seg in route.segments if getattr(seg, 'has_pantry', False))
        
        for tr in route.transfers:
            if RouteScorer.is_night_time(tr.arrival_time):
                penalty_val = 1000 if constraints.persona != Persona.EMERGENCY else 200
                comfort_adjustments += penalty_val
        
        if route.total_duration > 600:
            comfort_adjustments -= (pantry_count * 60)
            
        # 4. Confirmation Risk
        gn_penalty = 0
        for seg in route.segments:
            if getattr(seg, 'is_unconfirmed_allowed', False):
                if constraints.persona == Persona.EMERGENCY:
                    gn_penalty += 200
                else:
                    gn_penalty += 5000
        
        # 5. Connection Survival & Availability Intelligence (Task 27.5)
        survival_prob = RouteScorer.estimate_survival(route, reliability_scores)
        survival_penalty = (1.0 - survival_prob) * 1000 
        
        # ML-based confirmation probability penalty
        avail_penalty = (1.0 - route.availability_probability) * 2000 
        
        final_score = time_score + cost_score + transfer_penalty + comfort_adjustments + gn_penalty + survival_penalty + avail_penalty
        
        # [34.2] Reliability Contextualization
        rel_reason = "Highly Reliable" if survival_prob > 0.9 else "Moderate Connection Risk" if survival_prob > 0.7 else "High Miss Risk"
        
        # [36.1] Risk Corridors Detection
        risk_penalty = 0
        risk_warnings = []
        risk_level = "LOW"
        
        # Mock high-risk corridors: North-Central (CNB-ALD), East-Coast (BBS-VSKP)
        RISK_STATIONS = {"CNB", "ALD", "PRYJ", "MGS", "DDU", "BBS", "VSKP", "GHY", "GKP"}
        
        route_stations = {s.departure_code for s in route.segments} | {s.arrival_code for s in route.segments}
        hit_risk_stations = route_stations.intersection(RISK_STATIONS)
        
        if hit_risk_stations:
            risk_count = len(hit_risk_stations)
            if risk_count >= 3:
                risk_level = "HIGH"
                risk_penalty = 2000
                risk_warnings.append("Frequent heavy delays in this corridor (3+ congestion points)")
            elif risk_count >= 1:
                risk_level = "MEDIUM"
                risk_penalty = 500
                risk_warnings.append("Passing through high-congestion zones")

        final_score = time_score + cost_score + transfer_penalty + comfort_adjustments + gn_penalty + survival_penalty + avail_penalty + risk_penalty
        
        # [34.6] Scorer Integration: Enriched Metadata
        if not hasattr(route, 'metadata') or route.metadata is None:
            route.metadata = {}
            
        route.metadata["breakdown"] = {
            "time_mins": route.total_duration,
            "cost_val": route.total_cost,
            "transfers": len(route.transfers),
            "survival_prob": round(survival_prob, 2),
            "avail_prob": round(route.availability_probability, 2),
            "comfort_penalty": comfort_adjustments,
            "risk_penalty": gn_penalty + avail_penalty + risk_penalty,
            "reliability_label": rel_reason,
            "risk_level": risk_level
        }
        
        # Human readable summary for UI
        reasons = []
        if len(route.segments) == 1: reasons.append("Direct journey")
        if survival_prob > 0.9: reasons.append("Excellent connection timing")
        if route.availability_probability > 0.8: reasons.append("High seat availability")
        if pantry_count > 0: reasons.append("Pantry car available")
        if constraints.persona == Persona.BUDGET and route.total_cost < 1000: reasons.append("Very economical")
        
        route.metadata["ui_reasons"] = reasons[:5] # Top 5 reasons
        route.metadata["risk_warnings"] = risk_warnings
        
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
