from prometheus_client import Histogram, Counter, Gauge

# --- Search Metrics ---
# Histogram for search request duration in seconds
SEARCH_LATENCY_SECONDS = Histogram(
    'search_request_duration_seconds',
    'Histogram of search request processing durations.',
    ['endpoint'] # Label for distinguishing different search endpoints
)

# Counter for total search requests
SEARCH_REQUESTS_TOTAL = Counter(
    'search_requests_total',
    'Total number of search requests.',
    ['endpoint', 'status'] # Labels for endpoint and outcome (success/failure)
)

# --- Lock Contention Metrics ---
# Counter for lock acquisition attempts
LOCK_ACQUISITION_ATTEMPTS_TOTAL = Counter(
    'lock_acquisition_attempts_total',
    'Total number of lock acquisition attempts.',
    ['lock_name', 'outcome'] # Labels for lock name and outcome (acquired/failed)
)

# Histogram for lock hold duration
LOCK_HOLD_DURATION_SECONDS = Histogram(
    'lock_hold_duration_seconds',
    'Histogram of time (in seconds) that locks are held.',
    ['lock_name'] # Label for lock name
)

# --- Webhook Metrics ---
# Counter for total webhook events received
WEBHOOK_EVENTS_TOTAL = Counter(
    'webhook_events_total',
    'Total number of webhook events received.',
    ['provider', 'event_type', 'status'] # Labels for provider, event type, and processing status
)

# Counter for webhook processing errors
WEBHOOK_ERRORS_TOTAL = Counter(
    'webhook_errors_total',
    'Total number of errors encountered during webhook processing.',
    ['provider', 'event_type', 'error_type'] # Labels for provider, event type, and error type
)

# --- General Application Metrics ---
# Gauge for current active sessions (example)
ACTIVE_SESSIONS = Gauge(
    'active_sessions',
    'Number of currently active user sessions.'
)

# Example: Gauge for the number of loaded routes in RouteEngine
ROUTE_ENGINE_LOADED_STATUS = Gauge(
    'route_engine_loaded_status',
    'Status of the RouteEngine graph loading (1 if loaded, 0 otherwise).'
)

# Example: Gauge for the last successful ETL sync timestamp
LAST_ETL_SYNC_TIMESTAMP = Gauge(
    'last_etl_sync_timestamp',
    'Unix timestamp of the last successful ETL sync.'
)
