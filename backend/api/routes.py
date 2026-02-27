from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from api.dependencies import get_current_user
from database import get_db
from schemas import RouteDetailSchema, UserRead
from database.models import Route as RouteModel, User, Stop
from services.unlock_service import UnlockService
from services.search_service import SearchService
# Assuming get_current_user is defined here or in a similar dependencies file

router = APIRouter(prefix="/api/routes", tags=["routes"])
logger = logging.getLogger(__name__)


@router.get("/")
async def search_routes_get(
    source: str = Query(..., description="Source station code"),
    destination: str = Query(..., description="Destination station code"),
    date: str = Query(None, description="Travel date (YYYY-MM-DD)"),
    max_transfers: int = Query(2, description="Maximum number of transfers"),
    max_results: int = Query(50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """
    Unified search endpoint. This provides searching for train routes from source to destination.
    Returns: BackendRoutesResponse formatted JSON.
    """
    try:
        service = SearchService(db)
        if not date:
            from datetime import date as dt
            date = dt.today().strftime("%Y-%m-%d")

        # Call the unified service
        result = await service.search_routes(
            source=source.upper(),
            destination=destination.upper(),
            travel_date=date
        )
        
        return result
    except Exception as e:
        logger.error(f"Routes Search Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
        is_unlocked = await unlock_service.is_route_unlocked(user_id=str(current_user.id), route_id=route_id)

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
