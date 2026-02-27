"""
Booking API - REST Endpoints for Seat Inventory & Booking Engine

Provides RESTful APIs for:
- Seat availability checking
- Seat booking with distributed transactions
- Booking management (cancel, status)
- Waitlist operations

Integrates with Availability Service and Booking Orchestrator.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import logging

from .availability_service import availability_service, AvailabilityRequest, AvailabilityResponse
from .booking_orchestrator import booking_orchestrator, BookingRequest, BookingResponse
from .seat_inventory_models import QuotaType, BookingStatus
from .api.dependencies import get_current_user  # Corrected import path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/booking", tags=["booking"])


# Pydantic models for API requests/responses
class AvailabilityCheckRequest(BaseModel):
    trip_id: int = Field(..., description="Trip ID")
    from_stop_id: int = Field(..., description="Departure stop ID")
    to_stop_id: int = Field(..., description="Arrival stop ID")
    travel_date: date = Field(..., description="Travel date")
    quota_type: QuotaType = Field(..., description="Quota type")
    passengers: int = Field(1, ge=1, le=6, description="Number of passengers")

class AvailabilityCheckResponse(BaseModel):
    available: bool
    available_seats: int
    total_seats: int
    waitlist_position: Optional[int] = None
    confirmation_probability: Optional[float] = None
    message: str

class PassengerInfo(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=1, le=120)
    gender: str = Field(..., pattern="^(M|F|O)$")  # Male, Female, Other
    berth_preference: Optional[str] = Field(None, pattern="^(LB|UB|SL|SIDE|NO_PREF)$")

class PaymentMethod(BaseModel):
    type: str = Field(..., pattern="^(CARD|UPI|NET_BANKING|WALLET)$")
    details: Dict[str, Any]  # Encrypted payment details

class BookingCreateRequest(BaseModel):
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    travel_date: date
    quota_type: QuotaType
    passengers: List[PassengerInfo] = Field(..., min_items=1, max_items=6)
    payment_method: PaymentMethod
    preferences: Optional[Dict[str, Any]] = None

class BookingCreateResponse(BaseModel):
    success: bool
    pnr_number: Optional[str] = None
    booking_id: Optional[str] = None
    total_amount: Optional[float] = None
    message: str
    errors: List[str] = []

class BookingStatusResponse(BaseModel):
    pnr_number: str
    status: str
    travel_date: date
    total_amount: float
    passengers: int
    created_at: datetime
    cancelled_at: Optional[datetime] = None

class CancellationResponse(BaseModel):
    success: bool
    message: str
    refund_amount: Optional[float] = None

class WaitlistRequest(BaseModel):
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    travel_date: date
    quota_type: QuotaType
    passengers: List[PassengerInfo] = Field(..., min_items=1, max_items=6)
    preferences: Optional[Dict[str, Any]] = None

class WaitlistResponse(BaseModel):
    success: bool
    waitlist_position: Optional[int] = None
    message: str


@router.post("/availability", response_model=AvailabilityCheckResponse)
async def check_availability(
    request: AvailabilityCheckRequest,
    current_user: Dict = Depends(get_current_user)
) -> AvailabilityCheckResponse:
    """
    Check seat availability for a trip segment.

    Returns availability status, waitlist position, and confirmation probability.
    """
    try:
        avail_request = AvailabilityRequest(
            trip_id=request.trip_id,
            from_stop_id=request.from_stop_id,
            to_stop_id=request.to_stop_id,
            travel_date=request.travel_date,
            quota_type=request.quota_type,
            passengers=request.passengers
        )

        response = await availability_service.check_availability(avail_request)

        return AvailabilityCheckResponse(
            available=response.available,
            available_seats=response.available_seats,
            total_seats=response.total_seats,
            waitlist_position=response.waitlist_position,
            confirmation_probability=response.confirmation_probability,
            message=response.message
        )

    except Exception as e:
        logger.error(f"Availability check failed: {e}")
        raise HTTPException(status_code=500, detail="Availability check failed")


@router.post("/book", response_model=BookingCreateResponse)
async def create_booking(
    request: BookingCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
) -> BookingCreateResponse:
    """
    Create a new booking with distributed transaction handling.

    Uses Saga pattern to ensure atomicity across seat allocation, payment, and PNR generation.
    """
    try:
        # Convert to internal booking request
        booking_request = BookingRequest(
            user_id=current_user["id"],
            trip_id=request.trip_id,
            from_stop_id=request.from_stop_id,
            to_stop_id=request.to_stop_id,
            travel_date=request.travel_date.isoformat(),
            quota_type=request.quota_type.value,
            passengers=[passenger.dict() for passenger in request.passengers],
            payment_method=request.payment_method.dict(),
            preferences=request.preferences
        )

        # Process booking asynchronously to handle long-running transactions
        background_tasks.add_task(process_booking_async, booking_request)

        # Return immediate response - actual result will be sent via webhook/notification
        return BookingCreateResponse(
            success=True,
            message="Booking request submitted. You will receive confirmation shortly.",
            errors=[]
        )

    except Exception as e:
        logger.error(f"Booking creation failed: {e}")
        raise HTTPException(status_code=500, detail="Booking creation failed")


async def process_booking_async(booking_request: BookingRequest):
    """Process booking asynchronously"""
    try:
        result = await booking_orchestrator.process_booking(booking_request)

        # Send notification with result
        await send_booking_result_notification(booking_request.user_id, result)

    except Exception as e:
        logger.error(f"Async booking processing failed: {e}")
        # Send failure notification
        error_result = BookingResponse(
            success=False,
            message="Booking processing failed. Please try again."
        )
        await send_booking_result_notification(booking_request.user_id, error_result)


@router.get("/status/{pnr_number}", response_model=BookingStatusResponse)
async def get_booking_status(
    pnr_number: str,
    current_user: Dict = Depends(get_current_user)
) -> BookingStatusResponse:
    """
    Get booking status by PNR number.
    """
    try:
        status = await booking_orchestrator.get_booking_status(pnr_number, current_user["id"])

        if not status:
            raise HTTPException(status_code=404, detail="Booking not found")

        return BookingStatusResponse(**status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Booking status check failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve booking status")


@router.post("/cancel/{pnr_number}", response_model=CancellationResponse)
async def cancel_booking(
    pnr_number: str,
    current_user: Dict = Depends(get_current_user)
) -> CancellationResponse:
    """
    Cancel a booking by PNR number.

    Applies cancellation policy and processes refunds.
    """
    try:
        result = await booking_orchestrator.cancel_booking(pnr_number, current_user["id"])

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])

        return CancellationResponse(
            success=True,
            message=result["message"],
            refund_amount=result.get("refund_amount")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Booking cancellation failed: {e}")
        raise HTTPException(status_code=500, detail="Booking cancellation failed")


@router.post("/waitlist", response_model=WaitlistResponse)
async def add_to_waitlist(
    request: WaitlistRequest,
    current_user: Dict = Depends(get_current_user)
) -> WaitlistResponse:
    """
    Add booking request to waitlist when seats are not available.

    Automatically monitors for seat availability and promotes when possible.
    """
    try:
        avail_request = AvailabilityRequest(
            trip_id=request.trip_id,
            from_stop_id=request.from_stop_id,
            to_stop_id=request.to_stop_id,
            travel_date=request.travel_date,
            quota_type=request.quota_type,
            passengers=len(request.passengers)
        )

        passengers_json = [passenger.dict() for passenger in request.passengers]

        position = await availability_service.add_to_waitlist(
            avail_request, current_user["id"], passengers_json, request.preferences
        )

        return WaitlistResponse(
            success=True,
            waitlist_position=position,
            message=f"Added to waitlist at position {position}"
        )

    except Exception as e:
        logger.error(f"Waitlist addition failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to add to waitlist")


@router.get("/quota-types")
async def get_quota_types() -> Dict[str, List[Dict[str, str]]]:
    """
    Get available quota types for booking.
    """
    quota_types = [
        {"value": quota.value, "label": quota.name.replace("_", " ").title()}
        for quota in QuotaType
    ]

    return {"quota_types": quota_types}


@router.get("/booking-classes")
async def get_booking_classes() -> Dict[str, List[Dict[str, str]]]:
    """
    Get available booking classes/coach types.
    """
    from .seat_inventory_models import CoachClass

    classes = [
        {"value": cls.value, "label": cls.name.replace("_", " ").title()}
        for cls in CoachClass
    ]

    return {"booking_classes": classes}


# Webhook endpoint for payment gateway callbacks
@router.post("/payment/webhook")
async def payment_webhook(payload: Dict[str, Any]):
    """
    Handle payment gateway webhooks for booking confirmations.
    """
    try:
        # Process payment confirmation
        # This would update booking status based on payment result
        logger.info(f"Payment webhook received: {payload}")

        # Implementation would depend on payment gateway
        return {"status": "processed"}

    except Exception as e:
        logger.error(f"Payment webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


async def send_booking_result_notification(user_id: str, result: BookingResponse):
    """Send booking result notification to user"""
    # This would integrate with notification service
    # For now, just log it
    logger.info(f"Booking result for user {user_id}: {result.dict()}")


# Health check endpoint
@router.get("/health")
async def booking_health_check():
    """Health check for booking service"""
    return {
        "status": "healthy",
        "service": "booking-engine",
        "timestamp": datetime.utcnow().isoformat()
    }
