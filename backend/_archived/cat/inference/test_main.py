"""
Tests for the CAT inference service FastAPI application.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from cat.inference.main import create_app, app
from cat.inference.config import InferenceSettings


@pytest.fixture
def test_settings():
    """Create test settings."""
    return InferenceSettings(
        host="0.0.0.0",
        port=8000,
        workers=1,
        debug=True,
        cors_origins=["*"],
        log_level="DEBUG",
        log_request_enabled=True,
        log_response_enabled=True,
        log_request_timing=True,
        metrics_enabled=True,
        rate_limit_enabled=False
    )


@pytest.fixture
def client(test_settings):
    """Create test client."""
    app = create_app(test_settings)
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "CAT Inference Service"
    assert data["version"] == "1.0.0"
    assert data["status"] == "running"


def test_service_info_endpoint(client):
    """Test service info endpoint."""
    response = client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Contextual Availability Transformer"
    assert "endpoints" in data


def test_health_check_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "model_loaded" in data
    assert "uptime_seconds" in data
    assert "predictions_count" in data
    assert "timestamp" in data


def test_liveness_check_endpoint(client):
    """Test liveness check endpoint."""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


def test_readiness_check_endpoint(client):
    """Test readiness check endpoint."""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "model_loaded" in data
    assert "checks" in data


def test_metrics_endpoint(client):
    """Test metrics endpoint."""
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "uptime_seconds" in data
    assert "predictions_count" in data
    assert "model_loaded" in data
    assert "timestamp" in data


def test_health_details_endpoint(client):
    """Test health details endpoint."""
    response = client.get("/api/v1/health/details")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "model" in data
    assert "predictions" in data
    assert "checks" in data


def test_cors_headers(client):
    """Test CORS headers are set correctly."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type"
        }
    )
    # CORS preflight should succeed
    assert response.status_code in [200, 204]


def test_response_time_header(client):
    """Test response time header is added."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    # Response time header should be present
    assert "X-Response-Time-Ms" in response.headers


def test_invalid_path_returns_404(client):
    """Test invalid path returns 404."""
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404


def test_health_response_model():
    """Test health response model validation."""
    from cat.inference.routes.health import HealthResponse
    
    response = HealthResponse(
        status="healthy",
        model_loaded=True,
        uptime_seconds=100.5,
        predictions_count=50,
        last_prediction_time=datetime.utcnow().isoformat(),
        timestamp=datetime.utcnow().isoformat()
    )
    
    assert response.status == "healthy"
    assert response.model_loaded is True
    assert response.uptime_seconds == 100.5
    assert response.predictions_count == 50


def test_readiness_response_model():
    """Test readiness response model validation."""
    from cat.inference.routes.health import ReadinessResponse
    
    response = ReadinessResponse(
        status="ready",
        model_loaded=True,
        checks={"model_loaded": True}
    )
    
    assert response.status == "ready"
    assert response.model_loaded is True


def test_liveness_response_model():
    """Test liveness response model validation."""
    from cat.inference.routes.health import LivenessResponse
    
    response = LivenessResponse(
        status="alive",
        timestamp=datetime.utcnow().isoformat()
    )
    
    assert response.status == "alive"


def test_inference_settings_defaults():
    """Test inference settings have correct defaults."""
    settings = InferenceSettings()
    
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.workers == 4
    assert settings.debug is False
    assert settings.cors_origins == ["*"]
    assert settings.log_level == "INFO"
    assert settings.metrics_enabled is True
    assert settings.rate_limit_enabled is True
    assert settings.rate_limit_requests_per_minute == 100


def test_inference_settings_env_override(monkeypatch):
    """Test inference settings can be overridden by environment variables."""
    monkeypatch.setenv("CAT_INFERENCE_HOST", "127.0.0.1")
    monkeypatch.setenv("CAT_INFERENCE_PORT", "9000")
    monkeypatch.setenv("CAT_INFERENCE_LOG_LEVEL", "DEBUG")
    
    # Create new settings to pick up env vars
    settings = InferenceSettings()
    
    assert settings.host == "127.0.0.1"
    assert settings.port == 9000
    assert settings.log_level == "DEBUG"


def test_request_logging_middleware():
    """Test request logging middleware can be instantiated."""
    from cat.inference.middleware import RequestLoggingMiddleware
    
    middleware = RequestLoggingMiddleware(
        app=None,  # We don't need a real app for this test
        log_request=True,
        log_response=True,
        log_request_timing=True
    )
    
    assert middleware.log_request is True
    assert middleware.log_response is True
    assert middleware.log_request_timing is True


def test_request_timing_middleware():
    """Test request timing middleware can be instantiated."""
    from cat.inference.middleware import RequestTimingMiddleware
    
    middleware = RequestTimingMiddleware(app=None)
    stats = middleware.get_timing_stats()
    
    assert isinstance(stats, dict)


def test_metrics_middleware():
    """Test metrics middleware can be instantiated."""
    from cat.inference.middleware import MetricsMiddleware
    
    middleware = MetricsMiddleware(app=None)
    metrics = middleware.get_metrics()
    
    assert "request_count" in metrics
    assert "error_count" in metrics
    assert "total_latency_ms" in metrics
    assert "avg_latency_ms" in metrics
    assert "error_rate" in metrics


def test_setup_request_logging():
    """Test request logging setup function."""
    from cat.inference.middleware import setup_request_logging
    
    logger = setup_request_logging(
        logger_name="test_logger",
        log_level="DEBUG"
    )
    
    assert logger.name == "test_logger"
    assert logger.level == 10  # DEBUG


def test_create_logging_config():
    """Test logging configuration creation."""
    from cat.inference.middleware import create_logging_config
    
    config = create_logging_config(
        log_level="WARNING",
        log_format="%(message)s"
    )
    
    assert config["level"] == "WARNING"
    assert config["format"] == "%(message)s"