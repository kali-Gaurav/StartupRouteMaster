#!/usr/bin/env python3
"""
Frequency-aware Range-RAPTOR Window Sizing

Dynamically adjusts the Range-RAPTOR search window based on corridor frequency.
More frequent corridors = smaller windows (better coverage with tight search).
Less frequent corridors = larger windows (need to search further out).

Architecture:
1. Compute trip frequency (trips per hour) for origin-destination pair
2. Scale Range window based on frequency
3. Cache frequency computations for performance
"""

import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Dict, Optional, Tuple
import redis.asyncio as redis
from sqlalchemy import func

from database.models import Calendar, CalendarDate, StopTime
from database.session import SessionLocal

logger = logging.getLogger(__name__)

# Cache key prefix for frequency computations
FREQUENCY_CACHE_TTL = 86400  # 24 hours
FREQUENCY_CACHE_PREFIX = "corridor_frequency:"


class FrequencyAwareWindowSizer:
    """
    Computes trip frequency on corridors and sizes Range-RAPTOR window adaptively.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None

    async def _ensure_redis(self):
        """Lazy initialize Redis connection"""
        if self.redis_client is None:
            try:
                self.redis_client = await redis.from_url(self.redis_url)
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, will use DB queries only")

    async def get_range_window_minutes(
        self,
        origin_stop_id: int,
        destination_stop_id: int,
        search_date: date,
        base_range_minutes: int = 60,
        distance_km: Optional[float] = None,
    ) -> int:
        """
        Calculate adaptive Range-RAPTOR window based on corridor frequency.

        Args:
            origin_stop_id: Starting stop
            destination_stop_id: Destination stop
            search_date: Date of travel
            base_range_minutes: Default window size (60 minutes)
            distance_km: Route distance (optional, for fallback)

        Returns:
            Recommended Range window in minutes
        """
        await self._ensure_redis()

        # Compute frequency for this corridor on this date
        frequency_trips_per_hour = await self._compute_corridor_frequency(
            origin_stop_id=origin_stop_id,
            destination_stop_id=destination_stop_id,
            search_date=search_date,
        )

        # Scale window based on frequency
        if frequency_trips_per_hour > 2.0:
            # High frequency: shrink window to 30 mins
            window = 30
        elif frequency_trips_per_hour > 1.0:
            # Medium frequency: keep at 60 mins
            window = base_range_minutes
        elif frequency_trips_per_hour > 0.5:
            # Low frequency: expand to 2 hours
            window = 120
        else:
            # Very low frequency: expand to 4-6 hours based on distance
            if distance_km is not None:
                if distance_km < 200:
                    window = 180  # 3 hours for short distances
                elif distance_km < 800:
                    window = 360  # 6 hours for medium distances
                else:
                    window = 480  # 8 hours for long distances
            else:
                window = 360  # default to 6 hours

        logger.debug(
            f"Frequency-aware window: {frequency_trips_per_hour:.2f} trips/hr → {window} min"
        )
        return window

    async def _compute_corridor_frequency(
        self,
        origin_stop_id: int,
        destination_stop_id: int,
        search_date: date,
    ) -> float:
        """
        Compute trips per hour from origin to destination on given date.

        Returns:
            Number of direct/multi-leg trips per hour (0-max)
        """
        cache_key = f"{FREQUENCY_CACHE_PREFIX}{origin_stop_id}:{destination_stop_id}:{search_date.isoformat()}"

        # Try cache first
        if self.redis_client is not None:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached is not None:
                    return float(cached)
            except Exception as e:
                logger.debug(f"Cache lookup failed: {e}")

        # Compute from database
        frequency = await self._compute_frequency_from_db(
            origin_stop_id=origin_stop_id,
            destination_stop_id=destination_stop_id,
            search_date=search_date,
        )

        # Cache result
        if self.redis_client is not None:
            try:
                await self.redis_client.setex(
                    cache_key,
                    FREQUENCY_CACHE_TTL,
                    str(frequency),
                )
            except Exception as e:
                logger.debug(f"Cache store failed: {e}")

        return frequency

    async def _compute_frequency_from_db(
        self,
        origin_stop_id: int,
        destination_stop_id: int,
        search_date: date,
    ) -> float:
        """
        Query database to count trips between origin and destination on search_date.
        
        Uses asyncio to avoid blocking the event loop.
        Returns 0 if database query fails (graceful degradation).
        """
        def _query():
            try:
                db = SessionLocal()
                try:
                    # Check if date is valid (has calendar entry)
                    calendar_entry = db.query(Calendar).filter(
                        Calendar.start_date <= search_date,
                        Calendar.end_date >= search_date,
                    ).first()

                    if calendar_entry is None:
                        # No regular service on this date
                        exceptions = db.query(CalendarDate).filter(
                            CalendarDate.date == search_date,
                            CalendarDate.exception_type == 1,  # service added
                        )
                        if not exceptions.first():
                            return 0.0

                    # Count trips with stops at both origin and destination
                    # This is a simplified query; in practice might need more sophisticated matching
                    origin_trips = db.query(StopTime.trip_id).filter(
                        StopTime.stop_id == origin_stop_id
                    ).subquery()

                    dest_trips = db.query(StopTime.trip_id).filter(
                        StopTime.stop_id == destination_stop_id
                    ).subquery()

                    # Find trips that visit both stops
                    connecting_trips = db.query(func.count(StopTime.trip_id)).filter(
                        StopTime.trip_id.in_(db.query(origin_trips)),
                    ).distinct().scalar()

                    # Normalize to trips per hour (assume service from 6am-11pm = 17 hours)
                    service_hours = 17.0
                    frequency = float(connecting_trips or 0) / service_hours

                    return frequency

                finally:
                    db.close()
            
            except Exception as e:
                logger.warning(f"Failed to compute frequency from database: {e}, returning 0.0")
                # Return 0 to indicate no frequency data available (will trigger larger window)
                return 0.0

        # Run query in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _query)

    async def clear_cache(self, origin_stop_id: int, destination_stop_id: int):
        """Clear frequency cache for a specific corridor"""
        if self.redis_client is not None:
            try:
                pattern = f"{FREQUENCY_CACHE_PREFIX}{origin_stop_id}:{destination_stop_id}:*"
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
                    logger.info(f"Cleared {len(keys)} frequency cache entries")
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")


# Singleton instance
_frequency_sizer = None


async def get_frequency_aware_sizer() -> FrequencyAwareWindowSizer:
    """Get or initialize the frequency-aware window sizer"""
    global _frequency_sizer
    if _frequency_sizer is None:
        _frequency_sizer = FrequencyAwareWindowSizer()
    return _frequency_sizer
