import numpy as np
from typing import Dict, Any

class RLStateMapper:
    """[Task 7.2] Converts Pricing Context into a Normalized NumPy Vector."""
    
    @staticmethod
    def map_to_vector(context_dict: Dict[str, Any]) -> np.ndarray:
        """
        Input keys: [demand_score, occupancy_rate, time_to_departure_hours, route_popularity]
        Output: Normalized Vector (0 to 1 range for stable learning)
        """
        # 1. Normalize time (clip at 7 days / 168 hours)
        time_norm = min(context_dict.get('time_to_departure_hours', 168), 168) / 168.0
        
        # 2. Extract and Normalize
        vector = np.array([
            context_dict.get('demand_score', 0.5),
            context_dict.get('occupancy_rate', 0.5),
            1.0 - time_norm, # Closer to departure = higher values (urgency)
            context_dict.get('route_popularity', 0.5)
        ], dtype=float)
        
        return vector

rl_state_mapper = RLStateMapper()
