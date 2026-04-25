"""Simplified lifespan for development and isolated bootstrap verification."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger("routemaster.lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize only the minimal runtime dependencies needed for bootstrap-safe operation."""
    logger.info("Starting RouteMaster backend with simplified lifespan.")

    runtime = getattr(app.state, "runtime_components", {})
    runtime.setdefault("database", "unknown")
    runtime.setdefault("redis", "unknown")
    runtime.setdefault("route_engine", "unknown")
    runtime.setdefault("external_api", "unknown")

    try:
        from database.session import initialize_database_pools

        await initialize_database_pools()
        runtime["database"] = "ready"
        logger.info("Database pools initialized.")
    except Exception as exc:
        runtime["database"] = "degraded"
        logger.warning("Database initialization skipped: %s", exc)

    try:
        from core.container import container
        # Use container.get to ensure proper IoC initialization and status tracking
        cache_svc = await container.get("cache")
        runtime["redis"] = "ready" if cache_svc and getattr(cache_svc, 'redis', None) else "degraded"
        logger.info("Cache initialized via IoC.")
    except Exception as exc:
        runtime["redis"] = "degraded"
        logger.warning("Cache initialization skipped: %s", exc)

    try:
        from core.container import container
        from datetime import datetime

        # Ensure container.get is used for proper IoC initialization
        engine = await container.get("search")
        # Use graph_initialized attribute instead of is_loaded() method
        runtime["route_engine"] = "loaded" if engine and getattr(engine, 'graph_initialized', False) else "degraded"
        logger.info("Route engine bootstrap probe complete via IoC.")
    except Exception as exc:
        runtime["route_engine"] = "degraded"
        logger.warning("Route engine bootstrap probe failed: %s", exc)

    app.state.runtime_components = runtime

    @app.get("/health/detailed")
    async def detailed_health():
        return {
            "status": "operational" if runtime["database"] == "ready" else "degraded",
            "version": "3.0.0",
            "environment": getattr(getattr(app.state, "settings", None), "environment", "development"),
            "components": runtime,
        }

    logger.info("Simplified backend startup complete.")
    yield

    logger.info("Shutting down backend with simplified lifespan.")
    try:
        from database.session import _dispose_all_pools

        await _dispose_all_pools()
        logger.info("Database connections closed.")
    except Exception:
        pass

    logger.info("Backend shutdown complete.")
