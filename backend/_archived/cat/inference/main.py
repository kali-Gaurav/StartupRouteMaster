"""
Main FastAPI application for the CAT inference service.
Provides REST API for availability predictions with health checks and monitoring.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_inference_settings, InferenceSettings
from .middleware import (
    RequestLoggingMiddleware,
    RequestTimingMiddleware,
    MetricsMiddleware,
    setup_request_logging
)
from .routes.health import (
    health_router,
    set_start_time,
    set_model_loaded,
    record_prediction,
    set_timing_middleware
)
from .routes.streaming import (
    streaming_router,
    StreamEventType,
    StreamConfig
)

logger = logging.getLogger(__name__)

# Global instances
_timing_middleware: Optional[RequestTimingMiddleware] = None
_metrics_middleware: Optional[MetricsMiddleware] = None


def get_settings() -> InferenceSettings:
    """Get inference settings."""
    return get_inference_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events for the FastAPI application.
    """
    global _timing_middleware, _metrics_middleware
    
    settings = get_settings()
    
    # Setup logging
    log_config = setup_request_logging(
        logger_name="cat.inference",
        log_level=settings.log_level
    )
    logging.basicConfig(**log_config)
    
    # Initialize timing and metrics middleware
    _timing_middleware = RequestTimingMiddleware(app)
    _metrics_middleware = MetricsMiddleware(app)
    
    # Set global state
    set_start_time(datetime.utcnow())
    set_model_loaded(False)
    set_timing_middleware(_timing_middleware)
    
    logger.info("CAT Inference Service starting...")
    logger.info(f"Host: {settings.host}, Port: {settings.port}")
    logger.info(f"CORS origins: {settings.cors_origins}")
    logger.info(f"Log level: {settings.log_level}")
    
    # TODO: Initialize model here if needed
    # For now, model loading is handled by the main cat/main.py
    
    yield
    
    # Shutdown
    logger.info("CAT Inference Service shutting down...")


def create_app(settings: InferenceSettings = None) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Args:
        settings: Optional inference settings to use
        
    Returns:
        Configured FastAPI application instance
    """
    if settings is None:
        settings = get_settings()
    
    # Create FastAPI application with lifespan
    app = FastAPI(
        title="Contextual Availability Transformer API",
        description=(
            "Real-time availability predictions using Transformer-based "
            "machine learning. Provides health checks, metrics, and prediction endpoints."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add request logging middleware
    app.add_middleware(
        RequestLoggingMiddleware,
        log_request=settings.log_request_enabled,
        log_response=settings.log_response_enabled,
        log_request_timing=settings.log_request_timing
    )
    
    # Include health check routes
    app.include_router(health_router, prefix="/api/v1")
    
    # Include streaming routes
    app.include_router(streaming_router, prefix="/api/v1")
    
    # Add root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with service information."""
        return {
            "service": "CAT Inference Service",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs"
        }
    
    @app.get("/api/v1/info")
    async def service_info():
        """Get service information."""
        return {
            "service": "Contextual Availability Transformer",
            "version": "1.0.0",
            "description": "Real-time availability predictions using Transformer-based ML",
            "endpoints": {
                "health": "/api/v1/health",
                "health_live": "/api/v1/health/live",
                "health_ready": "/api/v1/health/ready",
                "metrics": "/api/v1/metrics",
                "docs": "/docs"
            }
        }
    
    return app


def create_inference_service() -> FastAPI:
    """
    Create the inference service FastAPI application.
    
    This is the main entry point for the inference service.
    It creates a FastAPI application with all middleware and routes configured.
    
    Returns:
        FastAPI application instance ready to serve
    """
    settings = get_settings()
    
    # Setup logging
    log_config = setup_request_logging(
        logger_name="cat.inference",
        log_level=settings.log_level
    )
    logging.basicConfig(**log_config)
    
    # Create application
    app = create_app(settings)
    
    logger.info("CAT Inference Service created successfully")
    
    return app


# Create default app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=settings.debug
    )