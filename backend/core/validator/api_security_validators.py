"""
API & Security Validators (RT-111 to RT-130)

This module handles validation logic for API security, parameter validation,
authentication, rate limiting, and compliance with security best practices.
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
import re
import hashlib
import hmac

logger = logging.getLogger(__name__)


class AuthTokenType(Enum):
    """Types of authentication tokens"""
    JWT = "jwt"
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    SESSION = "session"


class RequestMethod(Enum):
    """HTTP request methods"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class APIRequest:
    """Represents an API request"""
    request_id: str
    method: RequestMethod
    endpoint: str
    parameters: Dict[str, Any]
    headers: Dict[str, str]
    body: Optional[str] = None
    timestamp: datetime = None
    auth_token: Optional[str] = None
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class SecurityContext:
    """Security context for request validation"""
    user_id: Optional[str] = None
    token: Optional[str] = None
    token_type: AuthTokenType = AuthTokenType.JWT
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    permissions: List[str] = field(default_factory=list)
    is_authenticated: bool = False
    session_id: Optional[str] = None


@dataclass
class RateLimitInfo:
    """Rate limiting information"""
    requests_made: int = 0
    max_requests: int = 100
    time_window_seconds: int = 60
    reset_time: Optional[datetime] = None
    is_limited: bool = False


class APISecurityValidator:
    """Validator class for API security and parameter validation"""

    def __init__(self):
        """Initialize the API security validator"""
        self.max_payload_size_bytes = 10 * 1024 * 1024  # 10MB
        self.rate_limit_window = 60  # seconds
        self.token_expiry_minutes = 30
        self.password_min_length = 8
        self.sql_injection_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)",
            r"(--|#|/\*|\*/)",
            r"(union|exec|execute)",
        ]
        self.xss_patterns = [
            r"(<script[^>]*>|</script>)",
            r"(javascript:|onerror=|onload=)",
            r"(<iframe|<object|<embed)",
        ]
        self.allowed_content_types = [
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
        ]
        self.api_versions = ["v1", "v2", "v3"]
        self.request_log = []
        self.rate_limit_store = {}

    def validate_invalid_parameters_rejected(self, request: APIRequest) -> bool:
        """
        RT-111: Validate that invalid parameters are rejected.
        API should reject requests with invalid parameter types or values.
        """
        if not request.parameters:
            return True
        
        for key, value in request.parameters.items():
            # Check for obviously invalid values
            if value is None and key.endswith("_required"):
                logger.warning(f"Invalid parameter: {key} has None value")
                return False
            
            # Check for empty required strings
            if isinstance(value, str) and len(value) == 0 and key.endswith("_id"):
                logger.warning(f"Invalid parameter: {key} is empty string")
                return False
            
            # Check for invalid numeric values
            if key.endswith("_count") or key.endswith("_limit"):
                try:
                    num_val = int(value) if not isinstance(value, int) else value
                    if num_val < 0:
                        return False
                except (ValueError, TypeError):
                    return False
        
        return True

    def validate_missing_required_fields(self, request: APIRequest,
                                        required_fields: List[str]) -> bool:
        """
        RT-112: Validate that missing required fields are detected.
        API should reject requests missing any required field.
        """
        if not required_fields:
            return True
        
        for field in required_fields:
            if field not in request.parameters or request.parameters[field] is None:
                logger.warning(f"Missing required field: {field}")
                return False
            
            # Check if field value is empty
            value = request.parameters[field]
            if isinstance(value, str) and len(value.strip()) == 0:
                logger.warning(f"Required field {field} is empty")
                return False
        
        return True

    def validate_injection_attack_resistance(self, request: APIRequest) -> bool:
        """
        RT-113: Validate SQL and XSS injection attack resistance.
        API should sanitize all user inputs to prevent injection attacks.
        """
        for param_value in request.parameters.values():
            if not isinstance(param_value, str):
                continue
            
            # Check for SQL injection patterns
            for pattern in self.sql_injection_patterns:
                if re.search(pattern, param_value, re.IGNORECASE):
                    logger.warning(f"Potential SQL injection detected: {param_value[:50]}")
                    return False
            
            # Check for XSS patterns
            for pattern in self.xss_patterns:
                if re.search(pattern, param_value, re.IGNORECASE):
                    logger.warning(f"Potential XSS injection detected: {param_value[:50]}")
                    return False
        
        # Check body for injection patterns
        if request.body:
            for pattern in self.sql_injection_patterns + self.xss_patterns:
                if re.search(pattern, request.body, re.IGNORECASE):
                    logger.warning(f"Potential injection in body detected")
                    return False
        
        return True

    def validate_auth_token_validation(self, security_context: SecurityContext) -> bool:
        """
        RT-114: Validate authentication token validation.
        Token should be present, valid format, and not expired.
        """
        if not security_context.token:
            logger.warning("No authentication token provided")
            return False
        
        # Check token format based on type
        if security_context.token_type == AuthTokenType.JWT:
            # JWT should have three parts separated by dots
            parts = security_context.token.split('.')
            if len(parts) != 3:
                logger.warning("Invalid JWT format")
                return False
        
        elif security_context.token_type == AuthTokenType.BEARER:
            if not security_context.token.startswith("Bearer "):
                logger.warning("Invalid Bearer token format")
                return False
        
        # Check token expiration
        if security_context.expires_at:
            if datetime.utcnow() > security_context.expires_at:
                logger.warning("Token has expired")
                return False
        
        security_context.is_authenticated = True
        return True

    def validate_unauthorized_access_blocked(self, security_context: SecurityContext,
                                            required_permissions: List[str]) -> bool:
        """
        RT-115: Validate that unauthorized access is blocked.
        Request should be rejected if user lacks required permissions.
        """
        if not security_context.is_authenticated:
            logger.warning("Unauthenticated access attempt")
            return False
        
        if not required_permissions:
            return True
        
        # Check if user has required permissions
        for required_perm in required_permissions:
            if required_perm not in security_context.permissions:
                logger.warning(f"Missing permission: {required_perm}")
                return False
        
        return True

    def validate_large_payload_rejection(self, request: APIRequest) -> bool:
        """
        RT-116: Validate large payload rejection.
        API should reject requests exceeding maximum payload size.
        """
        if request.body:
            payload_size = len(request.body.encode('utf-8'))
            if payload_size > self.max_payload_size_bytes:
                logger.warning(f"Payload exceeds max size: {payload_size} > {self.max_payload_size_bytes}")
                return False
        
        return True

    def validate_rate_limit_enforcement(self, user_id: str,
                                       rate_limit_info: RateLimitInfo) -> bool:
        """
        RT-117: Validate rate limit enforcement.
        API should enforce rate limits per user/IP.
        """
        if user_id in self.rate_limit_store:
            info = self.rate_limit_store[user_id]
            reset_time = info.get('reset_time', datetime.utcnow())
            
            # Check if window has reset
            if datetime.utcnow() < reset_time:
                current_count = info.get('requests', 0)
                if current_count >= rate_limit_info.max_requests:
                    logger.warning(f"Rate limit exceeded for user {user_id}")
                    rate_limit_info.is_limited = True
                    return False
                
                # Increment request count
                self.rate_limit_store[user_id]['requests'] = current_count + 1
            else:
                # Reset window
                self.rate_limit_store[user_id] = {
                    'requests': 1,
                    'reset_time': datetime.utcnow() + timedelta(seconds=rate_limit_info.time_window_seconds)
                }
        else:
            # First request from this user
            self.rate_limit_store[user_id] = {
                'requests': 1,
                'reset_time': datetime.utcnow() + timedelta(seconds=rate_limit_info.time_window_seconds)
            }
        
        return True

    def validate_error_message_sanitization(self, error_message: str) -> bool:
        """
        RT-118: Validate error message sanitization.
        Error messages should not leak sensitive information.
        """
        sensitive_patterns = [
            r"(password|secret|api_key|token)",
            r"(database|sql|query|table)",
            r"(file_path|directory|\\|/home/|/var/)",
            r"(stack trace|traceback|Exception in)",
            r"(127\.0\.0\.1|localhost|192\.168)",
        ]
        
        for pattern in sensitive_patterns:
            if re.search(pattern, error_message, re.IGNORECASE):
                logger.warning(f"Error message contains sensitive info: {error_message[:50]}")
                return False
        
        return True

    def validate_api_version_compatibility(self, request: APIRequest) -> bool:
        """
        RT-119: Validate API version compatibility.
        Request should use supported API version.
        """
        # Extract version from endpoint (e.g., /api/v1/routes)
        version_match = re.search(r'/v(\d+)/', request.endpoint)
        
        if version_match:
            version = f"v{version_match.group(1)}"
            if version not in self.api_versions:
                logger.warning(f"Unsupported API version: {version}")
                return False
        
        return True

    def validate_schema_backward_compatibility(self, request_data: Dict[str, Any],
                                              expected_schema: Dict[str, Any]) -> bool:
        """
        RT-120: Validate schema backward compatibility.
        API should accept requests with older schema versions.
        """
        if not expected_schema:
            return True
        
        # Check that all expected required fields are present
        required_fields = expected_schema.get('required_fields', [])
        for field in required_fields:
            if field not in request_data:
                logger.warning(f"Required schema field missing: {field}")
                return False
        
        # Check field types match
        field_types = expected_schema.get('field_types', {})
        for field, expected_type in field_types.items():
            if field in request_data:
                actual_type = type(request_data[field]).__name__
                if expected_type == "string" and not isinstance(request_data[field], str):
                    return False
                elif expected_type == "integer" and not isinstance(request_data[field], int):
                    return False
                elif expected_type == "boolean" and not isinstance(request_data[field], bool):
                    return False
        
        return True

    def validate_replay_attack_prevention(self, request: APIRequest,
                                         nonce: str,
                                         previous_requests: List[str]) -> bool:
        """
        RT-121: Validate replay attack prevention.
        API should reject duplicate/replayed requests.
        """
        # Create request signature
        request_signature = self._create_request_signature(request, nonce)
        
        if request_signature in previous_requests:
            logger.warning("Replay attack detected: duplicate request signature")
            return False
        
        # Store request for future comparison
        previous_requests.append(request_signature)
        
        return True

    def validate_request_signature_validation(self, request: APIRequest,
                                             secret_key: str,
                                             provided_signature: str) -> bool:
        """
        RT-122: Validate request signature validation.
        API should verify request signatures for integrity.
        """
        # Create expected signature
        expected_signature = self._create_request_signature(request, secret_key)
        
        # Compare signatures using constant-time comparison
        if not self._constant_time_compare(expected_signature, provided_signature):
            logger.warning("Invalid request signature")
            return False
        
        return True

    def validate_cors_policy_correctness(self, request: APIRequest,
                                        allowed_origins: List[str]) -> bool:
        """
        RT-123: Validate CORS policy correctness.
        API should enforce proper CORS headers.
        """
        origin = request.headers.get('Origin')
        
        if not origin:
            return True
        
        # Check if origin is in allowed list
        if origin not in allowed_origins and "*" not in allowed_origins:
            logger.warning(f"CORS violation: unauthorized origin {origin}")
            return False
        
        # Verify credentials are not exposed with wildcard origin
        if origin == "*":
            access_control = request.headers.get('Access-Control-Allow-Credentials')
            if access_control == "true":
                logger.warning("CORS security issue: credentials with wildcard origin")
                return False
        
        return True

    def validate_https_enforcement(self, request: APIRequest) -> bool:
        """
        RT-124: Validate HTTPS enforcement.
        API should enforce HTTPS for all requests except development.
        """
        # Check endpoint for http/https scheme
        if not request.endpoint.startswith('https://') and not request.endpoint.startswith('http://'):
            # Assume HTTPS if scheme not specified
            return True
        
        if request.endpoint.startswith('http://') and request.endpoint not in [
            'http://localhost',
            'http://127.0.0.1',
        ]:
            logger.warning(f"HTTP used instead of HTTPS: {request.endpoint}")
            return False
        
        return True

    def validate_input_encoding_safety(self, request: APIRequest) -> bool:
        """
        RT-125: Validate input encoding safety.
        API should handle various input encodings safely.
        """
        for param_value in request.parameters.values():
            if isinstance(param_value, str):
                try:
                    # Try to encode/decode to ensure valid UTF-8
                    param_value.encode('utf-8')
                    param_value.encode('utf-8').decode('utf-8')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    logger.warning(f"Invalid encoding detected: {param_value[:50]}")
                    return False
        
        return True

    def validate_dos_attack_simulation(self, request: APIRequest,
                                      concurrent_threshold: int = 100) -> bool:
        """
        RT-126: Validate DOS attack detection and mitigation.
        API should detect and mitigate potential DOS attacks.
        """
        # Check for rapid repeated requests from same source
        if request.source_ip:
            if request.source_ip in self.request_log:
                recent_requests = [r for r in self.request_log[request.source_ip] 
                                 if (datetime.utcnow() - r) < timedelta(seconds=1)]
                
                if len(recent_requests) > 10:  # More than 10 requests per second
                    logger.warning(f"Potential DOS attack from {request.source_ip}")
                    return False
            else:
                self.request_log[request.source_ip] = []
            
            self.request_log[request.source_ip].append(datetime.utcnow())
        
        return True

    def validate_session_expiration_handling(self, security_context: SecurityContext) -> bool:
        """
        RT-127: Validate session expiration handling.
        Expired sessions should be rejected automatically.
        """
        if not security_context.expires_at:
            return True
        
        current_time = datetime.utcnow()
        time_until_expiry = security_context.expires_at - current_time
        
        # Check if session has expired
        if time_until_expiry.total_seconds() <= 0:
            logger.warning("Session has expired")
            return False
        
        return True

    def validate_audit_logging_correctness(self, request: APIRequest,
                                          security_context: SecurityContext,
                                          audit_log: List[Dict]) -> bool:
        """
        RT-128: Validate audit logging correctness.
        All security-relevant actions should be logged.
        """
        if not audit_log:
            audit_log = []
        
        # Create audit entry
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'request_id': request.request_id,
            'user_id': security_context.user_id,
            'endpoint': request.endpoint,
            'method': request.method.value,
            'source_ip': request.source_ip,
            'status': 'success'
        }
        
        # Validate audit entry has all required fields
        required_audit_fields = ['timestamp', 'request_id', 'endpoint', 'method']
        for field in required_audit_fields:
            if field not in audit_entry or not audit_entry[field]:
                logger.warning(f"Missing audit log field: {field}")
                return False
        
        audit_log.append(audit_entry)
        return True

    def validate_sensitive_data_masking(self, response_data: Dict[str, Any]) -> bool:
        """
        RT-129: Validate sensitive data masking in responses.
        Sensitive data should be masked/redacted in API responses.
        """
        sensitive_fields = ['password', 'secret', 'api_key', 'token', 'credit_card']
        
        for key, value in response_data.items():
            # Check if field contains sensitive data
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                if value and isinstance(value, str) and len(value) > 0:
                    # Sensitive data should not be in plaintext
                    if not (value.startswith("***") or value == "[REDACTED]"):
                        logger.warning(f"Sensitive field not masked: {key}")
                        return False
        
        return True

    def validate_token_refresh_logic(self, security_context: SecurityContext,
                                    token_refresh_interval_minutes: int = 15) -> bool:
        """
        RT-130: Validate token refresh logic.
        Tokens should be refreshable before expiration.
        """
        if not security_context.issued_at or not security_context.expires_at:
            return True
        
        time_until_expiry = security_context.expires_at - datetime.utcnow()
        
        # Token should be refreshed before expiration
        if time_until_expiry.total_seconds() < 0:
            logger.warning("Token has expired and cannot be refreshed")
            return False
        
        # Token should still have time remaining for refresh
        if time_until_expiry.total_seconds() < (token_refresh_interval_minutes * 60):
            # Token is within refresh window
            return True
        
        return True

    def _create_request_signature(self, request: APIRequest, secret: str) -> str:
        """Create a signature for request validation"""
        signature_data = f"{request.method.value}{request.endpoint}{str(request.parameters)}{secret}"
        return hashlib.sha256(signature_data.encode()).hexdigest()

    def _constant_time_compare(self, a: str, b: str) -> bool:
        """Compare two strings in constant time to prevent timing attacks"""
        if len(a) != len(b):
            return False
        
        result = 0
        for x, y in zip(a, b):
            result |= ord(x) ^ ord(y)
        
        return result == 0
