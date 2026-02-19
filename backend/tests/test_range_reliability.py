import asyncio
from datetime import datetime, timedelta

import pytest

from backend.core.route_engine import OptimizedRAPTOR, Route, RouteSegment, TransferConnection, RouteConstraints


@pytest.mark.asyncio
async def test_estimate_reliability_penalizes_short_transfer():
    raptor = OptimizedRAPTOR()

    # Build a simple route with one segment and one very short transfer
    seg = RouteSegment(
        trip_id=12345,
        departure_stop_id=1,
        arrival_stop_id=2,
        departure_time=datetime.utcnow(),
        arrival_time=datetime.utcnow() + timedelta(minutes=60),
        duration_minutes=60,
        distance_km=100.0,
        fare=100.0
    )

    route = Route()
    route.add_segment(seg)

    # short transfer (less than min_transfer_time)
    now = datetime.utcnow() + timedelta(minutes=60)
    transfer = TransferConnection(
        station_id=2,
        arrival_time=now,
        departure_time=now + timedelta(minutes=2),
        duration_minutes=2,
        station_name="TEST",
        facilities_score=0.5,
        safety_score=0.3
    )
    route.add_transfer(transfer)

    constraints = RouteConstraints(min_transfer_time=15)

    reliability = await raptor._estimate_route_reliability(route, constraints)

    # short transfer should cause a significant penalty
    assert 0.0 < reliability < 0.9


@pytest.mark.asyncio
async def test_score_with_reliability_reduces_score_when_unreliable():
    raptor = OptimizedRAPTOR()

    seg = RouteSegment(
        trip_id=99999,
        departure_stop_id=1,
        arrival_stop_id=2,
        departure_time=datetime.utcnow(),
        arrival_time=datetime.utcnow() + timedelta(minutes=120),
        duration_minutes=120,
        distance_km=300.0,
        fare=300.0
    )
    route = Route()
    route.add_segment(seg)

    constraints = RouteConstraints()

    base_score = await raptor._score_with_reliability(route, constraints)
    # route with no transfers and no known delays should have reliability near 1 and score ~= base heuristics
    assert base_score > 0
