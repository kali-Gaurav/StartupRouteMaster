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
    # Booking queue system schemas
    BookingRequestCreateSchema,
    BookingRequestResponseSchema,
    BookingQueueResponseSchema,
    RefundRequestSchema,
    RefundResponseSchema,
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

    # build a plain dict for the response to avoid ORM attributes entirely
    resp = {
        "id": booking.id,
        "pnr_number": booking.pnr_number,
        "user_id": booking.user_id,
        # Pydantic expects a full datetime value; ensure 'T' separator present
        "travel_date": (booking.travel_date.isoformat() + "T00:00:00") if hasattr(booking, "travel_date") and not isinstance(booking.travel_date, str) else (booking.travel_date or None),
        "booking_status": booking.booking_status,
        "amount_paid": booking.amount_paid,
        "booking_details": booking.booking_details,
        "passenger_details": [
            {
                "full_name": pax.full_name,
                "age": pax.age,
                "gender": pax.gender,
                "phone_number": pax.phone_number,
                "email": pax.email,
                "document_type": pax.document_type,
                "document_number": pax.document_number,
                "concession_type": pax.concession_type,
                "concession_discount": pax.concession_discount,
                "meal_preference": pax.meal_preference,
            }
            for pax in getattr(booking, "passenger_details", [])
        ] if getattr(booking, "passenger_details", None) else None,
        "created_at": booking.created_at,
        # legacy passenger fields - populate from first passenger if present
        "gender": booking.passenger_details[0].gender if booking.passenger_details else "M",
        "phone_number": booking.passenger_details[0].phone_number if booking.passenger_details else None,
        "email": booking.passenger_details[0].email if booking.passenger_details else None,
        "document_type": booking.passenger_details[0].document_type if booking.passenger_details else None,
        "document_number": booking.passenger_details[0].document_number if booking.passenger_details else None,
        "concession_type": booking.passenger_details[0].concession_type if booking.passenger_details else None,
        "concession_discount": booking.passenger_details[0].concession_discount if booking.passenger_details else 0.0,
        "meal_preference": booking.passenger_details[0].meal_preference if booking.passenger_details else None,
        "payment_status": booking.payment_status or "",
    }
    return resp

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


# --------------------------------------------------------------------------
# Compatibility endpoint: alias POST /confirm for clients still calling older
# path.  It simply creates a booking (identical to `/`) and then marks it as
# confirmed.  Keeping this here avoids breaking legacy integrations while
# slowly migrating frontends to the new endpoint name.

@router.post("/confirm", response_model=BookingResponseSchema)
async def confirm_booking_endpoint(
    request: BookingCreateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
    # immediately mark confirmed (payment should have succeeded already)
    service.confirm_booking(booking.id)
    # reuse logic from create_booking to build response
    return await create_booking(request, current_user, db)

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


# ==============================================================================
# BOOKING QUEUE SYSTEM ENDPOINTS
# ==============================================================================

@router.post("/request", response_model=BookingRequestResponseSchema)
async def create_booking_request(
    request: BookingRequestCreateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a booking request for the queue system.
    
    This endpoint is called after:
    1. User has unlocked route (paid ₹39)
    2. Route has been verified via RapidAPI
    3. User confirms they want to proceed with booking
    
    The request will be added to the booking queue for admin/automated execution.
    """
    from backend.database.models import BookingRequest, BookingRequestPassenger, BookingQueue, Payment, UnlockedRoute
    from datetime import datetime
    
    # Verify user has unlocked this route (has paid ₹39)
    # Find the most recent unlock payment for this user
    unlocked_route = db.query(UnlockedRoute).filter(
        UnlockedRoute.user_id == str(current_user.id),
        UnlockedRoute.is_active == True
    ).order_by(UnlockedRoute.unlocked_at.desc()).first()
    
    if not unlocked_route or not unlocked_route.payment_id:
        raise HTTPException(
            status_code=400,
            detail="Route must be unlocked before creating booking request. Please complete unlock payment first."
        )
    
    # Verify payment is completed
    payment = db.query(Payment).filter(Payment.id == unlocked_route.payment_id).first()
    if not payment or payment.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Unlock payment must be completed before creating booking request."
        )
    
    # Parse journey date
    try:
        journey_date = datetime.strptime(request.journey_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Create booking request
    booking_request = BookingRequest(
        user_id=str(current_user.id),
        source_station=request.source_station,
        destination_station=request.destination_station,
        journey_date=journey_date,
        train_number=request.train_number,
        train_name=request.train_name,
        class_type=request.class_type,
        quota=request.quota,
        status="PENDING",
        verification_status="VERIFIED",  # Assumed verified if user reached this point
        payment_id=unlocked_route.payment_id,
        route_details=request.route_details,
        verified_at=datetime.utcnow()
    )
    db.add(booking_request)
    db.flush()  # Get the ID
    
    # Add passengers
    for passenger_data in request.passengers:
        passenger = BookingRequestPassenger(
            booking_request_id=booking_request.id,
            name=passenger_data.name,
            age=passenger_data.age,
            gender=passenger_data.gender,
            berth_preference=passenger_data.berth_preference,
            id_proof_type=passenger_data.id_proof_type,
            id_proof_number=passenger_data.id_proof_number
        )
        db.add(passenger)
    
    # Create queue entry
    queue_entry = BookingQueue(
        booking_request_id=booking_request.id,
        priority=5,  # Default priority
        execution_mode="MANUAL",  # Start with manual execution
        status="WAITING"
    )
    db.add(queue_entry)
    
    # Update booking request status
    booking_request.status = "QUEUED"
    
    db.commit()
    db.refresh(booking_request)
    db.refresh(queue_entry)
    
    # Build response
    response_data = {
        "id": booking_request.id,
        "user_id": booking_request.user_id,
        "source_station": booking_request.source_station,
        "destination_station": booking_request.destination_station,
        "journey_date": booking_request.journey_date.isoformat(),
        "train_number": booking_request.train_number,
        "train_name": booking_request.train_name,
        "class_type": booking_request.class_type,
        "quota": booking_request.quota,
        "status": booking_request.status,
        "verification_status": booking_request.verification_status,
        "payment_id": booking_request.payment_id,
        "created_at": booking_request.created_at,
        "updated_at": booking_request.updated_at,
        "queue_status": queue_entry.status
    }
    
    return response_data


@router.get("/request/{request_id}", response_model=BookingRequestResponseSchema)
async def get_booking_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get booking request details by ID."""
    from backend.database.models import BookingRequest, BookingQueue
    
    booking_request = db.query(BookingRequest).filter(
        BookingRequest.id == request_id,
        BookingRequest.user_id == str(current_user.id)
    ).first()
    
    if not booking_request:
        raise HTTPException(status_code=404, detail="Booking request not found")
    
    queue_entry = db.query(BookingQueue).filter(
        BookingQueue.booking_request_id == request_id
    ).first()
    
    response_data = {
        "id": booking_request.id,
        "user_id": booking_request.user_id,
        "source_station": booking_request.source_station,
        "destination_station": booking_request.destination_station,
        "journey_date": booking_request.journey_date.isoformat(),
        "train_number": booking_request.train_number,
        "train_name": booking_request.train_name,
        "class_type": booking_request.class_type,
        "quota": booking_request.quota,
        "status": booking_request.status,
        "verification_status": booking_request.verification_status,
        "payment_id": booking_request.payment_id,
        "created_at": booking_request.created_at,
        "updated_at": booking_request.updated_at,
        "queue_status": queue_entry.status if queue_entry else None
    }
    
    return response_data


@router.get("/requests/my", response_model=List[BookingRequestResponseSchema])
async def get_my_booking_requests(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all booking requests for current user."""
    from backend.database.models import BookingRequest, BookingQueue
    
    requests = db.query(BookingRequest).filter(
        BookingRequest.user_id == str(current_user.id)
    ).order_by(BookingRequest.created_at.desc()).offset(skip).limit(limit).all()
    
    results = []
    for req in requests:
        queue_entry = db.query(BookingQueue).filter(
            BookingQueue.booking_request_id == req.id
        ).first()
        
        results.append({
            "id": req.id,
            "user_id": req.user_id,
            "source_station": req.source_station,
            "destination_station": req.destination_station,
            "journey_date": req.journey_date.isoformat(),
            "train_number": req.train_number,
            "train_name": req.train_name,
            "class_type": req.class_type,
            "quota": req.quota,
            "status": req.status,
            "verification_status": req.verification_status,
            "payment_id": req.payment_id,
            "created_at": req.created_at,
            "updated_at": req.updated_at,
            "queue_status": queue_entry.status if queue_entry else None
        })
    
    return results
