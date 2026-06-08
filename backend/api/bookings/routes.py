"""
V1 booking API for the route-search-to-booking workflow.

This router is a stable REST facade over the existing booking service. It keeps
the Kiro `/api/v1/bookings` contract callable while the v2 escrow flow continues
to serve the current frontend.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from database import get_db
from database.models import Booking, User
from schemas import (
    BookingCancellationResponseSchema,
    BookingCancellationSchema,
    BookingListResponseSchema,
    BookingRequestSchema,
    BookingResponseSchema,
    ErrorResponseSchema,
    PassengerSchema,
    PNRLookupResponseSchema,
    TrainInfoSchema,
)
from services.booking_service import BookingService
from services.booking_state_machine import BookingStateMachine
from services.fraud_detection_service import FraudDetectionService
from services.communication.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/bookings",
    tags=["bookings"],
    responses={
        400: {"model": ErrorResponseSchema},
        401: {"model": ErrorResponseSchema},
        403: {"model": ErrorResponseSchema},
        404: {"model": ErrorResponseSchema},
        500: {"model": ErrorResponseSchema},
    },
)

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "https://routemaster.io",
    "https://www.routemaster.io",
    "https://app.routemaster.io",
    "https://telegram.me/routemaster",
    "https://t.me/routemaster",
]


def setup_cors_middleware(app) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Correlation-ID", "X-Dev-Bypass"],
        expose_headers=["X-Request-ID", "X-Correlation-ID"],
        max_age=86400,
    )


def get_booking_service(db: Session = Depends(get_db)) -> BookingService:
    return BookingService(db)


def get_fraud_detection_service() -> FraudDetectionService:
    return FraudDetectionService()


def get_payment_service(db: Session = Depends(get_db)):
    from services.payment_service import PaymentService

    return PaymentService(db)


def get_notification_service() -> NotificationService:
    from services.communication.notification_service import NotificationService

    return NotificationService()


def _status_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _passenger_payloads(booking: Booking) -> List[PassengerSchema]:
    passengers = getattr(booking, "passenger_details", None) or []
    if passengers:
        return [
            PassengerSchema(
                full_name=p.full_name,
                age=p.age,
                gender=p.gender,
                phone_number=p.phone_number,
                email=p.email,
                berth_preference=p.berth_preference,
                meal_preference=p.meal_preference,
            )
            for p in passengers
        ]

    return [PassengerSchema(full_name="Passenger", age=0, gender="U", berth_preference=None)]


def _train_details(booking: Booking) -> Optional[TrainInfoSchema]:
    details = booking.booking_details or {}
    segments = details.get("segments") if isinstance(details, dict) else None
    first = segments[0] if isinstance(segments, list) and segments else {}
    train_number = booking.train_number or first.get("train_number") or first.get("trainNumber")
    if not train_number:
        return None

    return TrainInfoSchema(
        train_number=str(train_number),
        train_name=str(first.get("train_name") or first.get("trainName") or f"Train {train_number}"),
        from_station=str(first.get("from") or details.get("source") or ""),
        to_station=str(first.get("to") or details.get("destination") or ""),
        departure_time=str(first.get("departure") or first.get("departure_time") or ""),
        arrival_time=str(first.get("arrival") or first.get("arrival_time") or ""),
        duration_minutes=int(first.get("duration") or first.get("duration_minutes") or 0),
    )


def _booking_state(booking: Booking) -> Dict[str, Any]:
    escrow_status = getattr(booking, "escrow_status", None)
    if escrow_status is not None and hasattr(escrow_status, "value"):
        escrow_status_value = escrow_status.value
    else:
        escrow_status_value = str(escrow_status) if escrow_status is not None else "unknown"

    return {
        "booking_status": _status_value(booking.booking_status),
        "escrow_status": escrow_status_value,
    }


def _booking_response(booking: Booking, booking_service: BookingService, payment_url: Optional[str] = None) -> BookingResponseSchema:
    state_payload = _booking_state(booking)
    return BookingResponseSchema(
        id=str(booking.id),
        pnr_number=str(booking.pnr_number or ""),
        user_id=str(booking.user_id),
        travel_date=booking.travel_date or date.today(),
        booking_status=_status_value(booking.booking_status),
        train_details=_train_details(booking),
        passengers=_passenger_payloads(booking),
        total_amount=float(booking.amount_paid or 0.0),
        amount_paid=float(booking.amount_paid or 0.0),
        payment_url=payment_url,
        payment_status=_status_value(getattr(booking, "payment_status", getattr(booking, "escrow_status", ""))),
        created_at=booking.created_at or datetime.utcnow(),
        expires_at=(booking.created_at or datetime.utcnow()) + timedelta(minutes=30),
        current_state=state_payload,
        valid_next_actions=BookingStateMachine.get_valid_next_actions(booking),
        state_transition_history=booking_service.get_audit_trail(booking_id=str(booking.id)),
    )


def _request_hash(payload: BookingRequestSchema) -> str:
    return hashlib.sha256(payload.model_dump_json().encode("utf-8")).hexdigest()


@router.get("/health", summary="Booking service health check")
async def booking_health_check() -> Dict[str, Any]:
    return {"status": "healthy", "service": "booking", "timestamp": datetime.utcnow().isoformat()}


@router.post("/", response_model=BookingResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_booking(
    request: Request,
    booking_request: BookingRequestSchema,
    current_user: User = Depends(get_current_user),
    booking_service: BookingService = Depends(get_booking_service),
) -> BookingResponseSchema:
    idempotency_key = booking_service._generate_idempotency_key(
        str(current_user.id),
        booking_request.travel_date.isoformat(),
        booking_request.journey_id,
    )
    existing = booking_service.get_booking_by_idempotency(idempotency_key)
    if existing:
        return _booking_response(existing, booking_service)

    fraud_allowed, _, fraud_details = booking_service._check_fraud(
        str(current_user.id),
        amount=float(fraud_details_amount()),
    )
    if not fraud_allowed:
        raise HTTPException(status_code=403, detail=f"Booking rejected: {fraud_details.get('reason', 'risk threshold exceeded')}")

    try:
        from services.journey_cache import get_journey

        journey = await get_journey(booking_request.journey_id)
    except Exception:
        journey = None

    details: Dict[str, Any] = journey or {
        "journey_id": booking_request.journey_id,
        "class_type": booking_request.class_type,
        "payment_method": booking_request.payment_method,
    }
    amount = float(details.get("total_fare") or details.get("total_cost") or details.get("fare") or 0.0)
    passenger_details = [p.model_dump() for p in booking_request.passengers]

    booking = await booking_service.create_booking_async(
        user_id=str(current_user.id),
        route_id=booking_request.journey_id,
        travel_date=booking_request.travel_date.isoformat(),
        booking_details={**details, "request_hash": _request_hash(booking_request)},
        amount_paid=amount,
        passenger_details_list=passenger_details,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    if not booking:
        raise HTTPException(status_code=400, detail="Booking could not be created")

    return _booking_response(booking, booking_service)


def fraud_details_amount() -> float:
    # At v1 creation time the authoritative amount is hydrated from journey cache.
    # Use zero here to run velocity checks without falsely flagging unknown fares.
    return 0.0


@router.get("/", response_model=BookingListResponseSchema)
async def list_bookings(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    booking_service: BookingService = Depends(get_booking_service),
) -> BookingListResponseSchema:
    bookings, total = booking_service.get_user_bookings(
        user_id=str(current_user.id),
        skip=skip,
        limit=min(limit, 100),
        status_filter=status_filter,
        from_date=from_date,
        to_date=to_date,
    )
    return BookingListResponseSchema(
        bookings=[_booking_response(b, booking_service) for b in bookings],
        total=total,
        skip=skip,
        limit=min(limit, 100),
    )


@router.get("/pnr/{pnr_number}", response_model=PNRLookupResponseSchema)
async def lookup_booking_by_pnr(
    pnr_number: str,
    booking_service: BookingService = Depends(get_booking_service),
) -> PNRLookupResponseSchema:
    booking = booking_service.get_booking_by_pnr(pnr_number)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking with PNR {pnr_number} not found")

    details = booking.booking_details or {}
    passengers = getattr(booking, "passenger_details", None) or []
    state_payload = _booking_state(booking)
    return PNRLookupResponseSchema(
        pnr_number=str(booking.pnr_number or ""),
        train_number=booking.train_number,
        train_name=details.get("train_name") if isinstance(details, dict) else None,
        travel_date=booking.travel_date or date.today(),
        from_station=details.get("source") if isinstance(details, dict) else None,
        to_station=details.get("destination") if isinstance(details, dict) else None,
        booking_status=_status_value(booking.booking_status),
        passenger_count=max(1, len(passengers)),
        class_type=details.get("class_type") if isinstance(details, dict) else None,
        current_state=state_payload,
        valid_next_actions=BookingStateMachine.get_valid_next_actions(booking),
    )


@router.get("/{booking_id}", response_model=BookingResponseSchema)
async def get_booking(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    booking_service: BookingService = Depends(get_booking_service),
) -> BookingResponseSchema:
    booking = booking_service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking with ID {booking_id} not found")
    if str(booking.user_id) != str(current_user.id) and getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="You don't have permission to access this booking")
    return _booking_response(booking, booking_service)


@router.post("/{booking_id}/cancel", response_model=BookingCancellationResponseSchema)
async def cancel_booking(
    booking_id: str,
    cancellation: Optional[BookingCancellationSchema] = None,
    current_user: User = Depends(get_current_user),
    booking_service: BookingService = Depends(get_booking_service),
) -> BookingCancellationResponseSchema:
    booking = booking_service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking with ID {booking_id} not found")
    if str(booking.user_id) != str(current_user.id) and getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="You don't have permission to cancel this booking")
    if _status_value(booking.booking_status) in {"cancelled", "refunded"}:
        raise HTTPException(status_code=400, detail=f"Booking is already {_status_value(booking.booking_status)}")

    reason = cancellation.reason if cancellation and cancellation.reason else "User requested cancellation"
    cancelled = booking_service.cancel_booking(booking_id, reason=reason, user_id=str(current_user.id))
    if not cancelled:
        raise HTTPException(status_code=400, detail="Booking could not be cancelled")

    refreshed = booking_service.get_booking_by_id(booking_id) or booking
    return BookingCancellationResponseSchema(
        booking_id=booking_id,
        pnr_number=str(refreshed.pnr_number or ""),
        status="cancelled",
        refund_amount=float(refreshed.amount_paid or 0.0),
        refund_status="pending" if float(refreshed.amount_paid or 0.0) > 0 else "not_applicable",
        cancelled_at=datetime.utcnow(),
    )


__all__ = ["router", "setup_cors_middleware"]
