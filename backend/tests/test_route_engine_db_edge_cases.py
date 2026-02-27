import pytest
import backend.seat_inventory_models  # ensure Coach model is registered with Base before DB mapper configuration
from datetime import datetime, date, time, timedelta

from core.route_engine import RouteEngine, RouteConstraints
from database import SessionLocal
from database.models import Trip, StopTime


@pytest.mark.asyncio
async def test_rt_016_same_source_and_destination_returns_empty(db_session, sample_stops, sample_calendar):
    engine = RouteEngine()
    departure_dt = datetime.combine(date.today(), time(9, 0))

    # same station code for source and destination
    routes = await engine.search_routes(sample_stops['NDLS'].code, sample_stops['NDLS'].code, departure_dt)
    assert routes == []


@pytest.mark.asyncio
async def test_rt_017_midnight_crossing_is_handled(db_session, sample_stops, sample_route, sample_calendar):
    """Trip departs before midnight and arrives next day -> duration rolled over correctly"""
    # create a trip that departs 23:30 and arrives 01:30 (next day)
    trip = Trip(trip_id="OVN_DB_001", route_id=sample_route.id, service_id=sample_calendar.service_id)
    db_session.add(trip)
    db_session.commit()

    st1 = StopTime(trip_id=trip.id, stop_id=sample_stops['NDLS'].id,
                   arrival_time=time(23, 30), departure_time=time(23, 30), stop_sequence=1, cost=0.0)
    st2 = StopTime(trip_id=trip.id, stop_id=sample_stops['MMCT'].id,
                   arrival_time=time(1, 30), departure_time=time(1, 30), stop_sequence=2, cost=0.0)
    db_session.add_all([st1, st2])
    db_session.commit()

    engine = RouteEngine()
    departure_dt = datetime.combine(date.today(), time(22, 0))

    routes = await engine.search_routes('NDLS', 'MMCT', departure_dt)
    assert routes, "expected at least one route"
    route = routes[0]

    # the engine should have rolled the arrival to next day -> duration 120 minutes
    assert any(seg.duration_minutes == 120 for seg in route.segments)
    assert route.total_duration >= 120


@pytest.mark.asyncio
async def test_rt_018_multi_day_journey_calculated_correctly(db_session, sample_stops, sample_route, sample_calendar):
    """A journey spanning multiple day-rollovers should have correct total duration."""
    trip = Trip(trip_id="MULTI_DB_001", route_id=sample_route.id, service_id=sample_calendar.service_id)
    db_session.add(trip)
    db_session.commit()

    # Stop 1: depart day0 08:00
    s1 = StopTime(trip_id=trip.id, stop_id=sample_stops['NDLS'].id,
                  arrival_time=time(8, 0), departure_time=time(8, 0), stop_sequence=1, cost=0.0)

    # Stop 2: arrive day1 06:00 depart day1 07:00 (rollover once)
    s2 = StopTime(trip_id=trip.id, stop_id=sample_stops['PUNE'].id,
                  arrival_time=time(6, 0), departure_time=time(7, 0), stop_sequence=2, cost=0.0)

    # Stop 3: arrive day2 05:00 (rollover again) -> makes overall journey > 24h
    s3 = StopTime(trip_id=trip.id, stop_id=sample_stops['MMCT'].id,
                  arrival_time=time(5, 0), departure_time=time(5, 0), stop_sequence=3, cost=0.0)

    db_session.add_all([s1, s2, s3])
    db_session.commit()

    engine = RouteEngine()
    departure_dt = datetime.combine(date.today(), time(8, 0))

    routes = await engine.search_routes('NDLS', 'MMCT', departure_dt)
    assert routes, "expected route for multi-day trip"
    route = routes[0]

    assert route.total_duration > 24 * 60, "expected total_duration > 24 hours"


@pytest.mark.asyncio
async def test_rt_019_circular_routes_do_not_create_infinite_loops(db_session, sample_stops, sample_route, sample_calendar):
    """Graph contains loops (A->B, B->A) but engine should avoid revisiting stations within a single route."""
    # Trip A->B
    t_ab = Trip(trip_id="LOOP_AB", route_id=sample_route.id, service_id=sample_calendar.service_id)
    db_session.add(t_ab)
    db_session.commit()
    st_ab_1 = StopTime(trip_id=t_ab.id, stop_id=sample_stops['NDLS'].id,
                       arrival_time=time(9, 0), departure_time=time(9, 0), stop_sequence=1, cost=0.0)
    st_ab_2 = StopTime(trip_id=t_ab.id, stop_id=sample_stops['PUNE'].id,
                       arrival_time=time(10, 0), departure_time=time(10, 0), stop_sequence=2, cost=0.0)

    # Trip B->A (loop back)
    t_ba = Trip(trip_id="LOOP_BA", route_id=sample_route.id, service_id=sample_calendar.service_id)
    db_session.add(t_ba)
    db_session.commit()
    st_ba_1 = StopTime(trip_id=t_ba.id, stop_id=sample_stops['PUNE'].id,
                       arrival_time=time(10, 15), departure_time=time(10, 15), stop_sequence=1, cost=0.0)
    st_ba_2 = StopTime(trip_id=t_ba.id, stop_id=sample_stops['NDLS'].id,
                       arrival_time=time(11, 15), departure_time=time(11, 15), stop_sequence=2, cost=0.0)

    # Direct Trip A->C
    t_ac = Trip(trip_id="DIRECT_AC", route_id=sample_route.id, service_id=sample_calendar.service_id)
    db_session.add(t_ac)
    db_session.commit()
    st_ac_1 = StopTime(trip_id=t_ac.id, stop_id=sample_stops['NDLS'].id,
                       arrival_time=time(12, 0), departure_time=time(12, 0), stop_sequence=1, cost=0.0)
    st_ac_2 = StopTime(trip_id=t_ac.id, stop_id=sample_stops['BLRC'].id,
                       arrival_time=time(13, 0), departure_time=time(13, 0), stop_sequence=2, cost=0.0)

    db_session.add_all([st_ab_1, st_ab_2, st_ba_1, st_ba_2, st_ac_1, st_ac_2])
    db_session.commit()

    engine = RouteEngine()
    departure_dt = datetime.combine(date.today(), time(9, 0))

    routes = await engine.search_routes('NDLS', 'BLRC', departure_dt)
    assert routes, "expected at least one route to BLRC"
    route = routes[0]

    stations = route.get_all_stations()
    # no repeated stations inside same route
    assert len(stations) == len(set(stations))
    # prefer direct route (no loop) so first segment should be direct to BLRC
    assert route.segments[0].arrival_stop_id == sample_stops['BLRC'].id


@pytest.mark.asyncio
async def test_rt_020_transfer_minimum_time_respected(db_session, sample_stops, sample_route, sample_calendar):
    """Transfers shorter than the min_transfer_time should be rejected."""
    # A->B arrives 09:00
    t_ab = Trip(trip_id="AB_SHORT", route_id=sample_route.id, service_id=sample_calendar.service_id)
    db_session.add(t_ab)
    db_session.commit()
    st_ab_1 = StopTime(trip_id=t_ab.id, stop_id=sample_stops['NDLS'].id,
                       arrival_time=time(8, 0), departure_time=time(8, 0), stop_sequence=1, cost=0.0)
    st_ab_2 = StopTime(trip_id=t_ab.id, stop_id=sample_stops['PUNE'].id,
                       arrival_time=time(9, 0), departure_time=time(9, 0), stop_sequence=2, cost=0.0)

    # B->C short transfer (dep 09:05) -- should be rejected when min_transfer_time=15
    t_bc_short = Trip(trip_id="BC_SHORT", route_id=sample_route.id, service_id=sample_calendar.service_id)
    db_session.add(t_bc_short)
    db_session.commit()
    st_bc_s_1 = StopTime(trip_id=t_bc_short.id, stop_id=sample_stops['PUNE'].id,
                         arrival_time=time(9, 5), departure_time=time(9, 5), stop_sequence=1, cost=0.0)
    st_bc_s_2 = StopTime(trip_id=t_bc_short.id, stop_id=sample_stops['BLRC'].id,
                         arrival_time=time(10, 0), departure_time=time(10, 0), stop_sequence=2, cost=0.0)

    # B->C long transfer (dep 09:30) -- acceptable
    t_bc_long = Trip(trip_id="BC_LONG", route_id=sample_route.id, service_id=sample_calendar.service_id)
    db_session.add(t_bc_long)
    db_session.commit()
    st_bc_l_1 = StopTime(trip_id=t_bc_long.id, stop_id=sample_stops['PUNE'].id,
                         arrival_time=time(9, 30), departure_time=time(9, 30), stop_sequence=1, cost=0.0)
    st_bc_l_2 = StopTime(trip_id=t_bc_long.id, stop_id=sample_stops['BLRC'].id,
                         arrival_time=time(10, 30), departure_time=time(10, 30), stop_sequence=2, cost=0.0)

    db_session.add_all([st_ab_1, st_ab_2, st_bc_s_1, st_bc_s_2, st_bc_l_1, st_bc_l_2])
    db_session.commit()

    engine = RouteEngine()
    departure_dt = datetime.combine(date.today(), time(8, 0))

    constraints = RouteConstraints(min_transfer_time=15)
    routes = await engine.search_routes('NDLS', 'BLRC', departure_dt, constraints=constraints)

    assert routes, "expected at least one route"
    # ensure chosen route(s) have transfer durations >= 15
    for r in routes:
        for td in r.get_transfer_durations():
            assert td >= 15
