from datetime import datetime

from core.route_engine import OptimizedRAPTOR, TransferConnection, RouteConstraints


def test_rt_022_station_multiple_platforms():
    raptor = OptimizedRAPTOR()
    constraints = RouteConstraints()

    # Transfer where platform_from != platform_to should still be feasible
    arrival = datetime(2026, 2, 20, 12, 0)
    departure = datetime(2026, 2, 20, 12, 20)
    transfer = TransferConnection(
        station_id=200,
        arrival_time=arrival,
        departure_time=departure,
        duration_minutes=20,
        station_name="MultiPlatformStation",
        facilities_score=0.8,
        safety_score=0.9,
        platform_from="1",
        platform_to="5",
    )

    # Platform difference must NOT break continuity — transfer should be feasible
    assert raptor._is_feasible_transfer(transfer, constraints) is True
