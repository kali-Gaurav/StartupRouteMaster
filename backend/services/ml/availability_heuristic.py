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
        Heuristic model for confirmation probability.
        Factors:
        - Class: 1AC > 2AC > 3AC > SL
        - Day: Mid-week > Weekend
        - Distance from today: Further is usually better (unless Tatkal)
        """
        prob = 0.7 # Base 70%
        
        # 1. Class Factor
        class_map = {"1A": 0.2, "2A": 0.1, "3A": 0.0, "SL": -0.3, "CC": 0.1}
        prob += class_map.get(class_type.upper(), 0.0)
        
        # 2. Weekend Factor
        if travel_date.weekday() in [4, 5, 6]: # Fri, Sat, Sun
            prob -= 0.15
            
        # 3. Seasonal / Popular Train Mocks (Task 15.15)
        # Mocking some high-demand trains
        if train_no in ["12626", "12121", "12424"]:
            prob -= 0.2
            
        return max(0.05, min(0.99, prob))

    def get_route_availability_score(self, segments: list) -> float:
        """Calculates aggregate availability for a multi-leg route."""
        if not segments: return 1.0
        
        # Total probability is the product of individual leg probabilities
        # (Assuming independence, which is a safe heuristic for search)
        total_prob = 1.0
        for s in segments:
            # Default to 3A if class unknown
            total_prob *= self.estimate_confirmation_chance(s.train_number, "3A", s.departure_time)
            
        return total_prob

availability_heuristic = AvailabilityHeuristic()
