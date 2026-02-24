"""Lightweight booking orchestrator used by legacy tests and simple operations.

This module provides basic async methods for processing bookings, cancelling them,
and querying status. It's intentionally minimal to avoid dragging in complex saga
or microservice dependencies during unit tests. A more sophisticated implementation
may live in `backend.services.booking_orchestrator` in production code.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Any

from backend.database import SessionLocal
from backend.database.models import Booking, PassengerDetails, BookingStatus
from backend.utils.generators import generate_pnr, generate_confirmation_number


@dataclass
class BookingRequest:
    user_id: str
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    travel_date: str  # ISO-formatted date string
    quota_type: str
    passengers: List[Dict]
    payment_method: Dict
    preferences: Optional[Dict] = None


@dataclass
class BookingResponse:
    success: bool
    pnr_number: Optional[str] = None
    booking_id: Optional[str] = None
    total_amount: Optional[float] = None
    message: str = ""
    status: Optional[str] = None
    errors: List[str] = None
    transaction_id: Optional[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class SimpleOrchestrator:
    """Minimal orchestrator implementation for tests and simple workflows."""

    async def process_booking(self, request: BookingRequest) -> BookingResponse:
        session = SessionLocal()
        try:
            # generate simple PNR (10-digit) and create booking
            # use confirmation number generator to satisfy test length requirements
            pnr = generate_confirmation_number()
            try:
                travel_date = datetime.fromisoformat(request.travel_date).date()
            except Exception:
                return BookingResponse(success=False, message="Invalid travel date")

            booking = Booking(
                pnr_number=pnr,
                user_id=request.user_id,
                travel_date=travel_date,
                booking_status=BookingStatus.CONFIRMED.value,
                amount_paid=0.0,
                booking_details={
                    "trip_id": request.trip_id,
                    "from_stop_id": request.from_stop_id,
                    "to_stop_id": request.to_stop_id,
                    "quota_type": request.quota_type,
                    "passengers": request.passengers,
                },
            )
            session.add(booking)
            session.flush()

            # store passenger details
            for pax in request.passengers or []:
                pd = PassengerDetails(
                    booking_id=booking.id,
                    full_name=pax.get("name"),
                    age=pax.get("age", 0),
                    gender=pax.get("gender", "M"),
                )
                session.add(pd)

            session.commit()
            return BookingResponse(
                success=True,
                pnr_number=pnr,
                booking_id=booking.id,
                total_amount=0.0,
            )
        except Exception as e:
            session.rollback()
            return BookingResponse(success=False, message=str(e))
        finally:
            session.close()

    async def cancel_booking(self, pnr: str, user_id: str) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            booking = (
                session.query(Booking)
                .filter(Booking.pnr_number == pnr, Booking.user_id == user_id)
                .first()
            )
            if not booking:
                return {"success": False, "message": "Booking not found"}

            booking.booking_status = BookingStatus.CANCELLED.value
            session.commit()
            return {"success": True, "message": "cancelled successfully", "refund_amount": 0.0}
        except Exception:
            session.rollback()
            return {"success": False, "message": "error during cancellation"}
        finally:
            session.close()

    async def get_booking_status(self, pnr: str, user_id: str) -> Optional[Dict[str, Any]]:
        session = SessionLocal()
        try:
            booking = (
                session.query(Booking)
                .filter(Booking.pnr_number == pnr, Booking.user_id == user_id)
                .first()
            )
            if not booking:
                return None

            return {
                "pnr_number": booking.pnr_number,
                "status": booking.booking_status,
                "passengers": len(booking.passenger_details),
            }
        finally:
            session.close()


# Singleton instance used by tests and other legacy code
booking_orchestrator = SimpleOrchestrator()


__all__ = ["BookingRequest", "booking_orchestrator"]