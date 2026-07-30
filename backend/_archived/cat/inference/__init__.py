"""Inference module for CAT."""

from .main import (
    create_app,
    create_inference_service,
    app
)
from .config import (
    InferenceSettings,
    get_inference_settings,
    inference_settings
)
from .middleware import (
    RequestLoggingMiddleware,
    RequestTimingMiddleware,
    MetricsMiddleware,
    setup_request_logging
)
from .routes.health import (
    health_router,
    HealthResponse,
    ReadinessResponse,
    LivenessResponse
)
from .routes.streaming import (
    streaming_router,
    StreamEventType,
    StreamConfig
)

__all__ = [
    # Main application
    "create_app",
    "create_inference_service",
    "app",
    # Configuration
    "InferenceSettings",
    "get_inference_settings",
    "inference_settings",
    # Middleware
    "RequestLoggingMiddleware",
    "RequestTimingMiddleware",
    "MetricsMiddleware",
    "setup_request_logging",
    # Health routes
    "health_router",
    "HealthResponse",
    "ReadinessResponse",
    "LivenessResponse",
    # Streaming routes
    "streaming_router",
    "StreamEventType",
    "StreamConfig"
]