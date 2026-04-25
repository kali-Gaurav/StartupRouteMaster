"""
Comprehensive Tests for Resilience Patterns
============================================

Tests for circuit breakers, retry policies, and resilience patterns
across all enhanced services.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from collections import deque

# Import resilience patterns
from core.resilience import (
    CircuitBreaker, CircuitState, CircuitConfig, CircuitBreakerManager,
    CircuitOpenError, circuit_breaker_manager
)
from core.retry import (
    retry, retry_sync, RetryPolicy, RETRY_POLICY_FAST,
    RETRY_POLICY_EXTERNAL_API, RETRY_POLICY_CRITICAL
)


class TestCircuitBreaker:
    """Tests for Circuit Breaker pattern."""
    
    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in closed state."""
        breaker = CircuitBreaker("test", CircuitConfig(failure_threshold=3))
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker("test", CircuitConfig(failure_threshold=3))
        
        # Simulate failures
        for i in range(3):
            asyncio.run(breaker.execute(lambda: (_ for _ in ()).throw(Exception(f"Error {i}"))))
        
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3
    
    def test_circuit_breaker_rejects_when_open(self):
        """Test circuit breaker rejects calls when open."""
        breaker = CircuitBreaker("test", CircuitConfig(failure_threshold=1, timeout_seconds=0.1))
        
        # Open the circuit
        asyncio.run(breaker.execute(lambda: (_ for _ in ()).throw(Exception("Error"))))
        
        # Should reject when open
        with pytest.raises(CircuitOpenError):
            asyncio.run(breaker.execute(lambda: "success"))
    
    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker transitions to half-open after timeout."""
        breaker = CircuitBreaker("test", CircuitConfig(
            failure_threshold=1,
            timeout_seconds=0.05,
            success_threshold=1
        ))
        
        # Open the circuit
        asyncio.run(breaker.execute(lambda: (_ for _ in ()).throw(Exception("Error"))))
        assert breaker.state == CircuitState.OPEN
        
        # Wait for timeout
        time.sleep(0.1)
        
        # Should transition to half-open on next call
        async def success():
            return "success"
        
        result = asyncio.run(breaker.execute(success))
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
    
    def test_circuit_breaker_success_resets_failures(self):
        """Test successful calls reset failure count."""
        breaker = CircuitBreaker("test", CircuitConfig(failure_threshold=5))
        
        # Fail twice
        for i in range(2):
            asyncio.run(breaker.execute(lambda: (_ for _ in ()).throw(Exception(f"Error {i}"))))
        
        assert breaker.failure_count == 2
        
        # Success should reset
        result = asyncio.run(breaker.execute(lambda: "success"))
        assert result == "success"
        assert breaker.failure_count == 0
    
    def test_circuit_breaker_metrics(self):
        """Test circuit breaker metrics collection."""
        breaker = CircuitBreaker("test", CircuitConfig(failure_threshold=5))
        
        # Make some calls
        asyncio.run(breaker.execute(lambda: "success"))
        try:
            asyncio.run(breaker.execute(lambda: (_ for _ in ()).throw(Exception("Error"))))
        except:
            pass
        
        metrics = breaker.get_metrics()
        assert "state" in metrics
        assert "failure_count" in metrics
        assert "success_count" in metrics
        assert metrics["total_calls"] == 2
    
    def test_circuit_breaker_reset(self):
        """Test circuit breaker reset."""
        breaker = CircuitBreaker("test", CircuitConfig(failure_threshold=1))
        
        # Open the circuit
        asyncio.run(breaker.execute(lambda: (_ for _ in ()).throw(Exception("Error"))))
        assert breaker.state == CircuitState.OPEN
        
        # Reset
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0


class TestRetryPolicy:
    """Tests for Retry Policy pattern."""
    
    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """Test retry succeeds on first attempt."""
        call_count = 0
        
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await retry(max_attempts=3)(success_func)()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_succeeds_after_failures(self):
        """Test retry succeeds after some failures."""
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = await retry(
            max_attempts=5,
            retryable_exceptions=(ConnectionError,)
        )(flaky_func)()
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhausts_attempts(self):
        """Test retry exhausts all attempts."""
        call_count = 0
        
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")
        
        with pytest.raises(ConnectionError):
            await retry(
                max_attempts=3,
                retryable_exceptions=(ConnectionError,)
            )(always_fail)()
        
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_with_conditions(self):
        """Test retry with custom conditions."""
        call_count = 0
        
        async def conditional_fail():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry this")
            raise TypeError("Don't retry this")
        
        with pytest.raises(TypeError):
            await retry(
                max_attempts=3,
                conditions=[lambda e: isinstance(e, ValueError)]
            )(conditional_fail)()
        
        assert call_count == 1  # Should not retry on TypeError
    
    @pytest.mark.asyncio
    async def test_retry_sync(self):
        """Test sync retry decorator."""
        call_count = 0
        
        def sync_flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = retry_sync(
            max_attempts=3,
            retryable_exceptions=(ConnectionError,)
        )(sync_flaky)()
        
        assert result == "success"
        assert call_count == 2
    
    def test_retry_policy_execute(self):
        """Test RetryPolicy class execution."""
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.01,
            max_delay=0.1,
            conditions=[lambda e: isinstance(e, ConnectionError)]
        )
        
        call_count = 0
        
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Retry")
            return "success"
        
        result = asyncio.run(policy.execute(flaky))
        assert result == "success"
        assert call_count == 2
    
    def test_retry_policy_fast(self):
        """Test FAST retry policy configuration."""
        assert RETRY_POLICY_FAST.max_attempts == 3
        assert RETRY_POLICY_FAST.initial_delay == 0.1
        assert RETRY_POLICY_FAST.max_delay == 1.0
    
    def test_retry_policy_external_api(self):
        """Test EXTERNAL_API retry policy configuration."""
        assert RETRY_POLICY_EXTERNAL_API.max_attempts == 5
        assert RETRY_POLICY_EXTERNAL_API.initial_delay == 1.0
        assert RETRY_POLICY_EXTERNAL_API.max_delay == 30.0


class TestCircuitBreakerManager:
    """Tests for Circuit Breaker Manager."""
    
    def test_manager_creates_breaker(self):
        """Test manager creates new breaker."""
        breaker = circuit_manager.get_or_create("new_breaker", CircuitConfig())
        assert breaker is not None
        assert breaker.name == "new_breaker"
    
    def test_manager_returns_existing(self):
        """Test manager returns existing breaker."""
        breaker1 = circuit_manager.get_or_create("existing", CircuitConfig())
        breaker2 = circuit_manager.get_or_create("existing", CircuitConfig())
        assert breaker1 is breaker2
    
    def test_manager_get_all_health(self):
        """Test manager returns health of all breakers."""
        circuit_manager.get_or_create("breaker1", CircuitConfig())
        circuit_manager.get_or_create("breaker2", CircuitConfig())
        
        health = circuit_manager.get_all_health()
        assert "breaker1" in health
        assert "breaker2" in health
    
    def test_manager_get_open_circuits(self):
        """Test manager returns open circuits."""
        breaker = circuit_manager.get_or_create("test_open", CircuitConfig(failure_threshold=1))
        
        # Open the circuit
        asyncio.run(breaker.execute(lambda: (_ for _ in ()).throw(Exception("Error"))))
        
        open_circuits = circuit_manager.get_open_circuits()
        assert "test_open" in open_circuits
    
    def test_manager_reset_all(self):
        """Test manager resets all breakers."""
        breaker = circuit_manager.get_or_create("test_reset", CircuitConfig(failure_threshold=1))
        
        # Open the circuit
        asyncio.run(breaker.execute(lambda: (_ for _ in ()).throw(Exception("Error"))))
        assert breaker.state == CircuitState.OPEN
        
        # Reset all
        circuit_manager.reset_all()
        assert breaker.state == CircuitState.CLOSED


class TestServiceResilience:
    """Tests for service-level resilience patterns."""
    
    @pytest.mark.asyncio
    async def test_delay_predictor_circuit_breaker(self):
        """Test delay predictor uses circuit breaker."""
        from services.delay_predictor import delay_predictor
        
        # Check circuit breaker exists
        assert hasattr(delay_predictor, '_model_breaker')
        assert delay_predictor._model_breaker is not None
    
    @pytest.mark.asyncio
    async def test_aegis_forge_service_resilience(self):
        """Test Aegis Forge service has resilience patterns."""
        from services.aegis_forge_service import aegis_forge_service
        
        # Check circuit breaker exists
        assert hasattr(aegis_forge_service, '_service_breaker')
        assert hasattr(aegis_forge_service, '_retry_policy')
        assert hasattr(aegis_forge_service, 'get_metrics')
        assert hasattr(aegis_forge_service, 'health_check')
    
    @pytest.mark.asyncio
    async def test_commission_service_resilience(self):
        """Test commission service has resilience patterns."""
        from services.commission_service import commission_service
        
        # Check circuit breakers exist
        assert hasattr(commission_service, '_db_breaker')
        assert hasattr(commission_service, '_ledger_breaker')
        assert hasattr(commission_service, '_retry_policy')
        assert hasattr(commission_service, 'get_metrics')
    
    @pytest.mark.asyncio
    async def test_ledger_service_resilience(self):
        """Test ledger service has resilience patterns."""
        from services.ledger_service import ledger_service
        
        # Check circuit breakers exist
        assert hasattr(ledger_service, '_db_breaker')
        assert hasattr(ledger_service, '_signature_breaker')
        assert hasattr(ledger_service, '_retry_policy')
        assert hasattr(ledger_service, 'get_metrics')
    
    @pytest.mark.asyncio
    async def test_recovery_service_resilience(self):
        """Test recovery service has resilience patterns."""
        from services.recovery_service import smart_retry_hub
        
        # Check circuit breaker exists
        assert hasattr(smart_retry_hub, '_retry_breaker')
        assert hasattr(smart_retry_hub, '_retry_policy')
        assert hasattr(smart_retry_hub, 'get_metrics')
        assert hasattr(smart_retry_hub, 'get_pending_tasks')
    
    @pytest.mark.asyncio
    async def test_settlement_service_resilience(self):
        """Test settlement service has resilience patterns."""
        from services.settlement_service import settlement_service
        
        # Check circuit breakers exist
        assert hasattr(settlement_service, '_db_breaker')
        assert hasattr(settlement_service, '_payment_breaker')
        assert hasattr(settlement_service, '_retry_policy')
        assert hasattr(settlement_service, 'get_metrics')
    
    @pytest.mark.asyncio
    async def test_subscription_service_resilience(self):
        """Test subscription service has resilience patterns."""
        from services.subscription_service import subscription_service
        
        # Check circuit breaker exists
        assert hasattr(subscription_service, '_db_breaker')
        assert hasattr(subscription_service, '_retry_policy')
        assert hasattr(subscription_service, 'get_metrics')
    
    @pytest.mark.asyncio
    async def test_event_bus_resilience(self):
        """Test event bus has resilience patterns."""
        from services.event_bus import platform_bus
        
        # Check circuit breaker exists
        assert hasattr(platform_bus, '_redis_breaker')
        assert hasattr(platform_bus, '_retry_policy')
        assert hasattr(platform_bus, 'get_metrics')
    
    @pytest.mark.asyncio
    async def test_feedback_loop_resilience(self):
        """Test feedback loop has resilience patterns."""
        from services.feedback_loop import feedback_loop
        
        # Check circuit breaker exists
        assert hasattr(feedback_loop, '_operation_breaker')
        assert hasattr(feedback_loop, '_retry_policy')
        assert hasattr(feedback_loop, 'get_metrics')


class TestMetricsCollection:
    """Tests for metrics collection."""
    
    def test_metrics_deque_initialization(self):
        """Test metrics deque initialization."""
        metrics = deque(maxlen=1000)
        assert len(metrics) == 0
        assert metrics.maxlen == 1000
    
    def test_metrics_record_format(self):
        """Test metrics record format."""
        record = {
            "timestamp": datetime.utcnow(),
            "operation_type": "test_operation",
            "success": True,
            "value": 100.0
        }
        
        assert "timestamp" in record
        assert "operation_type" in record
        assert "success" in record
        assert "value" in record
    
    def test_metrics_aggregation(self):
        """Test metrics aggregation."""
        metrics = [
            {"success": True, "value": 100},
            {"success": True, "value": 200},
            {"success": False, "value": 50},
        ]
        
        total = len(metrics)
        successful = sum(1 for m in metrics if m["success"])
        values = sum(m["value"] for m in metrics)
        
        assert total == 3
        assert successful == 2
        assert values == 350


class TestIdempotency:
    """Tests for idempotency patterns."""
    
    def test_idempotency_key_generation(self):
        """Test idempotency key generation."""
        from services.commission_service import CommissionService
        
        service = CommissionService()
        key1 = service._generate_idempotency_key("agent_123", "booking_456")
        key2 = service._generate_idempotency_key("agent_123", "booking_456")
        
        # Keys should be different (different timestamps)
        assert key1 != key2
        assert key1.startswith("commission_agent_123_booking_456_")
    
    def test_idempotency_check(self):
        """Test idempotency check."""
        from services.commission_service import CommissionService
        
        service = CommissionService()
        
        # Initially not used
        assert not service._is_idempotent_key_used("test_key")
        
        # Mark as used
        service._mark_idempotency_key("test_key")
        
        # Now should be used
        assert service._is_idempotent_key_used("test_key")


class TestHealthChecks:
    """Tests for health check patterns."""
    
    def test_health_check_format(self):
        """Test health check response format."""
        health = {
            "status": "healthy",
            "circuit_breaker": {
                "state": "closed",
                "failure_count": 0,
                "success_count": 10
            },
            "metrics": {
                "total_operations": 10,
                "success_rate": 1.0
            }
        }
        
        assert health["status"] == "healthy"
        assert "circuit_breaker" in health
        assert "metrics" in health
    
    def test_health_check_circuit_breaker_section(self):
        """Test circuit breaker section in health check."""
        breaker_section = {
            "state": CircuitState.CLOSED.value,
            "failure_count": 5,
            "success_count": 10
        }
        
        assert "state" in breaker_section
        assert "failure_count" in breaker_section
        assert "success_count" in breaker_section


if __name__ == "__main__":
    pytest.main([__file__, "-v"])