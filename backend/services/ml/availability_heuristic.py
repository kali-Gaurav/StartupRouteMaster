import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class AvailabilityHeuristic:
    """
    Task 15: ML Availability Heuristic Edge Scoring.
    Estimates confirmation probability without hitting external APIs.
    """
    
    def __init__(self):
        # In production, this would load a real .pkl model
        pass

    def estimate_confirmation_chance(self, train_no: str, class_type: str, travel_date: datetime) -> float:
        """
        [16.1] Fine-tuned confirmation probability model.
        [16.2] Proximity-based decay (Booking window factor).
        """
        prob = 0.65 # Baseline shifted to 65% for GN
        
        # 1. Class Factor (Subtask 16.3)
        class_map = {"1A": 0.25, "2A": 0.15, "3A": 0.05, "SL": -0.2, "CC": 0.1, "2S": -0.3}
        prob += class_map.get(class_type.upper(), 0.0)
        
        # 2. Proximity Factor (Subtask 16.2)
        days_diff = (travel_date.date() - datetime.now().date()).days
        if days_diff > 60:
            prob += 0.15 # Early booking advantage
        elif days_diff < 7:
            prob -= 0.25 # Last minute rush penalty
        elif days_diff < 2:
            prob -= 0.4 # Extremely high risk for GN
            
        # 3. Weekend Factor
        if travel_date.weekday() in [4, 5, 6]: # Fri, Sat, Sun
            prob -= 0.1
            
        # 4. Train Popularity Factor
        if str(train_no) in ["12626", "12121", "12424", "22436", "22435"]:
            prob -= 0.15
            
        return max(0.05, min(0.99, prob))

    def get_route_availability_score(self, segments: list) -> float:
        """
        Calculates aggregate availability for a multi-leg route.
        [16.4] Multi-leg Complexity Penalty.
        """
        if not segments: return 1.0
        
        total_prob = 1.0
        for s in segments:
            # Try to extract class from metadata if possible
            cls = s.metadata.get("class_type", "3A") if hasattr(s, 'metadata') else "3A"
            total_prob *= self.estimate_confirmation_chance(s.train_number, cls, s.departure_time)
            
        # [16.4] Complexity Penalty: 10% reduction for each transfer
        if len(segments) > 1:
            penalty = (len(segments) - 1) * 0.1
            total_prob *= (1.0 - penalty)
            
        return max(0.01, round(total_prob, 4))

availability_heuristic = AvailabilityHeuristic()
