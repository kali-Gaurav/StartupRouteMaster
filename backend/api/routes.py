from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from backend.database import get_db
from backend.schemas import RouteDetailSchema, UserRead
from backend.database.models import Route as RouteModel, User
from backend.services.unlock_service import UnlockService
from backend.api.dependencies import get_current_user # Assuming get_current_user is defined here or in a similar dependencies file

router = APIRouter(prefix="/api/routes", tags=["routes"])
logger = logging.getLogger(__name__)


@router.get("/{route_id}")  # Removed response_model for testing
async def get_route_details(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed route information for a previously saved route."""
    try:
        route_model = db.query(RouteModel).filter(RouteModel.id == route_id).first()

        if not route_model:
            raise HTTPException(status_code=404, detail="Route not found")

        unlock_service = UnlockService(db)
        is_unlocked = unlock_service.is_route_unlocked(user_id=str(current_user.id), route_id=route_id)

        # Convert RouteModel to RouteDetailSchema and add is_unlocked status
        route_details = RouteDetailSchema.from_orm(route_model)
        route_details.is_unlocked = is_unlocked
        
        return route_details

    except HTTPException:
        raise
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
