"""Middleware to capture request context for audit logging."""

import logging
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from audit import set_request_context

logger = logging.getLogger("audit-middleware")


class AuditContextMiddleware(BaseHTTPMiddleware):
    """
    Extracts user context from request and makes it available to audit logger.
    Captures: user_id, IP address, session_id
    """

    async def dispatch(self, request: Request, call_next):
        """Extract context and pass to audit logger."""
        # Extract user_id from request (could come from JWT, session, headers)
        user_id = self._get_user_id(request)

        # Extract IP address
        ip_address = self._get_client_ip(request)

        # Extract session_id from cookies or headers
        session_id = self._get_session_id(request)

        # Set context for audit logger
        set_request_context(user_id=user_id, ip_address=ip_address, session_id=session_id)

        # Continue with request
        response = await call_next(request)

        return response

    @staticmethod
    def _get_user_id(request: Request) -> Optional[str]:
        """Extract user_id from request."""
        # Try from query params first (for testing)
        if "user_id" in request.query_params:
            return request.query_params["user_id"]

        # Try from headers (JWT token claim, custom header)
        if "x-user-id" in request.headers:
            return request.headers["x-user-id"]

        # Try from cookies
        if "user_id" in request.cookies:
            return request.cookies["user_id"]

        # Try from path params (if any)
        if hasattr(request, "path_params") and "user_id" in request.path_params:
            return request.path_params["user_id"]

        return None

    @staticmethod
    def _get_client_ip(request: Request) -> Optional[str]:
        """Extract client IP address from request."""
        # Check X-Forwarded-For header (for proxied requests)
        if "x-forwarded-for" in request.headers:
            # Take first IP in chain
            return request.headers["x-forwarded-for"].split(",")[0].strip()

        # Check X-Real-IP header
        if "x-real-ip" in request.headers:
            return request.headers["x-real-ip"]

        # Get direct connection IP
        if request.client:
            return request.client.host

        return None

    @staticmethod
    def _get_session_id(request: Request) -> Optional[str]:
        """Extract session_id from request."""
        # Try from headers
        if "x-session-id" in request.headers:
            return request.headers["x-session-id"]

        # Try from cookies
        if "session_id" in request.cookies:
            return request.cookies["session_id"]

        if "sessionid" in request.cookies:
            return request.cookies["sessionid"]

        # Try from query params (for testing)
        if "session_id" in request.query_params:
            return request.query_params["session_id"]

        return None
