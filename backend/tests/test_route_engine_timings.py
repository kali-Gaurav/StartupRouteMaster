import asyncio
import inspect
import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from database import SessionLocal
from models import Stop
from route_engine import (
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


@pytest.mark.asyncio
@pytest.mark.performance
async def test_route_engine_timings(db_session, sample_stops, sample_trip, sample_stop_times):
    """
    Performance helper test — measure wall-time (time.time) for important functions
    in `backend/route_engine.py` and write a simple JSON + console summary.

    Notes:
    - The test is non-failing for individual function errors; exceptions are captured and
      recorded in the output so you can see which functions need further attention.
    - Uses fixtures that populate a minimal DB (see `conftest.py`).
    """
    out_path = Path("test_output")
    out_path.mkdir(exist_ok=True)
    results = {}

    def time_sync(name, fn, *args, **kwargs):
        t0 = time.time()
        try:
            res = fn(*args, **kwargs)
            results[name] = {"elapsed_s": time.time() - t0, "error": None}
            return res
        except Exception as e:  # capture but don't fail the whole test
            results[name] = {"elapsed_s": time.time() - t0, "error": repr(e)}
            return None

    async def time_async(name, coro_fn, *args, **kwargs):
        t0 = time.time()
        try:
            # allow passing either a coroutine function or a coroutine object
            if inspect.iscoroutinefunction(coro_fn):
                res = await coro_fn(*args, **kwargs)
            else:
                # assume coro_fn is already a coroutine object
                res = await coro_fn
            results[name] = {"elapsed_s": time.time() - t0, "error": None}
            return res
        except Exception as e:
            results[name] = {"elapsed_s": time.time() - t0, "error": repr(e)}
            return None

    # Prepare instances and inputs
    rengine = RouteEngine()
    raptor = rengine.raptor
    now = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    constraints = RouteConstraints()
    # `find_routes` references a couple of attributes that aren't present on the
    # dataclass by default in this module (safe to attach dynamically for the test)
    setattr(constraints, "preferred_class", None)
    setattr(constraints, "include_wait_time", True)

    # 1) Utility functions / simple DB lookup
    time_sync("get_station_by_code", get_station_by_code, "NDLS")

    # direct DB lookup timing (searching station from DB)
    def db_lookup():
        session = SessionLocal()
        try:
            return session.query(Stop).filter(Stop.code == "NDLS").first()
        finally:
            session.close()

    time_sync("db.query.Stop.by_code", db_lookup)

    # fare calculator
    s1 = sample_stops["NDLS"]
    s2 = sample_stops["PUNE"]
    time_sync("calculate_segment_fare", calculate_segment_fare, s1, s2, "rail")

    # 2) Graph building (sync + async)
    time_sync("OptimizedRAPTOR._build_graph_sync", raptor._build_graph_sync, now)
    await time_async("OptimizedRAPTOR._build_graph", raptor._build_graph(now))

    # get graph instance for more timings
    graph = await raptor._build_graph(now)

    # 3) TimeDependentGraph helpers
    # pick an example stop & trip from fixtures
    sample_stop_obj = sample_stops["MMCT"]
    sample_stop_id = sample_stop_obj.id
    sample_trip_id = sample_trip.id

    time_sync(
        "TimeDependentGraph.get_departures_from_stop",
        graph.get_departures_from_stop,
        sample_stop_id,
        now,
    )

    time_sync(
        "TimeDependentGraph.get_transfers_from_stop",
        graph.get_transfers_from_stop,
        sample_stop_id,
        now,
        15,
    )

    time_sync(
        "TimeDependentGraph.get_trip_segments",
        graph.get_trip_segments,
        sample_trip_id,
    )

    # 4) RAPTOR helper methods that can be invoked safely
    # _get_active_service_ids (needs a DB session)
    time_sync("OptimizedRAPTOR._get_active_service_ids", raptor._get_active_service_ids, db_session, now)

    # _time_to_datetime
    sample_time = sample_stop_times[0].departure_time
    time_sync("OptimizedRAPTOR._time_to_datetime", raptor._time_to_datetime, now, sample_time)

    # construct a Route with one segment to exercise validators & scoring
    seg = RouteSegment(
        trip_id=sample_trip.id,
        departure_stop_id=sample_stops["MMCT"].id,
        arrival_stop_id=sample_stops["NDLS"].id,
        departure_time=raptor._time_to_datetime(now, sample_stop_times[0].departure_time),
        arrival_time=raptor._time_to_datetime(now, sample_stop_times[-1].arrival_time),
        duration_minutes=10,
        distance_km=100.0,
        fare=250.0,
        train_name="TEST",
        train_number=str(sample_trip.id),
    )

    route = Route()
    route.add_segment(seg)

    time_sync("OptimizedRAPTOR._validate_route_constraints", raptor._validate_route_constraints, route, constraints)
    time_sync("OptimizedRAPTOR._calculate_score", raptor._calculate_score, route, constraints)

    # _process_route_transfers (async)
    await time_async("OptimizedRAPTOR._process_route_transfers", raptor._process_route_transfers(route, graph, sample_stops["NDLS"].id, constraints))

    # 5) Higher-level flows (compute + find + public API)
    await time_async("OptimizedRAPTOR._compute_routes", raptor._compute_routes(sample_stops["MMCT"].id, sample_stops["NDLS"].id, now, constraints))

    # Attach missing attributes to constraints again before calling find_routes
    setattr(constraints, "preferred_class", None)
    setattr(constraints, "include_wait_time", True)

    await time_async("OptimizedRAPTOR.find_routes", raptor.find_routes(sample_stops["MMCT"].id, sample_stops["NDLS"].id, now, constraints))

    # RouteEngine public API
    await time_async("RouteEngine.search_routes", rengine.search_routes("MMCT", "NDLS", now, constraints))

    # 6) RouteEngine helpers
    await time_async("RouteEngine._apply_ml_ranking", rengine._apply_ml_ranking([route], None))
    await time_async("RouteEngine._invalidate_affected_routes", rengine._invalidate_affected_routes(sample_trip.id))

    # 7) Record and print results
    # convert elapsed to ms for easier scanning
    printable = []
    for k, v in results.items():
        ms = round(v["elapsed_s"] * 1000, 2) if v["elapsed_s"] is not None else None
        printable.append((k, ms, v["error"]))

    # sort by elapsed desc
    printable.sort(key=lambda x: (x[1] if x[1] is not None else -1), reverse=True)

    # save JSON
    (out_path / "route_engine_timings.json").write_text(json.dumps(results, indent=2))

    # print summary table
    print('\nRoute engine timing summary (ms):')
    print('-' * 60)
    for name, ms, err in printable:
        if err:
            print(f"{name:50s} {ms:10}  ERROR: {err}")
        else:
            print(f"{name:50s} {ms:10}")
    print('-' * 60)

    # basic assertion to ensure test recorded timings
    assert len(results) > 0
    # ensure the most important entry exists
    assert "RouteEngine.search_routes" in results
