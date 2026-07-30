from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
from enum import Enum
from core.data_utils.structures import Persona

class DiscoveryModel(Enum):
    BACKBONE = "BACKBONE"      # Tier 1: Internal DB Only (Free)
    MULTIMODAL = "MULTIMODAL"  # Tier 2: DB + API Discovery (Standard)
    OMNISCIENT = "OMNISCIENT"  # Tier 3: DB + API + Real-time Verification (Premium)

@dataclass
class RouteConstraints:
    """Constraints for route finding"""
    discovery_model: DiscoveryModel = DiscoveryModel.BACKBONE # Default to Free Tier
    max_journey_time: int =  60 * 60  # 60 hours in minutes (rail journeys can be long)
    max_transfers: int = 3
    min_transfer_time: int = 15  # minutes
    max_layover_time: int = 8 * 60  # 8 hours
    avoid_night_layovers: bool = False
    women_safety_priority: bool = False
    max_results: int = 100 # Task 20: Support larger result sets for pagination
    persona: Persona = Persona.COMFORT # Default
    
    # Task 20: Pagination Cursor
    cursor: Optional[int] = 0 # Offset for ZSET retrieval

    # Range-RAPTOR (search window)
    range_minutes: int = 0             # 0 = disabled; otherwise departure ± range_minutes/2
    range_step_minutes: int = 15      # granularity when scanning the window
    adaptive_range: bool = True       # let engine pick window based on distance/frequency
    
    # [Task 1] Multi-Departure Window Scanning
    lookahead_minutes: int = 1440      # 24-hour scanning window (default)

    # [Task 2] Pareto Frontier Expansion
    use_weighted_frontier: bool = False  # Enable distance + wait-time weighted Pareto
    
    # Reliability weighting (0..1) used to bias route score by reliability/confidence
    reliability_weight: float = 0.5
    # Capacity/Availability weighting (0..1) used to penalize high-occupancy routes
    capacity_weight: float = 0.4

    # Compatibility / advanced options
    preferred_class: Optional[str] = None
    # [Task 27] Multi-Class preference (e.g., ["3A", "SL"] to check 3A first, then SL)
    preferred_classes: list[str] = field(default_factory=lambda: ["3A", "2A", "SL"])
    
    include_wait_time: bool = False

    # Debug/diagnostics
    debug: bool = False
    # [Task 9] Search Timeout in Milliseconds
    timeout_ms: int = 5000
    
    # Task 26.1: Quota support (GN, TQ, LD, etc.)
    quota: str = "GN"
    
    # [Task 10] Discovery-Only Mode (Skip Hydration/Pricing)
    discovery_only: bool = False
    
    # [Task 1] Engine Filtering
    permitted_engines: Optional[list[str]] = None
    
    # [Task 41.22] Unified telemetry and cross-engine coordination
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Task 31: Adaptive Yield Goals
    yield_goal: int = 35
    search_depth: str = "SHALLOW" # SHALLOW, MEDIUM, DEEP
    hub_limit: int = 100         # Maximum hubs to consider for discovery

    # [Elite: Hub Bridge] Pre-resolved multimodal jumps (e.g., {"NDLS": [{"to_stop_id": 123, ...}]})
    multimodal_jumps: dict = field(default_factory=dict)
    
    # [Safety Engine] Passenger list for persona-aware scoring
    passengers: list = field(default_factory=list)
    
    # [Safety Engine] Real-time Safety Scores (station_id -> score 0.0-1.0)
    station_safety_scores: Dict[int, float] = field(default_factory=dict)
    
    # [Task 8] Must-Include / Must-Avoid stop constraints
    # must_include_stops: route MUST pass through ALL of these stop_ids (waypoints)
    must_include_stops: list = field(default_factory=list)
    # must_avoid_stops: route MUST NOT pass through any of these stop_ids (blacklist)
    must_avoid_stops: list = field(default_factory=list)
    # must_avoid_trains: route MUST NOT use these train numbers
    must_avoid_trains: list = field(default_factory=list)
    
    # [Task 9] Multi-Modal Train Type Preferences
    # e.g. ["RAJDHANI", "SHATABDI", "VANDE"] to prefer premium trains
    preferred_train_types: list = field(default_factory=list)
    # Penalty multiplier for non-preferred train types (1.0 = no penalty)
    non_preferred_train_penalty: float = 1.0

    @dataclass
    class Weights:
        time: float = 1.0
        cost: float = 0.3
        comfort: float = 0.2
        safety: float = 0.1
        tis: float = 1.0       # Transfer Intelligence Score weight
        transfer: float = 100.0 # Minutes of penalty per transfer
        reliability: float = 1.0 # Penalty per unit of unreliability

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
            self.weights.tis = 2.0      # High reliability required for emergencies
            self.weights.safety = 0.5   # Speed is primary over safety in emergencies
            self.max_transfers = 3 
            
        elif self.persona == Persona.COMFORT:
            self.weights.time = 1.0
            self.weights.cost = 0.5
            self.weights.comfort = 2.0
            self.weights.transfer = 500.0
            self.weights.tis = 3.0      # Comfort includes low-risk connections
            self.weights.safety = 2.0   # High safety preferred
            self.max_transfers = min(self.max_transfers, 2) 
            
        elif self.persona == Persona.BUDGET:
            self.weights.time = 0.5
            self.weights.cost = 2.5 # Increased cost sensitivity
            self.weights.transfer = 150.0
            self.weights.tis = 1.0
            self.weights.safety = 1.0
            self.max_transfers = min(self.max_transfers, 3)

        elif self.persona == Persona.FAST:
            self.weights.time = 3.0 # High weight on time
            self.weights.cost = 0.5
            self.weights.transfer = 50.0 # Faster transfers are okay
            self.weights.tis = 1.5
            self.weights.safety = 0.8
            self.max_transfers = min(self.max_transfers, 3)
            
        elif self.persona == Persona.FAMILY:
            self.weights.time = 1.0
            self.weights.cost = 0.8
            self.weights.comfort = 3.0 # Maximum comfort for families
            self.weights.transfer = 800.0 # Heavy penalty for transfers
            self.weights.reliability = 5.0 # High weight on reliability
            self.weights.tis = 5.0      # Extremely low risk required
            self.weights.safety = 5.0   # Maximum safety priority
            self.max_transfers = min(self.max_transfers, 1) # Prefer direct
            
    def expand_discovery(self):
        """
        [Task: VYA Load More] Evolves constraints for deeper discovery.
        Increases BFS depth, unlocks low-centrality hubs, and expands time window.
        """
        # 1. Expand Depth
        if self.search_depth == "SHALLOW": self.search_depth = "MEDIUM"
        elif self.search_depth == "MEDIUM": self.search_depth = "DEEP"
        
        # 2. Expand Time Window (+3 hours per iteration)
        self.lookahead_minutes += 180
        
        # 3. Increase Transfer Allowance (max 5)
        self.max_transfers = min(5, self.max_transfers + 1)
        
        # 4. Hub Sensitivity (Relaxed threshold for low-centrality hubs)
        current_threshold = self.metadata.get("hub_threshold", 0.8)
        self.metadata["hub_threshold"] = max(0.1, current_threshold - 0.2)
        
        # 5. Tracking
        self.metadata["search_iteration"] = self.metadata.get("search_iteration", 0) + 1
        
        from core.nexus.audit.governor import logger
        logger.info(f"🔄 [DISCOVERY:EXPAND] Depth: {self.search_depth}, Window: {self.lookahead_minutes}m, Hub_T: {self.metadata['hub_threshold']}")
