from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from core.data_structures import Route
from .constraints import RouteConstraints
from .graph import TimeDependentGraph

class RoutingRequest(BaseModel):
    """
    Standardized Request for all RouteMaster engines.
    Ensures that engines receive the same rich context.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_code: str
    destination_code: str
    source_stop_id: Optional[int] = None
    destination_stop_id: Optional[int] = None
    src_cluster_ids: List[int] = Field(default_factory=list)
    dst_cluster_ids: List[int] = Field(default_factory=list)
    departure_date: datetime
    constraints: RouteConstraints
    limit: int = 15
    budget: float = 1.0 
    graph: Optional[TimeDependentGraph] = None
    db_session: Any = None
    force_refresh: bool = False
    multi_modal: bool = False
    
    # [Task 41.22] Unified telemetry and cross-engine coordination
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RoutingResponse(BaseModel):
    """
    Standardized output from any RouteMaster engine.
    Ensures the Orchestrator can merge results without complex translation.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    engine_name: str
    routes: List[Route]
    latency_ms: float
    yield_count: int
    triage_status: str = "SUCCESS" # SUCCESS, FAILED, UNREACHABLE
    model_display_name: Optional[str] = None
    total_latency_ms: float = 0.0
    engines_invoked: int = 0
    engines_succeeded: int = 0
    engines_failed: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BaseRoutingEngine(ABC):
    """
    The Single Interface for all RouteMaster engines.
    Implementing this class makes an engine 'Nexus-Ready'.
    """
    graph: Optional[TimeDependentGraph] = None

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Unique ID for the engine (e.g., 'raptor-v3')."""
        pass

    def calculate_generalized_cost(self, arrival_ts: int, transfers: int, wait_mins: int, 
                                  distance_km: float, fare: float, comfort: float,
                                  reliability: float, constraints: RouteConstraints) -> float:
        """
        [Task 42.5] Centralized Persona-Aware Cost Calculation.
        Unifies search dominance criteria for RAPTOR, TBR, and Turbo.
        Updated for McRAPTOR: Includes Fare, Comfort, and Reliability.
        """
        w = constraints.weights
        
        # 1. Base Time Cost (minutes from midnight or departure)
        time_cost = arrival_ts * w.time
        
        # 2. Transfer Penalty
        transfer_cost = transfers * w.transfer
        
        # 3. Monetary Cost (weighted by persona)
        fare_cost = fare * w.cost
        
        # 4. Layover Fatigue / Comfort Score (Higher comfort = Lower cost)
        # We treat comfort as a negative cost (0..1 score)
        comfort_bonus = comfort * w.comfort * 100
        
        # 5. Reliability Penalty (1 - reliability) * weight
        # Higher weight means higher penalty for low reliability
        reliability_penalty = (1.0 - reliability) * w.reliability * 250.0 
        
        # 6. Distance efficiency
        distance_bias = distance_km * 0.1
        
        return float(time_cost + transfer_cost + fare_cost - comfort_bonus + reliability_penalty + distance_bias)

    @abstractmethod
    async def find_routes(self, *args: Any, **kwargs: Any) -> Any:
        """
        Executes the routing search and returns engine-specific output.
        """
        pass
