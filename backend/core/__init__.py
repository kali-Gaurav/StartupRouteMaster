"""
Core Route Finding Engine - Phase 2/3 Implementation

Main components for routing operations:
- RailwayRouteEngine: Main coordinator for route-finding
- Graph structures: StaticGraphSnapshot, RealtimeOverlay, TimeDependentGraph
- Algorithms: OptimizedRAPTOR, HybridRAPTOR
- Graph building: GraphBuilder, SnapshotManager
- Transfer optimization: TransferIntelligence

All Phase 1 optimizations enabled via StationDepartureService in database layer.
"""

try:
    # Try importing from new modular structure (route_engine/ directory)
    from .route_engine.engine import RailwayRouteEngine
    from .route_engine.graph import TimeDependentGraph, StaticGraphSnapshot, RealtimeOverlay
    from .route_engine.raptor import OptimizedRAPTOR, HybridRAPTOR
    from .route_engine.builder import GraphBuilder
    from .route_engine.snapshot_manager import SnapshotManager
    from .route_engine.transfer_intelligence import TransferIntelligence
    from .route_engine.hub import HubManager
except ImportError:
    # Fallback to legacy wrapper for backward compatibility
    from .route_engine import RouteEngine as RailwayRouteEngine
    TimeDependentGraph = None
    StaticGraphSnapshot = None
    RealtimeOverlay = None
    OptimizedRAPTOR = None
    HybridRAPTOR = None
    GraphBuilder = None
    SnapshotManager = None
    TransferIntelligence = None
    HubManager = None

# Also expose legacy interface for backward compatibility
try:
    from .route_engine import route_engine
except:
    route_engine = None

__all__ = [
    # Modern API
    "RailwayRouteEngine",
    "TimeDependentGraph",
    "StaticGraphSnapshot",
    "RealtimeOverlay",
    "OptimizedRAPTOR",
    "HybridRAPTOR",
    "GraphBuilder",
    "SnapshotManager",
    "TransferIntelligence",
    "HubManager",
    # Legacy API (backward compatibility)
    "route_engine",
]
