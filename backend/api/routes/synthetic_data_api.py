"""
API Routes for Synthetic Data Service.

Provides REST API endpoints for:
- Generating synthetic data
- Validating data quality
- Querying routes
- Checking availability
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import logging

from backend.services.synthetic_data_service import (
    get_synthetic_data_service,
    create_synthetic_data_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/synthetic",
    tags=["Synthetic Data"]
)


# Request/Response Models
class GenerateDataRequest(BaseModel):
    """Request model for data generation."""
    counts: Optional[Dict[str, int]] = None


class GenerateDataResponse(BaseModel):
    """Response model for data generation."""
    success: bool
    data: Dict[str, Any]


class ValidateDataRequest(BaseModel):
    """Request model for data validation."""
    real_data_path: str
    synthetic_data_path: str


class ValidateDataResponse(BaseModel):
    """Response model for data validation."""
    success: bool
    results: Dict[str, Any]


class GetRoutesRequest(BaseModel):
    """Request model for route queries."""
    from_station: str
    to_station: str
    travel_date: str
    max_transfers: Optional[int] = 2


class GetRoutesResponse(BaseModel):
    """Response model for route queries."""
    success: bool
    routes: List[Dict[str, Any]]


class GetAvailabilityRequest(BaseModel):
    """Request model for availability queries."""
    train_number: str
    travel_date: str
    travel_class: str


class GetAvailabilityResponse(BaseModel):
    """Response model for availability queries."""
    success: bool
    availability: Optional[Dict[str, Any]]


# API Endpoints
@router.post("/generate", response_model=GenerateDataResponse)
async def generate_synthetic_data(
    request: GenerateDataRequest
):
    """
    Generate synthetic data.
    
    Generates all types of synthetic data:
    - Train schedules
    - Fare records
    - Availability records
    - User behavior records
    """
    try:
        service = get_synthetic_data_service()
        results = service.generate_all_data(request.counts)
        
        return GenerateDataResponse(
            success=True,
            data=results
        )
    except Exception as e:
        logger.error(f"Error generating synthetic data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=ValidateDataResponse)
async def validate_synthetic_data(
    request: ValidateDataRequest
):
    """
    Validate synthetic data against real data.
    
    Compares synthetic data distributions with real data
    and returns validation results.
    """
    try:
        service = get_synthetic_data_service()
        results = service.validate_data(
            request.real_data_path,
            request.synthetic_data_path
        )
        
        return ValidateDataResponse(
            success=results.get('passed', False),
            results=results
        )
    except Exception as e:
        logger.error(f"Error validating synthetic data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/routes", response_model=GetRoutesResponse)
async def get_routes(
    request: GetRoutesRequest
):
    """
    Get routes between stations using synthetic data.
    
    Generates all possible routes between two stations
    without real-time API calls.
    """
    try:
        service = get_synthetic_data_service()
        routes = service.get_routes(
            request.from_station,
            request.to_station,
            request.travel_date,
            request.max_transfers
        )
        
        return GetRoutesResponse(
            success=True,
            routes=routes
        )
    except Exception as e:
        logger.error(f"Error getting routes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/availability", response_model=GetAvailabilityResponse)
async def get_availability(
    request: GetAvailabilityRequest
):
    """
    Get availability for a train using synthetic data.
    
    Returns availability information without real-time API calls.
    """
    try:
        service = get_synthetic_data_service()
        availability = service.get_availability(
            request.train_number,
            request.travel_date,
            request.travel_class
        )
        
        return GetAvailabilityResponse(
            success=True,
            availability=availability
        )
    except Exception as e:
        logger.error(f"Error getting availability: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns the status of the synthetic data service.
    """
    try:
        service = get_synthetic_data_service()
        
        return {
            "status": "healthy",
            "service": "synthetic_data",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """
    Get synthetic data statistics.
    
    Returns statistics about generated data.
    """
    try:
        service = get_synthetic_data_service()
        
        return {
            "status": "success",
            "data": {
                "schedules_count": 0,  # TODO: Implement
                "fares_count": 0,  # TODO: Implement
                "availability_count": 0,  # TODO: Implement
                "behavior_count": 0,  # TODO: Implement
            }
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))