from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
from typing import Dict, Any

from backend.database import get_db
from backend.services.realtime_ingestion.position_estimator import TrainPositionEstimator

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
        
    except Exception as e:
        logger.error(f"Error fetching status for {train_number}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
