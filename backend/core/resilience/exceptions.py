import asyncio
import logging
import secrets
import traceback
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse


from core.engines.orchestrator import orchestrator
from utils.responses import SafeJSONResponse

logger = logging.getLogger("routemaster.exceptions")


class RailwayException(Exception):
    """Base exception for railway-related errors."""
    
    def __init__(self, message: str, error_code: str = "RAILWAY_ERROR", details: Optional[dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class BookingException(RailwayException):
    """Exception related to booking operations."""
    def __init__(self, message: str, booking_id: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="BOOKING_ERROR", details={"booking_id": booking_id, **kwargs})


class PaymentException(RailwayException):
    """Exception related to payment operations."""
    def __init__(self, message: str, payment_id: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="PAYMENT_ERROR", details={"payment_id": payment_id, **kwargs})


class ValidationException(RailwayException):
    """Exception for validation errors."""
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None):
        details = {"field": field, "value": value} if field else {}
        super().__init__(message, error_code="VALIDATION_ERROR", details=details)


class ExternalServiceException(RailwayException):
    """Exception for external service failures."""
    def __init__(self, service_name: str, message: str, status_code: Optional[int] = None):
        super().__init__(
            message, 
            error_code=f"SERVICE_ERROR_{service_name.upper()}",
            details={"service": service_name, "status_code": status_code}
        )


class CircuitOpenException(RailwayException):
    """Exception raised when circuit breaker is open."""
    def __init__(self, service_name: str, retry_after: int = 60):
        super().__init__(
            f"Service {service_name} is temporarily unavailable",
            error_code="CIRCUIT_OPEN",
            details={"service": service_name, "retry_after": retry_after}
        )


class RateLimitException(RailwayException):
    """Exception for rate limit exceeded."""
    def __init__(self, limit: int, window: int = 60):
        super().__init__(
            f"Rate limit exceeded. Max {limit} requests per {window}s",
            error_code="RATE_LIMIT_EXCEEDED",
            details={"limit": limit, "window_seconds": window}
        )


async def handle_engine_crash(exc: Exception, request: Optional[Request] = None):
    """Fallback handler for ASGI middleware crash detection."""
    logger.critical(f"💥 ENGINE CRASH: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True, 
            "message": "Protocol Engine Crash: Automated Recovery Initiated.",
            "protocol_code": "ERR_NEXUS_CRASH"
        }
    )


def setup_exception_handlers(app: FastAPI):
    """
    Task 2: Modularized Exception Handlers.
    Registers global handlers for catastrophic and HTTP errors.
    """
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        from utils.structured_logging import get_request_id
        full_rid = get_request_id()
        # Extract base request ID (before the pipe)
        request_id = full_rid.split("|")[0] if "|" in full_rid else full_rid
        error_suffix = secrets.token_hex(2).upper()
        protocol_id = f"{request_id}-{error_suffix}"
        
        # Determine error type and appropriate response
        if isinstance(exc, RailwayException):
            error_code = exc.error_code
            message = exc.message
            status_code = _get_status_for_error_code(error_code)
            details = exc.details
        elif isinstance(exc, HTTPException):
            return await http_exception_handler(request, exc)
        else:
            error_code = f"ERR_{type(exc).__name__.upper()}"
            message = str(exc)
            status_code = 500
            details = {}
        
        # Log the error
        log_level = logging.ERROR if status_code >= 500 else logging.WARNING
        logger.log(
            log_level, 
            f"🚨 [{error_code}] [{protocol_id}]: {message}", 
            exc_info=status_code >= 500
        )
        
        # Report to penalty box for rate limiting
        try:
            client_ip = request.client.host if request.client else "unknown"
            await orchestrator.penalty_box.report_error(client_ip)
        except Exception:
            pass  # Don't let monitoring fail the response
        
        # Build response
        response_content = {
            "error": True,
            "message": message,
            "protocol_code": protocol_id,
            "error_code": error_code,
            "details": details,
            "request_id": request_id
        }
        
        # Add stack trace in development
        import os
        if os.getenv("ENVIRONMENT") == "development":
            response_content["stack_trace"] = traceback.format_exc()
        
        return SafeJSONResponse(
            status_code=status_code,
            content=response_content
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return SafeJSONResponse(
            status_code=exc.status_code,
            content={
                "error": True, 
                "message": exc.detail,
                "error_code": f"HTTP_{exc.status_code}"
            }
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle validation errors specifically."""
        error_id = secrets.token_hex(4).upper()
        logger.warning(f"⚠️ Validation error [{error_id}]: {exc}")
        
        return SafeJSONResponse(
            status_code=400,
            content={
                "error": True,
                "message": str(exc),
                "error_code": f"VALIDATION_ERROR_{error_id}",
                "protocol_code": "ERR_VALIDATION"
            }
        )
    
    @app.exception_handler(asyncio.TimeoutError)
    async def timeout_error_handler(request: Request, exc: asyncio.TimeoutError):
        """Handle timeout errors gracefully."""
        error_id = secrets.token_hex(4).upper()
        logger.warning(f"⏰ Request timeout [{error_id}]: {request.url}")
        
        return SafeJSONResponse(
            status_code=504,
            content={
                "error": True,
                "message": "Request timed out. Please try again.",
                "error_code": f"TIMEOUT_ERROR_{error_id}",
                "protocol_code": "ERR_GATEWAY_TIMEOUT"
            }
        )


def _get_status_for_error_code(error_code: str) -> int:
    """Map error codes to HTTP status codes."""
    status_mapping = {
        "VALIDATION_ERROR": 400,
        "BOOKING_ERROR": 400,
        "PAYMENT_ERROR": 402,
        "RATE_LIMIT_EXCEEDED": 429,
        "CIRCUIT_OPEN": 503,
        "SERVICE_ERROR": 502,
        "AUTH_ERROR": 401,
        "PERMISSION_ERROR": 403,
        "NOT_FOUND": 404,
    }
    
    for prefix, status in status_mapping.items():
        if error_code.startswith(prefix):
            return status
    return 500


# Exception mapping for graceful degradation
EXCEPTION_HANDLERS = {
    "railway": RailwayException,
    "booking": BookingException,
    "payment": PaymentException,
    "validation": ValidationException,
    "external_service": ExternalServiceException,
    "circuit_open": CircuitOpenException,
    "rate_limit": RateLimitException,
}
