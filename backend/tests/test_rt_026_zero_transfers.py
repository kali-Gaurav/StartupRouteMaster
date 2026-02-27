import pytest
from ..core.route_engine import OptimizedRAPTOR, RouteConstraints
from models import Route

@pytest.mark.asyncio
async def test_rt_026_zero_transfers():
    """Test case RT-026: Allow only direct routes when max_transfers = 0."""
    raptor = OptimizedRAPTOR()
    constraints = RouteConstraints(max_results=10, max_transfers=0)

    # Mock input data: routes with transfers
    route_with_transfer = Route(segments=[...], total_distance=100, transfers=[...])
    direct_route = Route(segments=[...], total_distance=50, transfers=[])

    # Mock graph and constraints
    graph = ...  # Mock graph with routes

    # Process routes
    valid_routes = await raptor._filter_routes_by_transfers([route_with_transfer, direct_route], constraints)

    # Assert only direct routes allowed
    assert len(valid_routes) == 1
    assert valid_routes[0] == direct_route
