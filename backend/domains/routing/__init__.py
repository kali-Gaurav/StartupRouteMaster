"""
Routing Domain - Route Finding & Optimization

This is the authoritative location for all routing logic.

PHASE 1 CONSOLIDATION:
This domain consolidates all route engine implementations into a single,
clean, production-grade routing system.

Architecture:
- engine.py: RailwayRouteEngine (main implementation)
- interfaces.py: RouteFinder protocol (contract)
- adapters.py: Backwards compatibility layer
- raptor.py, graph.py, etc: Supporting components (reference core/route_engine/)

Dependency: Single source of truth for routing - all old implementations (advanced_route_engine.py,
multi_modal_route_engine.py, etc.) are archived.

Usage:
    from domains.routing import RailwayRouteEngine
    engine = RailwayRouteEngine()
    routes = await engine.search_routes(source, dest, date)
"""

import sys
import os

# Handle imports for both running from backend/ and startupV2/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from .engine import RailwayRouteEngine
    from .interfaces import RouteFinder, Journey, Segment
    from .adapters import LegacyHybridSearchAdapter, get_legacy_adapter
except ImportError as e:
    # Fallback: try absolute imports
    try:
        from backend.domains.routing.engine import RailwayRouteEngine
        from backend.domains.routing.interfaces import RouteFinder, Journey, Segment
        from backend.domains.routing.adapters import LegacyHybridSearchAdapter, get_legacy_adapter
    except ImportError:
        raise e

__all__ = [
    "RailwayRouteEngine",
    "RouteFinder",
    "Journey",
    "Segment",
    "LegacyHybridSearchAdapter",
    "get_legacy_adapter",
]
