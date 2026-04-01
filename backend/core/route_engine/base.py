from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
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
    src_cluster_ids: List[int]
    dst_cluster_ids: List[int]
    departure_date: datetime
    constraints: RouteConstraints
    limit: int = 15
    graph: Optional[TimeDependentGraph] = None
    db_session: Any = None
    
    # Metadata for specialized routing behaviors
    metadata: Dict[str, Any] = {}

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
    metadata: Dict[str, Any] = {}

class BaseRoutingEngine(ABC):
    """
    The Single Interface for all RouteMaster engines.
    Implementing this class makes an engine 'Nexus-Ready'.
    """
    
    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Unique ID for the engine (e.g., 'raptor-v3')."""
        pass

    def calculate_generalized_cost(self, arrival_ts: int, transfers: int, wait_mins: int, 
                                  distance_km: float, constraints: RouteConstraints) -> float:
        """
        [Task 42.5] Centralized Persona-Aware Cost Calculation.
        Unifies search dominance criteria for RAPTOR, TBR, and Turbo.
        """
        w = constraints.weights
        
        # 1. Base Time Cost (minutes from midnight or departure)
        # We use a normalized 1.0 weight for time
        time_cost = arrival_ts * w.time
        
        # 2. Transfer Penalty (Heavy penalty to avoid hops for families/comfort)
        transfer_cost = transfers * w.transfer * 60 # Convert transfer penalty to seconds
        
        # 3. Distance/Efficiency Bias
        distance_cost = distance_km * w.cost * 10
        
        # 4. Layover Fatigue
        layover_cost = wait_mins * w.comfort * 60
        
        return float(time_cost + transfer_cost + distance_cost + layover_cost)

    @abstractmethod
    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        """
        Executes the routing search and returns a standardized response.
        """
        pass
