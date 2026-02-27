# Compatibility wrapper - actual implementation moved to backend.core
from core.route_engine import RouteEngine

route_engine = RouteEngine()

__all__ = ["RouteEngine", "route_engine"]

