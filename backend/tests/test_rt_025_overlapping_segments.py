import pytest
from ..core.route_engine import OptimizedRAPTOR, RouteConstraints
from models import Route

@pytest.mark.asyncio
async def test_rt_025_overlapping_segments():
    """Test case RT-025: Reject routes with overlapping segments."""
    raptor = OptimizedRAPTOR()
    constraints = RouteConstraints(max_results=10)

    # Mock input data: overlapping segments
    route = Route(segments=[...], total_distance=100, transfers=[])

    # Mock graph and constraints
    graph = ...  # Mock graph with overlapping segments

    # Process routes
    valid_routes = await raptor._validate_route_segments(route, constraints)

    # Assert invalid route rejected
    assert len(valid_routes) == 0
