# Compatibility wrapper - actual implementation moved to backend.core
from core.route_engine import get_route_engine, RailwayRouteEngine, RouteConstraints
from core.engines.route_engine import RouteEngine

# Note: Using lazy-initialization to prevent circular dependency at module level (G11.4).
def get_engine():
    return get_route_engine()

# For backward compatibility with files doing 'from services.route_engine import route_engine'
# We have to be careful here. If we instantiate it now, we loop.
# We can use a proxy or just update callers.

# Given the urgency, let's update this to a proxy-like function if possible,
# or just export the same name but as a function call? No, that breaks attribute access.

# Best approach: Update all callers of 'services.route_engine' to use core directly.
# For now, let's just make it clear.
