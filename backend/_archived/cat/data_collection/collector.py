"""
Unified Data Collector for the Contextual Availability Transformer (CAT) system.
Aggregates data from multiple sources with concurrent fetching, fallback strategies,
and data freshness validation.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..models.schemas import (
    EventCalendarData, WeatherData, HistoricalAvailabilityData,
    ContextualData, Location
)
from ..config import settings
from .clients import (
    EventCalendarClient, WeatherClient, HistoricalRecordsClient,
    CacheEntry
)


logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of a data fetch operation."""
    source: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    from_cache: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DataFreshnessStatus:
    """Status of data freshness for each source."""
    event_calendar_fresh: bool = False
    event_calendar_age_seconds: float = 0.0
    weather_fresh: bool = False
    weather_age_seconds: float = 0.0
    historical_fresh: bool = False
    historical_age_seconds: float = 0.0
    all_fresh: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_calendar_fresh": self.event_calendar_fresh,
            "event_calendar_age_seconds": self.event_calendar_age_seconds,
            "weather_fresh": self.weather_fresh,
            "weather_age_seconds": self.weather_age_seconds,
            "historical_fresh": self.historical_fresh,
            "historical_age_seconds": self.historical_age_seconds,
            "all_fresh": self.all_fresh
        }


class DataCollector:
    """
    Unified data collector that aggregates data from multiple sources.
    
    Implements:
    - Concurrent fetching with asyncio for parallel API calls
    - Partial failure handling with fallback strategies
    - Data freshness validation
    - Configurable caching with TTL
    - Comprehensive metrics and logging
    """
    
    def __init__(
        self,
        event_client: EventCalendarClient = None,
        weather_client: WeatherClient = None,
        historical_client: HistoricalRecordsClient = None,
        timeout_seconds: int = None,
        use_synthetic_fallback: bool = True,
        max_concurrent_fetches: int = 3,
        freshness_threshold_seconds: int = 3600  # 1 hour
    ):
        """
        Initialize the data collector.
        
        Args:
            event_client: Event calendar client
            weather_client: Weather client
            historical_client: Historical records client
            timeout_seconds: Timeout for all operations
            use_synthetic_fallback: Whether to use synthetic data when APIs fail
            max_concurrent_fetches: Maximum concurrent fetch operations
            freshness_threshold_seconds: Maximum age for fresh data
        """
        self.event_client = event_client or EventCalendarClient(
            use_synthetic_fallback=use_synthetic_fallback
        )
        self.weather_client = weather_client or WeatherClient(
            use_synthetic_fallback=use_synthetic_fallback
        )
        self.historical_client = historical_client or HistoricalRecordsClient(
            use_synthetic_fallback=use_synthetic_fallback
        )
        
        self.timeout = timeout_seconds or 30
        self.use_synthetic_fallback = use_synthetic_fallback
        self.max_concurrent = max_concurrent_fetches
        self.freshness_threshold = freshness_threshold_seconds
        
        # Unified cache for contextual data
        self._context_cache: Dict[str, CacheEntry] = {}
        self._cache_ttl = settings.prediction_cache_ttl_seconds
        
        # Metrics
        self._metrics = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "partial_failures": 0,
            "total_failures": 0,
            "total_duration_ms": 0.0
        }
    
    async def close(self) -> None:
        """Close all HTTP clients."""
        await self.event_client.close()
        await self.weather_client.close()
    
    def _get_context_cache_key(
        self,
        location_id: str,
        prediction_time: datetime,
        context_hours: int
    ) -> str:
        """Generate a cache key for contextual data."""
        return f"context:{location_id}:{prediction_time.isoformat()}:{context_hours}"
    
    def _get_cached_contextual_data(
        self,
        cache_key: str
    ) -> Optional[ContextualData]:
        """Get cached contextual data if valid."""
        if cache_key in self._context_cache:
            entry = self._context_cache[cache_key]
            if entry.is_valid():
                self._metrics["cache_hits"] += 1
                logger.debug(f"Context cache hit for {cache_key}")
                return entry.value
            del self._context_cache[cache_key]
        self._metrics["cache_misses"] += 1
        return None
    
    def _set_cached_contextual_data(
        self,
        cache_key: str,
        data: ContextualData
    ) -> None:
        """Cache contextual data."""
        self._context_cache[cache_key] = CacheEntry(data, self._cache_ttl)
    
    async def fetch_contextual_data(
        self,
        location_id: str,
        prediction_time: datetime,
        context_hours: int = None
    ) -> ContextualData:
        """
        Fetch all contextual data for a prediction request.
        
        Args:
            location_id: Location identifier
            prediction_time: Time to predict
            context_hours: Hours of historical context to include
            
        Returns:
            ContextualData with all contextual information
        """
        self._metrics["total_requests"] += 1
        context_hours = context_hours or settings.context_window_hours
        
        # Check cache first
        cache_key = self._get_context_cache_key(location_id, prediction_time, context_hours)
        cached = self._get_cached_contextual_data(cache_key)
        if cached is not None:
            return cached
        
        # Get location coordinates for weather API
        location = await self._get_location(location_id)
        context_start = prediction_time - timedelta(hours=context_hours)
        context_end = prediction_time + timedelta(hours=context_hours)
        
        # Fetch all data concurrently
        start_time = time.monotonic()
        results = await self._fetch_all_concurrently(
            location_id, location, context_start, context_end
        )
        duration_ms = (time.monotonic() - start_time) * 1000
        self._metrics["total_duration_ms"] += duration_ms
        
        # Process results
        events, weather, historical = results
        
        # Handle partial failures
        failure_count = sum(1 for r in [events, weather, historical] if not r.success)
        if failure_count > 0:
            self._metrics["partial_failures"] += 1
            logger.warning(
                f"Partial failure fetching data: {failure_count}/3 sources failed"
            )
        
        # Build contextual data
        contextual_data = ContextualData(
            event_calendar=events.data if events.success else EventCalendarData(
                events=[], last_updated=datetime.utcnow(), error_flag=True
            ),
            weather=weather.data if weather.success else WeatherData(
                current_conditions=None, forecast=[], last_updated=datetime.utcnow(), error_flag=True
            ),
            historical_availability=historical.data if historical.success else HistoricalAvailabilityData(
                records=[], location_id=location_id, error_flag=True
            ),
            timestamp=datetime.utcnow()
        )
        
        # Cache the result
        self._set_cached_contextual_data(cache_key, contextual_data)
        
        return contextual_data
    
    async def _fetch_all_concurrently(
        self,
        location_id: str,
        location: Location,
        context_start: datetime,
        context_end: datetime
    ) -> Tuple[FetchResult, FetchResult, FetchResult]:
        """
        Fetch all data sources concurrently.
        
        Returns:
            Tuple of FetchResult for events, weather, and historical
        """
        # Create semaphore to limit concurrent fetches
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def fetch_with_limit(
            source_name: str,
            coro
        ) -> FetchResult:
            async with semaphore:
                start = time.monotonic()
                try:
                    data = await asyncio.wait_for(coro, timeout=self.timeout)
                    duration_ms = (time.monotonic() - start) * 1000
                    return FetchResult(
                        source=source_name,
                        success=True,
                        data=data,
                        duration_ms=duration_ms
                    )
                except asyncio.TimeoutError:
                    duration_ms = (time.monotonic() - start) * 1000
                    logger.error(f"{source_name} fetch timed out after {duration_ms:.0f}ms")
                    return FetchResult(
                        source=source_name,
                        success=False,
                        error="Timeout",
                        duration_ms=duration_ms
                    )
                except Exception as e:
                    duration_ms = (time.monotonic() - start) * 1000
                    logger.error(f"{source_name} fetch failed: {e}")
                    return FetchResult(
                        source=source_name,
                        success=False,
                        error=str(e),
                        duration_ms=duration_ms
                    )
        
        # Launch concurrent fetches
        tasks = [
            fetch_with_limit(
                "event_calendar",
                self.event_client.fetch_events(
                    location_id, context_start, context_end
                )
            ),
            fetch_with_limit(
                "weather",
                self.weather_client.fetch_weather(
                    location.latitude, location.longitude,
                    context_start, context_end
                )
            ),
            fetch_with_limit(
                "historical",
                self.historical_client.fetch_historical(
                    location_id, context_start, context_end
                )
            )
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed FetchResults
        processed_results = []
        for i, (source_name, coro) in enumerate([
            ("event_calendar", tasks[0]),
            ("weather", tasks[1]),
            ("historical", tasks[2])
        ]):
            result = results[i]
            if isinstance(result, Exception):
                processed_results.append(FetchResult(
                    source=source_name,
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return tuple(processed_results)
    
    async def _get_location(self, location_id: str) -> Location:
        """
        Get location information by ID.
        
        In production, this would query a location database.
        For now, returns a default location.
        """
        # Placeholder: In production, query location database
        # Default coordinates (can be overridden with actual data)
        return Location(
            venue_id=location_id,
            latitude=40.7128,
            longitude=-74.0060,
            capacity=500
        )
    
    def validate_data_freshness(
        self,
        contextual_data: ContextualData
    ) -> DataFreshnessStatus:
        """
        Validate the freshness of contextual data.
        
        Args:
            contextual_data: The data to validate
            
        Returns:
            DataFreshnessStatus with freshness information
        """
        now = datetime.utcnow()
        status = DataFreshnessStatus()
        
        # Check event calendar freshness
        if contextual_data.event_calendar:
            event_age = (now - contextual_data.event_calendar.last_updated).total_seconds()
            status.event_calendar_age_seconds = event_age
            status.event_calendar_fresh = event_age < self.freshness_threshold
        
        # Check weather freshness
        if contextual_data.weather and contextual_data.weather.last_updated:
            weather_age = (now - contextual_data.weather.last_updated).total_seconds()
            status.weather_age_seconds = weather_age
            status.weather_fresh = weather_age < self.freshness_threshold
        
        # Check historical freshness (based on most recent record)
        if contextual_data.historical_availability and contextual_data.historical_availability.records:
            records = contextual_data.historical_availability.records
            if records:
                latest_record = max(records, key=lambda r: r.timestamp)
                hist_age = (now - latest_record.timestamp).total_seconds()
                status.historical_age_seconds = hist_age
                status.historical_fresh = hist_age < self.freshness_threshold
        
        # Overall freshness
        status.all_fresh = (
            status.event_calendar_fresh and
            status.weather_fresh and
            status.historical_fresh
        )
        
        return status
    
    async def fetch_with_fallback(
        self,
        location_id: str,
        prediction_time: datetime,
        context_hours: int = None,
        fallback_to_synthetic: bool = None
    ) -> Tuple[ContextualData, DataFreshnessStatus]:
        """
        Fetch contextual data with fallback strategies.
        
        Args:
            location_id: Location identifier
            prediction_time: Time to predict
            context_hours: Hours of historical context
            fallback_to_synthetic: Whether to use synthetic data on failure
            
        Returns:
            Tuple of (ContextualData, DataFreshnessStatus)
        """
        fallback = fallback_to_synthetic if fallback_to_synthetic is not None else self.use_synthetic_fallback
        
        try:
            data = await self.fetch_contextual_data(
                location_id, prediction_time, context_hours
            )
            freshness = self.validate_data_freshness(data)
            return data, freshness
        except Exception as e:
            logger.error(f"Failed to fetch contextual data: {e}")
            self._metrics["total_failures"] += 1
            
            if fallback:
                logger.info("Using synthetic data fallback")
                return await self._fetch_synthetic_fallback(
                    location_id, prediction_time, context_hours
                )
            else:
                raise
    
    async def _fetch_synthetic_fallback(
        self,
        location_id: str,
        prediction_time: datetime,
        context_hours: int
    ) -> Tuple[ContextualData, DataFreshnessStatus]:
        """Fetch synthetic data when real APIs fail."""
        from .synthetic_data import SyntheticDataGenerator
        
        generator = SyntheticDataGenerator()
        
        # Find or create location
        location = None
        for loc in generator.locations:
            if loc["location_id"] == location_id:
                location = loc
                break
        
        if location is None:
            location = {
                "location_id": location_id,
                "location_type": "downtown_parking",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "capacity": 500
            }
        
        contextual_data = generator.generate_contextual_data(
            location, prediction_time, context_hours
        )
        
        # Mark as synthetic
        contextual_data.event_calendar.last_updated = datetime.utcnow()
        contextual_data.weather.last_updated = datetime.utcnow()
        
        freshness = self.validate_data_freshness(contextual_data)
        
        return contextual_data, freshness
    
    def clear_cache(self) -> None:
        """Clear all caches."""
        self.event_client.clear_cache()
        self.weather_client.clear_cache()
        self.historical_client.clear_cache()
        self._context_cache.clear()
        logger.info("All data collector caches cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for all sources."""
        return {
            "context_cache": {
                "size": len(self._context_cache),
                "ttl_seconds": self._cache_ttl
            },
            "event_client": self.event_client._get_cache_stats(),
            "weather_client": self.weather_client._get_cache_stats(),
            "historical_client": self.historical_client.get_cache_stats()
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collector metrics."""
        metrics = self._metrics.copy()
        metrics["cache_hit_rate"] = (
            metrics["cache_hits"] / metrics["total_requests"]
            if metrics["total_requests"] > 0 else 0.0
        )
        metrics["avg_duration_ms"] = (
            metrics["total_duration_ms"] / metrics["total_requests"]
            if metrics["total_requests"] > 0 else 0.0
        )
        return metrics
    
    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._metrics = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "partial_failures": 0,
            "total_failures": 0,
            "total_duration_ms": 0.0
        }


async def create_data_collector() -> DataCollector:
    """
    Factory function to create a DataCollector with proper configuration.
    
    Returns:
        Configured DataCollector instance
    """
    return DataCollector()


# Example usage
if __name__ == "__main__":
    import json
    
    async def main():
        collector = await create_data_collector()
        
        # Test with synthetic data
        prediction_time = datetime.utcnow()
        
        print("Fetching contextual data...")
        data, freshness = await collector.fetch_with_fallback(
            location_id="downtown_parking_0001",
            prediction_time=prediction_time,
            context_hours=24
        )
        
        print(f"Events: {len(data.event_calendar.events)}")
        print(f"Weather: {data.weather.current_conditions.weather_type if data.weather.current_conditions else 'N/A'}")
        print(f"Historical records: {len(data.historical_availability.records)}")
        print(f"Data timestamp: {data.timestamp}")
        print(f"\nFreshness status: {freshness.to_dict()}")
        print(f"\nMetrics: {collector.get_metrics()}")
        
        await collector.close()
    
    asyncio.run(main())