"""Booking Domain Interfaces

Abstract protocols for booking management.
All implementations must follow these interfaces.
"""

from typing import Protocol, List, Optional
from dataclasses import dataclass
from enum import Enum


class BookingStatus(Enum):
    """Booking lifecycle states."""
    PENDING = "PENDING"           # Seats locked, not confirmed
    CONFIRMED = "CONFIRMED"       # Payment successful
    CANCELLED = "CANCELLED"       # User cancelled
    NO_SHOW = "NO_SHOW"          # Train departed, didn't board
    COMPLETED = "COMPLETED"       # Journey completed


@dataclass
class Booking:
    """A confirmed booking."""
    booking_id: str
    user_id: int
    journey_id: str
    seat_codes: List[str]
    total_fare: float
    status: BookingStatus
    created_at: float  # timestamp
    modified_at: float  # timestamp


class Booker(Protocol):
    """
    Abstract contract for booking operations.

    All booking implementations in domains/booking/
    must follow this interface.
    """

    async def create_booking(
        self,
        user_id: int,
        journey_id: str,
        seat_codes: List[str],
        total_fare: float,
    ) -> Booking:
        """
        Create a new booking (seats already locked).

        Args:
            user_id: User making the booking
            journey_id: Journey selected
            seat_codes: Allocated seat codes
            total_fare: Quoted fare

        Returns:
            Booking record

        Raises:
            SeatsNotAvailableError: Seats were released
            InvalidJourneyError: Journey not found or expired
        """
        ...

    async def confirm_booking(
        self,
        booking_id: str,
        payment_id: str,
    ) -> Booking:
        """
        Confirm a pending booking after payment.

        Args:
            booking_id: Booking ID to confirm
            payment_id: Associated payment transaction

        Returns:
            Updated Booking with CONFIRMED status
        """
        ...

    async def cancel_booking(
        self,
        booking_id: str,
        reason: Optional[str] = None,
    ) -> Booking:
        """
        Cancel a booking and release seats.

        Args:
            booking_id: Booking to cancel
            reason: Cancellation reason

        Returns:
            Updated Booking with CANCELLED status
        """
        ...

    async def get_booking(self, booking_id: str) -> Optional[Booking]:
        """Get booking details."""
        ...

    async def list_user_bookings(self, user_id: int) -> List[Booking]:
        """Get all bookings for a user."""
        ...
