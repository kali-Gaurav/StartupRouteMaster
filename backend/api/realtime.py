from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
from typing import Dict, Any

from database import get_db
from services.realtime_ingestion.position_estimator import TrainPositionEstimator
from pydantic import BaseModel
from typing import Optional
from database.models import LiveLocation, User
from api.dependencies import get_current_user

router = APIRouter(prefix="/api/realtime", tags=["realtime"])
logger = logging.getLogger(__name__)

@router.get("/train/{train_number}/position")
async def get_train_position(
    train_number: str,
    db: Session = Depends(get_db)
):
    """
    Get estimated geographical position of a train.
    Interpolates results between the last two stations.
    """
    try:
        estimator = TrainPositionEstimator(db)
        position = estimator.estimate_position(train_number)
        
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
async def get_detailed_train_status(
    train_number: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed real-time status including position and delay info.
    """
    try:
        estimator = TrainPositionEstimator(db)
        position = estimator.estimate_position(train_number)
        
        # In a real system, we'd also pull the latest delay propagation info here
        # For now, we return the position + a header
        
        return {
            "train_number": train_number,
            "realtime_metadata": {
                "source": "RappidAPI live feed",
                "interpolation_engine": "Routemaster PositionEstimator V1"
            },
            "position": position
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching status for {train_number}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Live location ingestion -------------------------------------------------

class LocationUpdateSchema(BaseModel):
    latitude: float
    longitude: float
    speed: Optional[float] = None

@router.post("/locations")
async def ingest_location(
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
        db.add(loc)
        db.commit()
        db.refresh(loc)
        return {"status": "ok", "id": loc.id}
    except Exception as e:
        logger.error(f"Error ingesting location: {e}")
        raise HTTPException(status_code=500, detail=str(e))
