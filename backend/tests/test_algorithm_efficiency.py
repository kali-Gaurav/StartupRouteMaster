#!/usr/bin/env python3
"""Unit tests for algorithm-efficiency improvements:
- bitset helpers
- route pattern indexing
- transfer precompute cache
- dominance pruning
"""

import pytest
from datetime import datetime

from backend.core.route_engine import TimeDependentGraph, Route, RouteSegment, TransferConnection, OptimizedRAPTOR


def make_segment(trip_id, dep_stop, arr_stop, dep_time=None, arr_time=None, distance=10.0):
    dep_time = dep_time or datetime(2026, 2, 19, 8, 0)
    arr_time = arr_time or datetime(2026, 2, 19, 9, 0)
    return RouteSegment(
        trip_id=trip_id,
        departure_stop_id=dep_stop,
        arrival_stop_id=arr_stop,
        departure_time=dep_time,
        arrival_time=arr_time,
        duration_minutes=int((arr_time - dep_time).total_seconds() // 60),
        distance_km=distance,
        fare=50.0
    )


def test_bitset_helpers():
    g = TimeDependentGraph()
    # populate stop_cache
    g.stop_cache = {10: None, 20: None, 30: None}
    g.build_stop_index()

    bits = g.stations_to_bitset([10, 30])
    assert isinstance(bits, int)
    # both positions set
    assert bits != 0

    # route -> bitset
    r = Route()
    r.segments = [make_segment(1, 10, 20), make_segment(1, 20, 30)]
    rb = g.route_to_bitset(r)
    assert rb & bits == bits


def test_transfer_cache_and_lookup():
    g = TimeDependentGraph()
    # add a transfer and ensure transfer_cache populated
    t = TransferConnection(
        station_id=20,
        arrival_time=datetime(2026, 2, 19, 0, 0),
        departure_time=datetime(2026, 2, 19, 23, 59),
        duration_minutes=10,
        station_name="Foo",
        facilities_score=0.8,
        safety_score=0.9
    )
    g.add_transfer(10, t)
    # lookup
    found = g.get_transfer_between_stops(10, 20)
    assert isinstance(found, list) and len(found) == 1
    assert found[0].duration_minutes == 10


@pytest.mark.asyncio
async def test_route_pattern_indexing_and_accessor():
    engine = OptimizedRAPTOR()
    g = TimeDependentGraph()

    # build stop cache and trip segments
    g.stop_cache = {1: None, 2: None, 3: None}
    segs = [make_segment(100, 1, 2), make_segment(100, 2, 3)]
    g.trip_segments[100] = segs

    # pattern_for_trip and route_patterns usage
    key = g.pattern_for_trip(100)
    assert isinstance(key, tuple)

    # manually populate route_patterns and ensure accessor works via engine
    g.route_patterns[key] = [100]

    # monkeypatch _build_graph to return our graph for a date
    engine._build_graph = lambda date: g
    trips = await engine.find_trips_by_stop_sequence([1, 2, 3])
    assert 100 in trips


@pytest.mark.asyncio
async def test_dominance_pruning_behaviour():
    engine = OptimizedRAPTOR()
    g = TimeDependentGraph()
    g.stop_cache = {1: None, 2: None, 3: None}
    g.build_stop_index()

    # Create routes with varying metrics
    r1 = Route(); r1.segments = [make_segment(1,1,2)]; r1.total_duration = 100; r1.total_cost = 100; r1.transfers = []; r1.reliability = 0.9; r1.score = 100
    r2 = Route(); r2.segments = [make_segment(2,1,2)]; r2.total_duration = 120; r2.total_cost = 90; r2.transfers = []; r2.reliability = 0.85; r2.score = 110
    r3 = Route(); r3.segments = [make_segment(3,1,3)]; r3.total_duration = 95; r3.total_cost = 110; r3.transfers = [TransferConnection(2, datetime.now(), datetime.now(), 10, "X", 0.7, 0.9)]; r3.reliability = 0.92; r3.score = 95

    kept = await engine._deduplicate_routes([r1, r2, r3], g)
    # r3 strictly better on duration and reliability than r2, r1 and r3 should remain; r2 should be pruned
    assert r2 not in kept
    assert r1 in kept or r3 in kept
