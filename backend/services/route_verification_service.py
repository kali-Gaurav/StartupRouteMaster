"""
Shim module for route_verification_service import compatibility.
The actual implementation is in services.planning.verification
"""

from services.planning.verification import RouteVerificationService

# Create a singleton instance for convenience
route_verification_service = RouteVerificationService()

__all__ = ["RouteVerificationService", "route_verification_service"]