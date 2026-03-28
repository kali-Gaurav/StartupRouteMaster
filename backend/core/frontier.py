
"""
Station Frontier Pruning - Task 3 of the 10X Evolution Plan.
Implements Pareto dominance for multi-criteria route optimization.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime

@dataclass
class FrontierRoute:
    """Represents a route candidate in a station's Pareto frontier."""
    arrival_time: int  # Minutes from midnight
    transfers: int
    total_wait: int
    total_distance: float
    reliability: float = 1.0  # [Task 173] 0.0 to 1.0 (1.0 is default/stable)
    score: float = 0.0
    trip_id: Optional[int] = None
    parent_trip_id: Optional[int] = None
    
    # [Task 2] Distance and Wait Time Weighting
    distance_weight: float = 0.2    # 20% importance for distance
    wait_weight: float = 0.15       # 15% importance for wait time
    reliability_weight: float = 0.25 # [Task 173] 25% importance
    
    def dominates(self, other: 'FrontierRoute', use_weighted: bool = False, epsilon_mins: int = 0) -> bool:
        """
        [Task 1.3 / Task 2 / Task 173] Pareto Dominance logic with optional weighted comparison.
        Added reliability dimension for Task 173.
        """
        if not use_weighted:
            # [Task 173] Reliability Dominance: Self dominates only if reliability is >=
            self_arr = self.arrival_time - epsilon_mins
            
            strictly_better = (
                self_arr < other.arrival_time or
                self.transfers < other.transfers or
                self.total_wait < other.total_wait or
                self.total_distance < other.total_distance or
                self.reliability > other.reliability
            )
            
            not_worse = (
                self_arr <= other.arrival_time and
                self.transfers <= other.transfers and
                self.total_wait <= other.total_wait and
                self.total_distance <= other.total_distance and
                self.reliability >= other.reliability
            )
        else:
            # [Task 173] Reliability in Weighted Scoring
            max_arrival = max(self.arrival_time, other.arrival_time) or 1
            max_transfers = max(self.transfers, other.transfers) or 1
            max_wait = max(self.total_wait, other.total_wait) or 1
            max_distance = max(self.total_distance, other.total_distance) or 1
            
            # [Task 173] Compute weighted scores (Adjusted weights for reliability)
            # Higher reliability lowers the score (better)
            self_score = (
                0.4 * (self.arrival_time / max_arrival) +
                0.15 * (self.transfers / max_transfers) +
                0.1 * (self.total_wait / max_wait) +
                0.1 * (self.total_distance / max_distance) +
                0.25 * (1.0 - self.reliability)
            )
            
            other_score = (
                0.4 * (other.arrival_time / max_arrival) +
                0.15 * (other.transfers / max_transfers) +
                0.1 * (other.total_wait / max_wait) +
                0.1 * (other.total_distance / max_distance) +
                0.25 * (1.0 - other.reliability)
            )
            
            # Better if at least one dimension is better and overall score is lower
            strictly_better = (
                (self.arrival_time < other.arrival_time or
                 self.transfers < other.transfers or
                 self.reliability > other.reliability or
                 self.total_distance < other.total_distance) and
                self_score < other_score
            )
            
            not_worse = self_score <= other_score
        
        return strictly_better and not_worse

class ParetoFrontier:
    """
    Pareto Frontier for a single station.
    
    [Task 2] Enhanced with explicit distance and wait-time weighting
    """
    def __init__(self, max_size: int = 10, use_weighted: bool = False):
        self.routes: List[FrontierRoute] = []
        self.max_size = max_size
        self.use_weighted = use_weighted  # [Task 2b] Enable weighted comparison

    def add(self, new_route: FrontierRoute, epsilon_mins: int = 0) -> bool:
        # 1. Check if any existing route dominates the new one or is identical
        for existing in self.routes:
            if (existing.arrival_time == new_route.arrival_time and 
                existing.transfers == new_route.transfers and 
                existing.total_wait == new_route.total_wait and
                existing.reliability == new_route.reliability and
                existing.total_distance == new_route.total_distance):
                return False
            # [Task 2b] Use weighted comparison if enabled
            if existing.dominates(new_route, use_weighted=self.use_weighted, epsilon_mins=epsilon_mins):
                return False
                
        # 2. Add and remove dominated
        self.routes = [r for r in self.routes if not new_route.dominates(r, use_weighted=self.use_weighted, epsilon_mins=epsilon_mins)]
        self.routes.append(new_route)
        
        # 3. [Task 2c] Sort by multiple criteria: arrival time → transfers → reliability → distance
        self.routes.sort(key=lambda x: (x.arrival_time, x.transfers, -x.reliability, x.total_distance, x.total_wait))
        
        if len(self.routes) > self.max_size:
            # [Task 2d] Smarter eviction: prioritize keeping diverse options
            # Don't just remove the last; remove the most redundant one
            min_transfers_route = min(self.routes, key=lambda x: x.transfers)
            eviction_candidate_idx = -1
            if self.routes[-1] == min_transfers_route:
                eviction_candidate_idx = -2
            self.routes.pop(eviction_candidate_idx)
            
        return True

class FrontierManager:
    """
    Global manager for frontiers. Optimized with NumPy for station lookup.
    
    [Task 2] Supports both standard and weighted Pareto comparison modes.
    """
    def __init__(self, max_routes_per_station: int = 5, max_stations: int = 10000, use_weighted: bool = False):
        self.max_routes = max_routes_per_station
        self.max_stations = max_stations
        self.use_weighted = use_weighted  # [Task 2b] Enable weighted comparison
        # Use an object array for Frontiers, initialized to None
        self.frontiers = np.full(max_stations, None, dtype=object)
        self._active_indices = []

    def get_frontier(self, station_id: int, max_size: Optional[int] = None) -> ParetoFrontier:
        if station_id >= self.max_stations:
            # Fallback for unexpected station IDs
            return ParetoFrontier(max_size=max_size or self.max_routes, use_weighted=self.use_weighted)
            
        f = self.frontiers[station_id]
        if f is None:
            # [Task 2b] Pass use_weighted flag to frontier
            f = ParetoFrontier(max_size=max_size or self.max_routes, use_weighted=self.use_weighted)
            self.frontiers[station_id] = f
            self._active_indices.append(station_id)
        return f

    def reset(self):
        """Fast reset using tracked active indices."""
        for idx in self._active_indices:
            self.frontiers[idx] = None
        self._active_indices = []

    def is_dominated(self, station_id: int, route: FrontierRoute, max_size: Optional[int] = None, epsilon_mins: int = 0) -> bool:
        frontier = self.get_frontier(station_id, max_size=max_size)
        return not frontier.add(route, epsilon_mins=epsilon_mins)

