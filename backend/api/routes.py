from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from database import get_db
from schemas import RouteDetailSchema
from models import Route as RouteModel

router = APIRouter(prefix="/api/routes", tags=["routes"])
logger = logging.getLogger(__name__)


@router.get("/{route_id}", response_model=RouteDetailSchema)
async def get_route_details(
    route_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed route information for a previously saved route."""
    try:
        # Note: This fetches a historical route. The `search` endpoint provides fresh results.
        route = db.query(RouteModel).filter(RouteModel.id == route_id).first()

        if not route:
            raise HTTPException(status_code=404, detail="Route not found")

        return route

    except Exception as e:
        logger.error(f"Failed to get route details: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve route details.")


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint to verify database connectivity."""
    try:
        db.execute("SELECT 1")
        return {"status": "OK"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Database connectivity issue")
