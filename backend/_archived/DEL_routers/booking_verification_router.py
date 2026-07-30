import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from datetime import date
import asyncio

# --- Import Models ---
from providers.models import BookingVerificationRequest, BookingVerificationResponse
from services.booking_verification_service import BookingVerificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# --- Dependency Injection (Optional but good practice) ---
# If BookingVerificationService requires complex setup or external resources,
# dependency injection can be used. For simplicity here, we'll instantiate it directly.
# In a real app, this might involve a provider function.

async def get_booking_verification_service():
    """Dependency provider for BookingVerificationService."""
    # In a real application, this would use dependency injection to provide the service instance.
    # For now, we instantiate it directly.
    return BookingVerificationService()

# --- API Endpoint ---
@router.post("/verify-booking", response_model=BookingVerificationResponse)
async def verify_booking_endpoint(
    request: BookingVerificationRequest,
    service: BookingVerificationService = Depends(get_booking_verification_service)
):
    """
    Endpoint to verify booking details against real-time data.

    Accepts booking information and returns verification status, PNR details,
    live status, and fare comparison.
    """
    logger.info(f"Received request to verify booking. PNR: {request.pnr_number}, Train: {request.train_number}, Date: {request.travel_date}")

    try:
        verification_result = await service.verify_booking_details(
            pnr_number=request.pnr_number,
            train_number=request.train_number,
            travel_date=request.travel_date,
            from_station_code=request.from_station_code,
            to_station_code=request.to_station_code,
            class_code=request.class_code,
            quota=request.quota,
            booking_fare=request.booking_fare
        )
        
        # The service returns a Dict, but our response_model expects Pydantic models.
        # We need to ensure the output matches the BookingVerificationResponse structure.
        # The current service return structure is:
        # { "pnr_status": {...}, "live_status": {...}, "fare_details": [...], "overall_verification": "...", "issues": [...] }
        # This matches the BookingVerificationResponse model structure.
        
        return BookingVerificationResponse(**verification_result)

    except Exception as e:
        logger.error(f"Error during booking verification endpoint: {e}", exc_info=True)
        # Return a generic error response, but log detailed exception
        raise HTTPException(status_code=500, detail="An internal error occurred during booking verification.")

