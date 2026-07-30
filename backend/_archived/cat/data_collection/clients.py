"""
API clients for the Contextual Availability Transformer (CAT) system.
Implements resilient HTTP clients for external APIs with rate limiting,
exponential backoff, and caching.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, TypeVar, Generic, Type
from functools import lru_cache

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
)

from ..models.schemas import (
    EventCalendarData, WeatherData, HistoricalAvailabilityData,
    CalendarEvent, Location, WeatherConditions, WeatherForecast,
    ContextualFactors, AvailabilityRecord, EventType, WeatherType, Season
)
from ..config import settings


logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheEntry:
    """Simple cache entry with TTL tracking."""
    
    def __init__(self, value: Any, ttl_seconds: int = None):
        self.value = value
        self.created_at = datetime.utcnow()
        self.ttl_seconds = ttl_seconds or settings.prediction_cache_ttl_seconds
    
    def is_valid(self) -> bool:
        """Check if the cache entry is still valid."""
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age < self.ttl_seconds


class RateLimiter:
    """Token bucket rate limiter for API calls."""
    
    def __init__(self, rate_per_second: float = 1.0, burst: int = 5):
        """
        Initialize rate limiter.
        
        Args:
            rate_per_second: Rate at which tokens are added
            burst: Maximum number of tokens (burst capacity)
        """
        self.rate = rate_per_second
        self.burst = burst
        self.tokens = burst
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """
        Acquire a token from the bucket.
        
        Returns:
            True if token acquired, False if rate limited
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            
            # Add tokens based on elapsed time
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False
    
    async def wait_for_token(self, timeout: float = 30.0) -> bool:
        """
        Wait until a token is available.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if token acquired, False if timed out
        """
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if await self.acquire():
                return True
            await asyncio.sleep(0.1)
        return False


class BaseAPIClient(ABC):
    """Base class for API clients with common functionality."""
    
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = None,
        max_retries: int = None,
        rate_limit_per_second: float = 1.0,
        cache_ttl_seconds: int = None
    ):
        """
        Initialize base API client.
        
        Args:
            api_url: Base URL for the API
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            rate_limit_per_second: Rate limit for API calls
            cache_ttl_seconds: Cache TTL in seconds
        """
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout or 30
        self.max_retries = max_retries or 3
        self.cache_ttl = cache_ttl_seconds or settings.prediction_cache_ttl_seconds
        
        # Rate limiter
        self.rate_limiter = RateLimiter(rate_per_second=rate_limit_per_second, burst=5)
        
        # Cache
        self._cache: Dict[str, CacheEntry] = {}
        
        # HTTP client (initialized lazily)
        self._http_client: Optional[httpx.AsyncClient] = None
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return ":".join(key_parts)
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get value from cache if valid."""
        if key in self._cache:
            entry = self._cache[key]
            if entry.is_valid():
                return entry.value
            del self._cache[key]
        return None
    
    def _set_cached(self, key: str, value: Any) -> None:
        """Set value in cache."""
        self._cache[key] = CacheEntry(value, self.cache_ttl)
    
    def _get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        valid_count = sum(1 for e in self._cache.values() if e.is_valid())
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_count,
            "ttl_seconds": self.cache_ttl
        }
    
    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        logger.info(f"{self.__class__.__name__} cache cleared")
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
    
    @abstractmethod
    async def fetch_data(self, *args, **kwargs) -> T:
        """Fetch data from the API. Must be implemented by subclasses."""
        pass
    
    async def _make_request(
        self,
        method: str,
        url: str,
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        data: Any = None
    ) -> httpx.Response:
        """
        Make an HTTP request with rate limiting and retries.
        
        Args:
            method: HTTP method
            url: Request URL
            params: Query parameters
            headers: Request headers
            data: Request body
            
        Returns:
            HTTP response
            
        Raises:
            httpx.HTTPError: If request fails after retries
        """
        # Wait for rate limit
        if not await self.rate_limiter.wait_for_token(timeout=30.0):
            raise httpx.ConnectError("Rate limit timeout")
        
        client = await self._get_http_client()
        
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(
                multiplier=1.0,
                min=1.0,
                max=10.0,
                jitter=1.0
            ),
            retry=retry_if_exception_type((
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.NetworkError
            )),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO)
        )
        async def _do_request():
            return await client.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                json=data if method in ["POST", "PUT", "PATCH"] else None
            )
        
        return await _do_request()


class EventCalendarClient(BaseAPIClient):
    """
    Client for fetching event calendar data.
    
    Implements HTTP client for Event Calendar API with authentication,
    rate limiting, exponential backoff, and caching.
    """
    
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = None,
        max_retries: int = None,
        use_synthetic_fallback: bool = True,
        cache_ttl_seconds: int = None
    ):
        """
        Initialize the event calendar client.
        
        Args:
            api_url: URL of the event calendar API
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            use_synthetic_fallback: Whether to use synthetic data when API fails
            cache_ttl_seconds: Cache TTL in seconds
        """
        super().__init__(
            api_url=api_url or settings.event_api_url,
            api_key=api_key or settings.event_api_key,
            timeout=timeout,
            max_retries=max_retries,
            rate_limit_per_second=2.0,  # 2 requests per second
            cache_ttl_seconds=cache_ttl_seconds
        )
        self.use_synthetic_fallback = use_synthetic_fallback
        self._synthetic_generator = None
    
    async def fetch_events(
        self,
        location_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> EventCalendarData:
        """
        Fetch event calendar data for a location and time range.
        
        Args:
            location_id: Location identifier
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            EventCalendarData with events in the time range
        """
        # Check cache
        cache_key = self._get_cache_key(
            "events", location_id, start_time.isoformat(), end_time.isoformat()
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for events: {location_id}")
            return cached
        
        # Use synthetic data if no API configured
        if not self.api_url:
            if self.use_synthetic_fallback:
                result = self._generate_synthetic_events(location_id, start_time, end_time)
                self._set_cached(cache_key, result)
                return result
            else:
                return EventCalendarData(events=[], last_updated=datetime.utcnow())
        
        try:
            result = await self._fetch_events_from_api(location_id, start_time, end_time)
            self._set_cached(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            if self.use_synthetic_fallback:
                logger.info("Using synthetic data fallback for events")
                result = self._generate_synthetic_events(location_id, start_time, end_time)
                self._set_cached(cache_key, result)
                return result
            else:
                return EventCalendarData(events=[], last_updated=datetime.utcnow())
    
    async def _fetch_events_from_api(
        self,
        location_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> EventCalendarData:
        """Fetch events from the API."""
        params = {
            "location_id": location_id,
            "start": start_time.isoformat(),
            "end": end_time.isoformat()
        }
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["Content-Type"] = "application/json"
        
        response = await self._make_request(
            method="GET",
            url=self.api_url,
            params=params,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            return self._parse_event_response(data)
        elif response.status_code == 404:
            # No events found
            return EventCalendarData(events=[], last_updated=datetime.utcnow())
        else:
            response.raise_for_status()
            return EventCalendarData(events=[], last_updated=datetime.utcnow())
    
    def _parse_event_response(self, data: Dict[str, Any]) -> EventCalendarData:
        """Parse API response into EventCalendarData."""
        events = []
        
        for event_data in data.get("events", []):
            try:
                event = CalendarEvent(
                    event_id=event_data.get("id"),
                    title=event_data.get("title", "Unknown Event"),
                    event_type=EventType(event_data.get("type", "other")),
                    expected_attendance=event_data.get("expected_attendance", 0),
                    location=Location(
                        venue_id=event_data.get("location", {}).get("id", "unknown"),
                        latitude=event_data.get("location", {}).get("lat", 0.0),
                        longitude=event_data.get("location", {}).get("lng", 0.0),
                        capacity=event_data.get("location", {}).get("capacity", 100)
                    ),
                    start_time=datetime.fromisoformat(event_data.get("start_time")),
                    end_time=datetime.fromisoformat(event_data.get("end_time")),
                    is_outdoor=event_data.get("is_outdoor", False)
                )
                events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event: {e}")
                continue
        
        return EventCalendarData(
            events=events,
            last_updated=datetime.utcnow()
        )
    
    def _generate_synthetic_events(
        self,
        location_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> EventCalendarData:
        """Generate synthetic events for testing."""
        from .synthetic_data import SyntheticDataGenerator
        
        if self._synthetic_generator is None:
            self._synthetic_generator = SyntheticDataGenerator()
        
        # Find the location
        location = None
        for loc in self._synthetic_generator.locations:
            if loc["location_id"] == location_id:
                location = loc
                break
        
        if location is None:
            # Create a default location
            location = {
                "location_id": location_id,
                "location_type": "downtown_parking",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "capacity": 500
            }
        
        # Generate events
        events = self._synthetic_generator._generate_events_for_location(
            location, start_time, end_time
        )
        
        return EventCalendarData(events=events, last_updated=datetime.utcnow())
    
    async def fetch_data(
        self,
        location_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> EventCalendarData:
        """Alias for fetch_events for compatibility with base class."""
        return await self.fetch_events(location_id, start_time, end_time)


class WeatherClient(BaseAPIClient):
    """
    Client for fetching weather data.
    
    Implements HTTP client for Weather API with authentication,
    rate limiting, exponential backoff, and caching.
    """
    
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = None,
        max_retries: int = None,
        use_synthetic_fallback: bool = True,
        cache_ttl_seconds: int = None
    ):
        """
        Initialize the weather client.
        
        Args:
            api_url: URL of the weather API
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            use_synthetic_fallback: Whether to use synthetic data when API fails
            cache_ttl_seconds: Cache TTL in seconds
        """
        super().__init__(
            api_url=api_url or settings.weather_api_url,
            api_key=api_key or settings.weather_api_key,
            timeout=timeout or settings.weather_api_timeout_seconds,
            max_retries=max_retries,
            rate_limit_per_second=2.0,  # 2 requests per second
            cache_ttl_seconds=cache_ttl_seconds
        )
        self.use_synthetic_fallback = use_synthetic_fallback
        self._synthetic_generator = None
    
    async def fetch_weather(
        self,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime
    ) -> WeatherData:
        """
        Fetch weather data for a location and time range.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            WeatherData with current conditions and forecast
        """
        # Check cache
        cache_key = self._get_cache_key(
            "weather", latitude, longitude, start_time.isoformat(), end_time.isoformat()
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for weather: {latitude}, {longitude}")
            return cached
        
        # Use synthetic data if no API configured
        if not self.api_url:
            if self.use_synthetic_fallback:
                result = self._generate_synthetic_weather(latitude, longitude, start_time)
                self._set_cached(cache_key, result)
                return result
            else:
                return WeatherData(current_conditions=None, forecast=[], last_updated=datetime.utcnow())
        
        try:
            result = await self._fetch_weather_from_api(latitude, longitude, start_time, end_time)
            self._set_cached(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Failed to fetch weather: {e}")
            if self.use_synthetic_fallback:
                logger.info("Using synthetic data fallback for weather")
                result = self._generate_synthetic_weather(latitude, longitude, start_time)
                self._set_cached(cache_key, result)
                return result
            else:
                return WeatherData(current_conditions=None, forecast=[], last_updated=datetime.utcnow())
    
    async def _fetch_weather_from_api(
        self,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime
    ) -> WeatherData:
        """Fetch weather from the API."""
        params = {
            "lat": latitude,
            "lon": longitude,
            "start": start_time.isoformat(),
            "end": end_time.isoformat()
        }
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["Content-Type"] = "application/json"
        
        response = await self._make_request(
            method="GET",
            url=self.api_url,
            params=params,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            return self._parse_weather_response(data)
        else:
            response.raise_for_status()
            return WeatherData(current_conditions=None, forecast=[], last_updated=datetime.utcnow())
    
    def _parse_weather_response(self, data: Dict[str, Any]) -> WeatherData:
        """Parse API response into WeatherData."""
        current = None
        if "current" in data:
            current_data = data["current"]
            current = WeatherConditions(
                temperature=current_data.get("temperature", 20.0),
                humidity=current_data.get("humidity", 50.0),
                precipitation_probability=current_data.get("precipitation_probability", 0.0),
                wind_speed=current_data.get("wind_speed", 0.0),
                weather_type=WeatherType(current_data.get("weather_type", "clear"))
            )
        
        forecast = []
        for forecast_data in data.get("forecast", []):
            try:
                forecast.append(WeatherForecast(
                    time=datetime.fromisoformat(forecast_data.get("time")),
                    temperature_high=forecast_data.get("temperature_high", 20.0),
                    temperature_low=forecast_data.get("temperature_low", 15.0),
                    precipitation_probability=forecast_data.get("precipitation_probability", 0.0),
                    weather_type=WeatherType(forecast_data.get("weather_type", "clear"))
                ))
            except Exception as e:
                logger.warning(f"Failed to parse forecast: {e}")
                continue
        
        return WeatherData(
            current_conditions=current,
            forecast=forecast,
            last_updated=datetime.utcnow()
        )
    
    def _generate_synthetic_weather(
        self,
        latitude: float,
        longitude: float,
        timestamp: datetime
    ) -> WeatherData:
        """Generate synthetic weather for testing."""
        from .synthetic_data import SyntheticDataGenerator
        
        if self._synthetic_generator is None:
            self._synthetic_generator = SyntheticDataGenerator()
        
        location = {
            "location_id": f"lat_{latitude}_lon_{longitude}",
            "location_type": "downtown_parking",
            "latitude": latitude,
            "longitude": longitude,
            "capacity": 500
        }
        
        return self._synthetic_generator._generate_weather(timestamp, location)
    
    async def fetch_data(
        self,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime
    ) -> WeatherData:
        """Alias for fetch_weather for compatibility with base class."""
        return await self.fetch_weather(latitude, longitude, start_time, end_time)


class HistoricalRecordsClient:
    """
    Client for fetching historical availability records.
    
    Implements database client for historical availability records
    with query capabilities and graceful handling of missing data.
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        table_name: str = None,
        use_synthetic_fallback: bool = True
    ):
        """
        Initialize the historical records client.
        
        Args:
            database_url: Database connection URL
            table_name: Name of the availability records table
            use_synthetic_fallback: Whether to use synthetic data when DB fails
        """
        self.database_url = database_url or settings.database_url
        self.table_name = table_name or settings.historical_records_table
        self.use_synthetic_fallback = use_synthetic_fallback
        
        # Cache for historical data
        self._cache: Dict[str, CacheEntry] = {}
        self._synthetic_generator = None
    
    def _get_cache_key(
        self,
        location_id: str,
        start_time: datetime,
        end_time: datetime,
        interval_minutes: int = 15
    ) -> str:
        """Generate a cache key."""
        return f"historical:{location_id}:{start_time.isoformat()}:{end_time.isoformat()}:{interval_minutes}"
    
    def _get_cached(self, key: str) -> Optional[HistoricalAvailabilityData]:
        """Get value from cache if valid."""
        if key in self._cache:
            entry = self._cache[key]
            if entry.is_valid():
                return entry.value
            del self._cache[key]
        return None
    
    def _set_cached(self, key: str, value: HistoricalAvailabilityData) -> None:
        """Set value in cache."""
        # Use longer TTL for historical data (1 hour)
        self._cache[key] = CacheEntry(value, ttl_seconds=3600)
    
    async def fetch_historical(
        self,
        location_id: str,
        start_time: datetime,
        end_time: datetime,
        interval_minutes: int = 15
    ) -> HistoricalAvailabilityData:
        """
        Fetch historical availability records for a location.
        
        Args:
            location_id: Location identifier
            start_time: Start of time range
            end_time: End of time range
            interval_minutes: Interval between records
            
        Returns:
            HistoricalAvailabilityData with records in the time range
        """
        # Check cache
        cache_key = self._get_cache_key(location_id, start_time, end_time, interval_minutes)
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for historical: {location_id}")
            return cached
        
        # Use synthetic data if no database configured
        if not self.database_url:
            if self.use_synthetic_fallback:
                result = self._generate_synthetic_historical(
                    location_id, start_time, end_time, interval_minutes
                )
                self._set_cached(cache_key, result)
                return result
            else:
                return HistoricalAvailabilityData(
                    records=[],
                    location_id=location_id,
                    time_range_start=start_time,
                    time_range_end=end_time
                )
        
        try:
            result = await self._fetch_historical_from_db(
                location_id, start_time, end_time, interval_minutes
            )
            self._set_cached(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            if self.use_synthetic_fallback:
                logger.info("Using synthetic data fallback for historical")
                result = self._generate_synthetic_historical(
                    location_id, start_time, end_time, interval_minutes
                )
                self._set_cached(cache_key, result)
                return result
            else:
                return HistoricalAvailabilityData(
                    records=[],
                    location_id=location_id,
                    time_range_start=start_time,
                    time_range_end=end_time
                )
    
    async def _fetch_historical_from_db(
        self,
        location_id: str,
        start_time: datetime,
        end_time: datetime,
        interval_minutes: int = 15
    ) -> HistoricalAvailabilityData:
        """
        Fetch historical data from database.
        
        This is a placeholder implementation. In production, this would
        use SQLAlchemy or asyncpg to query the database.
        """
        # Placeholder: In production, implement actual database query
        # Example:
        # async with asyncpg.create_pool(self.database_url) as pool:
        #     records = await pool.fetch("""
        #         SELECT timestamp, available_slots, total_slots, utilization_rate,
        #                event_count, weather_severity, is_holiday, is_weekend, season
        #         FROM availability_records
        #         WHERE location_id = $1 AND timestamp >= $2 AND timestamp <= $3
        #         ORDER BY timestamp
        #     """, location_id, start_time, end_time)
        
        logger.warning(f"Database not configured, using synthetic data for {location_id}")
        
        # Fall back to synthetic generation
        return self._generate_synthetic_historical(
            location_id, start_time, end_time, interval_minutes
        )
    
    def _generate_synthetic_historical(
        self,
        location_id: str,
        start_time: datetime,
        end_time: datetime,
        interval_minutes: int = 15
    ) -> HistoricalAvailabilityData:
        """Generate synthetic historical data for testing."""
        from .synthetic_data import SyntheticDataGenerator
        
        if self._synthetic_generator is None:
            self._synthetic_generator = SyntheticDataGenerator()
        
        # Find or create location
        location = None
        for loc in self._synthetic_generator.locations:
            if loc["location_id"] == location_id:
                location = loc
                break
        
        if location is None:
            location = {
                "location_id": location_id,
                "location_type": "downtown_parking",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "capacity": 500,
                "base_demand": 0.5,
                "event_sensitivity": 1.0,
                "weather_sensitivity": 0.5
            }
        
        return self._synthetic_generator.generate_historical_data(
            location,
            start_date=start_time,
            end_date=end_time,
            interval_minutes=interval_minutes
        )
    
    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        logger.info("Historical records cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        valid_count = sum(1 for e in self._cache.values() if e.is_valid())
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_count
        }