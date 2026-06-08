from __future__ import annotations

from datetime import datetime

import pytest

from core.data_utils.structures import RouteSegment
from core.integration.providers import ServiceStatus
from core.route_engine.engine import RailwayRouteEngine


def test_route_segment_exposes_time_seconds_properties():
    segment = RouteSegment(
        trip_id="T1",
        departure_stop_id=1,
        arrival_stop_id=2,
        departure_time=datetime(2026, 4, 22, 6, 15, 30),
        arrival_time=datetime(2026, 4, 22, 8, 45, 5),
        duration_minutes=150,
        distance_km=100.0,
        departure_code="NDLS",
        arrival_code="BCT",
        fare=500.0,
        train_name="Test Express",
        train_number="12345",
        service_mask=127,
        is_unconfirmed_allowed=False,
        has_pantry=False,
        departure_platform=None,
        arrival_platform=None,
        metadata={},
        stop_sequence=1,
    )

    assert segment.departure_time_seconds == 6 * 3600 + 15 * 60 + 30
    assert segment.arrival_time_seconds == 8 * 3600 + 45 * 60 + 5


@pytest.mark.asyncio
async def test_route_engine_init_initializes_db_pools(monkeypatch):
    engine = RailwayRouteEngine()
    engine.status = ServiceStatus.INITIALIZING

    calls = {"graph": 0}

    async def fake_get_current_graph(date, force_rebuild=False):
        calls["graph"] += 1
        engine.graph = None
        return None

    monkeypatch.setattr(engine, "_get_current_graph", fake_get_current_graph)

    await engine.init(force_rebuild=True)

    assert calls["graph"] == 1
    assert engine.graph_initialized is True
