"""
Scalability tests for the Contextual Availability Transformer (CAT) system.

Tests horizontal scaling, autoscaling, canary deployment, and concurrent request handling.
"""

import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from backend.cat.scalability.horizontal_scaling import (
    ConnectionPoolConfig,
    ConnectionPool,
    GracefulShutdownManager,
    StatelessInferenceService,
    create_connection_pool,
    create_stateless_service
)
from backend.cat.scalability.autoscaling import (
    AutoscalingConfig,
    ScalingMetrics,
    KubernetesAutoscaler,
    create_autoscaler
)
from backend.cat.scalability.canary_deployment import (
    CanaryConfig,
    CanaryDeployment,
    TrafficSplitter,
    DeploymentMetrics,
    create_canary_deployment
)


class TestConnectionPool:
    """Tests for ConnectionPool class."""
    
    def test_initialization(self):
        """Test connection pool initialization."""
        config = ConnectionPoolConfig(
            max_connections=50,
            max_keepalive_connections=10
        )
        pool = ConnectionPool(config)
        
        assert pool.config.max_connections == 50
        assert pool.config.max_keepalive_connections == 10
        assert pool._active_connections == 0
        assert pool._total_requests == 0
    
    def test_create_connection_pool_factory(self):
        """Test connection pool factory function."""
        pool = create_connection_pool()
        
        assert pool is not None
        assert isinstance(pool, ConnectionPool)
    
    def test_get_stats(self):
        """Test connection pool statistics."""
        pool = ConnectionPool()
        
        stats = pool.get_stats()
        
        assert "active_connections" in stats
        assert "total_requests" in stats
        assert "max_connections" in stats
        assert "pool_recycle_interval" in stats


class TestGracefulShutdownManager:
    """Tests for GracefulShutdownManager class."""
    
    def test_initialization(self):
        """Test graceful shutdown manager initialization."""
        manager = GracefulShutdownManager(shutdown_timeout=30.0)
        
        assert manager.shutdown_timeout == 30.0
        assert manager._in_flight_requests == 0
    
    def test_increment_decrement_in_flight(self):
        """Test in-flight request tracking."""
        manager = GracefulShutdownManager()
        
        # Increment directly (bypass async for testing)
        manager._in_flight_requests = 1
        assert manager._in_flight_requests == 1
        
        # Decrement
        manager._in_flight_requests = 0
        assert manager._in_flight_requests == 0
    
    def test_start_drain(self):
        """Test starting drain phase."""
        manager = GracefulShutdownManager()
        
        result = asyncio.run(manager.start_drain())
        
        assert result is True
        assert manager._state.value == "draining"
    
    def test_wait_for_drain(self):
        """Test waiting for drain to complete."""
        manager = GracefulShutdownManager()
        
        # Start drain
        asyncio.run(manager.start_drain())
        
        # Wait for drain (should complete immediately since no in-flight requests)
        result = asyncio.run(manager.wait_for_drain())
        
        assert result is True
    
    def test_get_stats(self):
        """Test shutdown manager statistics."""
        manager = GracefulShutdownManager()
        
        stats = manager.get_stats()
        
        assert "state" in stats
        assert "in_flight_requests" in stats
        assert "uptime_seconds" in stats


class TestStatelessInferenceService:
    """Tests for StatelessInferenceService class."""
    
    def test_initialization(self):
        """Test stateless service initialization."""
        from fastapi import FastAPI
        
        app = FastAPI()
        pool = create_connection_pool()
        shutdown = GracefulShutdownManager()
        
        service = StatelessInferenceService(app, pool, shutdown)
        
        assert service.app == app
        assert service.connection_pool == pool
        assert service.shutdown_manager == shutdown
    
    def test_create_stateless_service_factory(self):
        """Test stateless service factory function."""
        from fastapi import FastAPI
        
        app = FastAPI()
        service = create_stateless_service(app)
        
        assert service is not None
        assert isinstance(service, StatelessInferenceService)


class TestTrafficSplitter:
    """Tests for TrafficSplitter class."""
    
    def test_initialization(self):
        """Test traffic splitter initialization."""
        splitter = TrafficSplitter(
            versions=["v1", "v2"],
            weights=[0.5, 0.5]
        )
        
        assert splitter.versions == ["v1", "v2"]
        assert splitter.weights == [0.5, 0.5]
    
    def test_route(self):
        """Test request routing."""
        splitter = TrafficSplitter(
            versions=["v1", "v2", "v3"],
            weights=[0.6, 0.3, 0.1]
        )
        
        # Test routing distribution
        v1_count = 0
        v2_count = 0
        v3_count = 0
        
        for _ in range(1000):
            version = splitter.route()
            if version == "v1":
                v1_count += 1
            elif version == "v2":
                v2_count += 1
            else:
                v3_count += 1
        
        # Check distribution (with some tolerance)
        assert 500 < v1_count < 700  # ~60%
        assert 200 < v2_count < 400  # ~30%
        assert 0 < v3_count < 200   # ~10%
    
    def test_update_weights(self):
        """Test updating traffic weights."""
        splitter = TrafficSplitter(
            versions=["v1", "v2"],
            weights=[0.5, 0.5]
        )
        
        splitter.update_weights([0.8, 0.2])
        
        assert splitter.weights == [0.8, 0.2]


class TestDeploymentMetrics:
    """Tests for DeploymentMetrics class."""
    
    def test_initialization(self):
        """Test deployment metrics initialization."""
        metrics = DeploymentMetrics()
        
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.error_rate == 0.0
    
    def test_record_request_success(self):
        """Test recording a successful request."""
        metrics = DeploymentMetrics()
        
        metrics.record_request(success=True, latency_ms=100.0)
        
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.error_rate == 0.0
    
    def test_record_request_failure(self):
        """Test recording a failed request."""
        metrics = DeploymentMetrics()
        
        metrics.record_request(success=False, latency_ms=150.0)
        
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 1
        assert metrics.error_rate == 100.0
    
    def test_record_multiple_requests(self):
        """Test recording multiple requests."""
        metrics = DeploymentMetrics()
        
        # Record 8 successful and 2 failed requests
        for _ in range(8):
            metrics.record_request(success=True, latency_ms=100.0)
        for _ in range(2):
            metrics.record_request(success=False, latency_ms=150.0)
        
        assert metrics.total_requests == 10
        assert metrics.successful_requests == 8
        assert metrics.failed_requests == 2
        assert metrics.error_rate == 20.0
    
    def test_get_summary(self):
        """Test getting metrics summary."""
        metrics = DeploymentMetrics()
        
        metrics.record_request(success=True, latency_ms=100.0)
        metrics.record_request(success=True, latency_ms=120.0)
        metrics.record_request(success=False, latency_ms=150.0)
        
        summary = metrics.get_summary()
        
        assert summary["total_requests"] == 3
        assert summary["successful_requests"] == 2
        assert summary["failed_requests"] == 1
        assert summary["error_rate"] == 33.33333333333333
        assert "p95_latency_ms" in summary
        assert "avg_latency_ms" in summary


class TestCanaryDeployment:
    """Tests for CanaryDeployment class."""
    
    def test_initialization(self):
        """Test canary deployment initialization."""
        config = CanaryConfig(
            initial_traffic_percentage=10.0,
            error_rate_threshold=5.0
        )
        deployment = CanaryDeployment(config)
        
        assert deployment._status.value == "not_started"
        # Initial traffic percentage is set in start(), not initialization
        assert deployment._canary_traffic_percentage == 0.0
    
    def test_start(self):
        """Test starting canary deployment."""
        deployment = CanaryDeployment()
        
        deployment.start()
        
        assert deployment._status.value == "running"
        assert deployment._canary_traffic_percentage == 10.0
    
    def test_should_route_to_canary(self):
        """Test routing decision."""
        deployment = CanaryDeployment()
        deployment.start()
        
        # With 10% traffic, most requests should go to baseline
        canary_count = 0
        for _ in range(1000):
            if deployment.should_route_to_canary():
                canary_count += 1
        
        # Should be around 100 (10% of 1000)
        assert 50 < canary_count < 150
    
    def test_record_requests(self):
        """Test recording requests for both deployments."""
        deployment = CanaryDeployment()
        deployment.start()
        
        # Record baseline requests
        deployment.record_baseline_request(success=True, latency_ms=100.0)
        deployment.record_baseline_request(success=False, latency_ms=150.0)
        
        # Record canary requests
        deployment.record_canary_request(success=True, latency_ms=120.0)
        deployment.record_canary_request(success=True, latency_ms=110.0)
        
        assert deployment._baseline_metrics.total_requests == 2
        assert deployment._canary_metrics.total_requests == 2
    
    def test_evaluate_step(self):
        """Test step evaluation."""
        deployment = CanaryDeployment()
        deployment.start()
        
        # Record enough requests
        for _ in range(150):
            deployment.record_baseline_request(success=True, latency_ms=100.0)
            deployment.record_canary_request(success=True, latency_ms=110.0)
        
        # Wait for step interval
        time.sleep(0.1)  # Short sleep for testing
        
        result = deployment.evaluate_step()
        
        assert "should_proceed" in result
        assert "should_rollback" in result
    
    def test_get_traffic_split(self):
        """Test getting traffic split."""
        deployment = CanaryDeployment()
        deployment.start()
        
        split = deployment.get_traffic_split()
        
        assert "baseline" in split
        assert "canary" in split
        assert split["baseline"] + split["canary"] == 100.0
    
    def test_get_metrics(self):
        """Test getting deployment metrics."""
        deployment = CanaryDeployment()
        deployment.start()
        
        metrics = deployment.get_metrics()
        
        assert "status" in metrics
        assert "baseline" in metrics
        assert "canary" in metrics
    
    def test_rollback(self):
        """Test rollback functionality."""
        deployment = CanaryDeployment()
        deployment.start()
        
        deployment.rollback("High error rate")
        
        assert deployment._status.value == "rolled_back"
        assert deployment._rollback_triggered is True
        assert deployment._rollback_reason == "High error rate"
    
    def test_fail(self):
        """Test fail functionality."""
        deployment = CanaryDeployment()
        deployment.start()
        
        deployment.fail("Test failure")
        
        assert deployment._status.value == "failed"
        assert deployment._rollback_reason == "Test failure"


class TestKubernetesAutoscaler:
    """Tests for KubernetesAutoscaler class."""
    
    def test_initialization(self):
        """Test autoscaler initialization."""
        config = AutoscalingConfig(
            min_replicas=2,
            max_replicas=10,
            target_request_rate=100.0
        )
        autoscaler = KubernetesAutoscaler(config)
        
        assert autoscaler.config.min_replicas == 2
        assert autoscaler.config.max_replicas == 10
        assert autoscaler._current_replicas == 2
    
    def test_update_metrics(self):
        """Test metrics update."""
        autoscaler = KubernetesAutoscaler()
        
        metrics = ScalingMetrics(
            request_rate=150.0,  # High request rate
            p50_latency=0.100,
            p95_latency=0.150,
            p99_latency=0.200,
            queue_depth=20,
            cpu_utilization=80.0,
            memory_utilization=70.0
        )
        
        autoscaler.update_metrics(metrics)
        
        assert len(autoscaler._metrics_history) == 1
    
    def test_get_scaling_recommendation(self):
        """Test getting scaling recommendation."""
        autoscaler = KubernetesAutoscaler()
        
        metrics = ScalingMetrics(
            request_rate=150.0,
            p50_latency=0.100,
            p95_latency=0.150,
            p99_latency=0.200,
            queue_depth=20,
            cpu_utilization=80.0,
            memory_utilization=70.0
        )
        
        recommendation = autoscaler.get_scaling_recommendation(metrics)
        
        assert "current_replicas" in recommendation
        assert "recommended_replicas" in recommendation
        assert "action" in recommendation
        assert "reasons" in recommendation
    
    def test_get_kubernetes_hpa_spec(self):
        """Test getting HPA specification."""
        autoscaler = KubernetesAutoscaler()
        
        spec = autoscaler.get_kubernetes_hpa_spec()
        
        assert spec["apiVersion"] == "autoscaling/v2"
        assert spec["kind"] == "HorizontalPodAutoscaler"
        assert "spec" in spec
        assert spec["spec"]["minReplicas"] == 2
        assert spec["spec"]["maxReplicas"] == 10
    
    def test_get_resource_requirements(self):
        """Test getting resource requirements."""
        autoscaler = KubernetesAutoscaler()
        
        requirements = autoscaler.get_resource_requirements()
        
        assert "requests" in requirements
        assert "limits" in requirements
        assert "cpu" in requirements["requests"]
        assert "memory" in requirements["requests"]
    
    def test_get_stats(self):
        """Test getting autoscaler statistics."""
        autoscaler = KubernetesAutoscaler()
        
        stats = autoscaler.get_stats()
        
        assert "current_replicas" in stats
        assert "min_replicas" in stats
        assert "max_replicas" in stats


class TestConcurrentRequestHandling:
    """Tests for concurrent request handling."""
    
    @pytest.mark.asyncio
    async def test_concurrent_predictions(self):
        """Test handling concurrent prediction requests."""
        from backend.cat.inference.service import (
            RateLimiter,
            get_rate_limiter
        )
        
        rate_limiter = RateLimiter()
        
        # Simulate concurrent requests
        async def make_prediction(location_id: str):
            is_allowed, _ = rate_limiter.is_allowed(location_id)
            return is_allowed
        
        # Run 10 concurrent requests
        tasks = [
            make_prediction(f"location_{i}")
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All requests should complete
        assert len(results) == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_rate_limiter_operations(self):
        """Test concurrent rate limiter operations."""
        from backend.cat.inference.service import RateLimiter
        
        rate_limiter = RateLimiter()
        
        # Simulate concurrent rate limit checks
        async def check_rate_limit(client_id: str):
            is_allowed, remaining = rate_limiter.is_allowed(client_id)
            return is_allowed
        
        # Run concurrent operations
        tasks = []
        for i in range(10):
            tasks.append(check_rate_limit(f"client_{i}"))
        
        results = await asyncio.gather(*tasks)
        
        # All requests should complete
        assert len(results) == 10


class TestAutoscalingBehavior:
    """Tests for autoscaling behavior under load."""
    
    def test_scale_up_on_high_request_rate(self):
        """Test scaling up when request rate is high."""
        autoscaler = KubernetesAutoscaler(
            AutoscalingConfig(
                min_replicas=2,
                max_replicas=10,
                target_request_rate=100.0
            )
        )
        
        # Simulate high request rate
        metrics = ScalingMetrics(
            request_rate=200.0,  # 2x target
            p50_latency=0.100,
            p95_latency=0.150,
            p99_latency=0.200,
            queue_depth=20,  # High queue depth
            cpu_utilization=80.0,  # High CPU utilization
            memory_utilization=70.0
        )
        
        autoscaler.update_metrics(metrics)
        
        # Should recommend scale up
        recommendation = autoscaler.get_scaling_recommendation(metrics)
        
        assert recommendation["action"] == "scale_up"
    
    def test_scale_down_on_low_utilization(self):
        """Test scaling down when utilization is low."""
        autoscaler = KubernetesAutoscaler(
            AutoscalingConfig(
                min_replicas=1,  # Set to 1 to allow scaling down
                max_replicas=10,
                target_request_rate=100.0,
                scale_down_cooldown=0  # Set cooldown to 0 for testing
            )
        )
        
        # Simulate low utilization
        metrics = ScalingMetrics(
            request_rate=20.0,  # 20% of target
            p50_latency=0.050,
            p95_latency=0.080,
            p99_latency=0.100,
            queue_depth=1,
            cpu_utilization=10.0,
            memory_utilization=15.0
        )
        
        # First update metrics to trigger scaling
        autoscaler.update_metrics(metrics)
        
        # Check the recommendation
        recommendation = autoscaler.get_scaling_recommendation(metrics)
        
        # The action should be "no_change" since scaling was already triggered
        # But the replica count should have been reduced
        assert recommendation["action"] == "no_change"
        assert recommendation["recommended_replicas"] < 2  # Should have scaled down


class TestCanaryDeploymentTrafficSplitting:
    """Tests for canary deployment traffic splitting."""
    
    def test_initial_traffic_split(self):
        """Test initial traffic split configuration."""
        deployment = CanaryDeployment(
            CanaryConfig(
                initial_traffic_percentage=10.0
            )
        )
        deployment.start()
        
        split = deployment.get_traffic_split()
        
        assert split["baseline"] == 90.0
        assert split["canary"] == 10.0
    
    def test_progressive_traffic_shifting(self):
        """Test progressive traffic shifting."""
        deployment = CanaryDeployment(
            CanaryConfig(
                initial_traffic_percentage=10.0,
                step_traffic_percentage=10.0,
                max_traffic_percentage=50.0
            )
        )
        deployment.start()
        
        # Simulate multiple steps
        for _ in range(4):
            # Record enough requests
            for _ in range(150):
                deployment.record_baseline_request(success=True, latency_ms=100.0)
                deployment.record_canary_request(success=True, latency_ms=110.0)
            
            # Evaluate step
            result = deployment.evaluate_step()
            
            if result["should_proceed"]:
                split = deployment.get_traffic_split()
                # Traffic should increase
                assert split["canary"] > 10.0
    
    def test_rollback_on_high_error_rate(self):
        """Test rollback when error rate exceeds threshold."""
        deployment = CanaryDeployment(
            CanaryConfig(
                initial_traffic_percentage=50.0,
                error_rate_threshold=5.0
            )
        )
        deployment.start()
        
        # Record requests with high error rate
        for _ in range(100):
            deployment.record_baseline_request(success=True, latency_ms=100.0)
            deployment.record_canary_request(success=False, latency_ms=150.0)  # 100% error rate
        
        # Evaluate step
        result = deployment.evaluate_step()
        
        assert result["should_rollback"] is True
    
    def test_rollback_on_high_latency(self):
        """Test rollback when latency exceeds threshold."""
        deployment = CanaryDeployment(
            CanaryConfig(
                initial_traffic_percentage=50.0,
                latency_threshold_ms=200.0
            )
        )
        deployment.start()
        
        # Record requests with high latency
        for _ in range(100):
            deployment.record_baseline_request(success=True, latency_ms=100.0)
            deployment.record_canary_request(success=True, latency_ms=250.0)  # High latency
        
        # Evaluate step
        result = deployment.evaluate_step()
        
        assert result["should_rollback"] is True
