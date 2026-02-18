import pytest
from datetime import datetime

from backend.core.route_engine import OptimizedRAPTOR, TransferConnection, RouteConstraints


def test_rt_021_exact_transfer_boundary():
    raptor = OptimizedRAPTOR()
    constraints = RouteConstraints()

    # Transfer exactly equal to minimum allowed
    arrival = datetime(2026, 2, 20, 10, 0)
    departure = datetime(2026, 2, 20, 10, 15)  # exactly 15 minutes later
    transfer = TransferConnection(
        station_id=100,
        arrival_time=arrival,
        departure_time=departure,
        duration_minutes=15,
        station_name="Test Station",
        facilities_score=0.5,
        safety_score=0.5,
    )

    assert raptor._is_feasible_transfer(transfer, constraints) is True
