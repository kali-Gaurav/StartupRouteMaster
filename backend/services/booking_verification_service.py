"""
Shim module for booking_verification_service import compatibility.
The actual implementation is in services.booking.verification
"""

from services.booking.verification import BookingVerificationService

# Create a singleton instance for convenience
booking_verification_service = BookingVerificationService()

__all__ = ["BookingVerificationService", "booking_verification_service"]