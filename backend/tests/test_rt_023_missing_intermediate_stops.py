from datetime import datetime

from core.route_engine import OptimizedRAPTOR, RouteSegment


def test_rt_023_missing_intermediate_stops_rejected():
    raptor = OptimizedRAPTOR()

    # Two segments that are *not* contiguous (missing intermediate stop)
    seg1 = RouteSegment(
        trip_id=101,
        departure_stop_id=1,
        arrival_stop_id=3,  # jumped over station 2
        departure_time=datetime(2026, 2, 20, 8, 0),
        arrival_time=datetime(2026, 2, 20, 9, 0),
        duration_minutes=60,
        distance_km=100.0,
        fare=100.0,
        train_name="Jump",
        train_number="J101",
    )

    seg2 = RouteSegment(
        trip_id=101,
        departure_stop_id=4,
        arrival_stop_id=5,
        departure_time=datetime(2026, 2, 20, 10, 0),
        arrival_time=datetime(2026, 2, 20, 11, 0),
        duration_minutes=60,
        distance_km=80.0,
        fare=80.0,
        train_name="Later",
        train_number="L101",
    )

    assert raptor._validate_segment_continuity([seg1, seg2]) is False
