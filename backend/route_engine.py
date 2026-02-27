"""Compatibility layer replicating the historic ``backend.route_engine`` API."""

from __future__ import annotations

from typing import Optional

from core.route_engine import (
    RouteEngine,
    RailwayRouteEngine,
    OptimizedRAPTOR,
    HybridRAPTOR,
    TimeDependentGraph,
    RouteConstraints,
    Route,
    RouteSegment,
    TransferConnection,
    UserContext,
    route_engine as _lazy_route_engine,
)
from database import SessionLocal
from database.models import Stop

__all__ = [
    "RouteEngine",
    "RailwayRouteEngine",
    "OptimizedRAPTOR",
    "HybridRAPTOR",
    "TimeDependentGraph",
    "RouteConstraints",
    "Route",
    "RouteSegment",
    "TransferConnection",
    "UserContext",
    "route_engine",
    "get_station_by_code",
    "calculate_segment_fare",
]

route_engine = _lazy_route_engine


def get_station_by_code(code: str) -> Optional[Stop]:
    session = SessionLocal()
    try:
        return session.query(Stop).filter(Stop.code == code).first()
    finally:
        session.close()


def calculate_segment_fare(origin: Stop, destination: Stop, mode: str = "rail") -> float:
    base = 120.0 if mode == "rail" else 150.0
    distance = 0.0
    if origin and destination and hasattr(origin, "latitude") and hasattr(destination, "latitude"):
        distance = abs(origin.latitude - destination.latitude) + abs(origin.longitude - destination.longitude)
    return round(base + distance, 2)
