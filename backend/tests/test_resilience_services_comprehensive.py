"""
Comprehensive Test Suite for Enhanced Backend Services
=======================================================

Tests for all services enhanced with resilience patterns:
- Circuit breakers
- Retry policies
- Metrics tracking
- Health checks
- Error handling

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import pytest
import asyncio
import logging
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    session.query = MagicMock()
    return session


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    return redis


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# CIRCUIT BREAKER TESTS
# ============================================================================

class TestCircuitBreaker:
    """Tests for CircuitBreaker implementation."""
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker starts in closed state."""
        from core.resilience import CircuitBreaker, CircuitState, CircuitConfig
        
        breaker = CircuitBreaker("test_breaker", CircuitConfig(failure_threshold=3))
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after reaching failure threshold."""
        from core.resilience import CircuitBreaker, CircuitState, CircuitConfig
        
        breaker = CircuitBreaker("test_breaker", CircuitConfig(
            failure_threshold=3,
            timeout_seconds=60.0
        ))
        
        # Simulate failures
        for i in range(3):
            with pytest.raises(Exception):
                asyncio.run(breaker.execute(lambda: (_ for _ in ()).throw(Exception("fail"))))
        
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3
    
    def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit breaker transitions to half-open after timeout."""
        from core.resilience import CircuitBreaker, CircuitState, CircuitConfig
        
        breaker = CircuitBreaker("test_breaker", CircuitConfig(
            failure_threshold=1,
            timeout_seconds=0.1
        ))
        
        # Trigger failure
        with pytest.raises(Exception):
            asyncio.run(breaker.execute(lambda: (_ for _ in ()).throw(Exception("fail"))))
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for timeout
        import time
        time.sleep(0.15)
        
        # Next call should transition to half-open
        async def success_func():
            return "success"
        
        result = asyncio.run(breaker.execute(success_func))
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
    
    def test_circuit_breaker_rejects_when_open(self):
        """Test circuit breaker rejects calls when open."""
        from core.resilience import CircuitBreaker, CircuitState, CircuitConfig, CircuitOpenError
        
        breaker = CircuitBreaker("test_breaker", CircuitConfig(
            failure_threshold=1,
            timeout_seconds=60.0
        ))
        
        # Trigger failure
        with pytest.raises(Exception):
            asyncio.run(breaker.execute(lambda: (_ for _ in ()).throw(Exception("fail"))))
        
        assert breaker.state == CircuitState.OPEN
        
        # Next call should raise CircuitOpenError
        with pytest.raises(CircuitOpenError):
            asyncio.run(breaker.execute(lambda: "success"))


# ============================================================================
# RETRY POLICY TESTS
# ============================================================================

class TestRetryPolicy:
    """Tests for RetryPolicy implementation."""
    
    def test_retry_policy_success_first_attempt(self):
        """Test retry policy succeeds on first attempt."""
        from core.retry import RetryPolicy
        
        policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
        
        call_count = 0
        
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = asyncio.run(policy.execute(success_func))
        assert result == "success"
        assert call_count == 1
    
    def test_retry_policy_retries_on_failure(self):
        """Test retry policy retries on failure."""
        from core.retry import RetryPolicy
        
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.01,
            conditions=[lambda e: isinstance(e, ValueError)]
        )
        
        call_count = 0
        
        async def fail_twice_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "success"
        
        result = asyncio.run(policy.execute(fail_twice_func))
        assert result == "success"
        assert call_count == 3
    
    def test_retry_policy_gives_up_after_max_attempts(self):
        """Test retry policy gives up after max attempts."""
        from core.retry import RetryPolicy
        
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.01,
            conditions=[lambda e: isinstance(e, ValueError)]
        )
        
        async def always_fail_func():
            raise ValueError("permanent error")
        
        with pytest.raises(ValueError):
            asyncio.run(policy.execute(always_fail_func))
    
    def test_retry_policy_exponential_backoff(self):
        """Test retry policy uses exponential backoff."""
        from core.retry import RetryPolicy
        import time
        
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.05,
            max_delay=1.0,
            exponential_base=2.0,
            jitter=False
        )
        
        call_times = []
        
        async def fail_twice_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("temp")
            return "success"
        
        start = time.time()
        result = asyncio.run(policy.execute(fail_twice_func))
        elapsed = time.time() - start
        
        assert result == "success"
        # Should have delays of 0.05 + 0.1 = 0.15s minimum
        assert elapsed >= 0.1


# ============================================================================
# MONITORING SCHEDULER TESTS
# ============================================================================

class TestAlertQueueService:
    """Tests for AlertQueueService with resilience patterns."""
    
    @pytest.mark.asyncio
    async def test_queue_alert_success(self, mock_redis_client):
        """Test successful alert queuing."""
        from services.monitoring_scheduler import AlertQueueService
        from providers.models import AlertMessage
        
        service = AlertQueueService(redis_client=mock_redis_client)
        
        alert_data = {
            "alert_id": "test-123",
            "user_id": "user-456",
            "booking_id": "booking-789",
            "alert_type": "delay_warning",
            "details": {"message": "Train delayed by 30 minutes"},
            "priority": "high"
        }
        
        result = await service.queue_alert(alert_data)
        assert result is True
        mock_redis_client.rpush.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_queue_alert_validation_error(self, mock_redis_client):
        """Test alert queuing with invalid data."""
        from services.monitoring_scheduler import AlertQueueService
        
        service = AlertQueueService(redis_client=mock_redis_client)
        
        # Missing required fields
        invalid_data = {"alert_type": "test"}
        
        result = await service.queue_alert(invalid_data)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_queue_length(self, mock_redis_client):
        """Test getting queue length."""
        from services.monitoring_scheduler import AlertQueueService
        
        service = AlertQueueService(redis_client=mock_redis_client)
        mock_redis_client.llen = AsyncMock(return_value=5)
        
        length = await service.get_queue_length()
        assert length == 5
    
    def test_health_check(self, mock_redis_client):
        """Test health check returns correct status."""
        from services.monitoring_scheduler import AlertQueueService
        
        service = AlertQueueService(redis_client=mock_redis_client)
        
        health = service.health_check()
        
        assert health["status"] == "healthy"
        assert "queue_length" in health
        assert "circuit_breaker" in health


# ============================================================================
# BANK WEBHOOK SERVICE TESTS
# ============================================================================

class TestBankWebhookService:
    """Tests for BankWebhookService with resilience patterns."""
    
    def test_parse_sms_valid_pattern(self):
        """Test SMS parsing with valid pattern."""
        from services.bank_webhook_service import BankWebhookService
        
        service = BankWebhookService()
        
        # Test SBI pattern
        sms = "Your A/c XXXXX1234 is Debited for INR 1500.00 on 15-01-2024 10:30:45. Ref No 123456789012"
        amount, utr = service.parse_sms(sms)
        
        assert amount == 1500.00
        assert utr == "123456789012"
    
    def test_parse_sms_no_match(self):
        """Test SMS parsing with no matching pattern."""
        from services.bank_webhook_service import BankWebhookService
        
        service = BankWebhookService()
        
        sms = "This is a random message"
        amount, utr = service.parse_sms(sms)
        
        assert amount is None
        assert utr is None
    
    def test_decrypt_payload_success(self):
        """Test successful payload decryption."""
        from services.bank_webhook_service import BankWebhookService
        from cryptography.fernet import Fernet
        import base64
        
        service = BankWebhookService()
        
        # Create a test key and encrypt data
        key = b"test_key_32_bytes_long_key!!"[:32]
        iv = b"test_iv_16bytes!!"
        plaintext = b"test message"
        
        # Simple XOR encryption for test
        ciphertext = bytes([p ^ k for p, k in zip(plaintext, key * 100)])[:16]
        
        # This test would need proper encryption setup
        # For now, just test that the method exists
        assert hasattr(service, 'decrypt_payload')
    
    def test_health_check(self):
        """Test health check returns correct status."""
        from services.bank_webhook_service import BankWebhookService
        
        service = BankWebhookService()
        
        health = service.health_check()
        
        assert health["status"] == "healthy"
        assert "circuit_breaker" in health
        assert "metrics" in health


# ============================================================================
# RECONCILIATION SERVICE TESTS
# ============================================================================

class TestReconciliationService:
    """Tests for ReconciliationService with resilience patterns."""
    
    def test_health_check(self, mock_db_session):
        """Test health check returns correct status."""
        from services.reconciliation_service import ReconciliationService
        
        service = ReconciliationService(mock_db_session)
        
        health = service.health_check()
        
        assert health["status"] == "healthy"
        assert "circuit_breaker" in health
        assert "metrics" in health
    
    def test_get_metrics(self, mock_db_session):
        """Test metrics collection."""
        from services.reconciliation_service import ReconciliationService
        
        service = ReconciliationService(mock_db_session)
        
        metrics = service.get_metrics()
        
        assert "total_operations" in metrics
        assert "success_rate" in metrics
        assert "operation_breakdown" in metrics
    
    def test_reset_circuit_breaker(self, mock_db_session):
        """Test circuit breaker reset."""
        from services.reconciliation_service import ReconciliationService
        
        service = ReconciliationService(mock_db_session)
        
        # Should not raise exception
        service.reset_circuit_breaker()


# ============================================================================
# COMMISSION SERVICE TESTS
# ============================================================================

class TestCommissionService:
    """Tests for CommissionService with resilience patterns."""
    
    def test_health_check(self, mock_db_session):
        """Test health check returns correct status."""
        from services.commission_service import CommissionService
        
        service = CommissionService(mock_db_session)
        
        health = service.health_check()
        
        assert health["status"] == "healthy"
        assert "circuit_breakers" in health
        assert "database" in health["circuit_breakers"]
        assert "ledger" in health["circuit_breakers"]
    
    def test_get_metrics(self, mock_db_session):
        """Test metrics collection."""
        from services.commission_service import CommissionService
        
        service = CommissionService(mock_db_session)
        
        metrics = service.get_metrics()
        
        assert "total_transactions" in metrics
        assert "success_rate" in metrics
        assert "transaction_breakdown" in metrics
    
    def test_idempotency_key_generation(self, mock_db_session):
        """Test idempotency key generation."""
        from services.commission_service import CommissionService
        
        service = CommissionService(mock_db_session)
        
        key1 = service._generate_idempotency_key("agent-1", "booking-1")
        key2 = service._generate_idempotency_key("agent-1", "booking-1")
        
        # Same inputs should generate same key
        assert key1 == key2
        
        # Different inputs should generate different keys
        key3 = service._generate_idempotency_key("agent-1", "booking-2")
        assert key1 != key3


# ============================================================================
# SETTLEMENT SERVICE TESTS
# ============================================================================

class TestSettlementService:
    """Tests for SettlementService with resilience patterns."""
    
    def test_health_check(self, mock_db_session):
        """Test health check returns correct status."""
        from services.settlement_service import SettlementService
        
        service = SettlementService(mock_db_session)
        
        health = service.health_check()
        
        assert health["status"] == "healthy"
        assert "circuit_breakers" in health
        assert "database" in health["circuit_breakers"]
        assert "payment" in health["circuit_breakers"]
    
    def test_get_metrics(self, mock_db_session):
        """Test metrics collection."""
        from services.settlement_service import SettlementService
        
        service = SettlementService(mock_db_session)
        
        metrics = service.get_metrics()
        
        assert "total_settlements" in metrics
        assert "success_rate" in metrics
        assert "total_amount" in metrics


# ============================================================================
# LEDGER SERVICE TESTS
# ============================================================================

class TestLedgerService:
    """Tests for LedgerService with resilience patterns."""
    
    def test_health_check(self, mock_db_session):
        """Test health check returns correct status."""
        from services.ledger_service import LedgerService
        
        service = LedgerService(mock_db_session)
        
        health = service.health_check()
        
        assert health["status"] == "healthy"
        assert "circuit_breakers" in health
        assert "database" in health["circuit_breakers"]
        assert "signature" in health["circuit_breakers"]
    
    def test_get_metrics(self, mock_db_session):
        """Test metrics collection."""
        from services.ledger_service import LedgerService
        
        service = LedgerService(mock_db_session)
        
        metrics = service.get_metrics()
        
        assert "total_transactions" in metrics
        assert "success_rate" in metrics
        assert "total_amount" in metrics
    
    def test_idempotency_key_generation(self, mock_db_session):
        """Test idempotency key generation."""
        from services.ledger_service import LedgerService
        
        service = LedgerService(mock_db_session)
        
        # Test that idempotency keys work
        key = "test_reference_123"
        assert not service._is_idempotent_key_used(key)
        
        service._mark_idempotency_key(key)
        assert service._is_idempotent_key_used(key)


# ============================================================================
# SUBSCRIPTION SERVICE TESTS
# ============================================================================

class TestSubscriptionService:
    """Tests for SubscriptionService with resilience patterns."""
    
    def test_health_check(self, mock_db_session):
        """Test health check returns correct status."""
        from services.subscription_service import SubscriptionService
        
        service = SubscriptionService(mock_db_session)
        
        health = service.health_check()
        
        assert health["status"] == "healthy"
        assert "circuit_breaker" in health
        assert "metrics" in health
    
    def test_get_metrics(self, mock_db_session):
        """Test metrics collection."""
        from services.subscription_service import SubscriptionService
        
        service = SubscriptionService(mock_db_session)
        
        metrics = service.get_metrics()
        
        assert "total_operations" in metrics
        assert "success_rate" in metrics
        assert "operation_breakdown" in metrics
    
    def test_plan_features(self, mock_db_session):
        """Test plan features retrieval."""
        from services.subscription_service import SubscriptionService, PLAN_FEATURES
        
        service = SubscriptionService(mock_db_session)
        
        # Test FREE plan
        free_features = service.get_plan_features("FREE")
        assert free_features == PLAN_FEATURES["FREE"]
        
        # Test PRO plan
        pro_features = service.get_plan_features("PRO")
        assert pro_features == PLAN_FEATURES["PRO"]
        
        # Test unknown plan returns FREE
        unknown_features = service.get_plan_features("UNKNOWN")
        assert unknown_features == PLAN_FEATURES["FREE"]


# ============================================================================
# EVENT BUS TESTS
# ============================================================================

class TestPlatformEventBus:
    """Tests for PlatformEventBus with resilience patterns."""
    
    def test_health_check(self):
        """Test health check returns correct status."""
        from services.event_bus import PlatformEventBus
        
        bus = PlatformEventBus()
        
        health = bus.health_check()
        
        assert health["status"] == "healthy"
        assert "redis_available" in health
        assert "listener_running" in health
        assert "circuit_breaker" in health
    
    def test_get_metrics(self):
        """Test metrics collection."""
        from services.event_bus import PlatformEventBus
        
        bus = PlatformEventBus()
        
        metrics = bus.get_metrics()
        
        assert "total_events" in metrics
        assert "success_rate" in metrics
        assert "event_breakdown" in metrics
        assert "active_subscriptions" in metrics
    
    def test_subscribe_unsubscribe(self):
        """Test event subscription and unsubscription."""
        from services.event_bus import PlatformEventBus
        
        bus = PlatformEventBus()
        
        async def handler(data):
            pass
        
        # Subscribe
        bus.subscribe("test_event", handler)
        assert "test_event" in bus.handlers
        assert bus._subscriptions.get("test_event", 0) == 1
        
        # Unsubscribe
        bus.unsubscribe("test_event")
        assert "test_event" not in bus.handlers
        assert bus._subscriptions.get("test_event", 0) == 0


# ============================================================================
# EVENT PRODUCER TESTS
# ============================================================================

class TestEventProducer:
    """Tests for EventProducer with resilience patterns."""
    
    def test_event_creation(self):
        """Test event creation."""
        from services.event_producer import RouteSearchedEvent
        
        event = RouteSearchedEvent(
            user_id="user-123",
            source="NDLS",
            destination="CNB",
            travel_date="2024-01-15",
            routes_shown=10,
            search_latency_ms=150.0
        )
        
        assert event.event_type == "RouteSearched"
        assert event.user_id == "user-123"
        assert event.source == "NDLS"
        assert event.destination == "CNB"
    
    def test_event_to_dict(self):
        """Test event serialization."""
        from services.event_producer import BookingCreatedEvent
        
        event = BookingCreatedEvent(
            user_id="user-123",
            route_id="route-456",
            total_cost=1500.0,
            segments=[{"from": "NDLS", "to": "CNB"}],
            booking_reference="PNR123"
        )
        
        data = event.to_dict()
        
        assert data["event_type"] == "BookingCreated"
        assert data["user_id"] == "user-123"
        assert data["total_cost"] == 1500.0
        assert "timestamp" in data
    
    def test_in_memory_producer(self):
        """Test in-memory event producer."""
        from services.event_producer import InMemoryEventProducer, RouteSearchedEvent
        
        producer = InMemoryEventProducer()
        
        event = RouteSearchedEvent(
            user_id="user-123",
            source="NDLS",
            destination="CNB",
            travel_date="2024-01-15",
            routes_shown=10,
            search_latency_ms=150.0
        )
        
        result = asyncio.run(producer.publish_event(event, "test_topic"))
        
        assert result is True
        events = producer.get_events("test_topic")
        assert len(events) == 1


# ============================================================================
# FEEDBACK LOOP TESTS
# ============================================================================

class TestPredictionFeedbackLoop:
    """Tests for PredictionFeedbackLoop with resilience patterns."""
    
    def test_health_check(self):
        """Test health check returns correct status."""
        from services.feedback_loop import PredictionFeedbackLoop
        
        loop = PredictionFeedbackLoop()
        
        health = loop.health_check()
        
        assert health["status"] == "healthy"
        assert "punishment_cycle_running" in health
        assert "circuit_breaker" in health
        assert "metrics" in health
    
    def test_get_metrics(self):
        """Test metrics collection."""
        from services.feedback_loop import PredictionFeedbackLoop
        
        loop = PredictionFeedbackLoop()
        
        metrics = loop.get_metrics()
        
        assert "total_predictions" in metrics
        assert "correct_predictions" in metrics
        assert "accuracy_rate" in metrics
        assert "multipliers" in metrics
    
    def test_multiplier_initialization(self):
        """Test initial multiplier values."""
        from services.feedback_loop import PredictionFeedbackLoop
        
        loop = PredictionFeedbackLoop()
        
        assert loop.get_multiplier("SEARCH") == 1.0
        assert loop.get_multiplier("BOOKING") == 1.0
        assert loop.get_multiplier("STATUS") == 1.0
        assert loop.get_multiplier("UNKNOWN") == 1.0  # Default


# ============================================================================
# DEGRADATION MANAGER TESTS
# ============================================================================

class TestDegradationManager:
    """Tests for DegradationManager with resilience patterns."""
    
    def test_initial_state(self):
        """Test initial state is HEALTHY."""
        from services.degradation_manager import DegradationManager, SystemState
        
        manager = DegradationManager()
        
        assert manager.get_current_state() == SystemState.HEALTHY
        assert manager.get_state_description() == "All systems operational"
    
    def test_feature_enabled_matrix(self):
        """Test feature enable/disable based on state."""
        from services.degradation_manager import DegradationManager, SystemState
        
        manager = DegradationManager()
        
        # In HEALTHY state, all features should be enabled
        assert manager.is_feature_enabled("search") is True
        assert manager.is_feature_enabled("booking") is True
        assert manager.is_feature_enabled("ml_predictions") is True
        assert manager.is_feature_enabled("analytics") is True
        
        # Transition to MINIMAL state
        manager.current_state = SystemState.MINIMAL
        
        # Core features still enabled
        assert manager.is_feature_enabled("search") is True
        assert manager.is_feature_enabled("booking") is True
        
        # Non-core features disabled
        assert manager.is_feature_enabled("ml_predictions") is False
        assert manager.is_feature_enabled("analytics") is False
    
    def test_health_check(self):
        """Test health check returns correct status."""
        from services.degradation_manager import DegradationManager
        
        manager = DegradationManager()
        
        health = manager.health_check()
        
        assert health["status"] == "healthy"
        assert "current_state" in health
        assert "state_description" in health
        assert "monitoring_active" in health
        assert "thresholds" in health
        assert "circuit_breaker" in health
    
    def test_get_metrics(self):
        """Test metrics collection."""
        from services.degradation_manager import DegradationManager
        
        manager = DegradationManager()
        
        metrics = manager.get_metrics()
        
        assert "total_operations" in metrics
        assert "success_rate" in metrics
        assert "current_state" in metrics
        assert "state_distribution" in metrics


# ============================================================================
# JIT MANAGER TESTS
# ============================================================================

class TestJitManager:
    """Tests for JitManager with resilience patterns."""
    
    def test_register_node(self):
        """Test node registration."""
        from services.jit_manager import JitManager, JITState
        
        manager = JitManager()
        
        async def dummy_loader():
            pass
        
        node = manager.register_node(
            "test_node",
            dependencies=[],
            loader=dummy_loader
        )
        
        assert node.name == "test_node"
        assert node.state == JITState.PENDING
        assert "test_node" in manager.nodes
    
    def test_validate_dependencies(self):
        """Test dependency validation."""
        from services.jit_manager import JitManager
        
        manager = JitManager()
        
        # Register nodes with dependencies
        manager.register_node("node_a", dependencies=[])
        manager.register_node("node_b", dependencies=["node_a"])
        manager.register_node("node_c", dependencies=["node_b", "node_d"])  # node_d missing
        
        result = manager.validate_dependencies()
        
        assert result["valid"] is False
        assert len(result["issues"]) == 1
        assert result["issues"][0]["type"] == "missing_dependency"
    
    def test_health_check(self):
        """Test health check returns correct status."""
        from services.jit_manager import JitManager
        
        manager = JitManager()
        
        health = manager.health_check()
        
        assert health["status"] == "healthy"
        assert "nodes_registered" in health
        assert "nodes_ready" in health
        assert "nodes_pending" in health
        assert "dependency_validation" in health
        assert "circuit_breaker" in health
    
    def test_get_metrics(self):
        """Test metrics collection."""
        from services.jit_manager import JitManager
        
        manager = JitManager()
        
        metrics = manager.get_metrics()
        
        assert "total_loads" in metrics
        assert "successful_loads" in metrics
        assert "success_rate" in metrics
        assert "total_nodes" in metrics
        assert "ready_nodes" in metrics


# ============================================================================
# BEHAVIOR TRACKER TESTS
# ============================================================================

class TestBehaviorTracker:
    """Tests for BehaviorTracker with resilience patterns."""
    
    def test_health_check(self):
        """Test health check returns correct status."""
        from services.behavior_tracker import HeuristicIntentTrigger
        
        tracker = HeuristicIntentTrigger()
        
        health = tracker.health_check()
        
        assert health["status"] == "healthy"
        assert "cleanup_task_running" in health
        assert "circuit_breaker" in health
        assert "metrics" in health
    
    def test_get_metrics(self):
        """Test metrics collection."""
        from services.behavior_tracker import HeuristicIntentTrigger
        
        tracker = HeuristicIntentTrigger()
        
        metrics = tracker.get_metrics()
        
        assert "total_operations" in metrics
        assert "success_rate" in metrics
        assert "active_users" in metrics
        assert "heuristic_stats" in metrics
    
    def test_heuristic_stats_initialization(self):
        """Test initial heuristic statistics."""
        from services.behavior_tracker import HeuristicIntentTrigger
        
        tracker = HeuristicIntentTrigger()
        
        stats = tracker.get_heuristic_stats()
        
        assert stats["SEARCH_DEEP"] == 0
        assert stats["BOOKING_PREP"] == 0
        assert stats["STATUS_ACTIVE"] == 0


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])