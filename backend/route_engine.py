"""Top-level re-exports for `backend.core.route_engine`.

This file exists so code/tests that import `backend.route_engine` (historic path)
continue to work after the module was moved into `backend/core/`.
"""
from .core.route_engine import (
    RouteEngine,
    OptimizedRAPTOR,
    TimeDependentGraph,
    RouteConstraints,
    Route,
    RouteSegment,
    TransferConnection,
    get_station_by_code,
    calculate_segment_fare,
)

__all__ = [
    "RouteEngine",
    "OptimizedRAPTOR",
    "TimeDependentGraph",
    "RouteConstraints",
    "Route",
    "RouteSegment",
    "TransferConnection",
    "get_station_by_code",
    "calculate_segment_fare",
]
