from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import numpy as np

logger = logging.getLogger(__name__)
from core.data_structures import Route, RouteSegment, Passenger, ensure_datetime
from .constraints import RouteConstraints, Persona

class RouteScorer:
    """
    Unified Intelligence Branch - Phase 3.
    Decouples all business logic and persona-based ranking from the search engines.
    """
    
    @staticmethod
    async def score_route(route: Route, constraints: RouteConstraints, reliability_scores: Dict = None, passengers: List[Passenger] = None) -> float:
        """Async wrapper for backward compatibility."""
        return RouteScorer.score_route_sync(route, constraints, reliability_scores, passengers)

    @staticmethod
    def score_route_sync(route: Route, constraints: RouteConstraints, reliability_scores: Dict = None, passengers: List[Passenger] = None) -> float:
        try:
            return RouteScorer._score_route_impl(route, constraints, reliability_scores, passengers)
        except Exception as e:
            import traceback
            logger.error(f"CRITICAL: Scoring Error for route {route}: {e}")
            logger.error(traceback.format_exc())
            return 0.0

    @staticmethod
    def _score_route_impl(route: Route, constraints: RouteConstraints, reliability_scores: Dict = None, passengers: List[Passenger] = None) -> float:
        # [Task 25.1] Get specialized score based on persona for primary ranking
        persona_score = RouteScorer.get_persona_score(route, constraints)
        
        w = constraints.weights
        reliability_scores = reliability_scores or {}
        passengers = passengers or [Passenger()]
        
        # [3.1] Risk Thresholds
        MIN_SAFE_TRANSFER = 30
        MAX_COMFORT_TRANSFER = 360 # 6 hours
        
        # 1. Base Components (Time & Cost)
        time_score = (route.total_duration or 0) * w.time
        cost_score = (route.total_cost or 0.0) * w.cost
        
        # 2. Advanced Transfer Penalty
        base_transfer_p = (len(route.transfers) ** 1.5) * w.transfer
        smart_transfer_penalty = 0
        
        for tr in route.transfers:
            dur = getattr(tr, 'duration_minutes', 0) or 0
            if dur < MIN_SAFE_TRANSFER:
                diff = MIN_SAFE_TRANSFER - dur
                smart_transfer_penalty += (diff ** 2) * 10 
            
            if dur > MAX_COMFORT_TRANSFER:
                extra_hours = (dur - MAX_COMFORT_TRANSFER) / 60.0
                smart_transfer_penalty += extra_hours * 200 
        
        # Passenger Persona Adjustments
        has_senior = any(p.age >= 60 for p in passengers)
        has_infant = any(p.age < 5 for p in passengers)
        is_solo_female = len(passengers) == 1 and passengers[0].gender == "F"
        
        if has_senior or has_infant:
            base_transfer_p *= 2.0 
            
        safety_boost = 0
        if is_solo_female:
            for tr in route.transfers:
                if RouteScorer.is_night_time(tr.arrival_time) or RouteScorer.is_night_time(tr.departure_time):
                    safety_boost += 2000 
            
            if route.segments and RouteScorer.is_night_time(route.segments[-1].arrival_time):
                safety_boost += 1000 

        transfer_penalty = base_transfer_p + safety_boost
        
        # 3. Comfort & Safety Intelligence
        comfort_adjustments = 0
        pantry_count = sum(1 for seg in route.segments if getattr(seg, 'has_pantry', False))
        if route.total_duration > 720: 
            comfort_adjustments -= (pantry_count * 500)
        elif route.total_duration > 360:
            comfort_adjustments -= (pantry_count * 200)
            
        for tr in route.transfers:
            if RouteScorer.is_night_time(tr.arrival_time) or RouteScorer.is_night_time(tr.departure_time):
                penalty_val = 1500 if constraints.persona != Persona.EMERGENCY else 300
                comfort_adjustments += penalty_val
        
        gn_penalty = 0
        for seg in route.segments:
            if getattr(seg, 'quota', 'GN') == 'GN':
                train_no = str(getattr(seg, 'train_number', '0'))
                if train_no.startswith(('12', '22')):
                    gn_penalty += 800
            
            if getattr(seg, 'is_unconfirmed_allowed', False):
                if constraints.persona == Persona.EMERGENCY:
                    gn_penalty += 400
                else:
                    gn_penalty += 6000 
        
        # 5. Connection Survival & Availability Intelligence
        survival_prob = RouteScorer.estimate_survival(route, reliability_scores)
        if survival_prob is None: survival_prob = 1.0
        survival_penalty = (1.0 - survival_prob) * 1000 
        
        avail_prob = getattr(route, 'availability_probability', 0.9)
        if avail_prob is None: avail_prob = 0.9
        avail_penalty = (1.0 - avail_prob) * 2000 
        
        # Risk Corridors
        risk_penalty = 0
        risk_warnings = []
        risk_level = "LOW"
        RISK_STATIONS = {"CNB", "ALD", "PRYJ", "MGS", "DDU", "BBS", "VSKP", "GHY", "GKP"}
        
        route_stations = set()
        for s in route.segments:
            if hasattr(s, 'departure_code'): route_stations.add(s.departure_code)
            if hasattr(s, 'arrival_code'): route_stations.add(s.arrival_code)
            
        hit_risk_stations = route_stations.intersection(RISK_STATIONS)
        if hit_risk_stations:
            risk_count = len(hit_risk_stations)
            if risk_count >= 3:
                risk_level = "HIGH"; risk_penalty = 2000
                risk_warnings.append("Frequent heavy delays in this corridor")
            elif risk_count >= 1:
                risk_level = "MEDIUM"; risk_penalty = 500
                risk_warnings.append("Passing through high-congestion zones")

        # Hydrate Metadata
        if not hasattr(route, 'metadata') or route.metadata is None:
            route.metadata = {}
            
        route.metadata["breakdown"] = {
            "time_mins": route.total_duration,
            "cost_val": route.total_cost,
            "transfers": len(route.transfers),
            "smart_transfer_penalty": smart_transfer_penalty,
            "survival_prob": round(survival_prob, 2),
            "avail_prob": round(avail_prob, 2),
            "comfort_penalty": comfort_adjustments,
            "risk_penalty": gn_penalty + avail_penalty + risk_penalty,
            "risk_level": risk_level
        }
        route.metadata["persona_rank_score"] = persona_score
        
        # Human readable summary
        reasons = []
        if any((getattr(tr, 'duration_minutes', 0) or 0) < 30 for tr in route.transfers): reasons.append("Tight Connection")
        if any((getattr(tr, 'duration_minutes', 0) or 0) > 360 for tr in route.transfers): reasons.append("Long Wait")
        if len(route.segments) == 1: reasons.append("Direct journey")
        if survival_prob > 0.9: reasons.append("Highly Reliable")
        if avail_prob > 0.8: reasons.append("High seat availability")
        
        route.metadata["ui_reasons"] = reasons[:5]
        route.metadata["risk_warnings"] = risk_warnings
        
        # [Task 25.1] The actual score returned is the persona-optimized one
        return float(persona_score)

    @staticmethod
    def get_persona_score(route: Route, constraints: RouteConstraints) -> float:
        """
        [Task 25.1-25.5] Specialized Persona-Based Multi-Objective Scoring.
        Lower is better.
        """
        p = constraints.persona
        
        # [Task 25.2] BUDGET: Primary=Cost, Secondary=Duration
        if p == Persona.BUDGET or p == Persona.ECONOMY:
            return (route.total_cost * 1.0) + (route.total_duration * 0.1)
            
        # [Task 25.3] FAST: Primary=Duration, Secondary=Cost
        if p == Persona.FAST:
            return (route.total_duration * 1.0) + (route.total_cost * 0.05)
            
        # [Task 25.4] EMERGENCY: Primary=Departure Time (Soonest), Secondary=Duration
        if p == Persona.EMERGENCY:
            now = datetime.now()
            first_dep = ensure_datetime(route.segments[0].departure_time) if route.segments else now
            wait_from_now = max(0, (first_dep - now).total_seconds() / 60.0)
            return (wait_from_now * 5.0) + (route.total_duration * 1.0) # High weight on immediate departure
            
        # [Task 25.5] COMFORT: Primary=Transfers, Secondary=Score
        if p == Persona.COMFORT:
            transfer_penalty = len(route.transfers) * 2000 # Double penalty for comfort
            return transfer_penalty + (route.total_duration * 0.5)
            
        # Default: Standard Multi-objective
        return (route.total_duration * 0.6) + (route.total_cost * 0.2) + (len(route.transfers) * 300)

    @staticmethod
    def score_routes_batch(routes: List[Route], constraints: RouteConstraints) -> List[Route]:
        """Fast vectorized base scoring."""
        if not routes: return []
        durations = np.array([r.total_duration for r in routes], dtype=np.float32)
        costs = np.array([r.total_cost for r in routes], dtype=np.float32)
        transfers = np.array([len(r.transfers) for r in routes], dtype=np.float32)
        w = constraints.weights
        batch_scores = (durations * w.time) + (costs * w.cost) + (np.power(transfers, 1.5) * w.transfer)
        for i, r in enumerate(routes):
            r.score = float(batch_scores[i])
        return routes

    @staticmethod
    def is_night_time(dt: datetime) -> bool:
        if not dt: return False
        h, m = dt.hour, dt.minute
        return (h == 23 and m >= 30) or (h < 5)

    @staticmethod
    def estimate_survival(route: Route, scores: Dict) -> float:
        if not route.transfers: return 1.0
        prob = 1.0
        for i, tr in enumerate(route.transfers):
            trip_id = route.segments[i].trip_id
            score = scores.get((trip_id, tr.station_id), 0.95)
            if score is None: score = 0.95
            dur_mins = getattr(tr, 'duration_minutes', 0) or 0
            buffer_boost = min(1.0, dur_mins / 120.0)
            adjusted_prob = score + ((1.0 - score) * buffer_boost)
            prob *= adjusted_prob
        return prob
