from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from backend.database import get_db
from backend.services.booking_service import BookingService
from backend.api.dependencies import get_current_user
from backend.models import User
from backend.schemas import BookingResponseSchema, PassengerDetailsSchema, BookingCreateSchema # NEW: BookingCreateSchema

router = APIRouter(prefix="/api/bookings", tags=["bookings"])

@router.post("/", response_model=BookingResponseSchema)
async def create_booking(
    request: BookingCreateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unified booking creation endpoint.
    Expects a JSON body with route_id, travel_date, booking_details, etc.
    """
    service = BookingService(db)
    booking = service.create_booking(
        user_id=str(current_user.id),
        route_id=request.route_id,
        travel_date=request.travel_date,
        booking_details=request.booking_details,
        amount_paid=request.amount_paid,
        passenger_details_list=[f.dict() for f in request.passenger_details] if request.passenger_details else None
    )
    if not booking:
        raise HTTPException(status_code=400, detail="Booking creation failed")
    return booking

from backend.schemas import BookingResponseSchema, PassengerDetailsSchema, BookingCreateSchema, BookingListSchema

@router.get("/", response_model=BookingListSchema)
async def list_bookings(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List bookings for current user with optional pagination."""
    service = BookingService(db)
    bookings, total = service.get_user_bookings(str(current_user.id), skip=skip, limit=limit)
    return BookingListSchema(bookings=bookings, total=total, skip=skip, limit=limit)

@router.get("/{pnr}", response_model=BookingResponseSchema)
async def get_booking_by_pnr(
    pnr: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = BookingService(db)
    booking = service.get_booking_by_pnr(pnr)
    if not booking or str(booking.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking
