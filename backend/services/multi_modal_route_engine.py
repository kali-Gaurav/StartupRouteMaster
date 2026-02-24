# Consolidated wrapper - actual implementation is in backend.core.route_engine
# This file maintained for backwards compatibility
from backend.core.route_engine import RouteEngine, route_engine

# Export RouteEngine as MultiModalRouteEngine (alias for compatibility)
MultiModalRouteEngine = RouteEngine
multi_modal_route_engine = route_engine

__all__ = ["MultiModalRouteEngine", "multi_modal_route_engine", "route_engine"]

