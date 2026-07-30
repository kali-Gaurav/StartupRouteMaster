"""
Custom middleware for the CAT inference service.
Provides request logging, monitoring, and timing middleware.
"""

import logging
import time
from typing import Callable, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging incoming requests and outgoing responses.
    
    Logs request method, path, client info, and timing information.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        *,
        log_request: bool = True,
        log_response: bool = True,
        log_request_timing: bool = True
    ):
        """
        Initialize the request logging middleware.
        
        Args:
            app: The ASGI application
            log_request: Whether to log request details
            log_response: Whether to log response details
            log_request_timing: Whether to log request timing
        """
        super().__init__(app)
        self.log_request = log_request
        self.log_response = log_response
        self.log_request_timing = log_request_timing
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Process the request and log relevant information.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain
            
        Returns:
            The response from the next handler
        """
        # Start timing
        start_time = time.time()
        
        # Get client information
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else "unknown"
        
        # Log request
        if self.log_request:
            logger.info(
                f"Request: {request.method} {request.url.path} "
                f"from {client_host}:{client_port}"
            )
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"from {client_host}:{client_port} - {str(e)} "
                f"({elapsed_ms:.1f}ms)"
            )
            raise
        
        # Calculate timing
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Log response
        if self.log_response:
            logger.info(
                f"Response: {request.method} {request.url.path} "
                f"status={response.status_code} "
                f"({elapsed_ms:.1f}ms)"
            )
        
        # Add timing header if enabled
        if self.log_request_timing and hasattr(response, 'headers'):
            response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
        
        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for tracking request timing metrics.
    
    Records timing information for performance monitoring.
    """
    
    def __init__(self, app: ASGIApp):
        """
        Initialize the request timing middleware.
        
        Args:
            app: The ASGI application
        """
        super().__init__(app)
        self._request_times: dict = {}
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Track request timing and process the request.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain
            
        Returns:
            The response from the next handler
        """
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate timing
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Store timing for metrics collection
        path = request.url.path
        method = request.method
        key = f"{method}:{path}"
        
        if key not in self._request_times:
            self._request_times[key] = []
        
        # Keep last 100 timings
        self._request_times[key].append(elapsed_ms)
        if len(self._request_times[key]) > 100:
            self._request_times[key].pop(0)
        
        return response
    
    def get_timing_stats(self, path: str = None) -> dict:
        """
        Get timing statistics for requests.
        
        Args:
            path: Optional path to filter by
            
        Returns:
            Dictionary of timing statistics
        """
        stats = {}
        
        for key, times in self._request_times.items():
            if path is None or key.startswith(path):
                if times:
                    stats[key] = {
                        "count": len(times),
                        "min_ms": min(times),
                        "max_ms": max(times),
                        "avg_ms": sum(times) / len(times)
                    }
        
        return stats


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware for collecting request metrics.
    
    Tracks request counts, errors, and latency.
    """
    
    def __init__(self, app: ASGIApp):
        """
        Initialize the metrics middleware.
        
        Args:
            app: The ASGI application
        """
        super().__init__(app)
        self._request_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Collect metrics and process the request.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain
            
        Returns:
            The response from the next handler
        """
        start_time = time.time()
        
        try:
            response = await call_next(request)
            self._request_count += 1
        except Exception as e:
            self._error_count += 1
            raise
        finally:
            elapsed_ms = (time.time() - start_time) * 1000
            self._total_latency_ms += elapsed_ms
        
        return response
    
    def get_metrics(self) -> dict:
        """
        Get collected metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "total_latency_ms": self._total_latency_ms,
            "avg_latency_ms": (
                self._total_latency_ms / self._request_count
                if self._request_count > 0 else 0
            ),
            "error_rate": (
                self._error_count / self._request_count
                if self._request_count > 0 else 0
            )
        }


def create_logging_config(log_level: str = "INFO", log_format: str = None) -> dict:
    """
    Create logging configuration dictionary.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom log format string
        
    Returns:
        Dictionary suitable for logging.basicConfig
    """
    format_string = log_format or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    return {
        "level": log_level,
        "format": format_string
    }


def setup_request_logging(
    logger_name: str = None,
    log_level: str = "INFO"
) -> logging.Logger:
    """
    Set up request logging for the inference service.
    
    Args:
        logger_name: Name of the logger to create
        log_level: Logging level
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(logger_name or "cat.inference")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Add console handler if no handlers exist
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    return logger