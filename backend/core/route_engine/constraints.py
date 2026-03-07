from dataclasses import dataclass, field
from typing import Optional

from enum import Enum

from core.data_structures import Persona

@dataclass
class RouteConstraints:
    """Constraints for route finding"""
    max_journey_time: int =  60 * 60  # 60 hours in minutes (rail journeys can be long)
    max_transfers: int = 3
    min_transfer_time: int = 15  # minutes
    max_layover_time: int = 8 * 60  # 8 hours
    avoid_night_layovers: bool = False
    women_safety_priority: bool = False
    max_results: int = 10
    persona: Persona = Persona.COMFORT # Default

    # Range-RAPTOR (search window)
    range_minutes: int = 0             # 0 = disabled; otherwise departure ± range_minutes/2
    range_step_minutes: int = 15      # granularity when scanning the window
    adaptive_range: bool = True       # let engine pick window based on distance/frequency

    # Reliability weighting (0..1) used to bias route score by reliability/confidence
    reliability_weight: float = 0.5
    # Capacity/Availability weighting (0..1) used to penalize high-occupancy routes
    capacity_weight: float = 0.4

    # Compatibility / advanced options
    preferred_class: Optional[str] = None
    include_wait_time: bool = False

    # Debug/diagnostics
    debug: bool = False

    @dataclass
    class Weights:
        time: float = 1.0
        cost: float = 0.3
        comfort: float = 0.2
        safety: float = 0.1
        transfer: float = 100.0 # Minutes of penalty per transfer

    weights: Weights = field(default_factory=Weights)
    
    # Task 2: Fine-grained Priority Overrides (0.0 to 1.0)
    time_priority: float = 0.5
    cost_priority: float = 0.5

    def __post_init__(self):
        # Task 1: Base Persona Weights
        if self.persona == Persona.EMERGENCY:
            self.weights.time = 5.0
            self.weights.cost = 0.1
            self.weights.transfer = 5.0
            self.max_transfers = 4 
            
        elif self.persona == Persona.COMFORT:
            self.weights.time = 1.0
            self.weights.cost = 0.5
            self.weights.comfort = 2.0
            self.weights.transfer = 500.0
            self.max_transfers = 1 
            
        elif self.persona == Persona.BUDGET:
            self.weights.time = 0.5
            self.weights.cost = 2.0
            self.weights.transfer = 150.0
            
        # Task 2: Dynamic Weighting refinement
        # We scale the base weights by the user's explicit priorities
        self.weights.time *= (self.time_priority * 2.0) # 0.5 becomes 1.0 multiplier
        self.weights.cost *= (self.cost_priority * 2.0)
