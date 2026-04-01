
"""
Station Frontier Pruning - Task 3 of the 10X Evolution Plan.
Implements Pareto dominance for multi-criteria route optimization.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any
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
    
    def dominates(self, other: 'FrontierRoute', 
                  cost_fn: Optional[Any] = None,
                  constraints: Optional[Any] = None,
                  epsilon_mins: int = 0) -> bool:
        """
        [Task 42.6] Personalized Dominance.
        If cost_fn is provided, we use weighted generalized cost.
        Otherwise, we fall back to standard Pareto.
        """
        if cost_fn and constraints:
            self_cost = cost_fn(self.arrival_time, self.transfers, self.total_wait, self.total_distance, constraints)
            other_cost = cost_fn(other.arrival_time, other.transfers, other.total_wait, other.total_distance, constraints)
            
            # Better if cost is lower AND arrival is not significantly worse
            # (To avoid cost-dominating a much faster route)
            return self_cost <= other_cost and self.arrival_time <= other.arrival_time + 120
            
        # [Legacy/Standard Pareto]
        self_arr = self.arrival_time - epsilon_mins
        strictly_better = (
            self_arr < other.arrival_time or
            self.transfers < other.transfers or
            self.reliability > other.reliability
        )
        not_worse = (
            self_arr <= other.arrival_time and
            self.transfers <= other.transfers and
            self.reliability >= other.reliability
        )
        return strictly_better and not_worse

class ParetoFrontier:
    """
    Pareto Frontier for a single station.
    
    [Task 2] Enhanced with explicit distance and wait-time weighting
    """
    def __init__(self, max_size: int = 10, cost_fn: Optional[Any] = None, constraints: Optional[Any] = None):
        self.routes: List[FrontierRoute] = []
        self.max_size = max_size
        self.cost_fn = cost_fn
        self.constraints = constraints

    def add(self, new_route: FrontierRoute, epsilon_mins: int = 0) -> bool:
        # 1. Check dominance
        for existing in self.routes:
            if existing.dominates(new_route, cost_fn=self.cost_fn, constraints=self.constraints, epsilon_mins=epsilon_mins):
                return False
                
        # 2. Add and remove dominated
        self.routes = [r for r in self.routes if not new_route.dominates(r, cost_fn=self.cost_fn, constraints=self.constraints, epsilon_mins=epsilon_mins)]
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
    def __init__(self, max_routes_per_station: int = 5, max_stations: int = 10000, 
                 cost_fn: Optional[Any] = None, constraints: Optional[Any] = None):
        self.max_routes = max_routes_per_station
        self.max_stations = max_stations
        self.cost_fn = cost_fn
        self.constraints = constraints
        # Use an object array for Frontiers, initialized to None
        self.frontiers = np.full(max_stations, None, dtype=object)
        self._active_indices = []

    def get_frontier(self, station_id: int, max_size: Optional[int] = None) -> ParetoFrontier:
        if station_id >= self.max_stations:
            return ParetoFrontier(max_size=max_size or self.max_routes, 
                                 cost_fn=self.cost_fn, constraints=self.constraints)
            
        f = self.frontiers[station_id]
        if f is None:
            f = ParetoFrontier(max_size=max_size or self.max_routes, 
                              cost_fn=self.cost_fn, constraints=self.constraints)
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

