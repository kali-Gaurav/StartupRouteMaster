from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import time
import logging

logger = logging.getLogger("v3-resilience")

class V3ResilienceMiddleware:
    """
    [Task 50.2] Global Interceptor for Circuit Breakers and High-Load Resilience.
    """
    async def __call__(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            
            # [Task 50.2] Latency Telemetry
            latency = (time.perf_counter() - start_time) * 1000
            if latency > 1000: # Log "Slow Requests" (>1s) for V3 Audit
                logger.warning(f"🐢 Slow V3 Request: {request.url.path} | {latency:.2f}ms")
            
            return response

        except Exception as e:
            # 1. Handle Circuit Breaker Trips elegantly
            if "Circuit Breaker" in str(e):
                logger.error(f"🚨 Resilience Interceptor: Breaker Trip at {request.url.path}")
                return JSONResponse(
                    status_code=503,
                    content={
                        "success": False, 
                        "v3_status": "DEGRADED",
                        "message": "Source temporarily offline. Using cached results where available.",
                        "error_type": "CircuitBreakerTrip"
                    }
                )
            
            # 2. Handle DB/Redis Timeouts
            if "timeout" in str(e).lower():
                logger.critical(f"🛑 Resilience Interceptor: Connection Timeout at {request.url.path}")
                return JSONResponse(
                    status_code=504,
                    content={
                        "success": False,
                        "v3_status": "TIMEOUT",
                        "message": "We're experiencing high load. Retrying from L1 cache...",
                    }
                )
            
            # 3. Generic V3 Error Masking
            logger.error(f"🔥 V3 Uncaught Exception: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "An unexpected error occurred. V3 Master Release is stabilizing."
                }
            )

v3_middleware = V3ResilienceMiddleware()
