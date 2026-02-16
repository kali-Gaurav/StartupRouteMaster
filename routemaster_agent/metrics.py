from prometheus_client import Counter, Histogram, Gauge

# --- Extraction metrics ---
RMA_EXTRACTION_DURATION_SECONDS = Histogram(
    'rma_extraction_duration_seconds',
    'Histogram of extraction durations (seconds).',
    ['source', 'train_number', 'proxy_id'],
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120)
)
RMA_EXTRACTION_ATTEMPTS_TOTAL = Counter(
    'rma_extraction_attempts_total',
    'Total number of extraction attempts.',
    ['source', 'train_number', 'proxy_id']
)
RMA_EXTRACTION_FAILURES_TOTAL = Counter(
    'rma_extraction_failures_total',
    'Total number of extraction failures.',
    ['source', 'train_number', 'proxy_id']
)
RMA_EXTRACTION_SUCCESS_TOTAL = Counter(
    'rma_extraction_success_total',
    'Total number of successful extractions.',
    ['source', 'train_number', 'proxy_id']
)

# --- Data quality / validation ---
RMA_STATIONS_EXTRACTED_TOTAL = Counter(
    'rma_stations_extracted_total',
    'Number of station rows extracted per train.',
    ['source', 'train_number']
)
RMA_VALIDATION_FAILURES_TOTAL = Counter(
    'rma_validation_failures_total',
    'Validation failures during data cleaning/parsing.',
    ['source', 'train_number']
)
RMA_JSON_SCHEMA_FAILURES_TOTAL = Counter(
    'rma_json_schema_failures_total',
    'Failures while validating JSON schema for extracted payloads.',
    ['source', 'train_number']
)
RMA_CSV_PARITY_FAILURES_TOTAL = Counter(
    'rma_csv_parity_failures_total',
    'CSV parity / export consistency failures.',
    ['source', 'train_number']
)
RMA_DB_MISMATCH_TOTAL = Counter(
    'rma_db_mismatch_total',
    'Number of DB upsert/mismatch events detected.',
    ['train_number']
)

# --- Proxy intelligence ---
RMA_PROXY_REQUESTS_TOTAL = Counter(
    'rma_proxy_requests_total',
    'Number of HTTP requests attempted through a proxy.',
    ['proxy']
)
RMA_PROXY_FAILURES_TOTAL = Counter(
    'rma_proxy_failures_total',
    'Number of failed proxy requests.',
    ['proxy']
)
RMA_PROXY_DISABLED_TOTAL = Counter(
    'rma_proxy_disabled_total',
    'Number of times a proxy was auto-disabled by health checks.',
    ['proxy']
)
RMA_PROXY_HEALTH_SCORE = Gauge(
    'rma_proxy_health_score',
    'Computed health score for a proxy (0.0-1.0).',
    ['proxy']
)

# --- Selector telemetry & extraction confidence ---
RMA_SELECTOR_FALLBACK_TOTAL = Counter(
    'rma_selector_fallback_total',
    'Number of times selector fallback was used.',
    ['source', 'train_number']
)
RMA_SELECTOR_PRIMARY_FAILURES_TOTAL = Counter(
    'rma_selector_primary_failures_total',
    'Number of times primary selector failed and fallback was attempted.',
    ['source', 'train_number']
)
RMA_SELECTOR_SEMANTIC_SUCCESS_TOTAL = Counter(
    'rma_selector_semantic_success_total',
    'Number of times semantic/table heuristic successfully extracted data.',
    ['source', 'train_number']
)
RMA_EXTRACTION_CONFIDENCE = Gauge(
    'rma_extraction_confidence',
    'Per-extraction confidence score (0.0-1.0).',
    ['source', 'train_number']
)

# --- Selector promotion & registry metrics ---
RMA_SELECTOR_PROMOTIONS_TOTAL = Counter(
    'rma_selector_promotions_total',
    'Number of times a backup selector was auto-promoted to primary.',
    ['page_type']
)
RMA_SELECTOR_FAILURE_RATE = Gauge(
    'rma_selector_failure_rate',
    'Failure rate for the primary selector (0..1).',
    ['page_type']
)
RMA_SELECTOR_ACTIVE_PRIMARY = Gauge(
    'rma_selector_active_primary',
    'Active primary selector identifier (gauge with selector label set to 1 for the active primary).',
    ['page_type', 'selector']
)

# per-train reliability score (0..1)
RMA_TRAIN_RELIABILITY_SCORE = Gauge(
    'rma_train_reliability_score',
    'Computed reliability score for a train (0..1).',
    ['train_number']
)

# --- Train reliability computation metrics ---
RMA_TRAIN_RELIABILITY_COMPUTATION_SECONDS = Histogram(
    'rma_train_reliability_computation_seconds',
    'Duration of per-train reliability computation (seconds).',
    ['batch']
)
RMA_TRAIN_RELIABILITY_UPDATES_TOTAL = Counter(
    'rma_train_reliability_updates_total',
    'Number of train reliability updates performed by the hourly job.',
    ['batch']
)

# --- Route engine metrics (instrumented in backend) ---
# Placeholders here for local imports if needed elsewhere in the agent.


__all__ = [
    'RMA_EXTRACTION_DURATION_SECONDS',
    'RMA_EXTRACTION_ATTEMPTS_TOTAL',
    'RMA_EXTRACTION_FAILURES_TOTAL',
    'RMA_EXTRACTION_SUCCESS_TOTAL',
    'RMA_STATIONS_EXTRACTED_TOTAL',
    'RMA_VALIDATION_FAILURES_TOTAL',
    'RMA_JSON_SCHEMA_FAILURES_TOTAL',
    'RMA_CSV_PARITY_FAILURES_TOTAL',
    'RMA_DB_MISMATCH_TOTAL',
    'RMA_PROXY_REQUESTS_TOTAL',
    'RMA_PROXY_FAILURES_TOTAL',
    'RMA_PROXY_DISABLED_TOTAL',
    'RMA_PROXY_HEALTH_SCORE',
    'RMA_SELECTOR_FALLBACK_TOTAL',
    'RMA_SELECTOR_PRIMARY_FAILURES_TOTAL',
    'RMA_SELECTOR_SEMANTIC_SUCCESS_TOTAL',
    'RMA_EXTRACTION_CONFIDENCE',
    'RMA_TRAIN_RELIABILITY_SCORE',
    'RMA_TRAIN_RELIABILITY_COMPUTATION_SECONDS',
    'RMA_TRAIN_RELIABILITY_UPDATES_TOTAL',
]
