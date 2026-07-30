"""
API Routes for CAT (Contextual Availability Transformer).

Provides REST API endpoints for:
- Availability predictions
- Batch predictions
- Model management
- Health checks
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import logging

from backend.services.cat.inference_service import (
    get_inference_service,
    init_inference_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/cat",
    tags=["CAT"]
)


# Request/Response Models
class PredictionRequest(BaseModel):
    """Request model for prediction."""
    location_id: str
    prediction_time: str  # ISO format datetime string


class BatchPredictionRequest(BaseModel):
    """Request model for batch predictions."""
    predictions: List[PredictionRequest]


class PredictionResponse(BaseModel):
    """Response model for prediction."""
    success: bool
    prediction: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    timestamp: str
    model_loaded: bool
    external_apis_healthy: bool


# API Endpoints
@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns the status of the CAT inference service.
    """
    try:
        service = get_inference_service()
        status = service.get_health_status()
        
        return HealthResponse(
            status=status.status,
            timestamp=status.timestamp.isoformat(),
            model_loaded=status.model_loaded,
            external_apis_healthy=status.external_apis_healthy,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict", response_model=PredictionResponse)
async def predict_availability(
    request: PredictionRequest,
):
    """
    Get availability prediction for a location and time.
    
    Args:
        request: PredictionRequest with location_id and prediction_time
        
    Returns:
        PredictionResponse with availability prediction
    """
    try:
        service = get_inference_service()
        
        from datetime import datetime
        prediction_time = datetime.fromisoformat(request.prediction_time)
        
        prediction = await service.get_availability_prediction(
            request.location_id,
            prediction_time
        )
        
        return PredictionResponse(
            success=True,
            prediction=prediction.dict(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting availability: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict/batch", response_model=Dict[str, Any])
async def predict_batch(
    request: BatchPredictionRequest,
):
    """
    Get batch predictions for multiple locations and times.
    
    Args:
        request: BatchPredictionRequest with list of predictions
        
    Returns:
        Dictionary with predictions list
    """
    try:
        service = get_inference_service()
        
        from datetime import datetime
        predictions = []
        for pred_request in request.predictions:
            prediction_time = datetime.fromisoformat(pred_request.prediction_time)
            predictions.append({
                'location_id': pred_request.location_id,
                'prediction_time': prediction_time,
            })
        
        results = await service.get_batch_predictions(predictions)
        
        return {'predictions': results}
    except Exception as e:
        logger.error(f"Error in batch prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locations")
async def list_locations():
    """
    List available locations for predictions.
    
    Returns:
        List of location registry entries
    """
    try:
        service = get_inference_service()
        
        # TODO: Query database for available locations
        locations = [
            {'location_id': 'NDLS', 'location_name': 'New Delhi', 'timezone': 'Asia/Kolkata'},
            {'location_id': 'BCT', 'location_name': 'Mumbai', 'timezone': 'Asia/Kolkata'},
            {'location_id': 'MAS', 'location_name': 'Chennai', 'timezone': 'Asia/Kolkata'},
            {'location_id': 'HWH', 'location_name': 'Kolkata', 'timezone': 'Asia/Kolkata'},
        ]
        
        return {'locations': locations}
    except Exception as e:
        logger.error(f"Error listing locations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/version")
async def get_model_version():
    """
    Get current model version.
    
    Returns:
        Model version string
    """
    try:
        service = get_inference_service()
        return {'version': service.get_model_version()}
    except Exception as e:
        logger.error(f"Error getting model version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model/reload")
async def reload_model():
    """
    Reload the model from checkpoint.
    
    Returns:
        Success message
    """
    try:
        service = get_inference_service()
        
        # TODO: Implement model reload logic
        return {'status': 'success', 'message': 'Model reload not yet implemented'}
    except Exception as e:
        logger.error(f"Error reloading model: {e}")
        raise HTTPException(status_code=500, detail=str(e))