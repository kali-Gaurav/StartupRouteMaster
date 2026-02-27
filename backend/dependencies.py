"""
Dependency Injection Container

Centralizes all dependency creation and management for the backend.
Uses FastAPI's Depends() for proper lifecycle management.

Key Principles:
- Single responsibility: Each function creates one service
- Singletons: Engines are singletons created once and reused
- Feature flags: Configuration drives behavior
- Logging: Observability for which implementation is used
"""

import logging
import sys
import os
from functools import lru_cache
from typing import Union

from fastapi import Depends

# Handle imports for both running from backend/ and startupV2/
sys.path.insert(0, os.path.dirname(__file__))

try:
    from config import Config
    from domains.routing import RailwayRouteEngine, LegacyHybridSearchAdapter, get_legacy_adapter
except ImportError:
    from config import Config
    from domains.routing import RailwayRouteEngine, LegacyHybridSearchAdapter, get_legacy_adapter

logger = logging.getLogger(__name__)


# ============================================================================
# ROUTING ENGINE (Phase 1 Consolidation - Strangler Pattern)
# ============================================================================


@lru_cache(maxsize=1)
def get_route_engine() -> RailwayRouteEngine:
    """
    Get the new consolidated RailwayRouteEngine.

    This is the primary implementation. Created once and cached.

    Returns:
        RailwayRouteEngine instance

    Note:
        The engine logs its initialization status including detected mode
        (OFFLINE/HYBRID/ONLINE) on first creation.
    """
    logger.info("🚀 Initializing RailwayRouteEngine (domains/routing/engine.py)")
    engine = RailwayRouteEngine()
    logger.info("✅ RailwayRouteEngine initialized successfully")
    return engine


@lru_cache(maxsize=1)
def get_legacy_adapter_instance() -> LegacyHybridSearchAdapter:
    """
    Get the legacy adapter for backwards compatibility.

    Used only when USE_NEW_ROUTING_ENGINE=false (rollback scenario).

    Returns:
        LegacyHybridSearchAdapter instance wrapping the new engine

    Note:
        This adapter internally uses the new engine, ensuring consistent behavior.
    """
    logger.warning("🟡 Initializing LegacyHybridSearchAdapter (backwards compatibility mode)")
    engine = get_route_engine()  # Reuse same engine instance
    adapter = LegacyHybridSearchAdapter(engine)
    return adapter


def get_active_route_engine() -> Union[RailwayRouteEngine, LegacyHybridSearchAdapter]:
    """
    Get the active route engine based on feature flag.

    This is the main dependency for route-based API endpoints.
    Use this in FastAPI Depends() to get the correct implementation.

    Feature Flag: Config.USE_NEW_ROUTING_ENGINE
        - true: Returns new RailwayRouteEngine
        - false: Returns LegacyHybridSearchAdapter (instant rollback)

    Returns:
        Active route engine/adapter instance

    Example:
        @router.get("/api/search")
        async def search_routes(engine = Depends(get_active_route_engine)):
            routes = await engine.search_routes(...)
            return routes

    Monitoring:
        Check logs for:
        - "🟢 Using NEW RouteEngine" - Good (using new implementation)
        - "🟡 Using LEGACY HybridSearchAdapter" - Fallback mode
    """
    if Config.USE_NEW_ROUTING_ENGINE:
        logger.info("🟢 get_active_route_engine() returning NEW RouteEngine")
        return get_route_engine()
    else:
        logger.warning("🟡 get_active_route_engine() returning LEGACY HybridSearchAdapter (rollback)")
        return get_legacy_adapter_instance()


# ============================================================================
# SERVICES (Add more services here as needed)
# ============================================================================
# Future: add other domain services (booking, inventory, pricing, etc.)


# ============================================================================
# HEALTH CHECK / DIAGNOSTICS
# ============================================================================


def get_routing_engine_status() -> dict:
    """
    Get diagnostic information about the routing engine.

    Used for health checks and debugging.

    Returns:
        Dictionary with status information
    """
    return {
        "feature_flag_use_new": Config.USE_NEW_ROUTING_ENGINE,
        "active_engine": "RailwayRouteEngine" if Config.USE_NEW_ROUTING_ENGINE else "LegacyHybridSearchAdapter",
        "mode": Config.get_mode(),
        "offline_mode": Config.OFFLINE_MODE,
        "real_time_enabled": Config.REAL_TIME_ENABLED,
    }
