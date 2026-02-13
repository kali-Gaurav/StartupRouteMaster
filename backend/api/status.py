from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
from datetime import datetime

from database import get_db
from services.station_service import StationService
from services.route_engine import route_engine # Assuming route_engine can provide stats

router = APIRouter(prefix="/api", tags=["status"])
logger = logging.getLogger(__name__)

@router.get("/health")
async def general_health_check(db: Session = Depends(get_db)):
    """General health check endpoint for the application."""
    try:
        # Check database connectivity
        db.execute("SELECT 1")
        # Add other critical service checks here (e.g., payment service, cache service)
        return {"status": "healthy", "database": "up"}
    except Exception as e:
        logger.error(f"General health check failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Application is unhealthy")

@router.get("/health/live")
async def liveness_probe():
    """Liveness probe: indicates if the application is running."""
    return {"status": "live"}

@router.get("/health/ready")
async def readiness_probe(db: Session = Depends(get_db)):
    """Readiness probe: indicates if the application is ready to serve requests."""
    try:
        # Check if database is ready
        db.execute("SELECT 1")
        # Check if route engine is loaded (if applicable)
        if not route_engine.is_loaded(): # Assuming a method to check if loaded
             raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Route engine not loaded")
        
        # Add other readiness checks here
        return {"status": "ready", "database": "ready", "route_engine": "loaded"}
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
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
