import pytest
from ..core.route_engine import OptimizedRAPTOR, RouteConstraints, Route, RouteSegment

@pytest.mark.asyncio
async def test_rt_024_duplicate_trips():
    """Test case RT-024: Deduplicate routes with duplicate trips in dataset."""
    raptor = OptimizedRAPTOR()
    constraints = RouteConstraints(max_results=10)

    # Mock input data: duplicate trips. use two simple identical segments
    from datetime import datetime
    from ..core.route_engine import RouteSegment

    seg = RouteSegment(
        trip_id=1,
        departure_stop_id=10,
        arrival_stop_id=20,
        departure_time=datetime(2026,1,1,8,0),
        arrival_time=datetime(2026,1,1,10,0),
        duration_minutes=120,
        distance_km=200.0,
        fare=500.0
    )
    route1 = Route(segments=[seg], total_distance=200, transfers=[])
    # make a deep copy for duplicate
    route2 = Route(segments=[seg], total_distance=200, transfers=[])

    # graph is not needed for simple dedup logic
    deduplicated_routes = await raptor._deduplicate_routes([route1, route2])

    # Assert deduplication
    assert len(deduplicated_routes) == 1
