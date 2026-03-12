import time
import logging
import uuid
from starlette.types import ASGIApp, Scope, Receive, Send

logger = logging.getLogger("observability")

class ObservabilityMiddleware:
    """
    Native ASGI Observability Middleware.
    Provides high-fidelity timing and status logging without the overhead
    or instability of BaseHTTPMiddleware.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        from backend.utils.structured_logging import request_id_var
        
        # 1. Initialize metadata early to avoid UnboundLocalError
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "UNKNOWN")
        headers_dict = dict(scope.get("headers", []))
        request_id = headers_dict.get(b"x-request-id", str(uuid.uuid4()).encode()).decode()
        
        # 2. Set ContextVar for downstream loggers
        token = request_id_var.set(request_id)
        start_time = time.perf_counter()
        
        status_code = [0] 

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message.get("status", 0)
                # 3. Inject Request ID into response headers
                headers = list(message.get("headers", []))
                headers.append((b"X-Request-ID", request_id.encode()))
                message["headers"] = headers
            
            await send(message)
            
            if message["type"] == "http.response.body":
                if not message.get("more_body", False):
                    duration = (time.perf_counter() - start_time) * 1000
                    logger.info(
                        f"HTTP {method} {path} -> {status_code[0]} "
                        f"({duration:.2f}ms)"
                    )

        try:
            try:
                await self.app(scope, receive, send_wrapper)
            except Exception as e:
                duration = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"EXCEPTION {method} {path} after {duration:.2f}ms: {e}", 
                    exc_info=True
                )
                # Standardized internal crash response
                from backend.utils.responses import SafeJSONResponse
                response = SafeJSONResponse(
                    status_code=500,
                    content={"error": True, "message": "Internal Observability Error", "detail": str(e)}
                )
                return await response(scope, receive, send)
        finally:
            # 4. Clear context to prevent leaks
            request_id_var.reset(token)
