import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import logging
from typing import Dict, Any
from datetime import datetime

from database import get_db
from services.realtime_ingestion.position_estimator import TrainPositionEstimator
from pydantic import BaseModel
from typing import Optional
from database.models import LiveLocation, User
from api.dependencies import get_current_user
from utils.limiter import limiter

router = APIRouter(prefix="/api/realtime", tags=["realtime"])
logger = logging.getLogger(__name__)

@router.get("/train/{train_number}/position")
@limiter.limit("60/minute")
async def get_train_position(
    request: Request,
    train_number: str,
    db: Session = Depends(get_db)
):
    """
    Get estimated geographical position of a train.
    Interpolates results between the last two stations.
    """
    try:
        estimator = TrainPositionEstimator(db)
        position = await asyncio.to_thread(estimator.estimate_position, train_number)
        
        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Real-time position data not available for train {train_number}"
            )
            
        return position
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching position for {train_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error calculating train position"
        )

@router.get("/train/{train_number}/status")
@limiter.limit("30/minute")
async def get_detailed_train_status(
    request: Request,
    train_number: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed real-time status including position and delay info.
    Merges live external API data with internal position interpolation.
    """
    try:
        from services.realtime_ingestion.live_status_service import LiveStatusService
        
        # 1. Fetch live data from external API (Rappid.in)
        live_service = LiveStatusService()
        live_data = await live_service.get_live_status(train_number)
        
        # 2. Get interpolated geographical position
        estimator = TrainPositionEstimator(db)
        position = await asyncio.to_thread(estimator.estimate_position, train_number)
        
        # 3. Intelligence Merge:
        # If live_data has more recent delay info, use it.
        # If position estimator has high-confidence lat/long, include it.
        
        return {
            "train_number": train_number,
            "success": True,
            "live_status": live_data,
            "estimated_position": position,
            "last_verified_at": datetime.utcnow().isoformat(),
            "metadata": {
                "live_uplink": live_data is not None,
                "interpolation_active": position is not None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching status for {train_number}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

def _db_commit_location(db: Session, loc: LiveLocation):
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc

# --- Live location ingestion -------------------------------------------------

class LocationUpdateSchema(BaseModel):
    latitude: float
    longitude: float
    speed: Optional[float] = None

@router.post("/locations")
@limiter.limit("120/minute")
async def ingest_location(
    request: Request,
    payload: LocationUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Record a live location for the authenticated user.

    This endpoint can be called frequently by mobile/web clients and the data
    is stored in the `live_locations` table.  Optionally additional broadcasting
    logic (e.g. via Redis or WebSocket) can be added here.
    """
    loc = LiveLocation(
        user_id=str(current_user.id),
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed=payload.speed,
    )
    try:
        # DB writes might block the event loop if called at high frequency
        loc = await asyncio.to_thread(_db_commit_location, db, loc)
        return {"status": "ok", "id": loc.id}
    except Exception as e:
        logger.error(f"Error ingesting location: {e}")
        raise HTTPException(status_code=500, detail=str(e))
