"""
Shim module for AdvancedSeatAllocationEngine to maintain compatibility.
The actual implementation is in services.inventory.engine.
"""

from services.inventory.engine import (
    AdvancedSeatAllocationEngine,
    PassengerPreference,
    BerthType,
    SeatStatus,
    Coach,
    SeatAllocationResult,
    advanced_seat_allocation_engine
)

__all__ = [
    "AdvancedSeatAllocationEngine",
    "PassengerPreference",
    "BerthType",
    "SeatStatus",
    "Coach",
    "SeatAllocationResult",
    "advanced_seat_allocation_engine"
]
