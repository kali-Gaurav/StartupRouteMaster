from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from datetime import datetime
import redis.asyncio as aioredis

from database import get_db
from services.station_service import StationService
from services.route_engine import route_engine # Assuming route_engine can provide stats
from database.config import Config
from core.redis import async_redis_client

router = APIRouter(prefix="", tags=["status"])
logger = logging.getLogger(__name__)

@router.get("/health")
async def general_health_check(db: Session = Depends(get_db)):
    """General health check endpoint returning component statuses.

    Components include database, redis, route_engine and external_api.  The
    external_api component does **not** hit remote services on every call – it
    simply verifies that the most recent successful call was ``fresh`` (see
    ``backend.utils.external_api_health``).
    """
    from utils import external_api_health

    components = {
        "database": "down",
        "redis": "down",
        "route_engine": "unknown",
        "external_api": "unknown"
    }

    overall = "ok"
    # database
    try:
        db.execute(text("SELECT 1"))
        components["database"] = "ok"
    except Exception as e:
        logger.warning(f"Database health failed: {e}")
        components["database"] = "down"
        overall = "degraded"

    # redis
    try:
        await async_redis_client.ping()
        components["redis"] = "ok"
    except Exception as redis_err:
        logger.warning(f"Redis health check failed: {redis_err}")
        components["redis"] = "down"
        overall = "degraded"

    # route engine
    try:
        loaded = route_engine.is_loaded()
        components["route_engine"] = "loaded" if loaded else "loading"
        if not loaded:
            overall = "degraded"
    except Exception as e:
        logger.warning(f"Route engine health probe failed: {e}")
        components["route_engine"] = "down"
        overall = "degraded"

    # external API freshness
    if external_api_health.get_last_success():
        if external_api_health.is_fresh():
            components["external_api"] = "ok"
        else:
            components["external_api"] = "stale"
            overall = "degraded"
    else:
        components["external_api"] = "unknown"
        overall = "degraded"

    return {"status": overall, "components": components, "timestamp": datetime.utcnow().isoformat()}

@router.get("/health/live")
async def liveness_probe():
    """Liveness probe: indicates if the application is running."""
    return {
        "status": "live",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/ready")


async def readiness_probe(request: Request, db: Session = Depends(get_db)):
    """Readiness probe: indicates if the application is ready to serve requests.

    Combines database connectivity, route engine load state and a simple flag that
    is set once the warm‑up sequence (graph + station cache) completes.
    """
    try:
        logger.debug("Readiness probe: starting checks")
        # Basic DB check
        db.execute(text("SELECT 1"))
        logger.debug("Readiness probe: database connectivity OK")

        # Redis is optional; warn but do not fail
        try:
            await async_redis_client.ping()
            logger.debug("Readiness probe: Redis connectivity OK")
        except Exception as redis_err:
            logger.warning(f"Redis not available during readiness check: {redis_err}")

        # Route engine must be loaded
        loaded = route_engine.is_loaded()
        logger.debug("Readiness probe: route_engine.is_loaded() -> %s", loaded)

        if not loaded:
            # attempt synchronous load as a last resort
            try:
                from database import SessionLocal
                db2 = SessionLocal()
                try:
                    route_engine.load_graph_from_db(db2)
                    loaded = route_engine.is_loaded()
                    logger.debug("Readiness probe: attempted lazy-load -> %s", loaded)
                finally:
                    db2.close()
            except Exception as ex:
                logger.exception("Failed to lazy-load route_engine during readiness check: %s", ex)

        if not loaded:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Route engine not loaded")

        # check that startup warmup flag was set
        if not getattr(request.app.state, "startup_complete", False):
            logger.debug("Readiness probe: startup warmup not yet finished")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Warmup not finished")

        return {"status": "ready", "components": {"database": "ready", "route_engine": "loaded"}, "timestamp": datetime.utcnow().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Readiness probe failed: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Application is not ready")

@router.get("/stats")
async def get_application_stats(db: Session = Depends(get_db)):
    """Provides general statistics about the application."""
    import asyncio
    station_service = StationService(db)
    
    total_stations, total_routes, total_trains = await asyncio.gather(
        asyncio.to_thread(station_service.get_total_stations_count),
        asyncio.to_thread(route_engine.get_total_routes_count),
        asyncio.to_thread(route_engine.get_total_trains_count)
    )

    return {
        "total_stations": total_stations,
        "total_routes": total_routes,
        "total_trains": total_trains,
        "timestamp": datetime.utcnow().isoformat()
    }
