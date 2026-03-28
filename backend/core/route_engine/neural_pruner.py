
import logging
import numpy as np
from typing import Dict, Set, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger("nexus.raptor.pruner")

class NeuralRAPTORPruner:
    """
    Task 171: Neural-Inspired RAPTOR Pruning.
    Uses spatial and temporal signals to avoid exploring sub-optimal graph branches.
    Integrated with Nexus Governor for dynamic aggression.
    """
    def __init__(self, graph):
        self.graph = graph
        self.stop_cache = graph.stop_cache
        # Average speed of express trains in India (~60-80 km/h)
        # We use a conservative 'ideal' speed for pruning buffers
        self.ideal_speed_kmh = 100.0 
        self.earth_radius_km = 6371.0

    def get_coordinates(self, stop_id: int) -> Optional[Tuple[float, float]]:
        stop = self.stop_cache.get(stop_id)
        if stop and stop.latitude and stop.longitude:
            return (stop.latitude, stop.longitude)
        return None

    def haversine_distance(self, lat1, lon1, lat2, lon2) -> float:
        """Calculate the great circle distance between two points on the earth."""
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        a = (np.sin(dlat / 2) ** 2 + 
             np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2)
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        return self.earth_radius_km * c

    def should_prune(self, 
                    current_stop_id: int, 
                    dest_stop_ids: Set[int], 
                    current_arrival_mins: int,
                    global_min_arrival_mins: int,
                    round_num: int,
                    pressure: float = 0.0) -> bool:
        """
        [Task 171] Core Pruning Decision Logic.
        Returns True if the current station should NOT be expanded further.
        """
        # If we already found a much better route, be aggressive
        if global_min_arrival_mins < float('inf'):
            # Simple Temporal Pruning: If currently 24h+ later than best, prune
            if current_arrival_mins > global_min_arrival_mins + 1440:
                return True

        # Spatial Pruning (Requires Coordinates)
        curr_coords = self.get_coordinates(current_stop_id)
        if not curr_coords:
            return False

        # Find distance to closest destination stop
        min_dist_to_dest = float('inf')
        for d_id in dest_stop_ids:
            d_coords = self.get_coordinates(d_id)
            if d_coords:
                dist = self.haversine_distance(curr_coords[0], curr_coords[1], d_coords[0], d_coords[1])
                min_dist_to_dest = min(min_dist_to_dest, dist)
        
        if min_dist_to_dest == float('inf'):
            return False

        # 1. Ideal Time Test
        # If (current_time + time_to_dest_at_max_speed) > (global_min_arrival + buffer), prune.
        # This is a dynamic variant of A* for RAPTOR.
        ideal_time_remaining = (min_dist_to_dest / self.ideal_speed_kmh) * 60
        expected_arrival = current_arrival_mins + ideal_time_remaining
        
        # Buffer grows with pressure to allow more exploration when system is idle
        # and more aggressive pruning when system is stressed.
        buffer_mins = max(30, 240 * (1.0 - pressure)) 
        
        if expected_arrival > global_min_arrival_mins + buffer_mins:
            # We only prune after round 1 to allow discovery in early rounds
            if round_num >= 1:
                return True

        return False

# Factory function for standard pruner
def get_raptor_pruner(graph):
    return NeuralRAPTORPruner(graph)
