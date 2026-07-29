"""
Booking Service - Factory functions and re-exports for booking operations.
This file consolidates imports from the actual implementation in booking/service.py
"""

from sqlalchemy.orm import Session
from .booking.service import BookingService as _BookingService


class BookingService(_BookingService):
    """Alias for backward compatibility."""
    pass


def get_booking_service(db: Session) -> BookingService:
    """
    Factory function to get BookingService instance.

    Args:
        db: SQLAlchemy database session

    Returns:
        BookingService instance
    """
    return BookingService(db)
