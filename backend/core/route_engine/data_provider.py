"""
Unified Data Provider - Phase 3 Intelligent System

Provides unified data access with automatic fallback mechanism:
- Tries live APIs first (if configured and available)
- Falls back to database when APIs unavailable
- Gracefully handles null/missing configurations
- Zero knowledge of data sources in consumer code

This is the core abstraction that enables single-system offline/online/hybrid operation.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, time
import asyncio

from ...database import SessionLocal
from ...database.models import (
    Segment, Coach, Seat, Fare, Trip, Stop,
    StationDeparture
)

logger = logging.getLogger(__name__)


class DataProvider:
    """
    Unified data provider with automatic live API fallback to database.

    Configuration-driven via environment/config:
    - OFFLINE_MODE: bool (true = disable all online features)
    - REAL_TIME_ENABLED: bool (master switch for real-time)
    - LIVE_FARES_API: URL or None
    - LIVE_DELAY_API: URL or None
    - LIVE_SEAT_API: URL or None

    All methods maintain same interface regardless of data source.
    """

    def __init__(self, config=None):
        """
        Initialize data provider with configuration.

        Args:
            config: Optional config object with feature flags.
                   If None, will be imported at runtime.
        """
        self.config = config
        self.session = SessionLocal()

        # Feature capabilities (will be set by caller)
        self.has_live_fares = False
        self.has_live_delays = False
        self.has_live_seats = False
        self.offline_only = False

    def detect_available_features(self, config=None):
        """
        Auto-detect which live APIs are available.
        Called at startup by RailwayRouteEngine.

        This would typically check:
        - If LIVE_FARES_API is configured and responding
        - If LIVE_DELAY_API is configured and responding
        - If LIVE_SEAT_API is configured and responding
        """
        if config is None:
            if self.config is None:
                from ... import config as cfg
                config = cfg.Config
            else:
                config = self.config

        # For now, these would be determined by checking APIs
        # In production: try a test call to each API, measure latency
        # For MVP: just check if URLs are configured
        self.has_live_fares = bool(
            getattr(config, 'LIVE_FARES_API', None)
            and not getattr(config, 'OFFLINE_MODE', False)
        )
        self.has_live_delays = bool(
            getattr(config, 'LIVE_DELAY_API', None)
            and not getattr(config, 'OFFLINE_MODE', False)
        )
        self.has_live_seats = bool(
            getattr(config, 'LIVE_SEAT_API', None)
            and not getattr(config, 'OFFLINE_MODE', False)
        )
        self.offline_only = getattr(config, 'OFFLINE_MODE', False)

        logger.info(f"▶ Data Provider Capabilities:")
        logger.info(f"  · Offline Mode: {'✅ ENABLED' if self.offline_only else '❌ Disabled'}")
        logger.info(f"  · Live Fares: {'✅ Available' if self.has_live_fares else '❌ Using DB'}")
        logger.info(f"  · Live Delays: {'✅ Available' if self.has_live_delays else '❌ Assume 0'}")
        logger.info(f"  · Live Seats: {'✅ Available' if self.has_live_seats else '❌ Using DB'}")

    # ==================== FARE METHODS ====================

    async def get_fares(self, segment_id: int) -> Dict[str, float]:
        """
        Get fare information for a segment.

        Tries:
        1. Live Fares API (if configured and available)
        2. Database fallback

        Returns:
            Dict mapping class_type -> fare_amount
            Example: {'AC_1': 2500.0, 'AC_2': 1800.0, 'AC_3': 1200.0}
        """
        if self.has_live_fares:
            try:
                # TODO: Call actual live API
                # fares = await self._call_live_fares_api(segment_id)
                # if fares:
                #     return fares
                logger.debug(f"Live fares API configured but not yet implemented, using DB")
            except Exception as e:
                logger.warning(f"Live fares API failed: {e}, falling back to DB")

        # Database fallback
        return self._get_database_fares(segment_id)

    def _get_database_fares(self, segment_id: int) -> Dict[str, float]:
        """Get fares from database for a segment."""
        try:
            fares = self.session.query(Fare).filter(
                Fare.segment_id == segment_id
            ).all()

            result = {}
            for fare in fares:
                result[fare.class_type] = float(fare.amount)

            return result if result else {'AC_2': 1500.0}  # Safe default
        except Exception as e:
            logger.error(f"Database fare lookup failed: {e}")
            return {'AC_2': 1500.0}  # Safe default

    # ==================== SEAT/AVAILABILITY METHODS ====================

    async def get_seats(self, trip_id: int, date: datetime) -> Dict[str, int]:
        """
        Get available seats by class for a trip on a specific date.

        Tries:
        1. Live Seats API (if configured and available)
        2. Database fallback

        Returns:
            Dict mapping class_type -> available_seats
            Example: {'AC_1': 5, 'AC_2': 12, 'AC_3': 25}
        """
        if self.has_live_seats:
            try:
                # TODO: Call actual live API
                # seats = await self._call_live_seats_api(trip_id, date)
                # if seats:
                #     return seats
                logger.debug(f"Live seats API configured but not yet implemented, using DB")
            except Exception as e:
                logger.warning(f"Live seats API failed: {e}, falling back to DB")

        # Database fallback
        return self._get_database_seats(trip_id, date)

    def _get_database_seats(self, trip_id: int, date: datetime) -> Dict[str, int]:
        """Get available seats from database."""
        try:
            # Get coaches for trip
            coaches = self.session.query(Coach).filter(
                Coach.trip_id == trip_id
            ).all()

            if not coaches:
                logger.warning(f"No coaches found for trip {trip_id}")
                return {'AC_2': 48}  # Safe default

            # For each coach, get available seats by class
            availability = {}
            for coach in coaches:
                # Get seats info from coach
                # Simplified: assuming coaches have class_type attribute
                class_type = getattr(coach, 'class_type', 'AC_2')

                # Count available seats (simplified)
                available = self.session.query(Seat).filter(
                    Seat.coach_id == coach.id,
                    Seat.is_available == True
                ).count()

                if class_type not in availability:
                    availability[class_type] = 0
                availability[class_type] += available

            return availability if availability else {'AC_2': 48}
        except Exception as e:
            logger.error(f"Database seat lookup failed: {e}")
            return {'AC_2': 48}  # Safe default

    # ==================== DELAY METHODS ====================

    async def get_delays(self, trip_id: int) -> int:
        """
        Get current delay for a trip in minutes.

        Tries:
        1. Live Delay API (if configured and available)
        2. Returns 0 if unavailable (optimistic)

        Returns:
            Delay in minutes (0 = on-time, positive = late, negative = early)
        """
        if self.has_live_delays:
            try:
                # TODO: Call actual live API
                # delay = await self._call_live_delays_api(trip_id)
                # if delay is not None:
                #     return delay
                logger.debug(f"Live delays API configured but not yet implemented, assuming on-time")
            except Exception as e:
                logger.warning(f"Live delays API failed: {e}, assuming on-time")

        # Safe default: assume on-time
        return 0

    # ==================== TRANSFER METHODS ====================

    def get_transfers(self, from_stop_code: str, to_stop_code: str) -> Dict[str, Any]:
        """
        Get transfer information between two stops.

        Always from database (static, non-real-time data).

        Returns:
            Dict with transfer details:
            {
                'walking_time_minutes': 5,
                'distance_km': 0.5,
                'same_station': True,
                'feasible': True
            }
        """
        return self._get_database_transfers(from_stop_code, to_stop_code)

    def _get_database_transfers(self, from_stop_code: str, to_stop_code: str) -> Dict[str, Any]:
        """Get transfer information from database."""
        try:
            # Simplified: if same code, same station
            if from_stop_code == to_stop_code:
                return {
                    'walking_time_minutes': 5,
                    'distance_km': 0.5,
                    'same_station': True,
                    'feasible': True
                }

            # Otherwise, treat as different locations with longer transfer
            return {
                'walking_time_minutes': 30,
                'distance_km': 2.0,
                'same_station': False,
                'feasible': True
            }
        except Exception as e:
            logger.error(f"Database transfer lookup failed: {e}")
            return {
                'walking_time_minutes': 15,
                'distance_km': 1.0,
                'same_station': False,
                'feasible': True
            }

    # ==================== STATION DEPARTURE LOOKUP (Phase 1) ====================

    def get_departures_from_station(
        self,
        station_id: int,
        departure_time_min: datetime,
        departure_time_max: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fast Station → Time → Departures lookup (Phase 1 optimization).

        Uses composite index (station_id, departure_time) for < 1ms queries.

        Returns:
            List of departure records:
            [
                {
                    'trip_id': 12345,
                    'train_number': 'IR101',
                    'departure_time': datetime(...),
                    'next_station_id': 456,
                    'arrival_at_next': datetime(...),
                }
            ]
        """
        try:
            departures = self.session.query(StationDeparture).filter(
                StationDeparture.station_id == station_id,
                StationDeparture.departure_time >= departure_time_min.time(),
                StationDeparture.departure_time <= departure_time_max.time()
            ).all()

            result = []
            for dep in departures:
                result.append({
                    'trip_id': dep.trip_id,
                    'train_number': getattr(dep, 'train_number', 'UNKNOWN'),
                    'departure_time': dep.departure_time,
                    'next_station_id': dep.next_station_id,
                    'arrival_at_next': dep.arrival_time_at_next,
                })

            return result
        except Exception as e:
            logger.error(f"Station departure lookup failed: {e}")
            return []

    # ==================== CLEANUP ====================

    def close(self):
        """Close database connection."""
        if self.session:
            self.session.close()

    def __del__(self):
        """Cleanup on object destruction."""
        self.close()
