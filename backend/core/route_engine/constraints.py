from dataclasses import dataclass, field
from typing import Optional

@dataclass
class RouteConstraints:
    """Constraints for route finding"""
    max_journey_time: int = 24 * 60  # 24 hours in minutes
    max_transfers: int = 3
    min_transfer_time: int = 15  # minutes
    max_layover_time: int = 8 * 60  # 8 hours
    avoid_night_layovers: bool = False
    women_safety_priority: bool = False
    max_results: int = 10

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

    @dataclass
    class Weights:
        time: float = 1.0
        cost: float = 0.3
        comfort: float = 0.2
        safety: float = 0.1

    weights: Weights = field(default_factory=Weights)
