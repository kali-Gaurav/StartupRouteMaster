import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from services.multi_layer_cache import multi_layer_cache
        from database.config import Config

        # Skip for health/static
        if request.url.path.startswith(("/api/status/health", "/api/health", "/health", "/media", "/")):
            return await call_next(request)

        if not multi_layer_cache.redis:
            return await call_next(request)

        client_ip = request.client.host
        if client_ip in ("127.0.0.1", "localhost", "::1"):
            return await call_next(request)

        limit = Config.RATE_LIMIT_PER_MINUTE
        current_minute = int(time.time() / 60)
        key = f"rate_limit:{client_ip}:{current_minute}"

        try:
            request_count = await multi_layer_cache.redis.incr(key)
            if request_count == 1:
                await multi_layer_cache.redis.expire(key, 60)

            if request_count > limit:
                logger.warning(f"⚠️ Rate limit exceeded: {client_ip}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": True,
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please try again later.",
                        "limit": limit
                    }
                )
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            return await call_next(request)

        return await call_next(request)
