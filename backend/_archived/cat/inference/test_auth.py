"""
Tests for authentication and rate limiting in the CAT inference service.
Validates Requirements 10.4, 10.5, 10.6
"""

import pytest
import time
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import auth module components directly
from cat.inference.auth import (
    AuthType,
    Permission,
    ClientPermissions,
    AuthEvent,
    AuditLogger,
    OAuthValidator,
    ClientPermissionStore,
    RateLimiter,
    Authenticator,
    get_audit_logger,
    get_rate_limiter,
    get_authenticator,
    get_permission_store
)


class TestAuditLogger:
    """Tests for the AuditLogger class."""
    
    def test_log_authentication_event_success(self):
        """Test logging successful authentication event."""
        logger = AuditLogger()
        logger.log_authentication_event(
            client_id="test_client",
            auth_type=AuthType.API_KEY,
            success=True,
            details={"method": "api_key"}
        )
        
        events = logger.get_events()
        assert len(events) == 1
        assert events[0].success is True
        assert events[0].event_type == "authentication"
    
    def test_log_authentication_event_failure(self):
        """Test logging failed authentication event."""
        logger = AuditLogger()
        logger.log_authentication_event(
            client_id="invalid_key",
            auth_type=AuthType.API_KEY,
            success=False,
            details={"reason": "Invalid API key"}
        )
        
        events = logger.get_events()
        assert len(events) == 1
        assert events[0].success is False
    
    def test_log_rate_limit_event(self):
        """Test logging rate limit exceeded event."""
        logger = AuditLogger()
        logger.log_rate_limit_event(
            client_id="test_client",
            auth_type=AuthType.API_KEY,
            request_count=100,
            limit=100
        )
        
        events = logger.get_events(event_type="rate_limit_exceeded")
        assert len(events) == 1
        assert events[0].success is False
        assert events[0].details["request_count"] == 100
    
    def test_get_auth_stats(self):
        """Test getting authentication statistics."""
        logger = AuditLogger()
        
        # Log some events
        logger.log_authentication_event("client1", AuthType.API_KEY, True)
        logger.log_authentication_event("client2", AuthType.API_KEY, True)
        logger.log_authentication_event("client3", AuthType.API_KEY, False)
        logger.log_authentication_event("client4", AuthType.OAUTH_TOKEN, True)
        
        stats = logger.get_auth_stats()
        assert stats["total_events"] == 4
        assert stats["successful_authentications"] == 3
        assert stats["failed_authentications"] == 1
        assert stats["by_auth_type"]["api_key"] == 3
        assert stats["by_auth_type"]["oauth_token"] == 1


class TestOAuthValidator:
    """Tests for the OAuthValidator class."""
    
    def test_validate_empty_token(self):
        """Test validation of empty token."""
        validator = OAuthValidator()
        is_valid, claims, error = validator.validate_token("")
        
        assert is_valid is False
        assert claims is None
        assert "empty" in error.lower()
    
    def test_validate_jwt_token_valid(self):
        """Test validation of valid JWT token."""
        import base64
        import json
        
        # Create a simple JWT token (header.payload.signature)
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": "test_client",
            "permissions": ["predict", "batch_predict"],
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        signature = "fake_signature"
        
        token = f"{header_b64}.{payload_b64}.{signature}"
        
        validator = OAuthValidator()
        is_valid, claims, error = validator.validate_token(token)
        
        assert is_valid is True
        assert claims is not None
        assert claims["sub"] == "test_client"
    
    def test_validate_jwt_token_expired(self):
        """Test validation of expired JWT token."""
        import base64
        import json
        
        # Create an expired JWT token
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": "test_client",
            "exp": int((datetime.utcnow() - timedelta(hours=1)).timestamp())
        }
        
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        signature = "fake_signature"
        
        token = f"{header_b64}.{payload_b64}.{signature}"
        
        validator = OAuthValidator()
        is_valid, claims, error = validator.validate_token(token)
        
        assert is_valid is False
        assert "expired" in error.lower()
    
    def test_validate_opaque_token_valid(self):
        """Test validation of valid opaque token."""
        validator = OAuthValidator()
        validator.register_token("valid_opaque_token", {"sub": "client1"}, 3600)
        
        is_valid, claims, error = validator.validate_token("valid_opaque_token")
        
        assert is_valid is True
        assert claims["sub"] == "client1"
    
    def test_validate_opaque_token_invalid(self):
        """Test validation of invalid opaque token."""
        validator = OAuthValidator()
        
        is_valid, claims, error = validator.validate_token("invalid_token")
        
        assert is_valid is False
        assert claims is None
    
    def test_revoke_token(self):
        """Test revoking a token."""
        validator = OAuthValidator()
        validator.register_token("token_to_revoke", {"sub": "client1"}, 3600)
        
        # Token should be valid
        is_valid, _, _ = validator.validate_token("token_to_revoke")
        assert is_valid is True
        
        # Revoke the token
        result = validator.revoke_token("token_to_revoke")
        assert result is True
        
        # Token should now be invalid
        is_valid, _, _ = validator.validate_token("token_to_revoke")
        assert is_valid is False


class TestClientPermissionStore:
    """Tests for the ClientPermissionStore class."""
    
    def test_register_client(self):
        """Test registering a new client."""
        store = ClientPermissionStore()
        
        permissions = ClientPermissions(
            client_id="new_client",
            auth_type=AuthType.API_KEY,
            permissions={Permission.PREDICT, Permission.BATCH_PREDICT},
            allowed_locations={"loc1", "loc2"}
        )
        
        store.register_client("new_api_key", permissions)
        
        retrieved = store.get_client_permissions(api_key="new_api_key")
        assert retrieved is not None
        assert retrieved.client_id == "new_client"
        assert Permission.PREDICT in retrieved.permissions
    
    def test_check_permission_allowed(self):
        """Test checking permission when client has it."""
        store = ClientPermissionStore()
        
        permissions = ClientPermissions(
            client_id="test_client",
            auth_type=AuthType.API_KEY,
            permissions={Permission.PREDICT}
        )
        store.register_client("test_key", permissions)
        
        has_permission, reason = store.check_permission("test_client", Permission.PREDICT)
        
        assert has_permission is True
        assert reason == ""
    
    def test_check_permission_denied(self):
        """Test checking permission when client lacks it."""
        store = ClientPermissionStore()
        
        permissions = ClientPermissions(
            client_id="test_client",
            auth_type=AuthType.API_KEY,
            permissions={Permission.PREDICT}
        )
        store.register_client("test_key", permissions)
        
        has_permission, reason = store.check_permission("test_client", Permission.ADMIN)
        
        assert has_permission is False
        assert "Missing permission" in reason
    
    def test_check_location_access(self):
        """Test checking location access."""
        store = ClientPermissionStore()
        
        permissions = ClientPermissions(
            client_id="test_client",
            auth_type=AuthType.API_KEY,
            permissions={Permission.PREDICT},
            allowed_locations={"loc1", "loc2"}
        )
        store.register_client("test_key", permissions)
        
        # Should be allowed for loc1
        has_permission, _ = store.check_permission("test_client", Permission.PREDICT, "loc1")
        assert has_permission is True
        
        # Should be denied for loc3
        has_permission, reason = store.check_permission("test_client", Permission.PREDICT, "loc3")
        assert has_permission is False
        assert "not accessible" in reason
    
    def test_check_expired_client(self):
        """Test checking permission for expired client."""
        store = ClientPermissionStore()
        
        permissions = ClientPermissions(
            client_id="expired_client",
            auth_type=AuthType.API_KEY,
            permissions={Permission.PREDICT},
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        store.register_client("expired_key", permissions)
        
        has_permission, reason = store.check_permission("expired_client", Permission.PREDICT)
        
        assert has_permission is False
        assert "expired" in reason.lower()
    
    def test_add_remove_permissions(self):
        """Test adding and removing permissions."""
        store = ClientPermissionStore()
        
        permissions = ClientPermissions(
            client_id="test_client",
            auth_type=AuthType.API_KEY,
            permissions={Permission.PREDICT}
        )
        store.register_client("test_key", permissions)
        
        # Add permission
        store.add_client_permission("test_client", Permission.ADMIN)
        
        retrieved = store.get_client_permissions(client_id="test_client")
        assert Permission.ADMIN in retrieved.permissions
        
        # Remove permission
        store.remove_client_permission("test_client", Permission.ADMIN)
        
        retrieved = store.get_client_permissions(client_id="test_client")
        assert Permission.ADMIN not in retrieved.permissions


class TestRateLimiter:
    """Tests for the RateLimiter class."""
    
    def test_is_allowed_under_limit(self):
        """Test request allowed when under limit."""
        limiter = RateLimiter(requests_per_minute=10)
        
        is_allowed, remaining, headers = limiter.is_allowed("client1")
        
        assert is_allowed is True
        assert remaining == 9
        assert "X-RateLimit-Limit" in headers
    
    def test_is_allowed_at_limit(self):
        """Test request denied when at limit."""
        limiter = RateLimiter(requests_per_minute=3)
        
        # Make 3 requests
        for _ in range(3):
            limiter.is_allowed("client1")
        
        # Fourth request should be denied
        is_allowed, remaining, headers = limiter.is_allowed("client1")
        
        assert is_allowed is False
        assert remaining == 0
        assert headers["X-RateLimit-Remaining"] == "0"
    
    def test_rate_limit_headers(self):
        """Test rate limit headers are correct."""
        limiter = RateLimiter(requests_per_minute=60)
        
        is_allowed, remaining, headers = limiter.is_allowed("client1")
        
        assert headers["X-RateLimit-Limit"] == "60"
        assert int(headers["X-RateLimit-Remaining"]) == remaining
        assert "X-RateLimit-Reset" in headers
    
    def test_get_remaining(self):
        """Test getting remaining requests."""
        limiter = RateLimiter(requests_per_minute=10)
        
        # Make 5 requests
        for _ in range(5):
            limiter.is_allowed("client1")
        
        remaining = limiter.get_remaining("client1")
        
        assert remaining == 5
    
    def test_get_usage(self):
        """Test getting usage statistics."""
        limiter = RateLimiter(requests_per_minute=10)
        
        for _ in range(3):
            limiter.is_allowed("client1")
        
        usage = limiter.get_usage("client1")
        
        assert usage["requests_in_window"] == 3
        assert "window_seconds_remaining" in usage


class TestAuthenticator:
    """Tests for the Authenticator class."""
    
    def test_authenticate_api_key_valid(self):
        """Test authentication with valid API key."""
        authenticator = Authenticator(
            api_key="valid_key",
            audit_logger=AuditLogger()
        )
        
        auth_type, client_id, permissions = authenticator.authenticate(x_api_key="valid_key")
        
        assert auth_type == AuthType.API_KEY
        assert client_id is not None
    
    def test_authenticate_api_key_invalid(self):
        """Test authentication with invalid API key."""
        authenticator = Authenticator(
            api_key="valid_key",
            audit_logger=AuditLogger()
        )
        
        with pytest.raises(HTTPException) as exc_info:
            authenticator.authenticate(x_api_key="invalid_key")
        
        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail
    
    def test_authenticate_oauth_valid(self):
        """Test authentication with valid OAuth token."""
        import base64
        import json
        
        # Create a valid JWT
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": "oauth_client",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        
        token = f"{header_b64}.{payload_b64}.sig"
        
        authenticator = Authenticator(
            audit_logger=AuditLogger(),
            oauth_validator=OAuthValidator()
        )
        
        auth_type, client_id, permissions = authenticator.authenticate(authorization=f"Bearer {token}")
        
        assert auth_type == AuthType.OAUTH_TOKEN
        assert client_id == "oauth_client"
    
    def test_authenticate_no_credentials(self):
        """Test authentication with no credentials."""
        authenticator = Authenticator(audit_logger=AuditLogger())
        
        with pytest.raises(HTTPException) as exc_info:
            authenticator.authenticate()
        
        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail
    
    def test_authorize_permission_granted(self):
        """Test authorization when permission is granted."""
        store = ClientPermissionStore()
        permissions = ClientPermissions(
            client_id="test_client",
            auth_type=AuthType.API_KEY,
            permissions={Permission.PREDICT},
            allowed_locations=set()
        )
        store.register_client("test_key", permissions)
        
        authenticator = Authenticator(
            permission_store=store,
            audit_logger=AuditLogger()
        )
        
        authorized, reason = authenticator.authorize(
            client_id="test_client",
            permission=Permission.PREDICT,
            auth_type=AuthType.API_KEY
        )
        
        assert authorized is True
    
    def test_authorize_permission_denied(self):
        """Test authorization when permission is denied."""
        store = ClientPermissionStore()
        permissions = ClientPermissions(
            client_id="test_client",
            auth_type=AuthType.API_KEY,
            permissions={Permission.PREDICT},
            allowed_locations=set()
        )
        store.register_client("test_key", permissions)
        
        authenticator = Authenticator(
            permission_store=store,
            audit_logger=AuditLogger()
        )
        
        with pytest.raises(HTTPException) as exc_info:
            authenticator.authorize(
                client_id="test_client",
                permission=Permission.ADMIN,
                auth_type=AuthType.API_KEY
            )
        
        assert exc_info.value.status_code == 403
    
    def test_check_rate_limit(self):
        """Test rate limit checking."""
        limiter = RateLimiter(requests_per_minute=10)
        authenticator = Authenticator(
            audit_logger=AuditLogger()
        )
        authenticator._rate_limiter = limiter
        
        # Should be allowed
        is_allowed, remaining, headers = authenticator.check_rate_limit_with_defaults("client1")
        
        assert is_allowed is True
        assert remaining > 0


class TestGlobalInstances:
    """Tests for global instance functions."""
    
    def test_get_audit_logger_singleton(self):
        """Test that audit logger is a singleton."""
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        
        assert logger1 is logger2
    
    def test_get_rate_limiter_singleton(self):
        """Test that rate limiter is a singleton."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        
        assert limiter1 is limiter2
    
    def test_get_authenticator_singleton(self):
        """Test that authenticator is a singleton."""
        auth1 = get_authenticator()
        auth2 = get_authenticator()
        
        assert auth1 is auth2
    
    def test_get_permission_store_singleton(self):
        """Test that permission store is a singleton."""
        store1 = get_permission_store()
        store2 = get_permission_store()
        
        assert store1 is store2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])