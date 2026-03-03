import asyncio
from datetime import datetime

import pytest

from core.route_engine.graph import TimeDependentGraph, StaticGraphSnapshot
from core.route_engine.data_structures import RouteSegment
from core.route_engine.constraints import RouteConstraints
from core.route_engine.fast_router import FastPathRouter
from core.route_engine.raptor import HybridRAPTOR
from core.route_engine.hub import HubManager, HubConnectivityTable


def _build_tiny_snapshot():
    """
    Build a tiny in-memory snapshot:
    A(1) --T1--> B(2) --T1--> C(3)
    """
    snap = StaticGraphSnapshot(date=datetime(2026, 3, 3))
    snap.stop_cache = {
        1: type("Stop", (), {"id": 1, "name": "A"})(),
        2: type("Stop", (), {"id": 2, "name": "B"})(),
        3: type("Stop", (), {"id": 3, "name": "C"})(),
    }
    # Single trip 100 from A -> B -> C
    seg1 = RouteSegment(
        trip_id=100,
        departure_stop_id=1,
        arrival_stop_id=2,
        departure_time=datetime(2026, 3, 3, 8, 0),
        arrival_time=datetime(2026, 3, 3, 9, 0),
        duration_minutes=60,
        distance_km=100.0,
        fare=100.0,
        train_name="T100",
        train_number="100",
    )
    seg2 = RouteSegment(
        trip_id=100,
        departure_stop_id=2,
        arrival_stop_id=3,
        departure_time=datetime(2026, 3, 3, 9, 30),
        arrival_time=datetime(2026, 3, 3, 10, 30),
        duration_minutes=60,
        distance_km=120.0,
        fare=120.0,
        train_name="T100",
        train_number="100",
    )
    snap.trip_segments = {100: [seg1, seg2]}
    # Minimal departures_by_stop for RAPTOR
    snap.departures_by_stop = {
        1: [(seg1.departure_time, 100)],
        2: [(seg2.departure_time, 100)],
    }
    snap.transfer_graph = {}
    snap.arrivals_by_stop = {}
    snap.route_patterns = {}
    snap.transfer_cache = {}
    snap.stop_index = {}
    snap.transfer_metrics = {}
    snap.density_metrics = {}
    return snap


def _build_graph():
    snap = _build_tiny_snapshot()
    return TimeDependentGraph(snapshot=snap)


def test_fast_router_finds_simple_route():
    graph = _build_graph()
    router = FastPathRouter(graph)
    constraints = RouteConstraints(max_transfers=1, max_results=5)
    routes = router.find_routes(1, 3, datetime(2026, 3, 3, 8, 0), constraints)
    assert routes, "FastPathRouter should find at least one route A->C"
    r = routes[0]
    assert r.segments[0].departure_stop_id == 1
    assert r.segments[-1].arrival_stop_id == 3


@pytest.mark.asyncio
async def test_hybrid_raptor_on_tiny_graph():
    graph = _build_graph()
    # HubManager is required but we can pass a dummy SessionLocal factory since graph is synthetic
    from database.session import SessionLocal

    hub_manager = HubManager(SessionLocal)
    engine = HybridRAPTOR(hub_manager)
    constraints = RouteConstraints(max_transfers=0, max_results=5, range_minutes=0, adaptive_range=False)
    routes = await engine.find_routes(1, 3, datetime(2026, 3, 3, 8, 0), constraints, graph=graph)
    assert routes, "HybridRAPTOR should find at least one route A->C on tiny graph"
    r = routes[0]
    assert r.segments[0].departure_stop_id == 1
    assert r.segments[-1].arrival_stop_id == 3

