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

# --- User/Product Metrics ---
ACTIVE_USERS = Gauge(
    "active_users",
    "Current number of active users"
)

# --- User Behavior Metrics ---
ROUTE_SEARCH_TOTAL = Counter(
    "route_search_total",
    "Total number of route searches performed",
    ["mode"] # 'standard', 'women_safety'
)

ROUTE_SELECTED_TOTAL = Counter(
    "route_selected_total",
    "Total number of routes selected/viewed by users"
)

CHATBOT_MESSAGES_TOTAL = Counter(
    "chatbot_messages_total",
    "Total number of messages processed by Diksha AI",
    ["intent"]
)

CHATBOT_ACTION_EXECUTED_TOTAL = Counter(
    "chatbot_action_executed_total",
    "Total chatbot actions executed",
    ["action_type"]
)

CHATBOT_SOS_TRIGGERED_TOTAL = Counter(
    "chatbot_sos_triggered_total",
    "Total SOS triggered via chatbot"
)

CHATBOT_GUARDIAN_TRIGGERED_TOTAL = Counter(
    "chatbot_guardian_triggered_total",
    "Total Guardian mode triggered via chatbot"
)

CHATBOT_CONVERSION_TOTAL = Counter(
    "chatbot_conversion_total",
    "Total successful conversions/bookings via chatbot"
)

LOGIN_SUCCESS_TOTAL = Counter("login_success_total", "Total successful logins")
LOGIN_FAILURE_TOTAL = Counter("login_failure_total", "Total failed logins", ["reason"])

# --- Safety Intelligence Metrics ---
SAFETY_SCORE_AVG = Histogram(
    "safety_score_distribution",
    "Distribution of safety scores for generated routes",
    buckets=(0, 20, 40, 60, 70, 80, 90, 100)
)

RISK_ALERTS_TOTAL = Counter(
    "safety_risk_alerts_total",
    "Total AI-detected safety risk alerts",
    ["type"] # 'deviation', 'abnormal_stop', 'delay'
)

ABNORMAL_STOP_DETECTED_TOTAL = Counter(
    "abnormal_stop_detected_total",
    "Total number of abnormal stops detected by AI monitoring"
)

# --- Push System Metrics ---
PUSH_CLICKED_TOTAL = Counter(
    "push_notifications_clicked_total",
    "Total number of push notifications clicked by users"
)

# --- SOS/Emergency Metrics ---
SOS_ALERTS_TOTAL = Counter(
    "sos_alerts_total",
    "Total SOS alerts received",
    ["severity", "status"]
)

GUARDIAN_MODE_ACTIVATIONS = Counter(
    "guardian_mode_activations_total",
    "Total number of times Guardian Mode was activated"
)

# --- Performance Metrics ---
ROUTING_ENGINE_DURATION = Histogram(
    "routing_engine_duration_seconds",
    "Time taken for route computation",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
)

AI_PREDICTION_DURATION = Histogram(
    "ai_prediction_duration_seconds",
    "Time taken for AI delay/reliability predictions",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0)
)

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Time taken for database queries",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5)
)

REDIS_CACHE_HITS = Counter(
    "redis_cache_hits_total",
    "Total number of Redis cache hits"
)

REDIS_CACHE_MISSES = Counter(
    "redis_cache_misses_total",
    "Total number of Redis cache misses"
)

# --- Push Notification Metrics ---
PUSH_NOTIFICATIONS_SENT = Counter(
    "push_notifications_sent_total",
    "Total number of push notifications sent"
)

PUSH_NOTIFICATIONS_FAILED = Counter(
    "push_notifications_failed_total",
    "Total number of push notifications failed"
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
