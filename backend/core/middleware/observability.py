import time
import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger("observability")

class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        
        # Subtask 20.1: SOS Traffic Marking
        path = request.url.path
        is_sos = "/api/sos" in path or request.headers.get("X-SOS-Priority") == "true"
        if is_sos:
            logger.info(f"🚨 [PRIORITY] High-urgency SOS traffic detected: {path}")
            request.state.is_priority = True
        else:
            request.state.is_priority = False
        
        # Suggestion #4: Middleware Overhead tracking
        middleware_start = time.perf_counter()
        
        start_time = time.perf_counter()
        response = await call_next(request)
        duration = (time.perf_counter() - start_time) * 1000
        
        # Suggestion #5: Endpoint Heatmap
        path = request.url.path
        
        try:
            await multi_layer_cache.initialize()
            if multi_layer_cache.redis:
                ts = int(time.time())
                min_key = ts // 60
                latency_key = f"metrics:latency:{min_key}"
                heatmap_key = f"metrics:heatmap:{datetime.utcnow().date().isoformat()}"
                
                # 1. Percentile tracking (ZSET)
                await multi_layer_cache.redis.zadd(latency_key, {f"{duration}:{uuid.uuid4().hex[:4]}": duration})
                
                # 2. Heatmap tracking (HINCRBY)
                await multi_layer_cache.redis.hincrby(heatmap_key, path, 1)
                
                # 3. Auto-Throttle Trigger (Suggestion #3)
                # Check recent p99 (sample last 10 requests for speed)
                recent = await multi_layer_cache.redis.zrange(latency_key, -10, -1, withscores=True)
                if recent:
                    p99_sample = max([s for _, s in recent])
                    if p99_sample > 2000: # 2 seconds
                        await multi_layer_cache.redis.setex("system:low_latency_mode", 60, "1")
                        logger.critical(f"⚠️ AUTO-THROTTLE: p99 sample {p99_sample}ms > 2000ms. Low-latency mode enabled for 60s.")
                
        except Exception as e:
            logger.error(f"Metrics error: {e}")

        response.headers["X-Correlation-ID"] = correlation_id
        return response

from datetime import datetime
