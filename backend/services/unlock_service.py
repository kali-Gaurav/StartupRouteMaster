"""
Shim module for unlock_service import compatibility.
The actual implementation is in services.pricing.unlock
"""

from services.pricing.unlock import UnlockService

# Create a singleton instance for convenience
unlock_service = UnlockService()

__all__ = ["UnlockService", "unlock_service"]