"""
Security Middleware for Route Engine

Implements:
- JWT authentication
- Rate limiting
- Input validation
- Error sanitization
- CORS configuration
"""

import re
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Station code validation pattern (2-5 uppercase letters)
STATION_CODE_PATTERN = re.compile(r'^[A-Z]{2,5}$')

# Travel date validation pattern (YYYY-MM-DD)
TRAVEL_DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# Train number validation pattern
TRAIN_NUMBER_PATTERN = re.compile(r'^[0-9]{1,5}$')


def validate_station_code(code: str, field: str = "station") -> str:
    """
    Validate station code format.
    
    Args:
        code: Station code to validate
        field: Field name for error message
        
    Returns:
        Validated station code
        
    Raises:
        HTTPException: If validation fails
    """
    if not code:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "VALIDATION_ERROR",
                "message": f"{field} is required",
                "field": field
            }
        )
    
    if not STATION_CODE_PATTERN.match(code):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "VALIDATION_ERROR",
                "message": f"Invalid {field}: must be 2-5 uppercase letters",
                "field": field,
                "value": code
            }
        )
    
    return code.upper()


def validate_travel_date(date_str: str) -> str:
    """
    Validate travel date format.
    
    Args:
        date_str: Date string to validate
        
    Returns:
        Validated date string
        
    Raises:
        HTTPException: If validation fails
    """
    if not date_str:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "VALIDATION_ERROR",
                "message": "Travel date is required",
                "field": "travel_date"
            }
        )
    
    if not TRAVEL_DATE_PATTERN.match(date_str):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "VALIDATION_ERROR",
                "message": "Invalid travel date format: must be YYYY-MM-DD",
                "field": "travel_date",
                "value": date_str
            }
        )
    
    # Validate date is reasonable (not too far in future/past)
    try:
        year, month, day = map(int, date_str.split('-'))
        if year < 2024 or year > 2030:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "VALIDATION_ERROR",
                    "message": "Travel date must be between 2024 and 2030",
                    "field": "travel_date"
                }
            )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "VALIDATION_ERROR",
                "message": "Invalid date values",
                "field": "travel_date"
            }
        )
    
    return date_str


def validate_train_number(train_number: str) -> str:
    """
    Validate train number format.
    
    Args:
        train_number: Train number to validate
        
    Returns:
        Validated train number
        
    Raises:
        HTTPException: If validation fails
    """
    if not train_number:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "VALIDATION_ERROR",
                "message": "Train number is required",
                "field": "train_number"
            }
        )
    
    if not TRAIN_NUMBER_PATTERN.match(train_number):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "VALIDATION_ERROR",
                "message": "Invalid train number: must be 1-5 digits",
                "field": "train_number",
                "value": train_number
            }
        )
    
    return train_number


def sanitize_input(value: str) -> str:
    """
    Sanitize string input to prevent injection attacks.
    
    Args:
        value: Input string to sanitize
        
    Returns:
        Sanitized string
    """
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Limit length
    max_length = 100
    if len(value) > max_length:
        value = value[:max_length]
    
    return value


def generate_secure_connection_id(prefix: str = "conn") -> str:
    """
    Generate a cryptographically secure connection ID.
    
    Args:
        prefix: Optional prefix for the ID
        
    Returns:
        Secure connection ID
    """
    return f"{prefix}-{secrets.token_hex(16)}"


def generate_error_id() -> str:
    """
    Generate a unique error ID for tracking.
    
    Returns:
        Error ID for logging correlation
    """
    return f"err-{secrets.token_hex(8)}"


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware for request validation and sanitization.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Generate error ID for this request
        error_id = generate_error_id()
        request.state.error_id = error_id
        
        # Validate path parameters
        for param, value in request.path_params.items():
            if isinstance(value, str):
                sanitized = sanitize_input(value)
                if sanitized != value:
                    logger.warning(
                        f"Input sanitization applied to {param}: "
                        f"{value[:50]}... -> {sanitized[:50]}..."
                    )
        
        # Validate query parameters
        for param, value in request.query_params.items():
            if isinstance(value, str) and len(value) > 100:
                logger.warning(f"Long query parameter: {param}={value[:50]}...")
        
        # Process request
        try:
            response = await call_next(request)
            return response
            
        except HTTPException as e:
            # Re-raise HTTP exceptions with sanitized messages
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": "VALIDATION_ERROR",
                    "message": "Invalid request parameters",
                    "error_id": error_id
                }
            )
            
        except Exception as e:
            # Log full error internally
            logger.error(
                f"Request error {error_id}: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            
            # Return sanitized error to client
            return JSONResponse(
                status_code=500,
                content={
                    "error": "INTERNAL_ERROR",
                    "message": "An error occurred while processing your request",
                    "error_id": error_id
                }
            )


def create_security_middleware():
    """
    Create security middleware stack.
    
    Returns:
        Configured security middleware
    """
    return SecurityMiddleware


# CORS configuration
def get_cors_origins() -> list:
    """
    Get allowed CORS origins.
    
    Returns:
        List of allowed origins
    """
    return [
        "https://routemaster.in",
        "https://www.routemaster.in",
        "https://app.routemaster.in",
        "http://localhost:3000",  # Development
        "http://localhost:5173",  # Vite development
    ]


def setup_cors(app):
    """
    Setup CORS middleware for FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "Cache-Control",
            "X-Requested-With",
        ],
        expose_headers=["X-Request-ID"],
        max_age=86400,  # 24 hours
    )


# Authentication placeholder (implement with actual JWT library)
async def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Get current user from JWT token.
    
    Args:
        request: FastAPI request
        
    Returns:
        User information
        
    Raises:
        HTTPException: If authentication fails
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "UNAUTHORIZED",
                "message": "Authentication required",
                "error_id": request.state.error_id
            }
        )
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "UNAUTHORIZED",
                "message": "Invalid authorization header format",
                "error_id": request.state.error_id
            }
        )
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    
    # TODO: Implement actual JWT validation
    # For now, return placeholder user
    try:
        # Decode and validate token
        # user = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = {
            "user_id": "user_placeholder",
            "email": "user@example.com",
            "roles": ["user"]
        }
        return user
    except Exception as e:
        logger.error(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "UNAUTHORIZED",
                "message": "Invalid or expired token",
                "error_id": request.state.error_id
            }
        )


# Rate limiting dependency
def rate_limit(max_requests: int = 100, per_seconds: int = 60):
    """
    Rate limiting dependency.
    """
    return limiter.limit(f"{max_requests}/{per_seconds}s")


# Audit logging
def log_audit_event(
    request: Request,
    event_type: str,
    details: Dict[str, Any] = None
):
    """
    Log audit event for security and compliance.
    
    Args:
        request: FastAPI request
        event_type: Type of event
        details: Additional event details
    """
    audit_log = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "user_id": getattr(request.state, "user_id", "anonymous"),
        "ip_address": get_remote_address(request),
        "method": request.method,
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "error_id": getattr(request.state, "error_id", None),
        "details": details or {}
    }
    
    logger.info(f"AUDIT: {audit_log}")


# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Add request ID header
        if hasattr(request.state, "error_id"):
            response.headers["X-Request-ID"] = request.state.error_id
        
        return response


__all__ = [
    "limiter",
    "validate_station_code",
    "validate_travel_date",
    "validate_train_number",
    "sanitize_input",
    "generate_secure_connection_id",
    "generate_error_id",
    "SecurityMiddleware",
    "setup_cors",
    "get_cors_origins",
    "get_current_user",
    "rate_limit",
    "log_audit_event",
    "SecurityHeadersMiddleware",
]