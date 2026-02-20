"""Inventory Domain Interfaces

Abstract protocols for seat allocation and availability.
All implementations must follow these interfaces.
"""

from typing import Protocol, List, Optional
from dataclasses import dataclass


@dataclass
class SeatLock:
    """A locked seat with expiry."""
    trip_id: int
    seat_code: str
    user_id: int
    locked_at: float  # timestamp
    expires_at: float  # timestamp


class SeatAllocator(Protocol):
    """
    Abstract contract for seat allocation.

    All seat allocation implementations in domains/inventory/
    must follow this interface.

    CRITICAL: Only ONE implementation should exist.
    """

    async def allocate_seats(
        self,
        trip_id: int,
        requested_seats: int,
        seat_class: str = "GENERAL",
        user_id: Optional[int] = None,
        lock_duration_minutes: int = 15,
    ) -> List[str]:
        """
        Allocate specific seat codes for a trip.

        Args:
            trip_id: Train trip ID
            requested_seats: Number of seats needed
            seat_class: Seat class (GENERAL, SLEEPER, AC, etc)
            user_id: User making the request
            lock_duration_minutes: How long to lock seats

        Returns:
            List of allocated seat codes [A1, A2, B5, ...]

        Raises:
            InsufficientSeatsError: Not enough available seats
        """
        ...

    async def release_seats(
        self,
        trip_id: int,
        seat_codes: List[str],
    ):
        """
        Release locked seats (e.g., user cancelled booking).

        Args:
            trip_id: Train trip ID
            seat_codes: Seats to release
        """
        ...

    async def get_available_seats(
        self,
        trip_id: int,
        seat_class: str = "GENERAL",
    ) -> int:
        """
        Get count of available seats.

        Args:
            trip_id: Train trip ID
            seat_class: Filter by class

        Returns:
            Number of available seats
        """
        ...

    async def get_occupied_seats(
        self,
        trip_id: int,
    ) -> List[str]:
        """
        Get list of occupied/locked seats.

        Returns:
            List of seat codes that are not available
        """
        ...

    async def confirm_booking(
        self,
        trip_id: int,
        seat_codes: List[str],
        booking_id: str,
    ):
        """
        Convert locked seats to booked seats.

        Args:
            trip_id: Train trip ID
            seat_codes: Seats to confirm
            booking_id: Associated booking ID
        """
        ...
