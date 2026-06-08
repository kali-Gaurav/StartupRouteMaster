"""
Booking API Routes - REST endpoints for booking operations.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from database.session import get_db
from schemas.booking import (
    BookingRequest, BookingResponse, BookingListResponse,
    PassengerDetails, BookingStatus, CancelBookingRequest
)
from services.booking_service import get_booking_service, BookingService
from services.payment_service import get_payment_service, PaymentService
from services.sos_service import get_sos_service, SOSService
from core.auth import get_current_user

logger = logging.getLogger("api")

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])


@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    request: BookingRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Create a new booking.
    
    This endpoint initiates the booking process with:
    - Automatic seat allocation
    - Idempotency handling
    - Fraud detection
    - Payment initiation
    """
    try:
        booking_service = get_booking_service(db)
        result = await booking_service.create_booking(request, user.id)
        
        if result.status.value in ["failed", "error"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Booking creation failed"
            )
        
        return BookingResponse(
            booking_id=result.booking_id,
            pnr_number=result.pnr_number,
            status=BookingStatus(result.status.value),
            total_amount=result.total_amount,
            payment_url=result.payment_url,
            expires_at=result.expires_at,
            seats_allocated=result.seats_allocated,
            waitlist_position=result.waitlist_position
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating booking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during booking creation"
        )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Get booking details by ID."""
    booking_service = get_booking_service(db)
    booking = await booking_service.get_booking(booking_id, user.id)
    
    return BookingResponse(
        booking_id=booking.id,
        pnr_number=booking.pnr_number,
        status=BookingStatus(booking.booking_status),
        total_amount=booking.total_amount or 0,
        payment_url=booking.payment_url,
        expires_at=booking.expires_at,
        seats_allocated=booking.seats_allocated or [],
        waitlist_position=booking.waitlist_position
    )


@router.get("/pnr/{pnr_number}", response_model=BookingResponse)
async def get_booking_by_pnr(
    pnr_number: str,
    db: Session = Depends(get_db)
):
    """
    Get booking details by PNR number.
    
    This is a public endpoint for quick PNR lookups.
    """
    booking_service = get_booking_service(db)
    booking = await booking_service.get_booking_by_pnr(pnr_number)
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return BookingResponse(
        booking_id=booking.id,
        pnr_number=booking.pnr_number,
        status=BookingStatus(booking.booking_status),
        total_amount=booking.total_amount or 0,
        payment_url=booking.payment_url,
        expires_at=booking.expires_at,
        seats_allocated=booking.seats_allocated or [],
        waitlist_position=booking.waitlist_position
    )


@router.get("/", response_model=BookingListResponse)
async def list_bookings(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """List all bookings for the current user."""
    booking_service = get_booking_service(db)
    bookings = await booking_service.list_user_bookings(
        user.id, status_filter, limit, offset
    )
    
    return BookingListResponse(
        bookings=[
            BookingResponse(
                booking_id=b.id,
                pnr_number=b.pnr_number,
                status=BookingStatus(b.booking_status),
                total_amount=b.total_amount or 0,
                payment_url=b.payment_url,
                expires_at=b.expires_at,
                seats_allocated=b.seats_allocated or [],
                waitlist_position=b.waitlist_position
            )
            for b in bookings
        ],
        total=len(bookings),
        limit=limit,
        offset=offset
    )


@router.post("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: str,
    request: CancelBookingRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Cancel a booking and process refund if applicable."""
    booking_service = get_booking_service(db)
    result = await booking_service.cancel_booking(
        booking_id, user.id, request.reason
    )
    
    return {
        "booking_id": result.booking_id,
        "pnr_number": result.pnr_number,
        "status": result.status.value,
        "refund_amount": result.total_amount * 0.9 if result.status.value == "cancelled" else 0
    }


@router.post("/{booking_id}/confirm-payment")
async def confirm_payment(
    booking_id: str,
    payment_details: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Confirm payment and finalize booking."""
    booking_service = get_booking_service(db)
    result = await booking_service.confirm_booking(booking_id, payment_details)
    
    return {
        "booking_id": result.booking_id,
        "pnr_number": result.pnr_number,
        "status": result.status.value,
        "total_amount": result.total_amount
    }


@router.get("/{booking_id}/safety-score")
async def get_safety_score(
    booking_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Get safety score for a booking."""
    # Verify user owns the booking
    booking_service = get_booking_service(db)
    booking = await booking_service.get_booking(booking_id, user.id)
    
    sos_service = get_sos_service(db)
    score = await sos_service.get_safety_score(booking_id)
    
    return {
        "booking_id": booking_id,
        "safety_score": {
            "overall": score.overall_score,
            "station": score.station_score,
            "coach": score.coach_score,
            "route": score.route_score,
            "time": score.time_score
        },
        "factors": score.factors,
        "recommendations": score.recommendations
    }


@router.post("/{booking_id}/sos")
async def trigger_sos(
    booking_id: str,
    request: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Trigger SOS emergency alert for a booking.
    
    This will:
    - Notify all emergency contacts
    - Create safety incident record
    - Alert emergency services if critical
    """
    # Verify user owns the booking
    booking_service = get_booking_service(db)
    booking = await booking_service.get_booking(booking_id, user.id)
    
    sos_service = get_sos_service(db)
    result = await sos_service.trigger_sos(
        user_id=user.id,
        booking_id=booking_id,
        location=request.get("location"),
        description=request.get("description")
    )
    
    return result


@router.post("/{booking_id}/report-incident")
async def report_safety_incident(
    booking_id: str,
    request: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Report a safety incident."""
    sos_service = get_sos_service(db)
    result = await sos_service.report_safety_incident(
        user_id=user.id,
        booking_id=booking_id,
        incident_type=request.get("incident_type"),
        description=request.get("description"),
        location=request.get("location"),
        evidence=request.get("evidence")
    )
    
    return result