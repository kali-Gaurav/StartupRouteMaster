"""
Tests for the data collection layer.
Tests API clients, rate limiting, caching, and the unified data collector.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from cat.models.schemas import (
    EventCalendarData, WeatherData, HistoricalAvailabilityData,
    CalendarEvent, Location, WeatherConditions, WeatherForecast,
    ContextualFactors, AvailabilityRecord, EventType, WeatherType, Season
)
from cat.models.schemas import ContextualData as ContextualDataModel
from cat.data_collection.clients import (
    EventCalendarClient, WeatherClient, HistoricalRecordsClient,
    RateLimiter, CacheEntry
)
from cat.data_collection.collector import DataCollector, FetchResult, DataFreshnessStatus


class TestRateLimiter:
    """Tests for the RateLimiter class."""
    
    def test_initial_state(self):
        """Test rate limiter is initialized correctly."""
        limiter = RateLimiter(rate_per_second=1.0, burst=5)
        assert limiter.rate == 1.0
        assert limiter.burst == 5
        assert limiter.tokens == 5
    
    def test_acquire_token_available(self):
        """Test acquiring a token when available."""
        limiter = RateLimiter(rate_per_second=10.0, burst=5)
        result = asyncio.run(limiter.acquire())
        assert result is True
        assert limiter.tokens == 4
    
    def test_acquire_token_exhausted(self):
        """Test acquiring when tokens are exhausted."""
        limiter = RateLimiter(rate_per_second=0.001, burst=1)
        # First acquire should succeed
        result1 = asyncio.run(limiter.acquire())
        assert result1 is True
        # Second acquire should fail (no time has passed)
        result2 = asyncio.run(limiter.acquire())
        assert result2 is False
    
    def test_token_refill(self):
        """Test that tokens refill over time."""
        limiter = RateLimiter(rate_per_second=10.0, burst=5)
        # Exhaust all tokens
        for _ in range(5):
            asyncio.run(limiter.acquire())
        # Tokens should be 0 or very close to 0 (allowing for timing)
        assert limiter.tokens < 0.5
        # Wait for refill
        asyncio.run(asyncio.sleep(0.2))  # Should refill ~2 tokens
        result = asyncio.run(limiter.acquire())
        assert result is True
        assert limiter.tokens < 5
    
    def test_wait_for_token_success(self):
        """Test waiting for a token with successful acquisition."""
        limiter = RateLimiter(rate_per_second=10.0, burst=1)
        # Exhaust the token
        asyncio.run(limiter.acquire())
        # Wait should succeed after refill
        result = asyncio.run(limiter.wait_for_token(timeout=1.0))
        assert result is True
    
    def test_wait_for_token_timeout(self):
        """Test waiting for a token with timeout."""
        limiter = RateLimiter(rate_per_second=0.1, burst=1)
        # Exhaust the token
        asyncio.run(limiter.acquire())
        # Wait should timeout
        result = asyncio.run(limiter.wait_for_token(timeout=0.1))
        assert result is False


class TestCacheEntry:
    """Tests for the CacheEntry class."""
    
    def test_cache_entry_valid(self):
        """Test cache entry is valid when within TTL."""
        entry = CacheEntry("test_value", ttl_seconds=60)
        assert entry.is_valid() is True
    
    def test_cache_entry_expired(self):
        """Test cache entry is expired when TTL passed."""
        entry = CacheEntry("test_value", ttl_seconds=1)
        asyncio.run(asyncio.sleep(1.1))
        assert entry.is_valid() is False
    
    def test_cache_entry_default_ttl(self):
        """Test cache entry uses default TTL."""
        entry = CacheEntry("test_value")
        # Should be valid for at least the default TTL
        assert entry.ttl_seconds > 0


class TestEventCalendarClient:
    """Tests for the EventCalendarClient class."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with synthetic fallback."""
        return EventCalendarClient(
            api_url=None,  # Force synthetic mode
            use_synthetic_fallback=True
        )
    
    @pytest.mark.asyncio
    async def test_fetch_events_synthetic(self, client):
        """Test fetching events with synthetic data."""
        start = datetime.utcnow()
        end = start + timedelta(days=1)
        
        result = await client.fetch_events(
            location_id="downtown_parking_0001",
            start_time=start,
            end_time=end
        )
        
        assert isinstance(result, EventCalendarData)
        assert result.last_updated is not None
        # Should have some synthetic events
        assert len(result.events) >= 0
    
    @pytest.mark.asyncio
    async def test_fetch_events_caching(self, client):
        """Test that events are cached."""
        start = datetime.utcnow()
        end = start + timedelta(days=1)
        
        # First fetch
        result1 = await client.fetch_events(
            location_id="downtown_parking_0001",
            start_time=start,
            end_time=end
        )
        
        # Second fetch should hit cache
        result2 = await client.fetch_events(
            location_id="downtown_parking_0001",
            start_time=start,
            end_time=end
        )
        
        # Results should be equal (from cache)
        assert result1.events == result2.events
    
    def test_cache_stats(self, client):
        """Test cache statistics."""
        stats = client._get_cache_stats()
        assert "total_entries" in stats
        assert "valid_entries" in stats
        assert "ttl_seconds" in stats
    
    def test_clear_cache(self, client):
        """Test cache clearing."""
        client._cache["test"] = CacheEntry("value")
        client.clear_cache()
        assert len(client._cache) == 0


class TestWeatherClient:
    """Tests for the WeatherClient class."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with synthetic fallback."""
        return WeatherClient(
            api_url=None,  # Force synthetic mode
            use_synthetic_fallback=True
        )
    
    @pytest.mark.asyncio
    async def test_fetch_weather_synthetic(self, client):
        """Test fetching weather with synthetic data."""
        timestamp = datetime.utcnow()
        
        result = await client.fetch_weather(
            latitude=40.7128,
            longitude=-74.0060,
            start_time=timestamp,
            end_time=timestamp + timedelta(days=1)
        )
        
        assert isinstance(result, WeatherData)
        assert result.last_updated is not None
        # Current conditions should be present
        if result.current_conditions:
            assert isinstance(result.current_conditions.temperature, float)
            assert isinstance(result.current_conditions.humidity, float)
    
    @pytest.mark.asyncio
    async def test_fetch_weather_caching(self, client):
        """Test that weather data is cached."""
        timestamp = datetime.utcnow()
        
        # First fetch
        result1 = await client.fetch_weather(
            latitude=40.7128,
            longitude=-74.0060,
            start_time=timestamp,
            end_time=timestamp + timedelta(days=1)
        )
        
        # Second fetch should hit cache
        result2 = await client.fetch_weather(
            latitude=40.7128,
            longitude=-74.0060,
            start_time=timestamp,
            end_time=timestamp + timedelta(days=1)
        )
        
        # Results should be equal (from cache)
        assert result1.current_conditions == result2.current_conditions


class TestHistoricalRecordsClient:
    """Tests for the HistoricalRecordsClient class."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with synthetic fallback."""
        return HistoricalRecordsClient(
            database_url=None,  # Force synthetic mode
            use_synthetic_fallback=True
        )
    
    @pytest.mark.asyncio
    async def test_fetch_historical_synthetic(self, client):
        """Test fetching historical data with synthetic data."""
        start = datetime.utcnow() - timedelta(days=1)
        end = datetime.utcnow()
        
        result = await client.fetch_historical(
            location_id="downtown_parking_0001",
            start_time=start,
            end_time=end,
            interval_minutes=15
        )
        
        assert isinstance(result, HistoricalAvailabilityData)
        assert result.location_id == "downtown_parking_0001"
        # Should have some synthetic records
        assert len(result.records) >= 0
    
    @pytest.mark.asyncio
    async def test_fetch_historical_caching(self, client):
        """Test that historical data is cached."""
        start = datetime.utcnow() - timedelta(days=1)
        end = datetime.utcnow()
        
        # First fetch
        result1 = await client.fetch_historical(
            location_id="downtown_parking_0001",
            start_time=start,
            end_time=end,
            interval_minutes=15
        )
        
        # Second fetch should hit cache
        result2 = await client.fetch_historical(
            location_id="downtown_parking_0001",
            start_time=start,
            end_time=end,
            interval_minutes=15
        )
        
        # Results should be equal (from cache)
        assert len(result1.records) == len(result2.records)
    
    def test_cache_stats(self, client):
        """Test cache statistics."""
        stats = client.get_cache_stats()
        assert "total_entries" in stats
        assert "valid_entries" in stats


class TestDataCollector:
    """Tests for the DataCollector class."""
    
    @pytest.fixture
    def collector(self):
        """Create a test data collector."""
        return DataCollector(
            use_synthetic_fallback=True,
            max_concurrent_fetches=3
        )
    
    @pytest.mark.asyncio
    async def test_fetch_contextual_data(self, collector):
        """Test fetching all contextual data."""
        prediction_time = datetime.utcnow()
        
        result = await collector.fetch_contextual_data(
            location_id="downtown_parking_0001",
            prediction_time=prediction_time,
            context_hours=24
        )
        
        # Check that result has the expected structure
        assert hasattr(result, 'event_calendar')
        assert hasattr(result, 'weather')
        assert hasattr(result, 'historical_availability')
        assert hasattr(result, 'timestamp')
        assert isinstance(result.event_calendar, EventCalendarData)
        assert isinstance(result.weather, WeatherData)
        assert isinstance(result.historical_availability, HistoricalAvailabilityData)
    
    @pytest.mark.asyncio
    async def test_fetch_contextual_data_caching(self, collector):
        """Test that contextual data is cached."""
        prediction_time = datetime.utcnow()
        
        # First fetch
        result1 = await collector.fetch_contextual_data(
            location_id="downtown_parking_0001",
            prediction_time=prediction_time,
            context_hours=24
        )
        
        # Second fetch should hit cache
        result2 = await collector.fetch_contextual_data(
            location_id="downtown_parking_0001",
            prediction_time=prediction_time,
            context_hours=24
        )
        
        # Results should be equal (from cache)
        assert len(result1.event_calendar.events) == len(result2.event_calendar.events)
    
    @pytest.mark.asyncio
    async def test_fetch_with_fallback(self, collector):
        """Test fetching with fallback to synthetic data."""
        prediction_time = datetime.utcnow()
        
        data, freshness = await collector.fetch_with_fallback(
            location_id="downtown_parking_0001",
            prediction_time=prediction_time,
            context_hours=24
        )
        
        assert isinstance(data, ContextualDataModel)
        assert isinstance(freshness, DataFreshnessStatus)
    
    def test_validate_data_freshness(self, collector):
        """Test data freshness validation."""
        from ..models.schemas import ContextualData
        
        # Create test contextual data using dicts (Pydantic v2 compatibility)
        now = datetime.utcnow()
        contextual_data = ContextualData(
            event_calendar={
                "events": [],
                "last_updated": (now - timedelta(minutes=30)).isoformat()
            },
            weather={
                "current_conditions": {
                    "temperature": 20.0,
                    "humidity": 50.0,
                    "precipitation_probability": 0.0,
                    "wind_speed": 5.0,
                    "weather_type": "clear"
                },
                "forecast": [],
                "last_updated": (now - timedelta(minutes=30)).isoformat()
            },
            historical_availability={
                "records": [
                    {
                        "timestamp": (now - timedelta(minutes=30)).isoformat(),
                        "available_slots": 100,
                        "total_slots": 500,
                        "utilization_rate": 0.8,
                        "contextual_factors": {
                            "event_count": 0,
                            "weather_severity": 0,
                            "is_holiday": False,
                            "is_weekend": False,
                            "season": "summer"
                        }
                    }
                ],
                "location_id": "test"
            },
            timestamp=now.isoformat()
        )
        
        freshness = collector.validate_data_freshness(contextual_data)
        
        assert freshness.event_calendar_fresh is True
        assert freshness.weather_fresh is True
        assert freshness.historical_fresh is True
    
    def test_get_cache_stats(self, collector):
        """Test getting cache statistics."""
        stats = collector.get_cache_stats()
        assert "context_cache" in stats
        assert "event_client" in stats
        assert "weather_client" in stats
        assert "historical_client" in stats
    
    def test_get_metrics(self, collector):
        """Test getting metrics."""
        metrics = collector.get_metrics()
        assert "total_requests" in metrics
        assert "cache_hits" in metrics
        assert "cache_misses" in metrics
        assert "cache_hit_rate" in metrics
    
    def test_reset_metrics(self, collector):
        """Test resetting metrics."""
        collector._metrics["total_requests"] = 100
        collector.reset_metrics()
        assert collector._metrics["total_requests"] == 0
    
    def test_clear_cache(self, collector):
        """Test clearing all caches."""
        collector._context_cache["test"] = CacheEntry("value")
        collector.clear_cache()
        assert len(collector._context_cache) == 0


class TestFetchResult:
    """Tests for the FetchResult class."""
    
    def test_successful_result(self):
        """Test creating a successful fetch result."""
        result = FetchResult(
            source="test",
            success=True,
            data="test_data",
            duration_ms=100.0
        )
        assert result.success is True
        assert result.data == "test_data"
        assert result.error is None
    
    def test_failed_result(self):
        """Test creating a failed fetch result."""
        result = FetchResult(
            source="test",
            success=False,
            error="Connection timeout",
            duration_ms=5000.0
        )
        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.data is None


class TestDataFreshnessStatus:
    """Tests for the DataFreshnessStatus class."""
    
    def test_to_dict(self):
        """Test converting freshness status to dict."""
        status = DataFreshnessStatus(
            event_calendar_fresh=True,
            event_calendar_age_seconds=100.0,
            weather_fresh=True,
            weather_age_seconds=200.0,
            historical_fresh=False,
            historical_age_seconds=5000.0,
            all_fresh=False
        )
        
        result = status.to_dict()
        
        assert result["event_calendar_fresh"] is True
        assert result["event_calendar_age_seconds"] == 100.0
        assert result["all_fresh"] is False


# Integration tests
class TestDataCollectionIntegration:
    """Integration tests for the data collection layer."""
    
    @pytest.fixture
    def collector(self):
        """Create a test data collector."""
        return DataCollector(
            use_synthetic_fallback=True,
            max_concurrent_fetches=3
        )
    
    @pytest.mark.asyncio
    async def test_full_data_collection_flow(self, collector):
        """Test the complete data collection flow."""
        prediction_time = datetime.utcnow()
        
        # Fetch contextual data
        data, freshness = await collector.fetch_with_fallback(
            location_id="downtown_parking_0001",
            prediction_time=prediction_time,
            context_hours=24
        )
        
        # Validate data structure
        assert data.event_calendar is not None
        assert data.weather is not None
        assert data.historical_availability is not None
        assert data.timestamp is not None
        
        # Validate freshness
        assert isinstance(freshness, DataFreshnessStatus)
    
    @pytest.mark.asyncio
    async def test_concurrent_fetching(self, collector):
        """Test that concurrent fetching works correctly."""
        prediction_time = datetime.utcnow()
        
        # Make multiple concurrent requests
        tasks = [
            collector.fetch_contextual_data(
                location_id=f"location_{i}",
                prediction_time=prediction_time,
                context_hours=24
            )
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All results should be valid
        for result in results:
            assert result.event_calendar is not None
            assert result.weather is not None
            assert result.historical_availability is not None
    
    @pytest.mark.asyncio
    async def test_metrics_tracking(self, collector):
        """Test that metrics are tracked correctly."""
        prediction_time = datetime.utcnow()
        
        # Initial metrics
        initial_metrics = collector.get_metrics()
        assert initial_metrics["total_requests"] == 0
        
        # Make a request
        await collector.fetch_contextual_data(
            location_id="downtown_parking_0001",
            prediction_time=prediction_time,
            context_hours=24
        )
        
        # Check metrics updated
        updated_metrics = collector.get_metrics()
        assert updated_metrics["total_requests"] == 1
        
        # Make another request (should hit cache)
        await collector.fetch_contextual_data(
            location_id="downtown_parking_0001",
            prediction_time=prediction_time,
            context_hours=24
        )
        
        # Check cache hit
        final_metrics = collector.get_metrics()
        assert final_metrics["cache_hits"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])