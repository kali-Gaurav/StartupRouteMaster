
from .engine import RailwayRouteEngine, get_route_engine
from .constraints import RouteConstraints
from .raptor import OptimizedRAPTOR
from .graph import TimeDependentGraph, StaticGraphSnapshot, RealtimeOverlay
from .data_provider import DataProvider

# Standard singleton for service-wide access
route_engine = get_route_engine()

__all__ = [
    "RailwayRouteEngine", 
    "get_route_engine", 
    "route_engine", 
    "RouteConstraints",
    "OptimizedRAPTOR",
    "TimeDependentGraph",
    "StaticGraphSnapshot",
    "RealtimeOverlay",
    "DataProvider"
]

# Note: Deprecated 'route_engine' global instance. Use get_route_engine() instead (G11.4).
# route_engine = get_route_engine() # We can keep it for backward compat if it doesn't trigger loop
# But to be safe, we want callers to move to explicit lazy call if possible.


