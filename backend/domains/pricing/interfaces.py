"""Pricing Domain Interfaces

Abstract protocols for fare calculation and yield management.
All implementations must follow these interfaces.
"""

from typing import Protocol, Optional
from dataclasses import dataclass


@dataclass
class FareQuote:
    """A fare quote for a segment."""
    segment_id: str
    base_fare: float
    dynamic_factor: float  # 0.8 to 1.5 based on demand
    taxes: float
    total_fare: float
    seat_class: str


class PricingEngine(Protocol):
    """
    Abstract contract for fare calculation.

    All pricing implementations in domains/pricing/
    must follow this interface.

    CRITICAL: Only ONE implementation should exist.
    """

    async def calculate_fare(
        self,
        segment_id: str,
        seat_class: str,
        demand_level: Optional[float] = None,
    ) -> float:
        """
        Calculate dynamic fare for a segment.

        Args:
            segment_id: Train segment ID
            seat_class: Seat class (GENERAL, SLEEPER, AC, etc)
            demand_level: Demand factor (0.0 to 1.0)
                         if None, fetch from intelligence/

        Returns:
            Calculated fare amount
        """
        ...

    async def calculate_journey_fare(
        self,
        segment_ids: list[str],
        seat_class: str,
        demand_levels: Optional[dict] = None,
    ) -> FareQuote:
        """
        Calculate total fare for a journey (multiple segments).

        Args:
            segment_ids: List of segment IDs in journey
            seat_class: Seat class for all segments
            demand_levels: {segment_id: demand_factor} mapping

        Returns:
            FareQuote with total fare
        """
        ...

    async def get_base_fare(
        self,
        segment_id: str,
        seat_class: str,
    ) -> float:
        """
        Get base fare without dynamic pricing.

        Args:
            segment_id: Train segment ID
            seat_class: Seat class

        Returns:
            Base fare amount
        """
        ...

    async def apply_yield_management(
        self,
        segment_id: str,
        seat_class: str,
        occupancy_rate: float,
        days_until_departure: int,
    ) -> float:
        """
        Apply yield management rules for dynamic pricing.

        Args:
            segment_id: Train segment ID
            seat_class: Seat class
            occupancy_rate: Current occupancy (0.0 to 1.0)
            days_until_departure: Days until train departs

        Returns:
            Calculated dynamic fare
        """
        ...
