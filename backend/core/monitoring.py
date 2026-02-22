from prometheus_client import Counter, Gauge, Histogram, Summary
import time
from functools import wraps

# --- WebSocket Metrics ---
WS_CONNECTIONS = Gauge(
    "websocket_active_connections", 
    "Number of active WebSocket connections"
)

WS_TRAIN_SUBSCRIPTIONS = Gauge(
    "websocket_train_subscriptions_total",
    "Total active subscriptions to train updates",
    ["train_number"]
)

WS_BROADCAST_ERRORS = Counter(
    "websocket_broadcast_errors_total",
    "Total errors during WebSocket broadcasting",
    ["type"]  # 'pos' or 'sos'
)

# --- SOS/Emergency Metrics ---
SOS_ALERTS_TOTAL = Counter(
    "sos_alerts_total",
    "Total SOS alerts received",
    ["severity", "status"]
)

SOS_ENRICHMENT_LATENCY = Histogram(
    "sos_enrichment_duration_seconds",
    "Time taken to enrich raw SOS with railway context",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

SOS_BROADCAST_LATENCY = Histogram(
    "sos_broadcast_duration_seconds",
    "Time taken to broadcast SOS to all responders",
    buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1.0)
)

# --- Real-time Ingestion Metrics ---
BROADCASTER_TICK_DURATION = Summary(
    "broadcaster_tick_duration_seconds",
    "Time taken for one interpolation/broadcast tick"
)

REDIS_HEALTH_CHECKS = Counter(
    "redis_health_checks_total",
    "Total Redis connection health checks",
    ["status"]
)

SYSTEM_DEGRADED_MODE = Gauge(
    "system_degraded_mode",
    "Whether the system is in degraded mode (1=True, 0=False)",
    ["reason"] # redis_failure, database_latency
)

# --- Helper for timing ---
def track_latency(histogram):
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                latency = time.perf_counter() - start_time
                histogram.observe(latency)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                latency = time.perf_counter() - start_time
                histogram.observe(latency)
                
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
