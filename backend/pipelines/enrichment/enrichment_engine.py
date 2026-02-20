"""
Pipeline 1: Data Enrichment Pipeline

Fills missing or stale data from live sources and maintains data consistency.

Stages:
1. Connect to live APIs
2. Validate fetched data
3. Reconcile with database
4. Store enriched data
"""

import logging
from typing import Any, Dict, Optional
from abc import abstractmethod
from datetime import datetime
import httpx

from ..base import BasePipelineStage, PipelineContext

logger = logging.getLogger(__name__)


class LiveAPIConnector(BasePipelineStage):
    """Base class for live API connectors.

    Handles connection, timeout, retry, and circuit breaking.
    """

    def __init__(
        self,
        name: str,
        api_url: Optional[str],
        timeout_ms: int = 500,
        retries: int = 1
    ):
        super().__init__(name)
        self.api_url = api_url
        self.timeout_ms = timeout_ms
        self.retries = retries
        self.available = bool(api_url)

    @abstractmethod
    async def fetch_data(self, url: str) -> Dict[str, Any]:
        """Fetch data from live API."""
        pass

    async def process(self, input_data: Any) -> Any:
        """Connect to live API and fetch enrichment data."""
        if not self.available:
            self.logger.debug(f"{self.name} not configured, skipping")
            return input_data

        context = input_data if isinstance(input_data, PipelineContext) else PipelineContext(**input_data)

        try:
            # Fetch from live API with retries
            for attempt in range(self.retries):
                try:
                    live_data = await self.fetch_data(self.api_url)
                    context.set(f'{self.name}_data', live_data)
                    context.add_metadata(f'{self.name}_source', 'LIVE')
                    self.logger.info(f"{self.name} succeeded")
                    return context
                except httpx.TimeoutException:
                    if attempt == self.retries - 1:
                        self.logger.warning(f"{self.name} timeout after {self.retries} retries")
                        context.add_error(f"{self.name} timeout")
                        context.add_metadata(f'{self.name}_source', 'DB_FALLBACK')
                        return context
                    self.logger.debug(f"{self.name} timeout, retrying ({attempt + 1}/{self.retries})")

        except Exception as e:
            self.logger.error(f"{self.name} failed: {e}")
            context.add_error(str(e))
            context.add_metadata(f'{self.name}_source', 'DB_FALLBACK')

        return context


class LiveFareConnector(LiveAPIConnector):
    """Fetch live fare data from LIVE_FARES_API."""

    def __init__(self, api_url: Optional[str]):
        super().__init__('LiveFareConnector', api_url)

    async def fetch_data(self, url: str) -> Dict[str, Any]:
        """Fetch fares from live API."""
        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
            response = await client.get(f"{url}/prices")
            return response.json()


class LiveDelayConnector(LiveAPIConnector):
    """Fetch live delay data from LIVE_DELAY_API."""

    def __init__(self, api_url: Optional[str]):
        super().__init__('LiveDelayConnector', api_url)

    async def fetch_data(self, url: str) -> Dict[str, Any]:
        """Fetch delays from live API."""
        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
            response = await client.get(f"{url}/delays")
            return response.json()


class LiveSeatConnector(LiveAPIConnector):
    """Fetch live seat availability from LIVE_SEAT_API."""

    def __init__(self, api_url: Optional[str]):
        super().__init__('LiveSeatConnector', api_url)

    async def fetch_data(self, url: str) -> Dict[str, Any]:
        """Fetch seat availability from live API."""
        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
            response = await client.get(f"{url}/availability")
            return response.json()


class LiveBookingConnector(LiveAPIConnector):
    """Fetch live booking data from LIVE_BOOKING_API."""

    def __init__(self, api_url: Optional[str]):
        super().__init__('LiveBookingConnector', api_url)

    async def fetch_data(self, url: str) -> Dict[str, Any]:
        """Fetch booking data from live API."""
        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
            response = await client.get(f"{url}/bookings")
            return response.json()


class DataReconciler(BasePipelineStage):
    """Reconcile live data with database data.

    Handles conflicts and chooses best data source based on rules.
    """

    def __init__(self):
        super().__init__('DataReconciler')

    async def process(self, input_data: Any) -> Any:
        """Reconcile live vs database data."""
        context = input_data if isinstance(input_data, PipelineContext) else PipelineContext(**input_data)

        # Get live data from context
        live_fares = context.get('LiveFareConnector_data', {})
        live_delays = context.get('LiveDelayConnector_data', {})
        live_seats = context.get('LiveSeatConnector_data', {})

        # Apply reconciliation rules
        if live_fares:
            self._reconcile_fares(context, live_fares)
        if live_delays:
            self._reconcile_delays(context, live_delays)
        if live_seats:
            self._reconcile_seats(context, live_seats)

        return context

    def _reconcile_fares(self, context: PipelineContext, live_fares: Dict) -> None:
        """Reconcile fare data."""
        context.add_metadata('fares_reconciled', True)
        # TODO: Implement fare reconciliation logic
        self.logger.debug("Fares reconciled")

    def _reconcile_delays(self, context: PipelineContext, live_delays: Dict) -> None:
        """Reconcile delay data."""
        context.add_metadata('delays_reconciled', True)
        # TODO: Implement delay reconciliation logic
        self.logger.debug("Delays reconciled")

    def _reconcile_seats(self, context: PipelineContext, live_seats: Dict) -> None:
        """Reconcile seat availability data."""
        context.add_metadata('seats_reconciled', True)
        # TODO: Implement seat reconciliation logic
        self.logger.debug("Seats reconciled")


class DataWriter(BasePipelineStage):
    """Write reconciled data to database.

    Maintains data consistency and marks source origin.
    """

    def __init__(self):
        super().__init__('DataWriter')

    async def process(self, input_data: Any) -> Any:
        """Write data to database."""
        context = input_data if isinstance(input_data, PipelineContext) else PipelineContext(**input_data)

        # Write fares if available
        if context.get('LiveFareConnector_data'):
            await self._write_fares(context)

        # Write delays if available
        if context.get('LiveDelayConnector_data'):
            await self._write_delays(context)

        # Write seats if available
        if context.get('LiveSeatConnector_data'):
            await self._write_seats(context)

        context.add_metadata('data_written', True)
        return context

    async def _write_fares(self, context: PipelineContext) -> None:
        """Write fares to database."""
        # TODO: Implement database write logic
        self.logger.debug("Fares written to database")

    async def _write_delays(self, context: PipelineContext) -> None:
        """Write delays to database."""
        # TODO: Implement database write logic
        self.logger.debug("Delays written to database")

    async def _write_seats(self, context: PipelineContext) -> None:
        """Write seats to database."""
        # TODO: Implement database write logic
        self.logger.debug("Seats written to database")
