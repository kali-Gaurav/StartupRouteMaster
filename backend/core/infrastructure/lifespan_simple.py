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
        from core.infrastructure.container import container
        # Trigger explicit registration of core providers
        import core.auth.provider
        import core.nexus.bootstrapper
        
        # Use container.get to ensure proper IoC initialization and status tracking
        cache_svc = await container.get("cache")
        runtime["redis"] = "ready" if cache_svc and getattr(cache_svc, 'redis', None) else "degraded"
        logger.info("Cache initialized via IoC.")
    except Exception as exc:
        runtime["redis"] = "degraded"
        logger.warning("Cache initialization skipped: %s", exc)

    try:
        from core.infrastructure.container import container
        from datetime import datetime

        # Ensure container.get is used for proper IoC initialization
        engine = await container.get("search")
        # Use graph_initialized attribute instead of is_loaded() method
        runtime["route_engine"] = "loaded" if engine and getattr(engine, 'graph_initialized', False) else "degraded"
        logger.info("Route engine bootstrap probe complete via IoC.")
    except Exception as exc:
        runtime["route_engine"] = "degraded"
        logger.warning("Route engine bootstrap probe failed: %s", exc)

    try:
        from core.sovereign.network_pressure import network_pressure
        from core.sovereign.orchestrator import sio
        # Trigger an initial pressure refresh (non-blocking)
        import asyncio
        asyncio.create_task(network_pressure.refresh())
        
        # Start the Global Pulse Heartbeat (The Sovereign 'Breath')
        asyncio.create_task(sio.run_global_pulse())
        
        logger.info("Sovereign Intelligence: NPC & Global Pulse Heartbeat started.")

        try:
            from workers.orchestrator import start_reconciliation_worker
            start_reconciliation_worker()
            logger.info("🛠️ Reconciliation worker started in simplified lifespan.")
        except Exception as exc:
            logger.warning(f"Could not start reconciliation worker in simplified lifespan: {exc}")
            
        try:
            from telegram_bot.polling import polling_manager
            import asyncio
            asyncio.create_task(polling_manager.start())
            logger.info("Telegram polling manager started in simplified lifespan.")
        except Exception as exc:
            logger.warning(f"Could not start Telegram polling: {exc}")
            
    except Exception as exc:
        logger.error("Failed to initialize Sovereign Layer: %s", exc)

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
        from workers.orchestrator import stop_reconciliation_worker
        stop_reconciliation_worker()
        logger.info("🛠️ Reconciliation worker stopped in simplified lifespan.")
    except Exception as exc:
        logger.warning(f"Failed to stop reconciliation worker in simplified lifespan: {exc}")

    try:
        from database.session import _dispose_all_pools

        await _dispose_all_pools()
        logger.info("Database connections closed.")
    except Exception:
        pass

    logger.info("Backend shutdown complete.")
