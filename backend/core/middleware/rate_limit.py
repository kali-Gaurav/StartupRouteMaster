import time
import logging
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse
from utils.responses import SafeJSONResponse
from services.multi_layer_cache import multi_layer_cache
from database.config import Config
from utils.rate_limiter import RedisTokenBucket
from core.engines.orchestrator import orchestrator

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
            path = scope.get("path", "")
            
            # 1. Skip for health/static/root/stats
            if path.startswith(("/api/status/health", "/api/health", "/health", "/media", "/api/stats")) or path == "/":
                return await self.app(scope, receive, send)

            if not multi_layer_cache.redis:
                return await self.app(scope, receive, send)

            # 2. Extract Client IP
            client = scope.get("client")
            client_ip = client[0] if client else "unknown"
            
            if client_ip in ("127.0.0.1", "localhost", "::1"):
                return await self.app(scope, receive, send)

            # 3. Distributed Rate Limit Logic (Token Bucket)
            limiter = RedisTokenBucket(multi_layer_cache.redis)
            limit = Config.RATE_LIMIT_PER_MINUTE
            rate = limit / 60.0
            
            key = f"rl:token_bucket:{client_ip}"
            is_allowed, remaining = await limiter.is_allowed(key, rate, limit)

            if not is_allowed:
                logger.warning(f"⚠️ Rate limit exceeded (Token Bucket): {client_ip} on {path}")
                
                # [4.7] Report to PenaltyBox
                await orchestrator.penalty_box.report_error(client_ip)

                response = SafeJSONResponse(
                    status_code=429,
                    content={
                        "error": True,
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please try again later.",
                        "limit": limit
                    }
                )
                return await response(scope, receive, send)

            return await self.app(scope, receive, send)
            
        except Exception as exc:
            logger.error(f"CRITICAL: RateLimit Middleware Crash: {exc}", exc_info=True)
            response = SafeJSONResponse(
                status_code=500,
                content={"error": True, "message": "Internal Rate Limit Error", "detail": str(exc)}
            )
            return await response(scope, receive, send)
