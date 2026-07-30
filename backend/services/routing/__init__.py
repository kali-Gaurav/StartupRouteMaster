"""
Route Engine Evolution - Next-Generation Routing Services

Tier 1 Features:
- SSE Progressive Route Delivery
- Query Plan Optimizer (QPO)
- Transfer Intelligence Score (TIS)
- Corridor Safety Bus

Tier 2 Features (Next Quarter):
- Contextual Availability Transformer (CAT)
- Journey DNA Pre-computation
- Data Source Arbitrage Engine (DSAE)

Tier 3 Features (Strategic Moonshots):
- Event-Sourced Live Rail Graph (ELRG)
- RL Route Optimizer
- GTFS++ Schema

Unified Service:
- UnifiedRouteService - Tiered Intelligence Pipeline
"""

from backend.services.route_engine import RouteEngine, Journey, RouteSegment
from .sse_route_streamer import (
    RouteStreamManager,
    StreamConfig,
    StreamedRoute,
    EventType,
    sse_router
)
from .query_plan_optimizer import (
    QueryPlanOptimizer,
    QueryPlan,
    QueryContext,
    SearchDepth,
    DatabaseTarget,
    HubPriority,
    qpo_router
)
from .transfer_intelligence import (
    TransferIntelligenceService,
    TransferScore,
    JourneyTransferScore,
    RiskLevel,
    tis_router
)
from .corridor_safety_bus import (
    CorridorSafetyBus,
    CorridorSafetyStatus,
    SafetyEvent,
    SafetyEventType,
    SafetyEventProducer,
    SafetyEventConsumer,
    safety_router
)
from .unified_route_service import (
    UnifiedRouteService,
    UnifiedRouteRequest,
    EnrichedRoute,
    unified_router
)

__all__ = [
    # Core Engine
    "RouteEngine",
    "Journey",
    "RouteSegment",
    
    # SSE Streaming
    "RouteStreamManager",
    "StreamConfig",
    "StreamedRoute",
    "EventType",
    "sse_router",
    
    # Query Plan Optimizer
    "QueryPlanOptimizer",
    "QueryPlan",
    "QueryContext",
    "SearchDepth",
    "DatabaseTarget",
    "HubPriority",
    "qpo_router",
    
    # Transfer Intelligence
    "TransferIntelligenceService",
    "TransferScore",
    "JourneyTransferScore",
    "RiskLevel",
    "tis_router",
    
    # Corridor Safety Bus
    "CorridorSafetyBus",
    "CorridorSafetyStatus",
    "SafetyEvent",
    "SafetyEventType",
    "SafetyEventProducer",
    "SafetyEventConsumer",
    "safety_router",
    
    # Unified Service
    "UnifiedRouteService",
    "UnifiedRouteRequest",
    "EnrichedRoute",
    "unified_router",
]

# Version info
__version__ = "2.0.0"
__pipeline_version__ = "Tiered Intelligence Pipeline v1.0"
__target_latency_ms__ = 700