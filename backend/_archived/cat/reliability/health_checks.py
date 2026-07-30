"""
Health check utilities for the Contextual Availability Transformer (CAT) system.
Provides health check endpoints and status monitoring.
"""

import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, List, Any, Callable
from dataclasses import dataclass, field
import asyncio

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    status: HealthStatus
    component: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "component": self.component,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "error": self.error
        }


class HealthChecker:
    """
    Health checker for CAT system components.
    
    Provides health check utilities for model, data sources, and external APIs.
    """
    
    def __init__(
        self,
        model_available: Callable[[], bool] = None,
        data_collector_available: Callable[[], bool] = None,
        external_apis_available: Callable[[], bool] = None
    ):
        """
        Initialize the health checker.
        
        Args:
            model_available: Callable that returns True if model is available
            data_collector_available: Callable that returns True if data collector is available
            external_apis_available: Callable that returns True if external APIs are available
        """
        self._model_available = model_available or (lambda: True)
        self._data_collector_available = data_collector_available or (lambda: True)
        self._external_apis_available = external_apis_available or (lambda: True)
        
        self._check_results: Dict[str, HealthCheckResult] = {}
        self._last_check_time: Optional[datetime] = None
        self._check_interval_seconds = 30  # Check every 30 seconds
        
        # Register default health checks
        self._checks: List[Dict[str, Any]] = [
            {
                "name": "model",
                "description": "Transformer model availability",
                "checker": self._check_model
            },
            {
                "name": "data_collector",
                "description": "Data collector availability",
                "checker": self._check_data_collector
            },
            {
                "name": "external_apis",
                "description": "External API connectivity",
                "checker": self._check_external_apis
            },
            {
                "name": "cache",
                "description": "Prediction cache availability",
                "checker": self._check_cache
            }
        ]
    
    def run_health_checks(self) -> HealthCheckResult:
        """
        Run all health checks and return overall status.
        
        Returns:
            HealthCheckResult with overall system status
        """
        now = datetime.utcnow()
        
        # Check if we need to run checks (based on interval)
        if self._last_check_time and (now - self._last_check_time).seconds < self._check_interval_seconds:
            # Return cached result
            return self._get_overall_status()
        
        self._last_check_time = now
        
        # Run all checks
        results = []
        for check in self._checks:
            try:
                result = check["checker"]()
                results.append(result)
                self._check_results[check["name"]] = result
            except Exception as e:
                logger.error(f"Health check failed for {check['name']}: {e}")
                result = HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    component=check["name"],
                    error=str(e)
                )
                results.append(result)
                self._check_results[check["name"]] = result
        
        return self._get_overall_status()
    
    def _check_model(self) -> HealthCheckResult:
        """Check model availability."""
        try:
            is_available = self._model_available()
            if is_available:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    component="model",
                    details={"loaded": True}
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    component="model",
                    error="Model not loaded"
                )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="model",
                error=str(e)
            )
    
    def _check_data_collector(self) -> HealthCheckResult:
        """Check data collector availability."""
        try:
            is_available = self._data_collector_available()
            if is_available:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    component="data_collector",
                    details={"connected": True}
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    component="data_collector",
                    error="Data collector not connected"
                )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="data_collector",
                error=str(e)
            )
    
    def _check_external_apis(self) -> HealthCheckResult:
        """Check external API connectivity."""
        try:
            is_available = self._external_apis_available()
            if is_available:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    component="external_apis",
                    details={"connected": True}
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    component="external_apis",
                    error="External APIs not reachable"
                )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="external_apis",
                error=str(e)
            )
    
    def _check_cache(self) -> HealthCheckResult:
        """Check cache availability."""
        try:
            # Cache is considered available if it's configured
            from ..config import settings
            if settings.redis_url:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    component="cache",
                    details={"type": "redis", "configured": True}
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    component="cache",
                    details={"type": "local", "configured": True}
                )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                component="cache",
                error=str(e)
            )
    
    def _get_overall_status(self) -> HealthCheckResult:
        """Get overall system health status."""
        if not self._check_results:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="system",
                error="No health checks run yet"
            )
        
        # Determine overall status
        statuses = [r.status for r in self._check_results.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Collect all errors
        errors = [r.error for r in self._check_results.values() if r.error]
        
        return HealthCheckResult(
            status=overall_status,
            component="system",
            details={
                "component_checks": {k: v.status.value for k, v in self._check_results.items()},
                "uptime_seconds": (datetime.utcnow() - self._last_check_time).seconds if self._last_check_time else 0
            },
            error="; ".join(errors) if errors else None
        )
    
    def get_health_details(self) -> Dict[str, Any]:
        """Get detailed health information."""
        return {
            "overall": self._get_overall_status().to_dict(),
            "components": {k: v.to_dict() for k, v in self._check_results.items()},
            "last_check": self._last_check_time.isoformat() if self._last_check_time else None
        }


def create_health_checker(
    model_available: Callable[[], bool] = None,
    data_collector_available: Callable[[], bool] = None,
    external_apis_available: Callable[[], bool] = None
) -> HealthChecker:
    """
    Factory function to create a HealthChecker.
    
    Args:
        model_available: Callable that returns True if model is available
        data_collector_available: Callable that returns True if data collector is available
        external_apis_available: Callable that returns True if external APIs are available
    
    Returns:
        Configured HealthChecker instance
    """
    return HealthChecker(
        model_available=model_available,
        data_collector_available=data_collector_available,
        external_apis_available=external_apis_available
    )
