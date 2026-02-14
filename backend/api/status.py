from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from datetime import datetime

from backend.database import get_db
from backend.services.station_service import StationService
from backend.services.route_engine import route_engine # Assuming route_engine can provide stats

router = APIRouter(prefix="/api", tags=["status"])
logger = logging.getLogger(__name__)

@router.get("/health")
async def general_health_check(db: Session = Depends(get_db)):
    """General health check endpoint for the application."""
    try:
        # Check database connectivity
        db.execute(text("SELECT 1"))
        # Add other critical service checks here (e.g., payment service, cache service)
        return {"status": "healthy", "database": "up"}
    except Exception as e:
        # Log full exception with stack trace for easier debugging in CI/local runs
        logger.exception(f"General health check failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Application is unhealthy")

@router.get("/health/live")
async def liveness_probe():
    """Liveness probe: indicates if the application is running."""
    return {"status": "live"}

@router.get("/health/ready")
async def readiness_probe(db: Session = Depends(get_db)):
    """Readiness probe: indicates if the application is ready to serve requests."""
    try:
        logger.debug("Readiness probe: starting checks")
        # Check if database is ready
        db.execute(text("SELECT 1"))
        logger.debug("Readiness probe: database connectivity OK")

        # Check if route engine is loaded (if applicable)
        loaded = route_engine.is_loaded()
        logger.debug("Readiness probe: route_engine.is_loaded() -> %s", loaded)

        # If route engine isn't loaded yet, attempt a synchronous lazy-load for the readiness probe.
        if not loaded:
            try:
                from backend.database import SessionLocal

                db2 = SessionLocal()
                try:
                    route_engine.load_graph_from_db(db2)
                    loaded = route_engine.is_loaded()
                    logger.debug("Readiness probe: attempted lazy-load -> %s", loaded)
                finally:
                    db2.close()
            except Exception as ex:
                logger.exception("Failed to lazy-load route_engine during readiness check: %s", ex)

        if not loaded:  # Still not ready
            logger.debug("Readiness probe: route engine not loaded (will report NOT READY)")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Route engine not loaded")

        # Add other readiness checks here
        return {"status": "ready", "database": "ready", "route_engine": "loaded"}
    except Exception as e:
        # Include full exception trace to help diagnose readiness failures
        logger.exception(f"Readiness probe failed: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Application is not ready")

@router.get("/stats")
async def get_application_stats(db: Session = Depends(get_db)):
    """Provides general statistics about the application."""
    station_service = StationService(db)
    
    total_stations = station_service.get_total_stations_count() # Assuming this method exists
    total_routes = route_engine.get_total_routes_count() # Assuming this method exists
    total_trains = route_engine.get_total_trains_count() # Assuming this method exists

    return {
        "total_stations": total_stations,
        "total_routes": total_routes,
        "total_trains": total_trains,
        "timestamp": datetime.now().isoformat()
    }
