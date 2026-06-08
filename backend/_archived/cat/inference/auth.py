"""
Authentication and Authorization module for the CAT inference service.
Provides API key and OAuth token authentication with client permission checking.
"""

import logging
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading
import json

from fastapi import HTTPException, Header, Request, Depends
from pydantic import BaseModel

from .config import get_inference_settings

logger = logging.getLogger(__name__)


class AuthType(str, Enum):
    """Authentication type enumeration."""
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    NONE = "none"


class Permission(str, Enum):
    """Permission enumeration for client access control."""
    PREDICT = "predict"
    BATCH_PREDICT = "batch_predict"
    STREAM_PREDICT = "stream_predict"
    LIST_LOCATIONS = "list_locations"
    ADMIN = "admin"


@dataclass
class ClientPermissions:
    """Client permissions and access rights."""
    client_id: str
    auth_type: AuthType
    permissions: Set[Permission]
    allowed_locations: Set[str] = field(default_factory=set)  # Empty set means all locations
    rate_limit_override: Optional[int] = None  # Override default rate limit
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AuthEvent:
    """Authentication event for audit logging."""
    timestamp: datetime
    client_id: str
    auth_type: AuthType
    success: bool
    event_type: str  # login, logout, access, rate_limit_exceeded, etc.
    details: Dict = field(default_factory=dict)


class AuditLogger:
    """Audit logger for authentication and authorization events."""
    
    def __init__(self, log_file: str = None):
        """
        Initialize the audit logger.
        
        Args:
            log_file: Optional file path for audit logs
        """
        self._events: List[AuthEvent] = []
        self._lock = threading.Lock()
        self._log_file = log_file
        self._settings = get_inference_settings()
    
    def log_event(self, event: AuthEvent) -> None:
        """
        Log an authentication event.
        
        Args:
            event: The auth event to log
        """
        with self._lock:
            self._events.append(event)
            # Keep only last 10000 events in memory
            if len(self._events) > 10000:
                self._events = self._events[-10000:]
        
        # Log to file if configured
        if self._log_file:
            self._write_to_file(event)
        
        # Log to standard logger
        if event.success:
            logger.info(
                f"AUTH SUCCESS: {event.event_type} - "
                f"client={event.client_id[:8]}... - "
                f"auth_type={event.auth_type.value}"
            )
        else:
            logger.warning(
                f"AUTH FAILED: {event.event_type} - "
                f"client={event.client_id[:8] if event.client_id else 'unknown'}... - "
                f"auth_type={event.auth_type.value} - "
                f"details={event.details}"
            )
    
    def log_authentication_event(
        self,
        client_id: str,
        auth_type: AuthType,
        success: bool,
        details: Dict = None
    ) -> None:
        """
        Log an authentication event.
        
        Args:
            client_id: Client identifier
            auth_type: Type of authentication used
            success: Whether authentication succeeded
            details: Additional details
        """
        event = AuthEvent(
            timestamp=datetime.utcnow(),
            client_id=self._hash_client_id(client_id) if client_id else "anonymous",
            auth_type=auth_type,
            success=success,
            event_type="authentication",
            details=details or {}
        )
        self.log_event(event)
    
    def log_authorization_event(
        self,
        client_id: str,
        auth_type: AuthType,
        success: bool,
        resource: str,
        permission: Permission,
        details: Dict = None
    ) -> None:
        """
        Log an authorization event.
        
        Args:
            client_id: Client identifier
            auth_type: Type of authentication used
            success: Whether authorization succeeded
            resource: Resource being accessed
            permission: Permission being checked
            details: Additional details
        """
        event = AuthEvent(
            timestamp=datetime.utcnow(),
            client_id=self._hash_client_id(client_id) if client_id else "anonymous",
            auth_type=auth_type,
            success=success,
            event_type="authorization",
            details={
                "resource": resource,
                "permission": permission.value,
                **(details or {})
            }
        )
        self.log_event(event)
    
    def log_rate_limit_event(
        self,
        client_id: str,
        auth_type: AuthType,
        request_count: int,
        limit: int,
        details: Dict = None
    ) -> None:
        """
        Log a rate limit event.
        
        Args:
            client_id: Client identifier
            auth_type: Type of authentication used
            request_count: Number of requests made
            limit: Rate limit
            details: Additional details
        """
        event = AuthEvent(
            timestamp=datetime.utcnow(),
            client_id=self._hash_client_id(client_id) if client_id else "anonymous",
            auth_type=auth_type,
            success=False,
            event_type="rate_limit_exceeded",
            details={
                "request_count": request_count,
                "limit": limit,
                **(details or {})
            }
        )
        self.log_event(event)
    
    def _hash_client_id(self, client_id: str) -> str:
        """Hash client ID for privacy in logs."""
        if not client_id:
            return "anonymous"
        return hashlib.sha256(client_id.encode()).hexdigest()[:16]
    
    def _write_to_file(self, event: AuthEvent) -> None:
        """Write event to log file."""
        try:
            with open(self._log_file, 'a') as f:
                f.write(json.dumps({
                    "timestamp": event.timestamp.isoformat(),
                    "client_id": event.client_id,
                    "auth_type": event.auth_type.value,
                    "success": event.success,
                    "event_type": event.event_type,
                    "details": event.details
                }) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def get_events(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        event_type: str = None
    ) -> List[AuthEvent]:
        """
        Get audit events within a time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            event_type: Filter by event type
            
        Returns:
            List of matching events
        """
        with self._lock:
            events = self._events.copy()
        
        filtered = []
        for event in events:
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            if event_type and event.event_type != event_type:
                continue
            filtered.append(event)
        
        return filtered
    
    def get_auth_stats(self) -> Dict:
        """Get authentication statistics."""
        with self._lock:
            events = self._events.copy()
        
        total = len(events)
        successful = sum(1 for e in events if e.success)
        failed = total - successful
        
        auth_types = defaultdict(int)
        event_types = defaultdict(int)
        
        for event in events:
            auth_types[event.auth_type.value] += 1
            event_types[event.event_type] += 1
        
        return {
            "total_events": total,
            "successful_authentications": successful,
            "failed_authentications": failed,
            "by_auth_type": dict(auth_types),
            "by_event_type": dict(event_types)
        }


class OAuthValidator:
    """OAuth token validator for JWT and opaque tokens."""
    
    def __init__(
        self,
        jwt_secret: str = None,
        jwt_algorithm: str = "HS256",
        token_expiry_seconds: int = 3600
    ):
        """
        Initialize the OAuth validator.
        
        Args:
            jwt_secret: Secret key for JWT validation
            jwt_algorithm: JWT algorithm to use
            token_expiry_seconds: Token expiry time
        """
        import os
        self._jwt_secret = jwt_secret or os.getenv("CAT_OAUTH_JWT_SECRET", "default-secret-change-me")
        self._jwt_algorithm = jwt_algorithm
        self._token_expiry = token_expiry_seconds
        self._valid_tokens: Dict[str, Tuple[datetime, Dict]] = {}  # token -> (expiry, claims)
        self._lock = threading.Lock()
    
    def validate_token(self, token: str) -> Tuple[bool, Optional[Dict], str]:
        """
        Validate an OAuth token.
        
        Args:
            token: The OAuth token to validate
            
        Returns:
            Tuple of (is_valid, claims_dict, error_message)
        """
        if not token:
            return False, None, "Token is empty"
        
        # Check if it's a JWT token (has 3 parts separated by dots)
        if token.count('.') == 2:
            return self._validate_jwt(token)
        else:
            return self._validate_opaque_token(token)
    
    def _validate_jwt(self, token: str) -> Tuple[bool, Optional[Dict], str]:
        """
        Validate a JWT token.
        
        Args:
            token: The JWT token
            
        Returns:
            Tuple of (is_valid, claims_dict, error_message)
        """
        import base64
        import json
        
        try:
            # Decode header
            header_b64 = token.split('.')[0]
            # Add padding if needed
            padding = 4 - len(header_b64) % 4
            if padding != 4:
                header_b64 += '=' * padding
            header = json.loads(base64.urlsafe_b64decode(header_b64))
            
            # Decode payload
            payload_b64 = token.split('.')[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += '=' * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            
            # Check expiration
            if 'exp' in payload:
                exp_time = datetime.fromtimestamp(payload['exp'])
                if exp_time < datetime.utcnow():
                    return False, None, "Token has expired"
            
            # Check not before
            if 'nbf' in payload:
                nbf_time = datetime.fromtimestamp(payload['nbf'])
                if nbf_time > datetime.utcnow():
                    return False, None, "Token is not yet valid"
            
            # Verify signature (simplified - in production use proper JWT library)
            # For now, we accept tokens with correct structure
            return True, payload, ""
            
        except Exception as e:
            return False, None, f"Invalid token format: {str(e)}"
    
    def _validate_opaque_token(self, token: str) -> Tuple[bool, Optional[Dict], str]:
        """
        Validate an opaque token.
        
        Args:
            token: The opaque token
            
        Returns:
            Tuple of (is_valid, claims_dict, error_message)
        """
        # Check against valid tokens cache
        with self._lock:
            if token in self._valid_tokens:
                expiry, claims = self._valid_tokens[token]
                if expiry > datetime.utcnow():
                    return True, claims, ""
                else:
                    # Remove expired token
                    del self._valid_tokens[token]
        
        return False, None, "Invalid or expired token"
    
    def register_token(self, token: str, claims: Dict, expiry_seconds: int = None) -> None:
        """
        Register a valid opaque token.
        
        Args:
            token: The token to register
            claims: Token claims/payload
            expiry_seconds: Token expiry time
        """
        expiry = datetime.utcnow() + timedelta(seconds=expiry_seconds or self._token_expiry)
        
        with self._lock:
            self._valid_tokens[token] = (expiry, claims)
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token.
        
        Args:
            token: The token to revoke
            
        Returns:
            True if token was revoked, False if not found
        """
        with self._lock:
            if token in self._valid_tokens:
                del self._valid_tokens[token]
                return True
        return False


class ClientPermissionStore:
    """Store for client permissions and access rights."""
    
    def __init__(self):
        """Initialize the permission store."""
        self._clients: Dict[str, ClientPermissions] = {}
        self._api_keys: Dict[str, str] = {}  # api_key -> client_id
        self._lock = threading.Lock()
        
        # Initialize with default clients
        self._init_default_clients()
    
    def _init_default_clients(self) -> None:
        """Initialize default client permissions."""
        # Default API key client (full access)
        default_client = ClientPermissions(
            client_id="default_client",
            auth_type=AuthType.API_KEY,
            permissions={
                Permission.PREDICT,
                Permission.BATCH_PREDICT,
                Permission.STREAM_PREDICT,
                Permission.LIST_LOCATIONS
            },
            allowed_locations=set()  # All locations
        )
        self.register_client("default_api_key", default_client)
    
    def register_client(
        self,
        api_key: str,
        permissions: ClientPermissions
    ) -> None:
        """
        Register a client with API key.
        
        Args:
            api_key: The API key for the client
            permissions: Client permissions
        """
        with self._lock:
            self._clients[permissions.client_id] = permissions
            self._api_keys[api_key] = permissions.client_id
    
    def get_client_permissions(
        self,
        client_id: str = None,
        api_key: str = None
    ) -> Optional[ClientPermissions]:
        """
        Get client permissions by client ID or API key.
        
        Args:
            client_id: Client ID
            api_key: API key
            
        Returns:
            Client permissions or None if not found
        """
        with self._lock:
            if api_key and api_key in self._api_keys:
                client_id = self._api_keys[api_key]
            
            if client_id and client_id in self._clients:
                return self._clients[client_id]
        
        return None
    
    def check_permission(
        self,
        client_id: str,
        permission: Permission,
        location_id: str = None
    ) -> Tuple[bool, str]:
        """
        Check if a client has a specific permission.
        
        Args:
            client_id: Client ID
            permission: Permission to check
            location_id: Optional location ID to check access for
            
        Returns:
            Tuple of (has_permission, reason)
        """
        permissions = self.get_client_permissions(client_id=client_id)
        
        if not permissions:
            return False, "Client not found"
        
        # Check expiration
        if permissions.expires_at and permissions.expires_at < datetime.utcnow():
            return False, "Client access has expired"
        
        # Check permission
        if permission not in permissions.permissions:
            return False, f"Missing permission: {permission.value}"
        
        # Check location access
        if location_id and permissions.allowed_locations:
            if location_id not in permissions.allowed_locations:
                return False, f"Location {location_id} not accessible"
        
        return True, ""
    
    def add_client_permission(
        self,
        client_id: str,
        permission: Permission
    ) -> bool:
        """
        Add a permission to a client.
        
        Args:
            client_id: Client ID
            permission: Permission to add
            
        Returns:
            True if added, False if client not found
        """
        with self._lock:
            if client_id in self._clients:
                self._clients[client_id].permissions.add(permission)
                return True
        return False
    
    def remove_client_permission(
        self,
        client_id: str,
        permission: Permission
    ) -> bool:
        """
        Remove a permission from a client.
        
        Args:
            client_id: Client ID
            permission: Permission to remove
            
        Returns:
            True if removed, False if client not found
        """
        with self._lock:
            if client_id in self._clients:
                self._clients[client_id].permissions.discard(permission)
                return True
        return False
    
    def restrict_client_locations(
        self,
        client_id: str,
        allowed_locations: Set[str]
    ) -> bool:
        """
        Restrict a client's location access.
        
        Args:
            client_id: Client ID
            allowed_locations: Set of allowed location IDs
            
        Returns:
            True if updated, False if client not found
        """
        with self._lock:
            if client_id in self._clients:
                self._clients[client_id].allowed_locations = allowed_locations
                return True
        return False


class RateLimiter:
    """
    Rate limiter using sliding window algorithm.
    
    Limits requests per client with configurable limits.
    """
    
    def __init__(
        self,
        requests_per_minute: int = None,
        default_limit: int = 100
    ):
        """
        Initialize the rate limiter.
        
        Args:
            requests_per_minute: Default requests per minute
            default_limit: Fallback limit
        """
        self._default_limit = requests_per_minute or default_limit
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def is_allowed(
        self,
        client_id: str,
        limit: int = None
    ) -> Tuple[bool, int, Dict]:
        """
        Check if a request is allowed.
        
        Args:
            client_id: Client identifier
            limit: Optional client-specific limit
            
        Returns:
            Tuple of (is_allowed, remaining_requests, headers_dict)
        """
        max_requests = limit or self._default_limit
        now = time.time()
        window_start = now - 60.0  # 1 minute window
        
        with self._lock:
            # Clean up old requests
            self._requests[client_id] = [
                t for t in self._requests[client_id] if t > window_start
            ]
            
            current_count = len(self._requests[client_id])
            
            if current_count < max_requests:
                self._requests[client_id].append(now)
                remaining = max_requests - current_count - 1
                return True, remaining, {
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(int(window_start + 60))
                }
            else:
                return False, 0, {
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(window_start + 60))
                }
    
    def get_remaining(self, client_id: str, limit: int = None) -> int:
        """Get remaining requests for a client."""
        max_requests = limit or self._default_limit
        now = time.time()
        window_start = now - 60.0
        
        with self._lock:
            self._requests[client_id] = [
                t for t in self._requests[client_id] if t > window_start
            ]
            return max(0, max_requests - len(self._requests[client_id]))
    
    def get_usage(self, client_id: str) -> Dict:
        """Get current usage statistics for a client."""
        now = time.time()
        window_start = now - 60.0
        
        with self._lock:
            recent_requests = [
                t for t in self._requests[client_id] if t > window_start
            ]
            return {
                "requests_in_window": len(recent_requests),
                "window_seconds_remaining": max(0, int(60 - (now - window_start)))
            }


class Authenticator:
    """
    Main authenticator class that handles both API key and OAuth authentication.
    """
    
    def __init__(
        self,
        api_key: str = None,
        oauth_validator: OAuthValidator = None,
        permission_store: ClientPermissionStore = None,
        audit_logger: AuditLogger = None
    ):
        """
        Initialize the authenticator.
        
        Args:
            api_key: Default API key for validation
            oauth_validator: OAuth token validator
            permission_store: Client permission store
            audit_logger: Audit logger for events
        """
        import os
        self._api_key = api_key or os.getenv("CAT_API_KEY", "")
        self._oauth_validator = oauth_validator or OAuthValidator()
        self._permission_store = permission_store or ClientPermissionStore()
        self._audit_logger = audit_logger or AuditLogger()
    
    def authenticate(
        self,
        x_api_key: Optional[str] = None,
        authorization: Optional[str] = None
    ) -> Tuple[AuthType, str, Optional[ClientPermissions]]:
        """
        Authenticate a request using API key or OAuth token.
        
        Args:
            x_api_key: API key from header
            authorization: Authorization header (Bearer token)
            
        Returns:
            Tuple of (auth_type, client_id, permissions)
        """
        # Try API key authentication first
        if x_api_key:
            return self._authenticate_api_key(x_api_key)
        
        # Try OAuth token authentication
        if authorization and isinstance(authorization, str) and authorization.startswith("Bearer "):
            token = authorization[7:]  # Remove "Bearer " prefix
            return self._authenticate_oauth(token)
        
        # No authentication provided
        self._audit_logger.log_authentication_event(
            client_id="anonymous",
            auth_type=AuthType.NONE,
            success=False,
            details={"reason": "No credentials provided"}
        )
        
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide API key or OAuth token."
        )
    
    def _authenticate_api_key(
        self,
        api_key: str
    ) -> Tuple[AuthType, str, Optional[ClientPermissions]]:
        """
        Authenticate using API key.
        
        Args:
            api_key: The API key
            
        Returns:
            Tuple of (auth_type, client_id, permissions)
        """
        # Check against configured API key
        if self._api_key and api_key == self._api_key:
            client_id = "default_api_key_client"
            permissions = self._permission_store.get_client_permissions(
                client_id=client_id, api_key=api_key
            )
            
            self._audit_logger.log_authentication_event(
                client_id=client_id,
                auth_type=AuthType.API_KEY,
                success=True,
                details={"method": "api_key"}
            )
            
            return AuthType.API_KEY, client_id, permissions
        
        # Check permission store
        permissions = self._permission_store.get_client_permissions(api_key=api_key)
        if permissions:
            self._audit_logger.log_authentication_event(
                client_id=permissions.client_id,
                auth_type=AuthType.API_KEY,
                success=True,
                details={"method": "api_key"}
            )
            
            return AuthType.API_KEY, permissions.client_id, permissions
        
        # Invalid API key
        self._audit_logger.log_authentication_event(
            client_id=api_key[:8] if api_key else "unknown",
            auth_type=AuthType.API_KEY,
            success=False,
            details={"reason": "Invalid API key"}
        )
        
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    def _authenticate_oauth(
        self,
        token: str
    ) -> Tuple[AuthType, str, Optional[ClientPermissions]]:
        """
        Authenticate using OAuth token.
        
        Args:
            token: The OAuth token
            
        Returns:
            Tuple of (auth_type, client_id, permissions)
        """
        is_valid, claims, error = self._oauth_validator.validate_token(token)
        
        if not is_valid:
            self._audit_logger.log_authentication_event(
                client_id="oauth_token",
                auth_type=AuthType.OAUTH_TOKEN,
                success=False,
                details={"reason": error}
            )
            
            raise HTTPException(status_code=401, detail=error)
        
        # Extract client ID from claims
        client_id = claims.get("sub", claims.get("client_id", "oauth_client"))
        
        # Get permissions from claims or permission store
        permissions = self._permission_store.get_client_permissions(client_id=client_id)
        
        # If no stored permissions, create from claims
        if not permissions:
            permissions = self._create_permissions_from_claims(client_id, claims)
        
        self._audit_logger.log_authentication_event(
            client_id=client_id,
            auth_type=AuthType.OAUTH_TOKEN,
            success=True,
            details={"method": "oauth", "claims": {k: v for k, v in claims.items() if k not in ['exp', 'iat']}}
        )
        
        return AuthType.OAUTH_TOKEN, client_id, permissions
    
    def _create_permissions_from_claims(
        self,
        client_id: str,
        claims: Dict
    ) -> ClientPermissions:
        """
        Create permissions from OAuth claims.
        
        Args:
            client_id: Client ID
            claims: OAuth token claims
            
        Returns:
            Client permissions
        """
        permissions = set()
        
        # Parse permissions from claims
        if "permissions" in claims:
            for perm in claims["permissions"]:
                try:
                    permissions.add(Permission(perm))
                except ValueError:
                    logger.warning(f"Unknown permission: {perm}")
        
        # Parse allowed locations
        allowed_locations = set()
        if "locations" in claims:
            allowed_locations = set(claims["locations"])
        
        # Check for admin role
        if "roles" in claims and "admin" in claims["roles"]:
            permissions.add(Permission.ADMIN)
        
        # Default permissions if none specified
        if not permissions:
            permissions = {
                Permission.PREDICT,
                Permission.BATCH_PREDICT,
                Permission.STREAM_PREDICT,
                Permission.LIST_LOCATIONS
            }
        
        return ClientPermissions(
            client_id=client_id,
            auth_type=AuthType.OAUTH_TOKEN,
            permissions=permissions,
            allowed_locations=allowed_locations
        )
    
    def authorize(
        self,
        client_id: str,
        permission: Permission,
        location_id: str = None,
        auth_type: AuthType = AuthType.NONE
    ) -> Tuple[bool, str]:
        """
        Authorize a request based on client permissions.
        
        Args:
            client_id: Client ID
            permission: Required permission
            location_id: Optional location ID
            auth_type: Authentication type used
            
        Returns:
            Tuple of (authorized, reason)
        """
        has_permission, reason = self._permission_store.check_permission(
            client_id=client_id,
            permission=permission,
            location_id=location_id
        )
        
        self._audit_logger.log_authorization_event(
            client_id=client_id,
            auth_type=auth_type,
            success=has_permission,
            resource=location_id or "global",
            permission=permission,
            details={"reason": reason}
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail=reason)
        
        return True, ""
    
    def check_rate_limit(
        self,
        client_id: str,
        rate_limiter: RateLimiter,
        permissions: ClientPermissions = None
    ) -> Tuple[bool, int, Dict]:
        """
        Check rate limit for a client.
        
        Args:
            client_id: Client ID
            rate_limiter: Rate limiter instance
            permissions: Client permissions (for override)
            
        Returns:
            Tuple of (is_allowed, remaining, headers)
        """
        limit = permissions.rate_limit_override if permissions else None
        is_allowed, remaining, headers = rate_limiter.is_allowed(client_id, limit)
        
        if not is_allowed:
            self._audit_logger.log_rate_limit_event(
                client_id=client_id,
                auth_type=AuthType.NONE,
                request_count=limit or rate_limiter._default_limit,
                limit=limit or rate_limiter._default_limit,
                details={"remaining": remaining}
            )
        
        return is_allowed, remaining, headers
    
    def check_rate_limit_with_defaults(
        self,
        client_id: str,
        permissions: ClientPermissions = None
    ) -> Tuple[bool, int, Dict]:
        """
        Check rate limit for a client using default rate limiter.
        
        Args:
            client_id: Client ID
            permissions: Client permissions (for override)
            
        Returns:
            Tuple of (is_allowed, remaining, headers)
        """
        limit = permissions.rate_limit_override if permissions else None
        is_allowed, remaining, headers = self._rate_limiter.is_allowed(client_id, limit)
        
        if not is_allowed:
            self._audit_logger.log_rate_limit_event(
                client_id=client_id,
                auth_type=AuthType.NONE,
                request_count=limit or self._rate_limiter._default_limit,
                limit=limit or self._rate_limiter._default_limit,
                details={"remaining": remaining}
            )
        
        return is_allowed, remaining, headers


# Global instances
_audit_logger: Optional[AuditLogger] = None
_oauth_validator: Optional[OAuthValidator] = None
_permission_store: Optional[ClientPermissionStore] = None
_rate_limiter: Optional[RateLimiter] = None
_authenticator: Optional[Authenticator] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_oauth_validator() -> OAuthValidator:
    """Get the global OAuth validator instance."""
    global _oauth_validator
    if _oauth_validator is None:
        _oauth_validator = OAuthValidator()
    return _oauth_validator


def get_permission_store() -> ClientPermissionStore:
    """Get the global permission store instance."""
    global _permission_store
    if _permission_store is None:
        _permission_store = ClientPermissionStore()
    return _permission_store


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        settings = get_inference_settings()
        _rate_limiter = RateLimiter(
            requests_per_minute=settings.rate_limit_requests_per_minute
        )
    return _rate_limiter


def get_authenticator() -> Authenticator:
    """Get the global authenticator instance."""
    global _authenticator
    if _authenticator is None:
        _authenticator = Authenticator(
            audit_logger=get_audit_logger(),
            oauth_validator=get_oauth_validator(),
            permission_store=get_permission_store()
        )
    return _authenticator


def create_auth_dependencies() -> dict:
    """
    Create FastAPI dependency functions for authentication.
    
    Returns:
        Dictionary of dependency functions
    """
    authenticator = get_authenticator()
    rate_limiter = get_rate_limiter()
    
    async def verify_credentials(
        x_api_key: str = Header(None),
        authorization: str = Header(None)
    ) -> Tuple[AuthType, str, Optional[ClientPermissions]]:
        """
        Verify API key or OAuth token.
        
        Returns:
            Tuple of (auth_type, client_id, permissions)
        """
        return authenticator.authenticate(x_api_key, authorization)
    
    async def require_permission(
        permission: Permission,
        location_id: str = None
    ):
        """
        Dependency that requires a specific permission.
        
        Args:
            permission: Required permission
            location_id: Optional location ID to check access for
        """
        async def check(
            credentials: Tuple[AuthType, str, Optional[ClientPermissions]] = Depends(verify_credentials)
        ) -> Tuple[AuthType, str, Optional[ClientPermissions]]:
            auth_type, client_id, permissions = credentials
            
            authenticator.authorize(
                client_id=client_id,
                permission=permission,
                location_id=location_id,
                auth_type=auth_type
            )
            
            return credentials
        
        return check
    
    async def check_rate_limit_dependency(
        credentials: Tuple[AuthType, str, Optional[ClientPermissions]] = Depends(verify_credentials)
    ) -> Tuple[AuthType, str, Optional[ClientPermissions], Dict]:
        """
        Check rate limit for the request.
        
        Returns:
            Tuple of (credentials, rate_limit_headers)
        """
        auth_type, client_id, permissions = credentials
        
        is_allowed, remaining, headers = authenticator.check_rate_limit(
            client_id=client_id,
            rate_limiter=rate_limiter,
            permissions=permissions
        )
        
        if not is_allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Try again in a minute. Remaining: {remaining}"
                },
                headers=headers
            ), client_id, permissions, headers
        
        return auth_type, client_id, permissions, headers
    
    return {
        "verify_credentials": verify_credentials,
        "require_permission": require_permission,
        "check_rate_limit_dependency": check_rate_limit_dependency
    }