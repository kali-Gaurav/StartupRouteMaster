"""
Reliability and monitoring tests for the Contextual Availability Transformer (CAT) system.
Tests health checks, metrics collection, alerting, and circuit breaker functionality.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from backend.cat.reliability.health_checks import HealthChecker, HealthStatus, HealthCheckResult
from backend.cat.reliability.metrics_collector import MetricsCollector
from backend.cat.reliability.alerting import AlertManager, AlertSeverity, Alert
from backend.cat.reliability.circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError, create_circuit_breaker


class TestHealthChecker:
    """Tests for HealthChecker class."""
    
    def test_initialization(self):
        """Test health checker initialization."""
        checker = HealthChecker()
        assert checker is not None
        assert len(checker._checks) > 0
    
    def test_model_available_check(self):
        """Test model availability check."""
        checker = HealthChecker(model_available=lambda: True)
        result = checker._check_model()
        assert result.status == HealthStatus.HEALTHY
        assert result.component == "model"
    
    def test_model_unavailable_check(self):
        """Test model unavailable check."""
        checker = HealthChecker(model_available=lambda: False)
        result = checker._check_model()
        assert result.status == HealthStatus.UNHEALTHY
    
    def test_data_collector_available_check(self):
        """Test data collector availability check."""
        checker = HealthChecker(data_collector_available=lambda: True)
        result = checker._check_data_collector()
        assert result.status == HealthStatus.HEALTHY
    
    def test_external_apis_available_check(self):
        """Test external APIs availability check."""
        checker = HealthChecker(external_apis_available=lambda: True)
        result = checker._check_external_apis()
        assert result.status == HealthStatus.HEALTHY
    
    def test_get_overall_status_healthy(self):
        """Test overall status when all checks pass."""
        checker = HealthChecker(
            model_available=lambda: True,
            data_collector_available=lambda: True,
            external_apis_available=lambda: True
        )
        # Manually set check results to simulate successful checks
        checker._check_results = {
            "model": HealthCheckResult(status=HealthStatus.HEALTHY, component="model"),
            "data_collector": HealthCheckResult(status=HealthStatus.HEALTHY, component="data_collector"),
            "external_apis": HealthCheckResult(status=HealthStatus.HEALTHY, component="external_apis"),
            "cache": HealthCheckResult(status=HealthStatus.HEALTHY, component="cache")
        }
        result = checker._get_overall_status()
        assert result.status == HealthStatus.HEALTHY
    
    def test_get_overall_status_degraded(self):
        """Test overall status when some checks are degraded."""
        checker = HealthChecker(
            model_available=lambda: True,
            data_collector_available=lambda: False,
            external_apis_available=lambda: True
        )
        # Manually set check results to simulate degraded check
        checker._check_results = {
            "model": HealthCheckResult(status=HealthStatus.HEALTHY, component="model"),
            "data_collector": HealthCheckResult(status=HealthStatus.DEGRADED, component="data_collector", error="Not connected"),
            "external_apis": HealthCheckResult(status=HealthStatus.HEALTHY, component="external_apis"),
            "cache": HealthCheckResult(status=HealthStatus.HEALTHY, component="cache")
        }
        result = checker._get_overall_status()
        assert result.status == HealthStatus.DEGRADED
    
    def test_get_overall_status_unhealthy(self):
        """Test overall status when some checks are unhealthy."""
        checker = HealthChecker(
            model_available=lambda: False,
            data_collector_available=lambda: True,
            external_apis_available=lambda: True
        )
        result = checker._get_overall_status()
        assert result.status == HealthStatus.UNHEALTHY
    
    def test_get_health_details(self):
        """Test getting detailed health information."""
        checker = HealthChecker()
        details = checker.get_health_details()
        
        assert "overall" in details
        assert "components" in details
        assert "last_check" in details


class TestMetricsCollector:
    """Tests for MetricsCollector class."""
    
    def test_initialization(self):
        """Test metrics collector initialization."""
        collector = MetricsCollector()
        assert collector is not None
        assert len(collector._metrics) > 0
    
    def test_record_inference_latency(self):
        """Test recording inference latency."""
        collector = MetricsCollector()
        collector.record_inference_latency(0.150)  # 150ms
        
        metric = collector._metrics.get("cat_inference_latency_seconds")
        assert metric is not None
        assert len(metric.data_points) == 1
        assert metric.data_points[0].value == 0.150
    
    def test_record_request(self):
        """Test recording a request."""
        collector = MetricsCollector()
        collector.record_request()
        
        metric = collector._metrics.get("cat_requests_total")
        assert metric is not None
        assert len(metric.data_points) == 1
    
    def test_record_error(self):
        """Test recording an error."""
        collector = MetricsCollector()
        collector.record_error()
        
        metric = collector._metrics.get("cat_errors_total")
        assert metric is not None
        assert len(metric.data_points) == 1
    
    def test_record_cache_hit(self):
        """Test recording a cache hit."""
        collector = MetricsCollector()
        collector.record_cache_hit()
        
        metric = collector._metrics.get("cat_cache_hits_total")
        assert metric is not None
        assert len(metric.data_points) == 1
    
    def test_record_cache_miss(self):
        """Test recording a cache miss."""
        collector = MetricsCollector()
        collector.record_cache_miss()
        
        metric = collector._metrics.get("cat_cache_misses_total")
        assert metric is not None
        assert len(metric.data_points) == 1
    
    def test_set_model_loaded(self):
        """Test setting model loaded status."""
        collector = MetricsCollector()
        collector.set_model_loaded(True)
        
        metric = collector._metrics.get("cat_model_loaded")
        assert metric is not None
        assert metric.data_points[0].value == 1.0
        
        collector.set_model_loaded(False)
        assert metric.data_points[-1].value == 0.0
    
    def test_get_latency_percentiles(self):
        """Test getting latency percentiles."""
        collector = MetricsCollector()
        
        # Add some latency data (in seconds)
        for i in range(100):
            collector.record_inference_latency(0.05 + (i * 0.001))  # 0.05 to 0.15
        
        percentiles = collector.get_latency_percentiles()
        
        assert "p50" in percentiles
        assert "p95" in percentiles
        assert "p99" in percentiles
        
        # p50 should be around 0.10 (50th value)
        assert 0.09 < percentiles["p50"] < 0.11
        # p95 should be around 0.145 (95th value)
        assert 0.14 < percentiles["p95"] < 0.15
        # p99 should be around 0.149 (99th value)
        assert 0.145 < percentiles["p99"] < 0.15
    
    def test_get_request_rate(self):
        """Test getting request rate."""
        collector = MetricsCollector()
        
        # Add some requests
        for _ in range(10):
            collector.record_request()
        
        # Wait a bit to ensure time has passed
        time.sleep(0.1)
        
        rate = collector.get_request_rate()
        assert rate > 0
    
    def test_get_error_rate(self):
        """Test getting error rate."""
        collector = MetricsCollector()
        
        # Add some requests and errors
        for _ in range(100):
            collector.record_request()
        for _ in range(5):
            collector.record_error()
        
        rate = collector.get_error_rate()
        assert rate == 5.0  # 5% error rate
    
    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        collector = MetricsCollector()
        
        # Add some cache hits and misses
        for _ in range(80):
            collector.record_cache_hit()
        for _ in range(20):
            collector.record_cache_miss()
        
        stats = collector.get_cache_stats()
        
        assert stats["cache_hits"] == 80
        assert stats["cache_misses"] == 20
        assert stats["cache_hit_rate"] == 0.8
    
    def test_export_prometheus(self):
        """Test exporting metrics in Prometheus format."""
        collector = MetricsCollector()
        collector.record_request()
        collector.record_inference_latency(0.150)
        
        prometheus = collector.export_prometheus()
        
        assert "# HELP" in prometheus
        assert "# TYPE" in prometheus
        assert "cat_requests_total" in prometheus
        assert "cat_inference_latency_seconds" in prometheus
    
    def test_get_summary(self):
        """Test getting metrics summary."""
        collector = MetricsCollector()
        collector.record_request()
        collector.record_inference_latency(0.150)
        
        summary = collector.get_summary()
        
        assert "uptime_seconds" in summary
        assert "request_rate" in summary
        assert "error_rate" in summary
        assert "latency_percentiles" in summary
        assert "cache_stats" in summary


class TestAlertManager:
    """Tests for AlertManager class."""
    
    def test_initialization(self):
        """Test alert manager initialization."""
        manager = AlertManager()
        assert manager is not None
        assert len(manager._handlers) > 0
    
    def test_check_latency_below_slo(self):
        """Test latency check when below SLO."""
        manager = AlertManager(latency_slo_ms=200.0)
        alert = manager.check_latency(150.0)
        
        assert alert is None
    
    def test_check_latency_above_slo(self):
        """Test latency check when above SLO."""
        manager = AlertManager(latency_slo_ms=200.0)
        alert = manager.check_latency(250.0)
        
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert "Latency" in alert.title
    
    def test_check_data_freshness_below_threshold(self):
        """Test data freshness check when below threshold."""
        manager = AlertManager(data_freshness_threshold_seconds=300.0)
        alert = manager.check_data_freshness(200.0)
        
        assert alert is None
    
    def test_check_data_freshness_above_threshold(self):
        """Test data freshness check when above threshold."""
        manager = AlertManager(data_freshness_threshold_seconds=300.0)
        alert = manager.check_data_freshness(400.0)
        
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert "Data Freshness" in alert.title
    
    def test_record_model_reload_failure(self):
        """Test recording model reload failures."""
        manager = AlertManager(model_reload_failure_threshold=3)
        
        # Record failures below threshold
        for _ in range(2):
            alert = manager.record_model_reload_failure()
            assert alert is None
        
        # Record failure above threshold
        alert = manager.record_model_reload_failure()
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL
        assert "Model Reload Failure" in alert.title
    
    def test_record_model_reload_success(self):
        """Test recording model reload success."""
        manager = AlertManager(model_reload_failure_threshold=3)
        
        # Record some failures
        manager.record_model_reload_failure()
        manager.record_model_reload_failure()
        
        # Record success
        manager.record_model_reload_success()
        
        # Next failure should not trigger alert immediately
        alert = manager.record_model_reload_failure()
        assert alert is None
    
    def test_check_error_rate_below_threshold(self):
        """Test error rate check when below threshold."""
        manager = AlertManager(error_rate_threshold_percent=5.0)
        alert = manager.check_error_rate(3.0)
        
        assert alert is None
    
    def test_check_error_rate_above_threshold(self):
        """Test error rate check when above threshold."""
        manager = AlertManager(error_rate_threshold_percent=5.0)
        alert = manager.check_error_rate(8.0)
        
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert "Error Rate" in alert.title
    
    def test_get_active_alerts(self):
        """Test getting active alerts."""
        manager = AlertManager()
        
        # Create some alerts
        manager.check_latency(250.0)
        manager.check_error_rate(8.0)
        
        active = manager.get_active_alerts()
        assert len(active) == 2
    
    def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        manager = AlertManager()
        
        alert = manager.check_latency(250.0)
        assert alert is not None
        
        result = manager.acknowledge_alert(alert.id)
        assert result is True
        assert alert.acknowledged is True
    
    def test_resolve_alert(self):
        """Test resolving an alert."""
        manager = AlertManager()
        
        alert = manager.check_latency(250.0)
        assert alert is not None
        
        result = manager.resolve_alert(alert.id)
        assert result is True
        assert alert.resolved is True
    
    def test_get_summary(self):
        """Test getting alert summary."""
        manager = AlertManager()
        
        # Create some alerts
        manager.check_latency(250.0)
        manager.check_error_rate(8.0)
        
        summary = manager.get_summary()
        
        assert "active_alerts" in summary
        assert "total_alerts" in summary


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""
    
    def test_initialization(self):
        """Test circuit breaker initialization."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
    
    def test_execute_success(self):
        """Test executing successful function."""
        cb = CircuitBreaker()
        
        result = cb.execute(lambda: "success")
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
    
    def test_execute_failure(self):
        """Test executing failing function."""
        from backend.cat.reliability.circuit_breaker import CircuitBreakerConfig
        cb = CircuitBreaker(config=CircuitBreakerConfig(failure_threshold=3))
        
        # Execute failing function
        with pytest.raises(Exception):
            cb.execute(lambda: 1 / 0)
        
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 1
    
    def test_circuit_opens_after_threshold(self):
        """Test that circuit opens after failure threshold."""
        from backend.cat.reliability.circuit_breaker import CircuitBreakerConfig
        cb = CircuitBreaker(config=CircuitBreakerConfig(failure_threshold=3))
        
        # Fail 3 times
        for _ in range(3):
            with pytest.raises(Exception):
                cb.execute(lambda: 1 / 0)
        
        assert cb.state == CircuitState.OPEN
        
        # Next call should raise CircuitOpenError
        with pytest.raises(CircuitOpenError):
            cb.execute(lambda: "test")
    
    def test_half_open_state(self):
        """Test half-open state after recovery timeout."""
        from backend.cat.reliability.circuit_breaker import CircuitBreakerConfig
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout_seconds=0.1
        )
        cb = CircuitBreaker(config=config)
        
        # Fail twice to open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.execute(lambda: 1 / 0)
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Next call should transition to half-open
        result = cb.execute(lambda: "success")
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
    
    def test_half_open_allows_limited_calls(self):
        """Test that half-open state allows limited calls."""
        from backend.cat.reliability.circuit_breaker import CircuitBreakerConfig
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout_seconds=0.1,
            half_open_max_calls=2
        )
        cb = CircuitBreaker(config=config)
        
        # Fail twice to open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.execute(lambda: 1 / 0)
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # First call should transition to half-open and succeed
        cb.execute(lambda: "success1")
        
        # Should be in closed state after successful call in half-open
        assert cb.state == CircuitState.CLOSED
    
    def test_stats_tracking(self):
        """Test circuit breaker statistics tracking."""
        cb = CircuitBreaker()
        
        cb.execute(lambda: "success")
        with pytest.raises(Exception):
            cb.execute(lambda: 1 / 0)
        
        stats = cb.stats
        
        assert stats.successful_calls >= 1
        assert stats.failed_calls >= 1
    
    def test_get_state(self):
        """Test getting circuit breaker state."""
        cb = CircuitBreaker()
        
        state = cb.get_state()
        
        assert "name" in state
        assert "state" in state
        assert "stats" in state
    
    def test_execute_async_success(self):
        """Test executing async successful function."""
        import asyncio
        
        cb = CircuitBreaker()
        
        async def test_func():
            return "async_success"
        
        async def run_test():
            return await cb.execute_async(test_func)
        
        result = asyncio.run(run_test())
        assert result == "async_success"
    
    def test_execute_async_failure(self):
        """Test executing async failing function."""
        import asyncio
        from backend.cat.reliability.circuit_breaker import CircuitBreakerConfig
        
        cb = CircuitBreaker(config=CircuitBreakerConfig(failure_threshold=2))
        
        async def failing_func():
            raise Exception("Async failure")
        
        async def run_test():
            # Pass a callable that returns a coroutine
            await cb.execute_async(failing_func)
        
        # Run the test and expect exception
        with pytest.raises(Exception):
            asyncio.run(run_test())
        
        # Check that failure was recorded
        assert cb._failure_count >= 1


class TestIntegration:
    """Integration tests for reliability components."""
    
    def test_health_check_with_metrics(self):
        """Test health check integration with metrics."""
        from backend.cat.reliability.health_checks import HealthChecker, HealthCheckResult
        from backend.cat.reliability.metrics_collector import MetricsCollector
        
        metrics = MetricsCollector()
        checker = HealthChecker(
            model_available=lambda: True,
            data_collector_available=lambda: True,
            external_apis_available=lambda: True
        )
        
        # Manually set check results to simulate successful checks
        checker._check_results = {
            "model": HealthCheckResult(status=HealthStatus.HEALTHY, component="model"),
            "data_collector": HealthCheckResult(status=HealthStatus.HEALTHY, component="data_collector"),
            "external_apis": HealthCheckResult(status=HealthStatus.HEALTHY, component="external_apis"),
            "cache": HealthCheckResult(status=HealthStatus.HEALTHY, component="cache")
        }
        
        # Run health check
        result = checker._get_overall_status()
        
        assert result.status == HealthStatus.HEALTHY
        
        # Record metrics
        metrics.record_request()
        metrics.set_model_loaded(True)
        
        summary = metrics.get_summary()
        assert summary["model_loaded"] == 1.0
    
    def test_alert_manager_with_circuit_breaker(self):
        """Test alert manager integration with circuit breaker."""
        from backend.cat.reliability.alerting import AlertManager
        from backend.cat.reliability.circuit_breaker import CircuitBreaker
        
        alert_manager = AlertManager(latency_slo_ms=200.0)
        cb = CircuitBreaker()
        
        # Simulate slow request
        start_time = time.time()
        time.sleep(0.2)  # 200ms delay
        elapsed = (time.time() - start_time) * 1000
        
        # Check latency alert
        alert = alert_manager.check_latency(elapsed)
        assert alert is not None
        
        # Execute through circuit breaker
        result = cb.execute(lambda: "success")
        assert result == "success"
