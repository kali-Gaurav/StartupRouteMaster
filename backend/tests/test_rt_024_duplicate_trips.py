import pytest
from ..core.route_engine import OptimizedRAPTOR, RouteConstraints
from backend.models import Route

@pytest.mark.asyncio
async def test_rt_024_duplicate_trips():
    """Test case RT-024: Deduplicate routes with duplicate trips in dataset."""
    raptor = OptimizedRAPTOR()
    constraints = RouteConstraints(max_results=10)

    # Mock input data: duplicate trips
    route1 = Route(segments=[...], total_distance=100, transfers=[])
    route2 = Route(segments=[...], total_distance=100, transfers=[])  # Duplicate of route1

    # Mock graph and constraints
    graph = ...  # Mock graph with duplicate trips

    # Process routes
    deduplicated_routes = await raptor._deduplicate_routes([route1, route2])

    # Assert deduplication
    assert len(deduplicated_routes) == 1