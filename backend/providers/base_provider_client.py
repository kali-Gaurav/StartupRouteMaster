"""
Abstract base classes for data provider clients.

This module defines the common interface that all data provider clients
must adhere to. This ensures consistency and simplifies integration
with the ProviderGateway.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

# Import common models that providers will return or transform into
from providers.models import (
    UnifiedLiveStatus, UnifiedAvailability, UnifiedSchedule, 
    UnifiedFare, UnifiedPNRStatus
)

class BaseProviderClient(ABC):
    """
    Abstract base class for all data provider clients.

    All concrete provider clients must inherit from this class and implement
    the abstract methods.
    """
    def __init__(self, name: str, provider_config: Any):
        self.name = name
        self.config = provider_config
        self.logger = logging.getLogger(f"ProviderClient.{self.name}")
        self.logger.setLevel(logging.INFO) # Or appropriate level

    @abstractmethod
    async def get_live_status(self, train_number: str, **kwargs) -> Optional[UnifiedLiveStatus]:
        """
        Fetches live status for a given train.

        Args:
            train_number: The train number.
            **kwargs: Additional parameters (e.g., train_date).

        Returns:
            A UnifiedLiveStatus object if successful, otherwise None.
        """
        pass

    @abstractmethod
    async def get_seat_availability(self, train_number: str, travel_date: str, 
                                    from_station_code: str, to_station_code: str, 
                                    class_code: str, quota: str = "GN", **kwargs) -> Optional[List[Dict[str, Any]]]:
        """
        Fetches seat availability for a given route, date, class, and quota.

        Args:
            train_number: The train number.
            travel_date: The date of travel in 'YYYY-MM-DD' format.
            from_station_code: Departure station code.
            to_station_code: Arrival station code.
            class_code: Desired class type (e.g., "SL", "3A").
            quota: Quota type (e.g., "GN", "TQ").
            **kwargs: Additional parameters.

        Returns:
            A list of availability dictionaries, or None if unavailable.
        """
        pass
        
    @abstractmethod
    async def get_schedule(self, train_number: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Fetches the train schedule.

        Args:
            train_number: The train number.
            **kwargs: Additional parameters.

        Returns:
            A dictionary representing the schedule, or None if unavailable.
        """
        pass

    @abstractmethod
    async def get_fare(self, train_number: str, travel_date: str, 
                         from_station_code: str, to_station_code: str, 
                         class_code: str, quota: str = "GN") -> Optional[UnifiedFare]:
        """
        Fetches fare information for a given route and date.
        """
        pass

    @abstractmethod
    async def get_pnr_status(self, pnr_number: str) -> Optional[UnifiedPNRStatus]:
        """
        Fetches status for a given PNR number.
        """
        pass

# Note: These imports would typically be handled by the framework, but for clarity:
import logging
from providers.models import UnifiedLiveStatus, UnifiedAvailability, UnifiedSchedule # Assuming these exist
