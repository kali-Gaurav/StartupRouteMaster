"""
Health check endpoints for the CAT inference service.
Provides liveness and readiness probes for orchestration platforms.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..config import get_inference_settings
from ..middleware import RequestTimingMiddleware

logger = logging.getLogger(__name__)

# Create health check router
health_router = APIRouter(tags=["Health"])

# Global state for health tracking
_start_time: Optional[datetime] = None
_model_loaded: bool = False
_last_prediction_time: Optional[datetime] = None
_predictions_count: int = 0
_timing_middleware: Optional[RequestTimingMiddleware] = None


def set_start_time(time: datetime) -> None:
    """Set the service start time."""
    global _start_time
    _start_time = time


def set_model_loaded(loaded: bool) -> None:
    """Set the model loaded status."""
    global _model_loaded
    _model_loaded = loaded


def record_prediction() -> None:
    """Record a prediction was made."""
    global _last_prediction_time, _predictions_count
    _last_prediction_time = datetime.utcnow()
    _predictions_count += 1


def set_timing_middleware(middleware: RequestTimingMiddleware) -> None:
    """Set the timing middleware for metrics."""
    global _timing_middleware
    _timing_middleware = middleware


class HealthResponse(BaseModel):
    """Response model for health check endpoints."""
    status: str
    model_loaded: bool
    uptime_seconds: float
    predictions_count: int
    last_prediction_time: Optional[str] = None
    timestamp: str


class ReadinessResponse(BaseModel):
    """Response model for readiness check endpoints."""
    status: str
    model_loaded: bool
    checks: Dict[str, Any]


class LivenessResponse(BaseModel):
    """Response model for liveness check endpoints."""
    status: str
    timestamp: str


@health_router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for liveness and readiness probes.
    
    Returns the overall health status of the service including
    model status, uptime, and prediction statistics.
    """
    global _start_time, _model_loaded, _last_prediction_time, _predictions_count
    
    now = datetime.utcnow()
    uptime = (now - _start_time).total_seconds() if _start_time else 0
    
    # Determine status
    if _model_loaded:
        status = "healthy"
    else:
        status = "degraded"
    
    return HealthResponse(
        status=status,
        model_loaded=_model_loaded,
        uptime_seconds=round(uptime, 2),
        predictions_count=_predictions_count,
        last_prediction_time=_last_prediction_time.isoformat() if _last_prediction_time else None,
        timestamp=now.isoformat()
    )


@health_router.get("/health/live", response_model=LivenessResponse)
async def liveness_check() -> LivenessResponse:
    """
    Liveness check endpoint.
    
    Returns whether the service is alive. This is the most basic
    health check and should return quickly without checking
    external dependencies.
    """
    return LivenessResponse(
        status="alive",
        timestamp=datetime.utcnow().isoformat()
    )


@health_router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """
    Readiness check endpoint.
    
    Returns whether the service is ready to handle requests.
    This checks that the model is loaded and ready.
    """
    global _model_loaded
    
    checks = {
        "model_loaded": _model_loaded,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Determine overall readiness
    if _model_loaded:
        status = "ready"
    else:
        status = "not_ready"
    
    return ReadinessResponse(
        status=status,
        model_loaded=_model_loaded,
        checks=checks
    )


@health_router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """
    Get service metrics for monitoring.
    
    Returns timing statistics and request metrics.
    """
    global _start_time, _predictions_count, _last_prediction_time, _model_loaded
    
    now = datetime.utcnow()
    uptime = (now - _start_time).total_seconds() if _start_time else 0
    
    metrics = {
        "uptime_seconds": round(uptime, 2),
        "predictions_count": _predictions_count,
        "model_loaded": _model_loaded,
        "last_prediction_time": _last_prediction_time.isoformat() if _last_prediction_time else None,
        "timestamp": now.isoformat()
    }
    
    # Add timing statistics if available
    if _timing_middleware:
        timing_stats = _timing_middleware.get_timing_stats()
        metrics["timing"] = timing_stats
    
    return metrics


@health_router.get("/health/details")
async def health_details() -> Dict[str, Any]:
    """
    Get detailed health information.
    
    Returns comprehensive health information including
    all checks and their status.
    """
    global _start_time, _model_loaded, _last_prediction_time, _predictions_count
    
    now = datetime.utcnow()
    uptime = (now - _start_time).isoformat() if _start_time else None
    
    details = {
        "service": {
            "name": "CAT Inference Service",
            "status": "healthy" if _model_loaded else "degraded",
            "uptime": uptime,
            "start_time": _start_time.isoformat() if _start_time else None
        },
        "model": {
            "loaded": _model_loaded,
            "type": "CATModel"
        },
        "predictions": {
            "total_count": _predictions_count,
            "last_prediction_time": _last_prediction_time.isoformat() if _last_prediction_time else None
        },
        "checks": {
            "liveness": "alive",
            "readiness": "ready" if _model_loaded else "not_ready"
        },
        "timestamp": now.isoformat()
    }
    
    return details


def create_health_checker(
    model_loaded_check: callable = None,
    external_api_check: callable = None
) -> callable:
    """
    Create a health check function for use with the service.
    
    Args:
        model_loaded_check: Function that returns whether model is loaded
        external_api_check: Function that returns whether external APIs are available
        
    Returns:
        Async function that runs all health checks
    """
    async def run_health_checks() -> Dict[str, Any]:
        """
        Run all health checks and return results.
        
        Returns:
            Dictionary of check results
        """
        checks = {}
        
        # Check model
        if model_loaded_check:
            checks["model"] = {
                "status": "healthy" if model_loaded_check() else "unhealthy",
                "description": "CAT model loaded and ready"
            }
        
        # Check external APIs
        if external_api_check:
            checks["external_apis"] = {
                "status": "healthy" if external_api_check() else "unhealthy",
                "description": "External API connectivity"
            }
        
        # Overall status
        all_healthy = all(
            c.get("status") == "healthy" 
            for c in checks.values()
        )
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    return run_health_checks