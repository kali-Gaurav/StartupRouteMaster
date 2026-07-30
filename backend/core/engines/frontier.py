
"""
Station Frontier Pruning - Task 3 of the 10X Evolution Plan.
Implements Pareto dominance for multi-criteria route optimization.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any
from datetime import datetime

@dataclass(slots=True)
class FrontierRoute:
    """Represents a route candidate in a station's Pareto frontier."""
    arrival_time: int  # Minutes from midnight
    transfers: int
    total_wait: int
    total_distance: float
    reliability: float = 1.0  # [Task 173] 0.0 to 1.0 (1.0 is default/stable)
    total_cost: float = 0.0    # [McRAPTOR] Estimated monetary cost
    comfort_score: float = 0.5 # [McRAPTOR] 0.0 to 1.0 (Higher is better)
    safety_score: float = 0.5  # [Task RM-007] 0.0 to 1.0 (Higher is safer)
    score: float = 0.0
    trip_id: Optional[int] = None
    parent_trip_id: Optional[int] = None
    
    # [Task 2] Distance and Wait Time Weighting
    distance_weight: float = 0.1
    wait_weight: float = 0.1
    reliability_weight: float = 0.2
    cost_weight: float = 0.3    # [McRAPTOR] High priority for cost-sensitive users
    comfort_weight: float = 0.3 # [McRAPTOR] High priority for premium users
    
    def dominates(self, other: 'FrontierRoute', 
                  cost_fn: Optional[Any] = None,
                  constraints: Optional[Any] = None,
                  epsilon_mins: int = 0) -> bool:
        """
        [Task 42.6] Personalized Dominance.
        Updated for McRAPTOR: Includes Cost and Comfort.
        """
        if cost_fn and constraints:
            # If a complex cost function is provided, we use it for a scalar comparison
            # BUT we still allow Pareto dominance on time to avoid "cheap but slow" dominating "fast but slightly more expensive"
            self_cost = cost_fn(self.arrival_time, self.transfers, self.total_wait, self.total_distance, self.total_cost, self.comfort_score, self.reliability, constraints, self.safety_score)
            other_cost = cost_fn(other.arrival_time, other.transfers, other.total_wait, other.total_distance, other.total_cost, other.comfort_score, other.reliability, constraints, other.safety_score)
            
            # Pruning rule: Self dominates Other if it is significantly better in generalized cost
            # AND not significantly worse in arrival time.
            return self_cost <= other_cost and self.arrival_time <= other.arrival_time + 60
            
        # [Multi-Criteria Pareto Dominance]
        # Self dominates Other if it is NOT WORSE in any dimension AND BETTER in at least one.
        
        # Dimensions: arrival_time, transfers, reliability (inv), cost, comfort (inv)
        # Higher is better for Reliability/Comfort, so we check >= and >.
        # Lower is better for Arrival/Transfers/Cost, so we check <= and <.
        
        not_worse = (
            (self.arrival_time - epsilon_mins) <= other.arrival_time and
            self.transfers <= other.transfers and
            self.total_cost <= other.total_cost and
            self.reliability >= other.reliability and
            self.comfort_score >= other.comfort_score and
            self.safety_score >= other.safety_score
        )
        
        if not not_worse:
            return False
            
        strictly_better = (
            (self.arrival_time - epsilon_mins) < other.arrival_time or
            self.transfers < other.transfers or
            self.total_cost < other.total_cost or
            self.reliability > other.reliability or
            self.comfort_score > other.comfort_score or
            self.safety_score > other.safety_score
        )
        
        return strictly_better

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
        
        # 3. [Task 2c] Sort by multiple criteria: arrival time → transfers → safety → reliability → comfort
        self.routes.sort(key=lambda x: (x.arrival_time, x.transfers, -x.safety_score, -x.reliability, -x.comfort_score))
        
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

