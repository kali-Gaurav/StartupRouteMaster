"""Routing Domain Interfaces

Abstract protocols that define the contract for route finding.
All implementations must follow these interfaces.
"""

from typing import Protocol, List, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class Segment:
    """A journey segment (one train leg)."""
    trip_id: int
    from_station_id: int
    to_station_id: int
    departure_time: datetime
    arrival_time: datetime
    train_number: str
    seat_class: str
    distance_km: float


@dataclass
class Journey:
    """Complete journey from source to destination."""
    journey_id: str
    segments: List[Segment]
    total_Duration_minutes: int
    num_transfers: int
    total_fare_base: float


class RouteFinder(Protocol):
    """
    Abstract contract for finding routes between stations.

    All route-finding implementations in domains/routing/
    must follow this interface.
    """

    async def find_routes(
        self,
        source_station_id: int,
        destination_station_id: int,
        departure_time: datetime,
        max_transfers: int = 3,
        preferences: Optional[dict] = None,
    ) -> List[Journey]:
        """
        Find optimal routes between two stations.

        Args:
            source_station_id: Starting station ID
            destination_station_id: Ending station ID
            departure_time: Earliest departure time
            max_transfers: Maximum allowed transfers
            preferences: Optional preferences (direct_only, no_late_night, etc)

        Returns:
            List of journeys, sorted by distance/transfers/time
        """
        ...

    async def find_routes_with_dates(
        self,
        source_station_id: int,
        destination_station_id: int,
        departure_dates: List[datetime],
        max_transfers: int = 3,
    ) -> dict:
        """
        Find routes for multiple departure dates.

        Returns:
            {date: [journeys]}
        """
        ...
