"""
Standalone timing runner for `backend/route_engine.py`.
- Seeds minimal DB rows if missing (Stops, Agency, Route, Calendar, Trip, StopTimes)
- Measures wall-time for key functions (sync + async)
- Writes JSON summary to `test_output/route_engine_timings_runner.json`

Run: python scripts/measure_route_engine_timings.py
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from backend.database import SessionLocal
from backend.database.models import Agency, Route as GtfsRoute, Calendar, Trip, StopTime, Stop
import backend.seat_inventory_models  # ensure `Coach` model is registered with SQLAlchemy registry
from backend.route_engine import (
    RouteEngine,
    OptimizedRAPTOR,
    RouteConstraints,
    Route,
    RouteSegment,
    TransferConnection,
    TimeDependentGraph,
    get_station_by_code,
    calculate_segment_fare,
)

OUT = Path("test_output")
OUT.mkdir(exist_ok=True)

session = SessionLocal()
trip_id = None
try:
    # Seed minimal data if missing (idempotent)
    agency = session.query(Agency).filter(Agency.agency_id == "TEST_AGENCY_001").first()
    if not agency:
        agency = Agency(
            agency_id="TEST_AGENCY_001",
            name="Test Railway Corp",
            url="https://test.local",
            timezone="Asia/Kolkata",
            language="en",
        )
        session.add(agency)
        session.commit()

    route = session.query(GtfsRoute).filter(GtfsRoute.route_id == "TRAIN_RAJ_001").first()
    if not route:
        route = GtfsRoute(
            route_id="TRAIN_RAJ_001",
            agency_id=agency.id,
            short_name="RJ",
            long_name="Rajdhani Express",
            route_type=2,
        )
        session.add(route)
        session.commit()

    calendar = session.query(Calendar).filter(Calendar.service_id == "WKD_001").first()
    today = datetime.utcnow().date()
    if not calendar:
        calendar = Calendar(
            service_id="WKD_001",
            monday=True, tuesday=True, wednesday=True, thursday=True, friday=True, saturday=True, sunday=True,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=365),
        )
        session.add(calendar)
        session.commit()

    # Stops
    stops_to_ensure = {
        "NDLS": dict(code="NDLS", name="New Delhi", city="Delhi", state="Delhi", latitude=28.6431, longitude=77.1064, geom="SRID=4326;POINT(77.1064 28.6431)", location_type=1, safety_score=85.0, is_major_junction=True, facilities_json={"wifi": True}),
        "MMCT": dict(code="MMCT", name="Mumbai Central", city="Mumbai", state="Maharashtra", latitude=18.9688, longitude=72.8194, geom="SRID=4326;POINT(72.8194 18.9688)", location_type=1, safety_score=78.0, is_major_junction=True, facilities_json={"wifi": True}),
        "PUNE": dict(code="PUNE", name="Pune Junction", city="Pune", state="Maharashtra", latitude=18.5286, longitude=73.8395, geom="SRID=4326;POINT(73.8395 18.5286)", location_type=1, safety_score=72.0, is_major_junction=False, facilities_json={"wifi": False}),
    }

    created_stops = {}
    for sid, props in stops_to_ensure.items():
        s = session.query(Stop).filter(Stop.stop_id == sid).first()
        if not s:
            s = Stop(stop_id=sid, **props)
            session.add(s)
            session.commit()
        created_stops[sid] = s.id

    trip = session.query(Trip).filter(Trip.trip_id == "TRIP_RAJ_001").first()
    if not trip:
        trip = Trip(
            trip_id="TRIP_RAJ_001",
            route_id=route.id,
            service_id=calendar.service_id,
            headsign="New Delhi",
            direction_id=0,
            bike_allowed=False,
            wheelchair_accessible=True,
            trip_headsign="New Delhi",
        )
        session.add(trip)
        session.commit()

    trip_id = trip.id

    # StopTimes
    existing_sts = session.query(StopTime).filter(StopTime.trip_id == trip_id).all()
    if not existing_sts:
        from datetime import datetime as _dt
        st_objects = [
            StopTime(trip_id=trip_id, stop_id=created_stops["MMCT"], arrival_time=_dt.strptime("06:00", "%H:%M").time(), departure_time=_dt.strptime("06:20", "%H:%M").time(), stop_sequence=1, cost=0.0, pickup_type=0, drop_off_type=0, platform_number="1"),
            StopTime(trip_id=trip_id, stop_id=created_stops["PUNE"], arrival_time=_dt.strptime("10:00", "%H:%M").time(), departure_time=_dt.strptime("10:15", "%H:%M").time(), stop_sequence=2, cost=500.0, pickup_type=0, drop_off_type=0, platform_number="2"),
            StopTime(trip_id=trip_id, stop_id=created_stops["NDLS"], arrival_time=_dt.strptime("16:00", "%H:%M").time(), departure_time=_dt.strptime("16:00", "%H:%M").time(), stop_sequence=3, cost=1000.0, pickup_type=0, drop_off_type=0, platform_number="1"),
        ]
        session.add_all(st_objects)
        session.commit()

finally:
    session.close()


def time_sync(fn, *args, **kwargs):
    t0 = time.time()
    try:
        r = fn(*args, **kwargs)
        return time.time() - t0, None, r
    except Exception as e:
        return time.time() - t0, repr(e), None


async def time_async(coro_fn, *args, **kwargs):
    t0 = time.time()
    try:
        if asyncio.iscoroutinefunction(coro_fn):
            r = await coro_fn(*args, **kwargs)
        else:
            r = await coro_fn
        return time.time() - t0, None, r
    except Exception as e:
        return time.time() - t0, repr(e), None


async def run_all(departure_dt=None, source_code: str = "MMCT", dest_code: str = "NDLS"):
    results = {}
    # determine departure datetime (default = today @ 06:00)
    if departure_dt is None:
        now = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    elif isinstance(departure_dt, datetime):
        now = departure_dt
    else:
        # assume a date-like object -> set to 06:00 on that date
        try:
            now = datetime.combine(departure_dt, datetime.min.time()).replace(hour=6, minute=0, second=0, microsecond=0)
        except Exception:
            now = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)

    rengine = RouteEngine()
    raptor = rengine.raptor
    constraints = RouteConstraints()
    setattr(constraints, "preferred_class", None)
    setattr(constraints, "include_wait_time", True)

    # Ensure a direct trip (adjacent stop_times) exists between source and dest using only DB data.
    # If no direct segment exists, create a new Trip that copies times from an existing trip that visits both stops.
    session = SessionLocal()
    try:
        # resolve stop IDs from seeded stops mapping
        src_stop_id = created_stops.get(source_code)
        dst_stop_id = created_stops.get(dest_code)

        if src_stop_id is None or dst_stop_id is None:
            # fall back to DB lookup (defensive)
            s = session.query(Stop).filter(Stop.code == source_code).first()
            d = session.query(Stop).filter(Stop.code == dest_code).first()
            src_stop_id = src_stop_id or (s.id if s else None)
            dst_stop_id = dst_stop_id or (d.id if d else None)

        if src_stop_id and dst_stop_id:
            # look for an existing trip that has both stops in correct order
            from sqlalchemy.orm import aliased
            st1 = aliased(StopTime)
            st2 = aliased(StopTime)
            existing = session.query(st1.trip_id).join(st2, st1.trip_id == st2.trip_id).filter(
                st1.stop_id == src_stop_id,
                st2.stop_id == dst_stop_id,
                st1.stop_sequence < st2.stop_sequence
            ).first()

            direct_trip_id = None
            if existing:
                # pick the trip id (integer primary key)
                direct_trip_id = existing[0]

                # check if stops are adjacent within that trip
                src_st = session.query(StopTime).filter(StopTime.trip_id == direct_trip_id, StopTime.stop_id == src_stop_id).first()
                dst_st = session.query(StopTime).filter(StopTime.trip_id == direct_trip_id, StopTime.stop_id == dst_stop_id).first()
                if src_st and dst_st and (dst_st.stop_sequence - src_st.stop_sequence == 1):
                    # already a direct adjacent segment — nothing to do
                    pass
                else:
                    # will create a direct trip below using times from this trip
                    direct_trip_id = None

            if not direct_trip_id and existing:
                # existing trip visits both stops but not adjacent — capture times to copy
                src_st = session.query(StopTime).filter(StopTime.trip_id == existing[0], StopTime.stop_id == src_stop_id).first()
                dst_st = session.query(StopTime).filter(StopTime.trip_id == existing[0], StopTime.stop_id == dst_stop_id).first()
                dep_time_to_copy = src_st.departure_time if src_st else None
                arr_time_to_copy = dst_st.arrival_time if dst_st else None
            else:
                dep_time_to_copy = None
                arr_time_to_copy = None

            if not direct_trip_id:
                # create a direct trip using DB route/calendar where possible
                route_row = session.query(GtfsRoute).filter(GtfsRoute.route_type == 2).first() or session.query(GtfsRoute).first()
                calendar_row = None
                if route_row:
                    # Prefer a calendar active on the requested date
                    weekday = now.strftime('%A').lower()
                    calendar_row = session.query(Calendar).filter(getattr(Calendar, weekday) == True, Calendar.start_date <= now.date(), Calendar.end_date >= now.date()).first()
                if not calendar_row:
                    calendar_row = session.query(Calendar).first()

                if route_row is None or calendar_row is None:
                    # cannot create a validated trip without route/calendar — skip
                    direct_trip_id = None
                else:
                    # If we didn't copy times from an existing trip, attempt to reuse times from any stop_time at src/dst
                    if dep_time_to_copy is None:
                        sample_src_st = session.query(StopTime).filter(StopTime.stop_id == src_stop_id).order_by(StopTime.stop_sequence).first()
                        dep_time_to_copy = sample_src_st.departure_time if sample_src_st else None
                    if arr_time_to_copy is None:
                        sample_dst_st = session.query(StopTime).filter(StopTime.stop_id == dst_stop_id).order_by(StopTime.stop_sequence.desc()).first()
                        arr_time_to_copy = sample_dst_st.arrival_time if sample_dst_st else None

                    # ensure we have times and arrival > departure (fallback to +/- hours when necessary)
                    from datetime import datetime as _dt, timedelta as _td
                    if dep_time_to_copy and arr_time_to_copy and arr_time_to_copy <= dep_time_to_copy:
                        # push arrival forward by 3 hours when times collate
                        arr_time_to_copy = (_dt.combine(now.date(), dep_time_to_copy) + _td(hours=3)).time()

                    if dep_time_to_copy and arr_time_to_copy:
                        # create new trip row
                        new_trip_id_str = f"AUTO_DIRECT_{source_code}_{dest_code}_{int(time.time())}"
                        new_trip = Trip(trip_id=new_trip_id_str, route_id=route_row.id, service_id=calendar_row.service_id, headsign=f"{dest_code}", direction_id=0, bike_allowed=False, wheelchair_accessible=True)
                        session.add(new_trip)
                        session.commit()

                        # insert adjacent stop_times: source (sequence 1) -> dest (sequence 2)
                        st_src = StopTime(trip_id=new_trip.id, stop_id=src_stop_id, arrival_time=dep_time_to_copy, departure_time=dep_time_to_copy, stop_sequence=1, cost=0.0, pickup_type=0, drop_off_type=0, platform_number="1")
                        st_dst = StopTime(trip_id=new_trip.id, stop_id=dst_stop_id, arrival_time=arr_time_to_copy, departure_time=arr_time_to_copy, stop_sequence=2, cost=0.0, pickup_type=0, drop_off_type=0, platform_number="1")
                        session.add_all([st_src, st_dst])
                        session.commit()

                        direct_trip_id = new_trip.id
    finally:
        session.close()

    # 1) Utilities
    elapsed, err, _ = time_sync(get_station_by_code, source_code)
    results["get_station_by_code"] = {"elapsed_s": elapsed, "error": err}

    elapsed, err, _ = time_sync(calculate_segment_fare, created_stops[source_code], created_stops[dest_code], "rail")
    results["calculate_segment_fare"] = {"elapsed_s": elapsed, "error": err}

    # 2) Graph building
    elapsed, err, _ = time_sync(raptor._build_graph_sync, now)
    results["OptimizedRAPTOR._build_graph_sync"] = {"elapsed_s": elapsed, "error": err}

    elapsed, err, _ = await time_async(raptor._build_graph(now))
    results["OptimizedRAPTOR._build_graph"] = {"elapsed_s": elapsed, "error": err}

    graph = await raptor._build_graph(now)

    # TDG helpers
    sample_stop_id = created_stops[source_code]
    elapsed, err, _ = time_sync(graph.get_departures_from_stop, sample_stop_id, now)
    results["TimeDependentGraph.get_departures_from_stop"] = {"elapsed_s": elapsed, "error": err}

    elapsed, err, _ = time_sync(graph.get_transfers_from_stop, sample_stop_id, now, 15)
    results["TimeDependentGraph.get_transfers_from_stop"] = {"elapsed_s": elapsed, "error": err}

    elapsed, err, _ = time_sync(graph.get_trip_segments, trip_id)
    results["TimeDependentGraph.get_trip_segments"] = {"elapsed_s": elapsed, "error": err} 

    # RAPTOR helpers
    session = SessionLocal()
    try:
        elapsed, err, _ = time_sync(raptor._get_active_service_ids, session, now)
        results["OptimizedRAPTOR._get_active_service_ids"] = {"elapsed_s": elapsed, "error": err}
    finally:
        session.close()

    elapsed, err, _ = time_sync(raptor._time_to_datetime, now, datetime.now().time())
    results["OptimizedRAPTOR._time_to_datetime"] = {"elapsed_s": elapsed, "error": err}

    # Create a Route object to test validators and scoring
    # fetch stop times with a fresh session (previous session may be closed)
    _tmp_s = SessionLocal()
    try:
        _first_st = _tmp_s.query(StopTime).filter(StopTime.trip_id == trip_id).order_by(StopTime.stop_sequence).first()
        _last_st = _tmp_s.query(StopTime).filter(StopTime.trip_id == trip_id).order_by(StopTime.stop_sequence.desc()).first()
        dep_time = _first_st.departure_time if _first_st is not None else datetime.now().time()
        arr_time = _last_st.arrival_time if _last_st is not None else datetime.now().time()
    finally:
        _tmp_s.close()

    seg = RouteSegment(
        trip_id=trip_id,
        departure_stop_id=created_stops[source_code],
        arrival_stop_id=created_stops[dest_code],
        departure_time=raptor._time_to_datetime(now, dep_time),
        arrival_time=raptor._time_to_datetime(now, arr_time),
        duration_minutes=10,
        distance_km=100.0,
        fare=250.0,
        train_name="TEST",
        train_number=str(trip_id),
    )

    route = Route()
    route.add_segment(seg)

    elapsed, err, _ = time_sync(raptor._validate_route_constraints, route, constraints)
    results["OptimizedRAPTOR._validate_route_constraints"] = {"elapsed_s": elapsed, "error": err}

    elapsed, err, _ = time_sync(raptor._calculate_score, route, constraints)
    results["OptimizedRAPTOR._calculate_score"] = {"elapsed_s": elapsed, "error": err}

    elapsed, err, _ = await time_async(raptor._process_route_transfers(route, graph, created_stops["NDLS"], constraints))
    results["OptimizedRAPTOR._process_route_transfers"] = {"elapsed_s": elapsed, "error": err}

    # Higher-level flows
    elapsed, err, routes = await time_async(raptor._compute_routes(created_stops[source_code], created_stops[dest_code], now, constraints))
    sample = None
    if routes:
        first = routes[0]
        sample = {"segments": len(first.segments), "total_duration": first.total_duration, "total_cost": first.total_cost, "score": first.score}
    results["OptimizedRAPTOR._compute_routes"] = {"elapsed_s": elapsed, "error": err, "result_count": len(routes) if routes else 0, "sample_route": sample}

    elapsed, err, routes = await time_async(raptor.find_routes(created_stops[source_code], created_stops[dest_code], now, constraints))
    sample = None
    if routes:
        first = routes[0]
        sample = {"segments": len(first.segments), "total_duration": first.total_duration, "total_cost": first.total_cost, "score": first.score}
    results["OptimizedRAPTOR.find_routes"] = {"elapsed_s": elapsed, "error": err, "result_count": len(routes) if routes else 0, "sample_route": sample}

    elapsed, err, routes = await time_async(rengine.search_routes(source_code, dest_code, now, constraints))
    sample = None
    if routes:
        first = routes[0]
        sample = {"segments": len(first.segments), "total_duration": first.total_duration, "total_cost": first.total_cost, "score": first.score}
    results["RouteEngine.search_routes"] = {"elapsed_s": elapsed, "error": err, "result_count": len(routes) if routes else 0, "sample_route": sample} 

    elapsed, err, _ = await time_async(rengine._apply_ml_ranking([route], None))
    results["RouteEngine._apply_ml_ranking"] = {"elapsed_s": elapsed, "error": err}

    elapsed, err, _ = await time_async(rengine._invalidate_affected_routes(trip_id))
    results["RouteEngine._invalidate_affected_routes"] = {"elapsed_s": elapsed, "error": err}

    # Persist results
    (OUT / "route_engine_timings_runner.json").write_text(json.dumps(results, indent=2))

    # Print a short summary
    print("\nRoute engine timings (ms):")
    print("-" * 60)
    for k, v in sorted(results.items(), key=lambda kv: kv[1]["elapsed_s"], reverse=True):
        ms = round(v["elapsed_s"] * 1000, 2) if v["elapsed_s"] is not None else None
        err = v["error"]
        print(f"{k:50s} {ms:10} {('ERROR:'+err) if err else ''}")
    print("-" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Measure route engine timings")
    parser.add_argument("--date", help="Departure date (YYYY-MM-DD). Defaults to today.", default=None)
    parser.add_argument("--source", help="Source station code", default="MMCT")
    parser.add_argument("--dest", help="Destination station code", default="NDLS")
    args = parser.parse_args()

    departure_dt = None
    if args.date:
        try:
            d = datetime.strptime(args.date, "%Y-%m-%d").date()
            departure_dt = datetime.combine(d, datetime.min.time()).replace(hour=6, minute=0)
        except Exception:
            departure_dt = None

    asyncio.run(run_all(departure_dt, args.source, args.dest))
