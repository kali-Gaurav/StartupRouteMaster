import logging
import math
import numpy as np
from typing import Dict, Set, Optional, Tuple, List

logger = logging.getLogger("nexus.raptor.pruner")

class NeuralRAPTORPruner:
    """
    [Phase A3] GNN-Inspired Path Pruner.
    Uses multi-dimensional signals (spatial, temporal, and hub-reachability) 
    to aggressively prune sub-optimal branches in the routing graph.
    
    Integrated with Nexus Governor for dynamic congestion-aware pruning.
    """
    def __init__(self, graph):
        self.graph = graph
        self.stop_cache = graph.stop_cache
        self.ideal_speed_kmh = 100.0 
        self.earth_radius_km = 6371.0
        
        # Pre-calculated hub scores (Top stations in India by connectivity)
        # station_id: score (0.0 to 1.0)
        self.hub_scores = self._initialize_hub_scores()
        self._allowed_corridor: Set[int] = set()

    def _initialize_hub_scores(self) -> Dict[int, float]:
        """Loads connectivity weights for major railway junctions."""
        # This would ideally be loaded from a config or database
        # For now, we use a mapping of common major hubs
        return {
            7161: 1.0, # NDLS
            1234: 0.9, # CSMT
            5678: 0.9, # HWH
            9999: 0.9  # MAS
        }

    def prepare_for_search(self, src_id: int, dest_stop_ids: Set[int], od_dist_km: float):
        """
        [Subtask A3.2] Pre-calculates the 'Active Corridor' for the current search.
        This reduces the check overhead inside the hot search loop.
        """
        src_coords = self.get_coordinates(src_id)
        if not src_coords:
            self._allowed_corridor = set() # Allow all
            return

        # Midpoint of the search
        dest_list = [self.get_coordinates(did) for did in dest_stop_ids if self.get_coordinates(did)]
        if not dest_list:
            self._allowed_corridor = set()
            return
            
        avg_dest_lat = sum(c[0] for c in dest_list) / len(dest_list)
        avg_dest_lon = sum(c[1] for c in dest_list) / len(dest_list)
        
        # Elliptical Corridor Width
        # Longer routes need wider corridors for hub-hopping
        corridor_buffer = max(200.0, od_dist_km * 0.5)
        
        self._allowed_corridor = set()
        for sid, stop in self.stop_cache.items():
            # Hub check (High-degree nodes are always considered)
            if self.hub_scores.get(sid, 0.0) > 0.8:
                self._allowed_corridor.add(sid)
                continue
                
            dist_src = self.haversine_distance(stop.latitude, stop.longitude, src_coords[0], src_coords[1])
            dist_dst = self.haversine_distance(stop.latitude, stop.longitude, avg_dest_lat, avg_dest_lon)
            
            # If the stop is roughly 'on the way' (sum of distances < O-D dist + buffer)
            if (dist_src + dist_dst) < (od_dist_km + corridor_buffer):
                self._allowed_corridor.add(sid)
        
        logger.info(f"🧠 [GNN_PRUNER] Pre-search pruning: Allowed {len(self._allowed_corridor)}/{len(self.stop_cache)} stops.")

    def get_coordinates(self, stop_id: int) -> Optional[Tuple[float, float]]:
        stop = self.stop_cache.get(stop_id)
        if stop and stop.latitude and stop.longitude:
            return (stop.latitude, stop.longitude)
        return None

    def haversine_distance(self, lat1, lon1, lat2, lon2) -> float:
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
        Decision Logic combining Corridor Pruning and Temporal Lower-Bounding.
        """
        # 1. Global Corridor Filter (Fast Set Check)
        if self._allowed_corridor and current_stop_id not in self._allowed_corridor:
            return True

        # 2. Temporal Bound (A* Heuristic)
        if global_min_arrival_mins < float('inf'):
            # If currently 18h+ later than best found, prune (Relaxed for multi-day rail)
            if current_arrival_mins > global_min_arrival_mins + 1080:
                return True

        curr_coords = self.get_coordinates(current_stop_id)
        if not curr_coords:
            return False

        min_dist_to_dest = float('inf')
        for d_id in dest_stop_ids:
            d_coords = self.get_coordinates(d_id)
            if d_coords:
                dist = self.haversine_distance(curr_coords[0], curr_coords[1], d_coords[0], d_coords[1])
                min_dist_to_dest = min(min_dist_to_dest, dist)
        
        if min_dist_to_dest == float('inf'):
            return False

        # 3. Dynamic Lower Bound
        ideal_time_remaining = (min_dist_to_dest / self.ideal_speed_kmh) * 60
        expected_arrival = current_arrival_mins + ideal_time_remaining
        
        # Buffer narrows as pressure increases
        buffer_mins = max(180, 600 * (1.0 - pressure)) 
        
        if expected_arrival > global_min_arrival_mins + buffer_mins:
            if round_num >= 1:
                return True

        return False

def get_raptor_pruner(graph):
    return NeuralRAPTORPruner(graph)
