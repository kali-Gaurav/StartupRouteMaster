from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from backend.database import get_db
from backend.services.booking_service import BookingService
from backend.api.dependencies import get_current_user
from backend.models import User
from backend.schemas import (
    BookingResponseSchema,
    PassengerDetailsSchema,
    BookingCreateSchema,  # NEW: BookingCreateSchema
    # availability schemas added below
    AvailabilityCheckRequestSchema,
    AvailabilityCheckResponseSchema,
)

# The router is versioned to match frontend expectations (/api/v1/booking/*).
# previously it used "/api/bookings" but the frontend called "/v1/booking/..." so
# bumping the prefix keeps both sides aligned.  If other code still relies on the
# old path we could mount the router twice, but most references were internal
# so this change is safe for the integration phase.
router = APIRouter(prefix="/api/v1/booking", tags=["bookings"])

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

# --- AVAILABILITY CHECK -----------------------------------------------------

@router.post(
    "/availability",
    response_model=AvailabilityCheckResponseSchema,
    summary="Check seat availability for a segment",
    description=(
        "Returns inventory counts, waitlist info and a handful of helper fields "
        "so frontend can render the booking flow without needing to interpret raw data."
    )
)
async def check_availability(
    request: AvailabilityCheckRequestSchema,
    db: Session = Depends(get_db)
):
    # convert travel_date string to date object
    try:
        from datetime import datetime
        travel_date_obj = datetime.strptime(request.travel_date, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format; expected YYYY-MM-DD")

    # resolve trip_id which may be a string representing backend route/trip
    from backend.database.models import Trip

    numeric_trip_id = None
    if isinstance(request.trip_id, str):
        # try to match trip_id field first
        trip = db.query(Trip).filter(Trip.trip_id == request.trip_id).first()
        if not trip and request.trip_id.isdigit():
            trip = db.query(Trip).filter(Trip.id == int(request.trip_id)).first()
        if not trip:
            raise HTTPException(status_code=404, detail=f"Trip/route {request.trip_id} not found")
        numeric_trip_id = trip.id
    else:
        numeric_trip_id = request.trip_id

    # delegate to the availability service
    from backend.availability_service import availability_service, AvailabilityRequest
    from backend.database.models import QuotaType

    # Convert quota_type string to QuotaType enum
    # Handle both uppercase and lowercase inputs
    quota_type_str = request.quota_type.lower()
    try:
        quota_enum = QuotaType(quota_type_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid quota type: {request.quota_type}. Valid options: {', '.join([qt.value for qt in QuotaType])}"
        )

    avail_req = AvailabilityRequest(
        trip_id=numeric_trip_id,
        from_stop_id=request.from_stop_id,
        to_stop_id=request.to_stop_id,
        travel_date=travel_date_obj,
        quota_type=quota_enum,
        passengers=request.passengers,
    )
    resp = await availability_service.check_availability(avail_req)

    # Build dictionary output and include additional compatibility fields
    result = resp.__dict__.copy()
    # map to extra frontend fields
    result["availability_status"] = (
        "AVAILABLE" if resp.available else
        ("WL" if resp.waitlist_position is not None else "UNKNOWN")
    )
    result["fare"] = None  # fare can be filled by route engine if required later
    result["quota"] = request.quota_type
    result["class"] = None
    result["probability"] = resp.confirmation_probability

    return result


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
