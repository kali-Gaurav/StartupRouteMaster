import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Task 13: Redis-based API Rate Limiting.
    Protects against DDoS and brute-force by limiting requests per IP.
    """
    async def dispatch(self, request: Request, call_next):
        # Lazy imports to avoid pulling heavy dependencies into app startup.
        from services.multi_layer_cache import multi_layer_cache
        from database.config import Config

        # Skip rate limiting for health checks and static files
        if request.url.path.startswith(("/api/status/health", "/health", "/media", "/")):
            if request.url.path == "/": # Keep root simple
                return await call_next(request)
            if request.url.path.startswith(("/api/status/health", "/health", "/media")):
                return await call_next(request)

        # Skip if Redis is not available (local dev fallback)
        if not multi_layer_cache.redis:
            return await call_next(request)

        client_ip = request.client.host
        
        # Task 4.10: Whitelist localhost/internal for verification scripts
        if client_ip in ("127.0.0.1", "localhost", "::1"):
            return await call_next(request)

        # Window: 1 minute
        current_minute = int(time.time() / 60)
        key = f"rate_limit:{client_ip}:{current_minute}"

        try:
            # Increment request count for this IP in the current minute
            request_count = await multi_layer_cache.redis.incr(key)
            if request_count == 1:
                # Set expiry if this is the first request in this window
                await multi_layer_cache.redis.expire(key, 60)

            if request_count > Config.RATE_LIMIT_PER_MINUTE:
                logger.warning(f"⚠️ Rate limit exceeded for IP: {client_ip} ({request_count} requests)")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": True,
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please try again in a minute."
                    }
                )
        except Exception as e:
            # Fallback: if Redis fails, allow the request but log the error
            logger.error(f"Rate limiter error: {e}")
            return await call_next(request)

        return await call_next(request)
