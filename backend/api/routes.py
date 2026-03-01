from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import DataError, SQLAlchemyError
from uuid import UUID
import logging
import json

from api.dependencies import get_current_user
from database import get_db
from schemas import RouteDetailSchema, UserRead
from database.models import Route as RouteModel, User, Stop, PrecalculatedRoute
from services.unlock_service import UnlockService
from services.search_service import SearchService
from core.redis import async_redis_client # Added for async cache access

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

@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint to verify database connectivity."""
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"status": "OK"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Database connectivity issue")


@router.get("/{route_id}", response_model=RouteDetailSchema)
async def get_route_details(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed route information for a previously saved or searched route.
    Upgraded to handle modern journey format (rt_) and legacy PrecalculatedRoute database entries.
    """
    try:
        unlock_service = UnlockService(db)
        is_unlocked = await unlock_service.is_route_unlocked(user_id=str(current_user.id), route_id=route_id)

        # 1. Modern journey_id (cache-based) lookup
        if route_id.startswith("rt_"):
            # Attempt to pull from Redis cache if it's a recent search
            try:
                cached_data = await async_redis_client.get(f"journey:{route_id}")
                if cached_data:
                    journey = json.loads(cached_data)
                    return RouteDetailSchema(
                        id=route_id,
                        source=journey.get("source", "Unknown"),
                        destination=journey.get("destination", "Unknown"),
                        segments=journey.get("segments", []),
                        total_duration=str(journey.get("total_duration", 0)),
                        total_cost=float(journey.get("total_fare", 0.0)),
                        budget_category="standard",
                        num_transfers=len(journey.get("segments", [])) - 1,
                        created_at=journey.get("timestamp"),
                        is_unlocked=is_unlocked
                    )
                else:
                    # Not found in cache; they should use the /api/v2/journey/{id}/unlock-details endpoint
                    raise HTTPException(status_code=404, detail="Journey expired or not found. Please search again.")
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Failed to fetch modern journey from cache: {e}")
                # Fallback to database lookup if cache error

        # 2. Legacy database lookup
        # Fix: Query PrecalculatedRoute instead of GTFS RouteModel to match RouteDetailSchema
        route_model = db.query(PrecalculatedRoute).filter(PrecalculatedRoute.id == route_id).first()

        if not route_model:
            raise HTTPException(status_code=404, detail="Route not found in database or cache.")

        # Convert PrecalculatedRoute to RouteDetailSchema and add is_unlocked status
        # Since PrecalculatedRoute lacks budget_category and num_transfers, supply defaults
        route_details = RouteDetailSchema(
            id=route_model.id,
            source=route_model.source,
            destination=route_model.destination,
            segments=route_model.segments or [],
            total_duration=route_model.total_duration or "0",
            total_cost=route_model.total_cost or 0.0,
            budget_category="standard",
            num_transfers=len(route_model.segments or []) - 1 if route_model.segments else 0,
            created_at=route_model.created_at or datetime.utcnow(),
            is_unlocked=is_unlocked
        )

        return route_details

    except DataError:
        # Invalid UUID format string sent to DB
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid route_id format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get route details for {route_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve route details.")
