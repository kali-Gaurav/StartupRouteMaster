import time
import logging
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

class RateLimitMiddleware:
    """
    Native ASGI Rate Limit Middleware.
    Prevents abuse without the overhead of BaseHTTPMiddleware.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        try:
            from services.multi_layer_cache import multi_layer_cache
            from database.config import Config

            path = scope.get("path", "")
            
            # 1. Skip for health/static/root
            if path.startswith(("/api/status/health", "/api/health", "/health", "/media")) or path == "/":
                return await self.app(scope, receive, send)

            if not multi_layer_cache.redis:
                return await self.app(scope, receive, send)

            # 2. Extract Client IP
            client = scope.get("client")
            client_ip = client[0] if client else "unknown"
            
            if client_ip in ("127.0.0.1", "localhost", "::1"):
                return await self.app(scope, receive, send)

            # 3. Rate Limit Logic
            limit = Config.RATE_LIMIT_PER_MINUTE
            current_minute = int(time.time() / 60)
            key = f"rate_limit:{client_ip}:{current_minute}"

            try:
                request_count = await multi_layer_cache.redis.incr(key)
                if request_count == 1:
                    await multi_layer_cache.redis.expire(key, 60)

                if request_count > limit:
                    logger.warning(f"⚠️ Rate limit exceeded: {client_ip} on {path}")
                    response = JSONResponse(
                        status_code=429,
                        content={
                            "error": True,
                            "error_code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please try again later.",
                            "limit": limit
                        }
                    )
                    return await response(scope, receive, send)
            except Exception as e:
                logger.error(f"Rate limiter inner error: {e}")
                # On Redis error, allow request to pass (fail open)
                return await self.app(scope, receive, send)

            return await self.app(scope, receive, send)
            
        except Exception as exc:
            logger.error(f"CRITICAL: RateLimit Middleware Crash: {exc}", exc_info=True)
            from backend.utils.responses import SafeJSONResponse
            response = SafeJSONResponse(
                status_code=500,
                content={"error": True, "message": "Internal Rate Limit Error", "detail": str(exc)}
            )
            return await response(scope, receive, send)
