"""
Comprehensive Tests for Resilience-Enhanced Services
Tests circuit breakers, retry logic, caching, and error handling
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from collections import deque

# Import services
import sys
sys.path.insert(0, 'backend')

from services.telegram_service import TelegramService
from services.live_status_service import (
    LiveStatusService, LiveStatusConfig, LiveStatusProvider, LiveStatusResult
)
from services.verification_engine import (
    VerificationService, VerificationConfig, VerificationStatus,
    SeatCheckResult, TrainScheduleCheckResult, FareCheckResult, VerificationDetails
)
from core.resilience.core import circuit_manager, CircuitBreakerState
from core.resilience.retry import RetryPolicy, retry_async


class TestTelegramService:
    """Tests for TelegramService with resilience patterns."""
    
    @pytest.fixture
    def telegram_service(self):
        """Create a TelegramService instance with mocked config."""
        with patch('services.telegram_service.Config') as mock_config:
            mock_config.TELEGRAM_TOKEN = "test_token"
            service = TelegramService()
            service.bot_token = "test_token"
            return service
    
    def test_service_initialization(self, telegram_service):
        """Test service initializes correctly."""
        assert telegram_service.bot_token == "test_token"
        assert telegram_service.base_url == "https://api.telegram.org/bottest_token"
        assert telegram_service._rate_limit_max == 30
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, telegram_service):
        """Test successful message sending."""
        with patch.object(telegram_service, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            mock_get_client.return_value = mock_client
            
            result = await telegram_service.send_message("12345", "Test message")
            
            assert result is True
            mock_client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_no_token(self, telegram_service):
        """Test message sending without token."""
        telegram_service.bot_token = None
        
        result = await telegram_service.send_message("12345", "Test message")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_message_rate_limit(self, telegram_service):
        """Test rate limiting."""
        # Fill up the rate limit
        telegram_service._message_history = [datetime.now() for _ in range(30)]
        
        result = await telegram_service.send_message("12345", "Test message")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_message_with_retry(self, telegram_service):
        """Test retry logic on failure."""
        with patch.object(telegram_service, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.raise_for_status = Mock(side_effect=Exception("Server error"))
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            mock_get_client.return_value = mock_client
            
            result = await telegram_service.send_message("12345", "Test message")
            
            assert result is False
            # Should retry 2 more times (3 total attempts)
            assert mock_client.post.call_count == 3
    
    @pytest.mark.asyncio
    async def test_broadcast_sos_parallel(self, telegram_service):
        """Test parallel SOS broadcasting."""
        with patch.object(telegram_service, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = [True, True, False]
            
            result = await telegram_service.broadcast_sos(
                user_name="John Doe",
                lat=12.34,
                lng=56.78,
                telegram_ids=["123", "456", "789"]
            )
            
            assert result["total"] == 3
            assert result["success"] == 2
            assert result["failed"] == 1
            assert result["all_success"] is False
    
    def test_health_check(self, telegram_service):
        """Test health check returns correct status."""
        health = telegram_service.health_check()
        
        assert health["status"] == "healthy"
        assert health["bot_configured"] is True
        assert "circuit_breaker" in health


class TestLiveStatusService:
    """Tests for LiveStatusService with resilience patterns."""
    
    @pytest.fixture
    def live_status_service(self):
        """Create a LiveStatusService instance."""
        config = LiveStatusConfig(
            provider=LiveStatusProvider.MOCK,
            cache_ttl_seconds=60,
            retry_policy=RetryPolicy(
                max_attempts=2,
                base_delay=0.1,
                max_delay=1.0
            )
        )
        return LiveStatusService(config=config)
    
    def test_service_initialization(self, live_status_service):
        """Test service initializes correctly."""
        assert live_status_service.config.provider == LiveStatusProvider.MOCK
        assert live_status_service.config.cache_ttl_seconds == 60
        assert len(live_status_service._cache) == 0
    
    def test_get_cache_key(self, live_status_service):
        """Test cache key generation."""
        key = live_status_service._get_cache_key("12345", "2024-01-15")
        assert key == "live_status:12345:2024-01-15"
    
    def test_set_and_get_cache(self, live_status_service):
        """Test caching functionality."""
        result = LiveStatusResult(
            train_number="12345",
            status="success",
            source="test",
            data={"status": "ON TIME"}
        )
        
        live_status_service._set_cache_result("12345", "2024-01-15", result)
        
        cached = live_status_service._get_cached_result("12345", "2024-01-15")
        assert cached is not None
        assert cached.status == "success"
        assert cached.cached is True
    
    def test_cache_expiration(self, live_status_service):
        """Test cache expiration."""
        result = LiveStatusResult(
            train_number="12345",
            status="success",
            source="test"
        )
        
        # Set cache with old timestamp
        live_status_service._cache["live_status:12345:2024-01-15"] = (result, datetime.utcnow() - timedelta(hours=1))
        
        cached = live_status_service._get_cached_result("12345", "2024-01-15")
        assert cached is None
    
    @pytest.mark.asyncio
    async def test_get_live_status_with_provider_gateway(self, live_status_service):
        """Test live status fetching via provider gateway."""
        mock_status = Mock()
        mock_status.model_dump = Mock(return_value={
            "train_number": "12345",
            "status": "ON TIME"
        })
        
        with patch('services.live_status_service.provider_gateway') as mock_gateway:
            mock_gateway.get_live_status = AsyncMock(return_value=mock_status)
            
            result = await live_status_service.get_live_status("12345")
            
            assert result is not None
            assert result["status"] == "ON TIME"
            mock_gateway.get_live_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_live_status_batch(self, live_status_service):
        """Test batch live status fetching."""
        mock_status = Mock()
        mock_status.model_dump = Mock(return_value={"status": "ON TIME"})
        
        with patch('services.live_status_service.provider_gateway') as mock_gateway:
            mock_gateway.get_live_status = AsyncMock(return_value=mock_status)
            
            result = await live_status_service.get_live_status_batch(
                ["12345", "67890", "11111"]
            )
            
            assert len(result) == 3
            assert all(r is not None for r in result.values())
    
    def test_get_metrics(self, live_status_service):
        """Test metrics collection."""
        # Add some mock requests
        for i in range(5):
            live_status_service._record_request(LiveStatusResult(
                train_number=f"123{i}",
                status="success" if i < 4 else "error",
                source="test",
                response_time_ms=100
            ))
        
        metrics = live_status_service.get_metrics()
        
        assert metrics["total_requests"] == 5
        assert metrics["successful_requests"] == 4
        assert metrics["success_rate"] == 0.8
        assert "circuit_breaker_state" in metrics
    
    def test_health_check(self, live_status_service):
        """Test health check."""
        health = live_status_service.health_check()
        
        assert health["status"] == "healthy"
        assert health["provider"] == "mock"
        assert "circuit_breaker" in health


class TestVerificationService:
    """Tests for VerificationService with resilience patterns."""
    
    @pytest.fixture
    def verification_service(self):
        """Create a VerificationService instance."""
        config = VerificationConfig(
            cache_ttl_seconds=180,
            timeout_seconds=30.0,
            max_concurrent_checks=3
        )
        return VerificationService(config=config)
    
    def test_service_initialization(self, verification_service):
        """Test service initializes correctly."""
        assert verification_service.config.cache_ttl_seconds == 180
        assert verification_service.config.max_concurrent_checks == 3
        assert verification_service.verification_service is not None
    
    def test_get_cache_key(self, verification_service):
        """Test cache key generation."""
        key = verification_service._get_cache_key("journey123", "2024-01-15")
        assert key == "verification:journey123:2024-01-15"
    
    def test_seat_check_result_to_dict(self):
        """Test SeatCheckResult serialization."""
        result = SeatCheckResult(
            status=VerificationStatus.VERIFIED,
            total_seats=72,
            available_seats=45,
            booked_seats=27,
            message="Seats available",
            response_time_ms=150,
            source="data_provider"
        )
        
        data = result.to_dict()
        
        assert data["status"] == "verified"
        assert data["total_seats"] == 72
        assert data["response_time_ms"] == 150
    
    def test_train_schedule_check_result_to_dict(self):
        """Test TrainScheduleCheckResult serialization."""
        result = TrainScheduleCheckResult(
            status=VerificationStatus.VERIFIED,
            scheduled_departure="08:00",
            scheduled_arrival="12:00",
            delay_minutes=5,
            message="On time",
            response_time_ms=100,
            source="data_provider"
        )
        
        data = result.to_dict()
        
        assert data["status"] == "verified"
        assert data["delay_minutes"] == 5
    
    def test_fare_check_result_to_dict(self):
        """Test FareCheckResult serialization."""
        result = FareCheckResult(
            status=VerificationStatus.VERIFIED,
            base_fare=1000.0,
            GST=180.0,
            total_fare=1180.0,
            applicable_discounts=["SENIOR_CITIZEN"],
            response_time_ms=200,
            source="data_provider"
        )
        
        data = result.to_dict()
        
        assert data["status"] == "verified"
        assert data["total_fare"] == 1180.0
        assert "SENIOR_CITIZEN" in data["applicable_discounts"]
    
    def test_verification_details_to_dict(self):
        """Test VerificationDetails serialization."""
        seat = SeatCheckResult(
            status=VerificationStatus.VERIFIED,
            total_seats=72, available_seats=45, booked_seats=27
        )
        schedule = TrainScheduleCheckResult(
            status=VerificationStatus.VERIFIED,
            scheduled_departure="08:00", scheduled_arrival="12:00"
        )
        fare = FareCheckResult(
            status=VerificationStatus.VERIFIED,
            base_fare=1000.0, GST=180.0, total_fare=1180.0
        )
        
        details = VerificationDetails(
            journey_id="journey123",
            verification_timestamp=datetime.now().isoformat(),
            overall_status=VerificationStatus.VERIFIED,
            seat_verification=seat,
            schedule_verification=schedule,
            fare_verification=fare,
            restrictions=[],
            warnings=["Limited seats"],
            is_bookable=True,
            response_time_ms=500,
            sources={"seat": "data_provider", "schedule": "data_provider", "fare": "data_provider"}
        )
        
        data = details.to_dict()
        
        assert data["journey_id"] == "journey123"
        assert data["overall_status"] == "verified"
        assert data["is_bookable"] is True
        assert "Limited seats" in data["warnings"]
    
    def test_get_metrics(self, verification_service):
        """Test metrics collection."""
        # Add mock verification results
        for i in range(5):
            asyncio.run(verification_service._record_metrics(VerificationDetails(
                journey_id=f"journey{i}",
                verification_timestamp=datetime.now().isoformat(),
                overall_status=VerificationStatus.VERIFIED if i < 4 else VerificationStatus.FAILED,
                seat_verification=SeatCheckResult(
                    status=VerificationStatus.VERIFIED,
                    total_seats=72, available_seats=45, booked_seats=27
                ),
                schedule_verification=TrainScheduleCheckResult(
                    status=VerificationStatus.VERIFIED,
                    scheduled_departure="08:00", scheduled_arrival="12:00"
                ),
                fare_verification=FareCheckResult(
                    status=VerificationStatus.VERIFIED,
                    base_fare=1000.0, GST=180.0, total_fare=1180.0
                ),
                restrictions=[],
                warnings=[],
                is_bookable=i < 4,
                response_time_ms=500
            )))
        
        metrics = verification_service.get_metrics()
        
        assert metrics["total_verifications"] == 5
        assert metrics["successful_verifications"] == 4
        assert metrics["success_rate"] == 0.8
        assert "circuit_breaker_states" in metrics
    
    def test_health_check(self, verification_service):
        """Test health check."""
        health = verification_service.health_check()
        
        assert health["status"] == "healthy"
        assert "config" in health
        assert "circuit_breakers" in health
        assert "metrics" in health


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker patterns."""
    
    def test_circuit_breaker_states(self):
        """Test circuit breaker state transitions."""
        breaker = circuit_manager.get_breaker("test_breaker")
        
        # Initial state should be CLOSED
        assert breaker.get_state() == CircuitBreakerState.CLOSED
    
    def test_multiple_breakers(self):
        """Test multiple named circuit breakers."""
        breaker1 = circuit_manager.get_breaker("service_a")
        breaker2 = circuit_manager.get_breaker("service_b")
        
        assert breaker1 is not None
        assert breaker2 is not None
        assert breaker1 is not breaker2


class TestRetryPolicy:
    """Tests for retry policy configuration."""
    
    def test_default_retry_policy(self):
        """Test default retry policy values."""
        policy = RetryPolicy()
        
        assert policy.max_attempts == 3
        assert policy.base_delay == 1.0
        assert policy.exponential_base == 2.0
    
    def test_custom_retry_policy(self):
        """Test custom retry policy."""
        policy = RetryPolicy(
            max_attempts=5,
            base_delay=0.5,
            max_delay=10.0,
            exponential_base=3.0
        )
        
        assert policy.max_attempts == 5
        assert policy.base_delay == 0.5
        assert policy.max_delay == 10.0
        assert policy.exponential_base == 3.0


class TestVerificationStatus:
    """Tests for VerificationStatus enum."""
    
    def test_status_values(self):
        """Test all verification status values."""
        assert VerificationStatus.VERIFIED.value == "verified"
        assert VerificationStatus.PENDING.value == "pending"
        assert VerificationStatus.FAILED.value == "failed"
        assert VerificationStatus.DELAYED.value == "delayed"
        assert VerificationStatus.CANCELLED.value == "cancelled"
        assert VerificationStatus.UNKNOWN.value == "unknown"
    
    def test_status_string_conversion(self):
        """Test status conversion from string."""
        status = VerificationStatus("verified")
        assert status == VerificationStatus.VERIFIED


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
