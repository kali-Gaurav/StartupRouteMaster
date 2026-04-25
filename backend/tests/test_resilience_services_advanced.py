"""
Comprehensive Tests for Advanced Resilience Patterns
====================================================

Tests for:
- advanced_seat_allocation_engine.py
- booking_verification_service.py
- chronos_service.py
- cancellation_predictor.py
- credit_service.py
- delay_predictor.py

With circuit breakers, retry logic, and metrics tracking.
"""

import pytest
import asyncio
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

# Add backend to path
sys.path.insert(0, 'backend')

from core.resilience import (
    CircuitBreaker, CircuitState, CircuitConfig, 
    circuit_breaker_manager, CircuitOpenError
)
from core.retry import RetryPolicy, retry, retry_sync


class TestAdvancedSeatAllocationEngine:
    """Tests for AdvancedSeatAllocationEngine with resilience patterns."""
    
    @pytest.fixture
    def engine(self):
        """Create a fresh engine instance for each test."""
        from services.advanced_seat_allocation_engine import AdvancedSeatAllocationEngine
        return AdvancedSeatAllocationEngine()
    
    def test_init_with_resilience_patterns(self, engine):
        """Test that engine initializes with circuit breaker and metrics."""
        assert engine._breaker is not None
        assert engine._breaker.name == "seat_allocation"
        assert hasattr(engine, '_metrics')
        assert hasattr(engine, '_retry_policy')
        print("✓ Engine initialized with resilience patterns")
    
    def test_initialize_coaches_with_retry(self, engine):
        """Test coach initialization with retry logic."""
        coaches_config = [
            {'coach_id': 'S1', 'class': 'SL', 'seats': 72},
            {'coach_id': 'S2', 'class': 'SL', 'seats': 72},
        ]
        
        result = engine.initialize_coaches(train_id=12301, coaches_config=coaches_config)
        
        assert result is True
        assert len(engine.coaches) == 2
        assert 'S1' in engine.coaches
        assert 'S2' in engine.coaches
        print("✓ Coaches initialized successfully with retry")
    
    def test_initialize_coaches_invalid_config(self, engine):
        """Test coach initialization with invalid config."""
        coaches_config = [
            {'coach_id': '', 'class': 'SL', 'seats': 72},  # Invalid: empty coach_id
        ]
        
        with pytest.raises(ValueError):
            engine.initialize_coaches(train_id=12301, coaches_config=coaches_config)
        print("✓ Invalid config raises ValueError")
    
    def test_allocate_seats_fair_distribution(self, engine):
        """Test fair seat distribution across coaches."""
        # Initialize coaches
        coaches_config = [
            {'coach_id': 'S1', 'class': 'SL', 'seats': 10},
            {'coach_id': 'S2', 'class': 'SL', 'seats': 10},
        ]
        engine.initialize_coaches(train_id=12301, coaches_config=coaches_config)
        
        # Allocate seats
        from services.advanced_seat_allocation_engine import PassengerPreference, BerthType
        preferences = [
            PassengerPreference(berth_type=BerthType.LOWER),
            PassengerPreference(berth_type=BerthType.UPPER),
        ]
        
        result = engine.allocate_seats_fair_distribution(
            pnr="1234567890",
            num_passengers=2,
            preferences=preferences
        )
        
        assert result.success is True
        assert len(result.seats) == 2
        assert result.status == "confirmed"
        print("✓ Fair seat distribution works correctly")
    
    def test_get_metrics(self, engine):
        """Test metrics collection."""
        # Initialize and make some allocations
        coaches_config = [{'coach_id': 'S1', 'class': 'SL', 'seats': 10}]
        engine.initialize_coaches(train_id=12301, coaches_config=coaches_config)
        engine.allocate_seats_fair_distribution("PNR1", 1)
        engine.allocate_seats_fair_distribution("PNR2", 1)
        
        metrics = engine.get_metrics()
        
        assert metrics['total_allocations'] >= 2
        assert 'circuit_breaker_state' in metrics
        assert 'coach_distribution' in metrics
        print("✓ Metrics collection works correctly")
    
    def test_health_check(self, engine):
        """Test health check endpoint."""
        health = engine.health_check()
        
        assert 'status' in health
        assert 'coaches_configured' in health
        assert 'circuit_breaker' in health
        assert 'metrics' in health
        print("✓ Health check returns all required fields")
    
    def test_circuit_breaker_state(self, engine):
        """Test circuit breaker state tracking."""
        state = engine._breaker.get_state()
        
        assert state in [CircuitState.CLOSED, CircuitState.OPEN, CircuitState.HALF_OPEN]
        print(f"✓ Circuit breaker state: {state.value}")
    
    def test_reset_circuit_breaker(self, engine):
        """Test circuit breaker reset."""
        engine._breaker.failure_count = 5
        engine.reset_circuit_breaker()
        
        assert engine._breaker.failure_count == 0
        assert engine._breaker.get_state() == CircuitState.CLOSED
        print("✓ Circuit breaker reset works correctly")


class TestBookingVerificationService:
    """Tests for BookingVerificationService with resilience patterns."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh service instance for each test."""
        from services.booking_verification_service import BookingVerificationService
        return BookingVerificationService()
    
    def test_init_with_circuit_breakers(self, service):
        """Test that service initializes with circuit breakers for each check type."""
        assert service._availability_breaker is not None
        assert service._pnr_breaker is not None
        assert service._live_status_breaker is not None
        assert service._fare_breaker is not None
        assert hasattr(service, '_metrics')
        assert hasattr(service, '_availability_retry')
        print("✓ Service initialized with circuit breakers for all check types")
    
    def test_get_metrics(self, service):
        """Test metrics collection."""
        metrics = service.get_metrics()
        
        assert 'total_verifications' in metrics
        assert 'success_rate' in metrics
        assert 'circuit_breaker_states' in metrics
        print("✓ Metrics collection works correctly")
    
    def test_health_check(self, service):
        """Test health check endpoint."""
        health = service.health_check()
        
        assert 'status' in health
        assert 'circuit_breakers' in health
        assert 'metrics' in health
        assert 'availability' in health['circuit_breakers']
        assert 'pnr' in health['circuit_breakers']
        assert 'live_status' in health['circuit_breakers']
        assert 'fare' in health['circuit_breakers']
        print("✓ Health check returns all required fields")
    
    def test_reset_circuit_breakers(self, service):
        """Test resetting all circuit breakers."""
        service._availability_breaker.failure_count = 3
        service._pnr_breaker.failure_count = 3
        service.reset_circuit_breakers()
        
        assert service._availability_breaker.failure_count == 0
        assert service._pnr_breaker.failure_count == 0
        print("✓ All circuit breakers reset correctly")


class TestChronosService:
    """Tests for ChronosService with resilience patterns."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        return db
    
    @pytest.fixture
    def auditor(self, mock_db):
        """Create a ChronosAuditorAgent with mocked dependencies."""
        from services.chronos_service import ChronosAuditorAgent
        return ChronosAuditorAgent(mock_db)
    
    def test_init_with_resilience_patterns(self, auditor):
        """Test that auditor initializes with circuit breaker and metrics."""
        assert auditor._live_status_breaker is not None
        assert auditor._live_status_breaker.name == "chronos_live_status"
        assert hasattr(auditor, '_metrics')
        assert hasattr(auditor, '_retry_policy')
        print("✓ Auditor initialized with resilience patterns")
    
    def test_get_metrics(self, auditor):
        """Test metrics collection."""
        metrics = auditor.get_metrics()
        
        assert 'total_audits' in metrics
        assert 'avg_drift' in metrics
        assert 'high_drift_count' in metrics
        assert 'circuit_breaker_state' in metrics
        print("✓ Metrics collection works correctly")
    
    def test_health_check(self, auditor):
        """Test health check endpoint."""
        health = auditor.health_check()
        
        assert 'status' in health
        assert 'circuit_breaker' in health
        assert 'metrics' in health
        print("✓ Health check returns all required fields")
    
    def test_reset_circuit_breaker(self, auditor):
        """Test circuit breaker reset."""
        auditor._live_status_breaker.failure_count = 5
        auditor.reset_circuit_breaker()
        
        assert auditor._live_status_breaker.failure_count == 0
        assert auditor._live_status_breaker.get_state() == CircuitState.CLOSED
        print("✓ Circuit breaker reset works correctly")


class TestCancellationPredictor:
    """Tests for CancellationPredictor with resilience patterns."""
    
    @pytest.fixture
    def predictor(self):
        """Create a fresh predictor instance for each test."""
        from services.cancellation_predictor import CancellationPredictor
        return CancellationPredictor()
    
    def test_init_with_resilience_patterns(self, predictor):
        """Test that predictor initializes with circuit breaker and metrics."""
        assert predictor._model_breaker is not None
        assert predictor._model_breaker.name == "cancellation_predictor"
        assert hasattr(predictor, '_metrics')
        assert hasattr(predictor, '_retry_policy')
        print("✓ Predictor initialized with resilience patterns")
    
    def test_train_scaffold_model(self, predictor):
        """Test scaffold model training."""
        predictor.train_scaffold_model()
        
        assert predictor.is_trained is True
        assert predictor.model is not None
        assert len(predictor.feature_names) > 0
        print("✓ Scaffold model trained successfully")
    
    def test_predict_cancellation_rate(self, predictor):
        """Test cancellation rate prediction."""
        predictor.train_scaffold_model()
        
        prediction = predictor.predict_cancellation_rate(
            train_id=12301,
            travel_date="2026-04-25",
            quota_type="general",
            days_to_departure=10,
            booking_velocity=5.0,
            route_popularity=0.7,
            demand_forecast=0.8,
            historical_cancellation_rate=0.08
        )
        
        assert prediction is not None
        assert 0 <= prediction.predicted_cancellation_rate <= 1
        assert 0 <= prediction.confidence_score <= 1
        assert prediction.recommendation in ["safe_to_overbook", "moderate_caution", "high_risk_no_overbook"]
        print(f"✓ Prediction made: {prediction.predicted_cancellation_rate:.2%} ({prediction.recommendation})")
    
    def test_get_metrics(self, predictor):
        """Test metrics collection."""
        predictor.train_scaffold_model()
        # Make some predictions
        for _ in range(3):
            predictor.predict_cancellation_rate(
                train_id=12301,
                travel_date="2026-04-25",
                quota_type="general",
                days_to_departure=10,
                booking_velocity=5.0,
                route_popularity=0.7,
                demand_forecast=0.8,
                historical_cancellation_rate=0.08
            )
        
        metrics = predictor.get_metrics()
        
        assert 'total_predictions' in metrics
        assert 'avg_predicted_rate' in metrics
        assert 'avg_confidence' in metrics
        assert 'circuit_breaker_state' in metrics
        print("✓ Metrics collection works correctly")
    
    def test_health_check(self, predictor):
        """Test health check endpoint."""
        predictor.train_scaffold_model()
        
        health = predictor.health_check()
        
        assert 'status' in health
        assert 'model_trained' in health
        assert 'circuit_breaker' in health
        assert 'metrics' in health
        print("✓ Health check returns all required fields")
    
    def test_reset_circuit_breaker(self, predictor):
        """Test circuit breaker reset."""
        predictor._model_breaker.failure_count = 5
        predictor.reset_circuit_breaker()
        
        assert predictor._model_breaker.failure_count == 0
        assert predictor._model_breaker.get_state() == CircuitState.CLOSED
        print("✓ Circuit breaker reset works correctly")


class TestCreditService:
    """Tests for CreditService with resilience patterns."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh service instance for each test."""
        from services.credit_service import UnlockCreditService
        return UnlockCreditService()
    
    def test_init_with_resilience_patterns(self, service):
        """Test that service initializes with circuit breaker and metrics."""
        assert service._db_breaker is not None
        assert service._db_breaker.name == "credit_service_db"
        assert hasattr(service, '_metrics')
        assert hasattr(service, '_retry_policy')
        print("✓ Service initialized with resilience patterns")
    
    def test_get_metrics(self, service):
        """Test metrics collection."""
        metrics = service.get_metrics()
        
        assert 'total_transactions' in metrics
        assert 'success_rate' in metrics
        assert 'transaction_breakdown' in metrics
        assert 'circuit_breaker_state' in metrics
        print("✓ Metrics collection works correctly")
    
    def test_health_check(self, service):
        """Test health check endpoint."""
        health = service.health_check()
        
        assert 'status' in health
        assert 'circuit_breaker' in health
        assert 'metrics' in health
        print("✓ Health check returns all required fields")
    
    def test_reset_circuit_breaker(self, service):
        """Test circuit breaker reset."""
        service._db_breaker.failure_count = 5
        service.reset_circuit_breaker()
        
        assert service._db_breaker.failure_count == 0
        assert service._db_breaker.get_state() == CircuitState.CLOSED
        print("✓ Circuit breaker reset works correctly")


class TestDelayPredictor:
    """Tests for DelayPredictor with resilience patterns."""
    
    @pytest.fixture
    def predictor(self):
        """Create a fresh predictor instance for each test."""
        from services.delay_predictor import DelayPredictor
        return DelayPredictor()
    
    def test_init_with_resilience_patterns(self, predictor):
        """Test that predictor initializes with circuit breaker and metrics."""
        assert predictor._model_breaker is not None
        assert predictor._model_breaker.name == "delay_predictor"
        assert hasattr(predictor, '_metrics')
        assert hasattr(predictor, '_retry_policy')
        print("✓ Predictor initialized with resilience patterns")
    
    def test_get_metrics(self, predictor):
        """Test metrics collection."""
        metrics = predictor.get_metrics()
        
        assert 'total_predictions' in metrics
        assert 'success_rate' in metrics
        assert 'avg_prediction' in metrics
        assert 'circuit_breaker_state' in metrics
        print("✓ Metrics collection works correctly")
    
    def test_health_check(self, predictor):
        """Test health check endpoint."""
        health = predictor.health_check()
        
        assert 'status' in health
        assert 'model_trained' in health
        assert 'circuit_breaker' in health
        assert 'metrics' in health
        print("✓ Health check returns all required fields")
    
    def test_reset_circuit_breaker(self, predictor):
        """Test circuit breaker reset."""
        predictor._model_breaker.failure_count = 5
        predictor.reset_circuit_breaker()
        
        assert predictor._model_breaker.failure_count == 0
        assert predictor._model_breaker.get_state() == CircuitState.CLOSED
        print("✓ Circuit breaker reset works correctly")


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker behavior."""
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test that circuit breaker opens after threshold is reached."""
        breaker = CircuitBreaker(
            "test_breaker",
            CircuitConfig(failure_threshold=3, timeout_seconds=1.0)
        )
        
        # Simulate failures
        async def failing_func():
            raise ConnectionError("Test failure")
        
        async def test():
            for _ in range(3):
                try:
                    await breaker.execute(failing_func)
                except:
                    pass
        
        asyncio.run(test())
        
        assert breaker.get_state() == CircuitState.OPEN
        print("✓ Circuit breaker opens after threshold failures")
    
    def test_circuit_breaker_allows_success_after_reset(self):
        """Test that circuit breaker allows success after reset."""
        breaker = CircuitBreaker(
            "test_breaker",
            CircuitConfig(failure_threshold=1, timeout_seconds=0.1)
        )
        
        async def failing_func():
            raise ConnectionError("Test failure")
        
        async def success_func():
            return "success"
        
        async def test():
            # First call fails
            try:
                await breaker.execute(failing_func)
            except:
                pass
            
            # Wait for timeout
            await asyncio.sleep(0.2)
            
            # Reset and try success
            breaker.reset()
            result = await breaker.execute(success_func)
            return result
        
        result = asyncio.run(test())
        
        assert result == "success"
        assert breaker.get_state() == CircuitState.CLOSED
        print("✓ Circuit breaker allows success after reset")
    
    def test_circuit_breaker_rejects_when_open(self):
        """Test that circuit breaker rejects calls when open."""
        breaker = CircuitBreaker(
            "test_breaker",
            CircuitConfig(failure_threshold=1, timeout_seconds=60.0)
        )
        
        async def failing_func():
            raise ConnectionError("Test failure")
        
        async def test():
            # First call fails
            try:
                await breaker.execute(failing_func)
            except:
                pass
            
            # Second call should be rejected
            with pytest.raises(CircuitOpenError):
                await breaker.execute(failing_func)
        
        asyncio.run(test())
        print("✓ Circuit breaker rejects calls when open")


class TestRetryPolicyIntegration:
    """Integration tests for retry policy behavior."""
    
    def test_retry_on_connection_error(self):
        """Test that retry policy retries on connection errors."""
        call_count = 0
        
        @retry(
            max_attempts=3,
            initial_delay=0.01,
            max_delay=0.1,
            retryable_exceptions=(ConnectionError, TimeoutError)
        )
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"
        
        async def test():
            return await flaky_function()
        
        result = asyncio.run(test())
        
        assert result == "success"
        assert call_count == 3
        print("✓ Retry policy retries on connection errors")
    
    def test_retry_sync_on_exception(self):
        """Test that sync retry policy retries on exceptions."""
        call_count = 0
        
        @retry_sync(
            max_attempts=3,
            initial_delay=0.01,
            max_delay=0.1,
            retryable_exceptions=(ConnectionError, TimeoutError)
        )
        def flaky_sync_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = flaky_sync_function()
        
        assert result == "success"
        assert call_count == 3
        print("✓ Sync retry policy retries on exceptions")


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("COMPREHENSIVE RESILIENCE PATTERNS TEST SUITE")
    print("="*70 + "\n")
    
    # Run all test classes
    test_classes = [
        TestAdvancedSeatAllocationEngine,
        TestBookingVerificationService,
        TestChronosService,
        TestCancellationPredictor,
        TestCreditService,
        TestDelayPredictor,
        TestCircuitBreakerIntegration,
        TestRetryPolicyIntegration,
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        print(f"\n{'='*70}")
        print(f"TESTING: {test_class.__name__}")
        print('='*70)
        
        instance = test_class()
        
        # Get all test methods
        test_methods = [m for m in dir(instance) if m.startswith('test_')]
        
        for method_name in test_methods:
            method = getattr(instance, method_name)
            try:
                # Handle async methods
                if asyncio.iscoroutinefunction(method):
                    asyncio.run(method())
                else:
                    method()
                total_tests += 1
                passed_tests += 1
            except Exception as e:
                total_tests += 1
                print(f"✗ {method_name}: {e}")
    
    print("\n" + "="*70)
    print(f"TEST SUMMARY: {passed_tests}/{total_tests} tests passed")
    print("="*70)
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED! Resilience patterns are working correctly.")
    else:
        print(f"\n⚠️ {total_tests - passed_tests} tests failed. Please review the output above.")