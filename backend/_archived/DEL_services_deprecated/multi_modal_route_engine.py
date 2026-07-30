# Consolidated wrapper - actual implementation is in backend.core.route_engine
# This file maintained for backwards compatibility
from core.route_engine import RailwayRouteEngine, route_engine

# Export RailwayRouteEngine as MultiModalRouteEngine (alias for compatibility)
MultiModalRouteEngine = RailwayRouteEngine
multi_modal_route_engine = route_engine

__all__ = ["MultiModalRouteEngine", "multi_modal_route_engine", "route_engine"]

