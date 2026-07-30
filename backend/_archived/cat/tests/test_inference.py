"""
Unit tests for the CAT inference service.
Tests API endpoints, caching, rate limiting, and prediction flow.
"""

import pytest
import torch
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from backend.cat.inference.service import (
    app, PredictionCache, RateLimiter, create_inference_service
)
from backend.cat.models.schemas import (
    AvailabilityPrediction, LocationInfo, HealthStatus
)
from backend.cat.config import settings


class TestPredictionCache:
    """Tests for PredictionCache class."""
    
    def test_cache_key_generation(self):
        """Test that cache keys are generated correctly."""
        cache = PredictionCache()
        
        prediction_time = datetime(2024, 6, 15, 18, 0, 0)
        cache_key = cache._get_cache_key("test_location", prediction_time)
        
        assert "test_location" in cache_key
        assert "2024-06-15" in cache_key
        assert cache_key.startswith(settings.redis_cache_prefix)
    
    def test_local_cache_set_and_get(self):
        """Test local cache set and get operations."""
        cache = PredictionCache(redis_url=None)  # Force local cache
        
        prediction = AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="test_loc",
            prediction_time=datetime.utcnow().isoformat(),
            model_version="1.0.0"
        )
        
        prediction_time = datetime(2024, 6, 15, 18, 0, 0)
        
        # Set and get
        cache.set("test_loc", prediction_time, prediction)
        retrieved = cache.get("test_loc", prediction_time)
        
        assert retrieved is not None
        assert retrieved.probability == 0.75
        assert retrieved.location_id == "test_loc"
    
    def test_cache_miss_returns_none(self):
        """Test that cache miss returns None."""
        cache = PredictionCache(redis_url=None)
        
        prediction_time = datetime(2024, 6, 15, 18, 0, 0)
        result = cache.get("nonexistent_location", prediction_time)
        
        assert result is None
    
    def test_cache_invalidation(self):
        """Test cache invalidation."""
        cache = PredictionCache(redis_url=None)
        
        # Add some cached predictions
        prediction = AvailabilityPrediction(
            probability=0.5,
            confidence_interval=(0.3, 0.7),
            contributing_factors=[],
            location_id="loc1",
            prediction_time=datetime.utcnow().isoformat(),
            model_version="1.0.0"
        )
        
        cache.set("loc1", datetime(2024, 6, 15, 18, 0, 0), prediction)
        cache.set("loc2", datetime(2024, 6, 15, 18, 0, 0), prediction)
        
        # Invalidate specific location
        cache.invalidate("loc1")
        
        assert cache.get("loc1", datetime(2024, 6, 15, 18, 0, 0)) is None
        # loc2 should still be cached
        assert cache.get("loc2", datetime(2024, 6, 15, 18, 0, 0)) is not None
    
    def test_cache_clear(self):
        """Test clearing all cached predictions."""
        cache = PredictionCache(redis_url=None)
        
        prediction = AvailabilityPrediction(
            probability=0.5,
            confidence_interval=(0.3, 0.7),
            contributing_factors=[],
            location_id="test_loc",
            prediction_time=datetime.utcnow().isoformat(),
            model_version="1.0.0"
        )
        
        cache.set("loc1", datetime(2024, 6, 15, 18, 0, 0), prediction)
        cache.set("loc2", datetime(2024, 6, 15, 18, 0, 0), prediction)
        
        cache.clear()
        
        assert cache.get_stats()["local_cache_size"] == 0
    
    def test_get_stats(self):
        """Test getting cache statistics."""
        cache = PredictionCache(redis_url=None)
        
        stats = cache.get_stats()
        
        assert "local_cache_size" in stats
        assert "ttl_seconds" in stats
        assert stats["ttl_seconds"] == settings.prediction_cache_ttl_seconds


class TestRateLimiter:
    """Tests for RateLimiter class."""
    
    def test_rate_limiter_allows_requests_under_limit(self):
        """Test that requests under the limit are allowed."""
        limiter = RateLimiter(requests_per_minute=10)
        
        for i in range(10):
            is_allowed, remaining = limiter.is_allowed("test_client")
            assert is_allowed is True
            assert remaining == 10 - i - 1
    
    def test_rate_limiter_blocks_requests_over_limit(self):
        """Test that requests over the limit are blocked."""
        limiter = RateLimiter(requests_per_minute=5)
        
        # Use all allowed requests
        for i in range(5):
            limiter.is_allowed("test_client")
        
        # Next request should be blocked
        is_allowed, remaining = limiter.is_allowed("test_client")
        assert is_allowed is False
        assert remaining == 0
    
    def test_rate_limiter_different_clients(self):
        """Test that different clients have separate limits."""
        limiter = RateLimiter(requests_per_minute=2)
        
        # Client 1 uses limit
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        
        # Client 2 should still be allowed
        is_allowed, _ = limiter.is_allowed("client2")
        assert is_allowed is True
    
    def test_get_remaining(self):
        """Test getting remaining requests."""
        limiter = RateLimiter(requests_per_minute=10)
        
        remaining = limiter.get_remaining("test_client")
        assert remaining == 10
        
        limiter.is_allowed("test_client")
        remaining = limiter.get_remaining("test_client")
        assert remaining == 9


class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_health_check_returns_200(self, client):
        """Test that health check endpoint returns 200."""
        with patch('backend.cat.inference.service.get_model') as mock_model:
            mock_model.return_value = None
            
            response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "model_loaded" in data
        assert "uptime_seconds" in data
    
    def test_readiness_check_when_not_ready(self, client):
        """Test readiness check when model is not loaded."""
        with patch('backend.cat.inference.service.get_model') as mock_model:
            mock_model.return_value = None
            
            response = client.get("/ready")
        
        assert response.status_code == 503
    
    def test_readiness_check_when_ready(self, client):
        """Test readiness check when model is loaded."""
        mock_model = Mock()
        mock_model.transformer = Mock()
        
        with patch('backend.cat.inference.service.get_model', return_value=mock_model):
            response = client.get("/ready")
        
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


class TestPredictionEndpoints:
    """Tests for prediction endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_prediction(self):
        """Create a mock prediction."""
        return AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="test_loc",
            prediction_time=datetime.utcnow().isoformat(),
            model_version="1.0.0"
        )
    
    @pytest.fixture
    def mock_contextual_data(self):
        """Create properly structured mock contextual data."""
        from backend.cat.models.schemas import (
            ContextualData, HistoricalAvailabilityData, AvailabilityRecord,
            EventCalendarData, WeatherData, ContextualFactors, Season
        )
        
        record = AvailabilityRecord(
            timestamp=datetime(2024, 6, 15, 17, 0, 0),
            available_slots=150,
            total_slots=500,
            utilization_rate=0.7,
            contextual_factors=ContextualFactors(
                event_count=2,
                weather_severity=3,
                is_holiday=False,
                is_weekend=True,
                season=Season.SUMMER
            )
        )
        
        historical = HistoricalAvailabilityData(
            records=[record],
            location_id="test_loc"
        )
        
        return ContextualData(
            location_id="test_loc",
            event_calendar=EventCalendarData(events=[], last_updated=datetime.utcnow()),
            weather=WeatherData(current=Mock(), forecast=[]),
            historical_availability=historical
        )
    
    def test_predict_endpoint_returns_prediction(self, client, mock_prediction, mock_contextual_data):
        """Test that predict endpoint returns a valid prediction."""
        with patch('backend.cat.inference.service.get_model') as mock_model, \
             patch('backend.cat.inference.service.get_collector') as mock_collector, \
             patch('backend.cat.inference.service.get_preprocessor') as mock_preprocessor, \
             patch('backend.cat.inference.service.get_cache') as mock_cache:
            
            # Setup mocks
            mock_model_instance = Mock()
            mock_model_instance.transformer = Mock()
            mock_model.return_value = mock_model_instance
            
            mock_collector_instance = AsyncMock()
            mock_collector_instance.fetch_contextual_data = AsyncMock(return_value=mock_contextual_data)
            mock_collector.return_value = mock_collector_instance
            
            mock_preprocessor_instance = Mock()
            mock_preprocessor_instance.preprocess = Mock(return_value=(
                torch.randn(64),
                torch.randn(32),
                torch.randn(24, 64),
                torch.randn(64)
            ))
            mock_preprocessor_instance.create_model_input = Mock(return_value=torch.randn(256))
            mock_preprocessor.return_value = mock_preprocessor_instance
            
            mock_cache_instance = Mock()
            mock_cache_instance.get = Mock(return_value=None)
            mock_cache_instance.set = Mock()
            mock_cache.return_value = mock_cache_instance
            
            # Mock model output
            mock_output = {
                "probability": torch.tensor(0.75),
                "confidence_lower": torch.tensor(0.65),
                "confidence_upper": torch.tensor(0.85),
                "contributing_factors": []
            }
            mock_model_instance.return_value = mock_output
            
            response = client.post(
                "/predict",
                json={
                    "location_id": "test_loc",
                    "prediction_time": "2024-06-15T18:00:00",
                    "context_hours": 24
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "probability" in data
        assert "confidence_interval" in data
        assert "location_id" in data
    
    def test_batch_predict_endpoint(self, client, mock_prediction, mock_contextual_data):
        """Test batch prediction endpoint."""
        with patch('backend.cat.inference.service.get_model') as mock_model, \
             patch('backend.cat.inference.service.get_collector') as mock_collector, \
             patch('backend.cat.inference.service.get_preprocessor') as mock_preprocessor, \
             patch('backend.cat.inference.service.get_cache') as mock_cache:
            
            mock_model_instance = Mock()
            mock_model_instance.transformer = Mock()
            mock_model.return_value = mock_model_instance
            
            mock_collector_instance = AsyncMock()
            mock_collector_instance.fetch_contextual_data = AsyncMock(return_value=mock_contextual_data)
            mock_collector.return_value = mock_collector_instance
            
            mock_preprocessor_instance = Mock()
            mock_preprocessor_instance.preprocess = Mock(return_value=(
                torch.randn(64),
                torch.randn(32),
                torch.randn(24, 64),
                torch.randn(64)
            ))
            mock_preprocessor_instance.create_model_input = Mock(return_value=torch.randn(256))
            mock_preprocessor.return_value = mock_preprocessor_instance
            
            mock_cache_instance = Mock()
            mock_cache_instance.get = Mock(return_value=None)
            mock_cache_instance.set = Mock()
            mock_cache.return_value = mock_cache_instance
            
            mock_output = {
                "probability": torch.tensor(0.75),
                "confidence_lower": torch.tensor(0.65),
                "confidence_upper": torch.tensor(0.85),
                "contributing_factors": []
            }
            mock_model_instance.return_value = mock_output
            
            response = client.post(
                "/predict/batch",
                json={
                    "predictions": [
                        {
                            "location_id": "loc1",
                            "prediction_time": "2024-06-15T18:00:00",
                            "context_hours": 24
                        },
                        {
                            "location_id": "loc2",
                            "prediction_time": "2024-06-15T19:00:00",
                            "context_hours": 24
                        }
                    ]
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert "total_time_ms" in data
        assert len(data["predictions"]) == 2
    
    def test_locations_endpoint(self, client):
        """Test locations list endpoint."""
        response = client.get("/locations")
        
        assert response.status_code == 200
        data = response.json()
        assert "locations" in data
        assert "total_count" in data
        assert data["total_count"] > 0
    
    def test_cache_invalidation_endpoint(self, client):
        """Test cache invalidation endpoint."""
        with patch('backend.cat.inference.service.get_cache') as mock_cache:
            mock_cache_instance = Mock()
            mock_cache_instance.invalidate = Mock(return_value=1)
            mock_cache.return_value = mock_cache_instance
            
            response = client.post("/cache/invalidate", params={"location_id": "test_loc"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        mock_cache_instance.invalidate.assert_called_once_with("test_loc")
    
    def test_metrics_endpoint(self, client):
        """Test metrics endpoint."""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        # Metrics endpoint now returns Prometheus format
        assert "# HELP" in response.text
        assert "# TYPE" in response.text
        assert "cat_requests_total" in response.text


class TestAPIKeyAuthentication:
    """Tests for API key authentication."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_invalid_api_key_returns_401(self, client):
        """Test that invalid API key returns 401."""
        with patch('backend.cat.inference.service.get_model') as mock_model, \
             patch('backend.cat.inference.service.get_collector') as mock_collector, \
             patch('backend.cat.inference.service.get_preprocessor') as mock_preprocessor, \
             patch('backend.cat.inference.service.get_cache') as mock_cache:
            
            # Set a valid API key in settings
            original_key = settings.api_key
            settings.api_key = "valid_key"
            
            try:
                response = client.post(
                    "/predict",
                    json={
                        "location_id": "test_loc",
                        "prediction_time": "2024-06-15T18:00:00"
                    },
                    headers={"X-API-Key": "invalid_key"}
                )
                
                assert response.status_code == 401
            finally:
                settings.api_key = original_key
    
    def test_no_api_key_when_required(self, client):
        """Test request without API key when required."""
        with patch('backend.cat.inference.service.get_model') as mock_model, \
             patch('backend.cat.inference.service.get_collector') as mock_collector, \
             patch('backend.cat.inference.service.get_preprocessor') as mock_preprocessor, \
             patch('backend.cat.inference.service.get_cache') as mock_cache:
            
            original_key = settings.api_key
            settings.api_key = "valid_key"
            
            try:
                response = client.post(
                    "/predict",
                    json={
                        "location_id": "test_loc",
                        "prediction_time": "2024-06-15T18:00:00"
                    }
                )
                
                assert response.status_code == 401
            finally:
                settings.api_key = original_key
    
    def test_no_api_key_when_not_required(self, client):
        """Test request without API key when authentication is disabled."""
        from backend.cat.models.schemas import (
            ContextualData, HistoricalAvailabilityData, AvailabilityRecord,
            EventCalendarData, WeatherData, ContextualFactors, Season
        )
        
        record = AvailabilityRecord(
            timestamp=datetime(2024, 6, 15, 17, 0, 0),
            available_slots=150,
            total_slots=500,
            utilization_rate=0.7,
            contextual_factors=ContextualFactors(
                event_count=2,
                weather_severity=3,
                is_holiday=False,
                is_weekend=True,
                season=Season.SUMMER
            )
        )
        
        historical = HistoricalAvailabilityData(
            records=[record],
            location_id="test_loc"
        )
        
        mock_contextual_data = ContextualData(
            location_id="test_loc",
            event_calendar=EventCalendarData(events=[], last_updated=datetime.utcnow()),
            weather=WeatherData(current=Mock(), forecast=[]),
            historical_availability=historical
        )
        
        with patch('backend.cat.inference.service.get_model') as mock_model, \
             patch('backend.cat.inference.service.get_collector') as mock_collector, \
             patch('backend.cat.inference.service.get_preprocessor') as mock_preprocessor, \
             patch('backend.cat.inference.service.get_cache') as mock_cache:
            
            original_key = settings.api_key
            settings.api_key = None  # Disable authentication
            
            try:
                mock_model_instance = Mock()
                mock_model_instance.transformer = Mock()
                mock_model.return_value = mock_model_instance
                
                mock_collector_instance = AsyncMock()
                mock_collector_instance.fetch_contextual_data = AsyncMock(return_value=mock_contextual_data)
                mock_collector.return_value = mock_collector_instance
                
                mock_preprocessor_instance = Mock()
                mock_preprocessor_instance.preprocess = Mock(return_value=(
                    torch.randn(64),
                    torch.randn(32),
                    torch.randn(24, 64),
                    torch.randn(64)
                ))
                mock_preprocessor_instance.create_model_input = Mock(return_value=torch.randn(256))
                mock_preprocessor.return_value = mock_preprocessor_instance
                
                mock_cache_instance = Mock()
                mock_cache_instance.get = Mock(return_value=None)
                mock_cache_instance.set = Mock()
                mock_cache.return_value = mock_cache_instance
                
                mock_output = {
                    "probability": torch.tensor(0.75),
                    "confidence_lower": torch.tensor(0.65),
                    "confidence_upper": torch.tensor(0.85),
                    "contributing_factors": []
                }
                mock_model_instance.return_value = mock_output
                
                response = client.post(
                    "/predict",
                    json={
                        "location_id": "test_loc",
                        "prediction_time": "2024-06-15T18:00:00"
                    }
                )
                
                # Should not return 401 when auth is disabled
                assert response.status_code != 401
            finally:
                settings.api_key = original_key


class TestRateLimiting:
    """Tests for rate limiting functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_rate_limit_exceeded(self, client):
        """Test that rate limit exceeded returns 429."""
        with patch('backend.cat.inference.service.get_model') as mock_model, \
             patch('backend.cat.inference.service.get_collector') as mock_collector, \
             patch('backend.cat.inference.service.get_preprocessor') as mock_preprocessor, \
             patch('backend.cat.inference.service.get_cache') as mock_cache, \
             patch('backend.cat.inference.service.get_rate_limiter') as mock_limiter:
            
            mock_model_instance = Mock()
            mock_model_instance.transformer = Mock()
            mock_model.return_value = mock_model_instance
            
            mock_collector_instance = AsyncMock()
            mock_collector_instance.fetch_contextual_data = AsyncMock(return_value=Mock())
            mock_collector.return_value = mock_collector_instance
            
            mock_preprocessor_instance = Mock()
            mock_preprocessor_instance.preprocess = Mock(return_value=(
                torch.randn(64),
                torch.randn(32),
                torch.randn(24, 64),
                torch.randn(64)
            ))
            mock_preprocessor_instance.create_model_input = Mock(return_value=torch.randn(256))
            mock_preprocessor.return_value = mock_preprocessor_instance
            
            mock_cache_instance = Mock()
            mock_cache_instance.get = Mock(return_value=None)
            mock_cache_instance.set = Mock()
            mock_cache.return_value = mock_cache_instance
            
            # Mock rate limiter to block
            mock_limiter_instance = Mock()
            mock_limiter_instance.is_allowed = Mock(return_value=(False, 0))
            mock_limiter.return_value = mock_limiter_instance
            
            response = client.post(
                "/predict",
                json={
                    "location_id": "test_loc",
                    "prediction_time": "2024-06-15T18:00:00"
                }
            )
        
        assert response.status_code == 429
        data = response.json()
        assert "Rate limit exceeded" in data["detail"]


class TestCreateInferenceService:
    """Tests for the inference service factory function."""
    
    def test_create_inference_service(self):
        """Test that factory function creates a FastAPI app."""
        service = create_inference_service()
        
        assert service is not None
        assert service.title == "Contextual Availability Transformer API"
        assert service.version == "1.0.0"
    
    def test_service_has_required_endpoints(self):
        """Test that service has all required endpoints."""
        service = create_inference_service()
        
        routes = [route.path for route in service.routes]
        
        assert "/health" in routes
        assert "/ready" in routes
        assert "/predict" in routes
        assert "/predict/batch" in routes
        assert "/locations" in routes
        assert "/cache/invalidate" in routes
        assert "/metrics" in routes