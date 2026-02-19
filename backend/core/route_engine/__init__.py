from .engine import RailwayRouteEngine as RouteEngine, RailwayRouteEngine
from .offline_engine import OfflineRouteEngine
from .data_structures import Route, RouteSegment, TransferConnection, UserContext
from .constraints import RouteConstraints
from .raptor import OptimizedRAPTOR, HybridRAPTOR
from .graph import TimeDependentGraph, StaticGraphSnapshot, RealtimeOverlay # Import RealtimeOverlay
from .builder import GraphBuilder
from .hub import HubManager, HubToHubConnection
from .regions import RegionManager
from .snapshot_manager import SnapshotManager
from .transfer_intelligence import TransferIntelligenceManager
from .validators_offline import (
    SegmentValidator,
    TransferValidator,
    RouteValidator,
    AvailabilityValidator,
    ValidationResult,
    ValidationStatus,
    ValidationError,
)

# Lazy global instance for backward compatibility — avoids heavy DB access at import time
class _LazyRouteEngineProxy:
    """Proxy that instantiates RailwayRouteEngine on first access. Keeps backward-compatible API while
    avoiding expensive initialization during import (useful for tests and tools)."""
    def __init__(self):
        self.__dict__['_instance'] = None

    def _ensure(self):
        if self.__dict__['_instance'] is None:
            self.__dict__['_instance'] = RailwayRouteEngine()

    def __getattr__(self, name):
        self._ensure()
        return getattr(self.__dict__['_instance'], name)

    def __setattr__(self, name, value):
        # forward writes to the real instance (create it if necessary)
        if name == '_instance':
            self.__dict__['_instance'] = value
        else:
            self._ensure()
            setattr(self.__dict__['_instance'], name, value)

    def __repr__(self):
        inst = self.__dict__.get('_instance')
        return f"<LazyRouteEngineProxy initialized={inst is not None}>"

route_engine = _LazyRouteEngineProxy()

__all__ = [
    # Routing engines
    'RouteEngine',
    'RailwayRouteEngine',
    'OfflineRouteEngine',  # NEW: Offline mode
    'route_engine',
    # Data structures
    'Route',
    'RouteSegment',
    'TransferConnection',
    'UserContext',
    'RouteConstraints',
    # Algorithms
    'OptimizedRAPTOR',
    'HybridRAPTOR',
    # Graph
    'TimeDependentGraph',
    'StaticGraphSnapshot',
    'GraphBuilder',
    'HubManager',
    'HubToHubConnection',
    'RegionManager',
    'SnapshotManager',
    'RealtimeOverlay',
    'TransferIntelligenceManager',
    # Validators (NEW: Offline mode)
    'SegmentValidator',
    'TransferValidator',
    'RouteValidator',
    'AvailabilityValidator',
    'ValidationResult',
    'ValidationStatus',
    'ValidationError',
]
