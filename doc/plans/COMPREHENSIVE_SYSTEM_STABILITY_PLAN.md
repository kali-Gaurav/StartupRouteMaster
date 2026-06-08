# 10-Phase Comprehensive System Stability & Optimization Plan

## Task 1: Middleware & ASGI Protocol Resilience
**Focus:** Fix `RuntimeError: No response returned` and `h11 LocalProtocolError` by stabilizing the request lifecycle.
1.1 Refactor `unified_jit_middleware` to native ASGI (remove `BaseHTTPMiddleware` wrapping).
1.2 Refactor `ObservabilityMiddleware` to native ASGI to prevent task group collapse.
1.3 Refactor `DatabaseLifecycleMiddleware` to native ASGI to guarantee session closure.
1.4 Implement strict `scope["type"] == "http"` checks across all middleware.
1.5 Implement request disconnection detection (`request.is_disconnected()`) in heavy search endpoints.
1.6 Standardize streaming response (`StreamingResponse`) exception capturing.
1.7 Isolate global exception handlers from middleware execution flow (prevent double-handling).
1.8 Add resilient CORS header injection on 500/503 error responses.
1.9 Add unique Request ID (`X-Request-ID`) propagation through the entire async stack.
1.10 Validate memory leaks in middleware using `tracemalloc` across 10k synthetic requests.
1.11 Implement a localized circuit breaker within middleware for known heavy routes.
1.12 Ensure GZip middleware gracefully handles aborted client connections without chunking errors.
1.13 Create a deterministic test suite verifying `h11` state transitions under load.
1.14 Optimize middleware order (Security -> Rate Limit -> JIT -> DB -> Route).
1.15 Add hard timeout wrapper (e.g., `asyncio.wait_for`) inside the routing layer.
1.16 Implement fallback JSON serializers for non-serializable exception types.
1.17 Add jitter to middleware timing to prevent thundering herds on cache misses.
1.18 Build a custom `SafeStreamingResponse` that cleanly aborts on disconnect.
1.19 Refactor JIT readiness check to use asyncio primitives without blocking the event loop.
1.20 Run final integration: Simulate 100 concurrent network drops during active database reads.

## Task 2: Route Engine Deduplication & Payload Safety
**Focus:** Fix search endpoint crashes, timeout issues, and datatype mismatches (e.g., `strftime` errors).
2.1 Audit all `datetime` vs `str` field assignments in `RouteSegment`.
2.2 Implement strict Pydantic validation at the Route Engine output boundary.
2.3 Optimize Global Deduplication algorithm from O(N^2) to O(N) using pre-computed hashes.
2.4 Fix `Ultra-Turbo` midnight duration rollover edge cases.
2.5 Isolate `SearchService` execution in a protected `try-except` block to prevent ASGI crashes.
2.6 Implement partial success returns (e.g., return DB results if RapidAPI fails).
2.7 Add `__slots__` to `RouteSegment` and `Route` dataclasses for memory reduction.
2.8 Refactor `journey_id` generation to be computationally cheaper.
2.9 Implement tiered search timeouts (Fast DB: 2s, Live API: 5s, Deep Search: 8s).
2.10 Fix cross-day routing bugs in `csa_kernel`.
2.11 Add payload size limits to prevent out-of-memory errors on massive JSON serializations.
2.12 Optimize `orjson` serialization configuration for API outputs.
2.13 Implement strict station code normalization (uppercase, strip whitespaces) at ingestion.
2.14 Build a standalone test suite for `csa_kernel` timetable loading.
2.15 Add heuristic pre-filtering to drop absurd routes (e.g., > 100 hours) before deduplication.
2.16 Implement parallel route fetching with fail-fast semantics using `asyncio.as_completed`.
2.17 Add diagnostic tracing inside `search_routes` to log exact failure line numbers.
2.18 Create a graceful fallback mechanism when Redis snapshot loading fails.
2.19 Refactor `RapidAPI` data normalization to perfectly match internal `RouteSegment` schemas.
2.20 Run extreme fuzz testing on search inputs (invalid dates, SQL injection strings, nulls).

## Task 3: Database Connection Pool Hardening
**Focus:** Resolve memory reaping crashes, pool exhaustion, and connection leaks.
3.1 Implement strict context managers (`async with`) for all DB queries globally.
3.2 Refactor `run_connection_reaper` to use gentle connection recycling instead of hard `dispose()`.
3.3 Implement `pool_pre_ping=True` and `pool_recycle=3600` on all SQLAlchemy engines.
3.4 Monitor and limit total connections mapped to available system RAM.
3.5 Isolate read-heavy analytical queries to a separate connection pool.
3.6 Fix dynamic pool sizing logic in `run_pool_scaler` to dynamically adjust `max_overflow`.
3.7 Add connection leak detection wrapper that logs unclosed sessions.
3.8 Optimize `init_raw_transit_pool` to handle dynamic scaling based on load.
3.9 Implement query timeout at the database driver level (e.g., SQLite/Postgres pragma).
3.10 Migrate heavy `IN (...)` queries in `Ultra-Turbo` to temporary tables or CTEs.
3.11 Add detailed Prometheus metrics for active, idle, and overflow connections.
3.12 Implement a robust retry mechanism for transient `OperationalError` (e.g., DB locked).
3.13 Fix `Isolated Auth Session` to ensure it never gets starved by transit queries.
3.14 Optimize JIT DB reflection to only load schemas when strictly necessary.
3.15 Implement a connection warmup strategy that correctly handles async loop boundaries.
3.16 Add automated indexing validation to ensure no missing indices degrade performance.
3.17 Refactor `get_source_connection` to prevent file-locking issues in SQLite.
3.18 Optimize `fetchmany()` chunk sizes in massive route queries.
3.19 Add explicit WAL mode pragma enforcement on SQLite startup.
3.20 Simulate 5,000 concurrent DB requests and analyze connection queueing behavior.

## Task 4: External API Fallback & Circuit Breaker Engine
**Focus:** Ensure RapidAPI/Rappid failures never cascade into system 500 errors.
4.1 Refactor `ExternalAPIHealth` to use local memory cache fallback if Redis is unreachable.
4.2 Implement exponential backoff for external API retries.
4.3 Add separate circuit breakers for `Availability`, `Fare`, and `Status` endpoints.
4.4 Build a mocking layer that activates instantly when the circuit breaker opens.
4.5 Optimize `aiohttp` client session management (avoiding session-per-request).
4.6 Add strict connection and read timeouts to all `aiohttp` requests.
4.7 Implement a fallback Fare Calculator locally for when RapidAPI Fare is down.
4.8 Implement a fallback Availability Predictor (ML) when RapidAPI Availability is down.
4.9 Fix logging noise during Circuit Breaker HALF_OPEN state.
4.10 Ensure external API responses are strictly validated with Pydantic before use.
4.11 Add payload caching for identical external API requests within a 5-minute window.
4.12 Implement a "dry-run" mode for circuit breakers to test thresholds safely.
4.13 Handle HTTP 429 (Too Many Requests) explicitly by immediately tripping the breaker.
4.14 Create a dead-letter queue for failed booking/PNR sync requests to retry later.
4.15 Implement API key rotation logic when encountering 401/403 errors.
4.16 Add detailed latency histograms for external providers to Grafana.
4.17 Fix `asyncio.gather` behavior to prevent one failed external API from canceling others.
4.18 Implement a local station-to-station fare mapping cache.
4.19 Add automated alerts via Telegram/Email when critical APIs go offline.
4.20 Simulate upstream API outages (500s, 502s, timeouts) and verify graceful UI degradation.

## Task 5: Data Serialization & Type Enforcement
**Focus:** Prevent runtime type errors, `AttributeErrors`, and ensure API contract adherence.
5.1 Enforce strict `mypy` typing across `core/data_structures.py`.
5.2 Replace basic Python `dataclasses` with Pydantic `BaseModel` for validation at boundaries.
5.3 Build global custom JSON encoders/decoders for `datetime`, `Enum`, and `Set`.
5.4 Fix all instances of implicit string-to-datetime conversions.
5.5 Standardize API error payload structures (`{error: bool, message: str, detail: any}`).
5.6 Audit and fix missing attributes in mock data used for tests.
5.7 Implement a strict schema for Redis cache payloads to prevent decode errors.
5.8 Create automated schema migration tests for local databases.
5.9 Enforce timezone-aware datetimes (`UTC`) universally across the backend.
5.10 Refactor `Passenger` and `UserContext` models to handle missing legacy fields.
5.11 Implement input sanitization middleware to strip malicious payloads.
5.12 Fix numeric type precision issues (e.g., float vs decimal for fares).
5.13 Add schema validation to the Telegram bot webhook payloads.
5.14 Standardize pagination metadata structures across all list endpoints.
5.15 Implement deep-copy mechanisms for cached objects to prevent reference mutation.
5.16 Fix edge cases in `to_dict()` methods where nested objects are not serialized.
5.17 Create a unified `ResponseSchema` wrapper for all FastAPI routes.
5.18 Implement strict Enum parsing with safe fallbacks for legacy string values.
5.19 Add comprehensive OpenAPI (Swagger) documentation types.
5.20 Run property-based testing (Hypothesis) on all data parsers.

## Task 6: Async Event Loop & Concurrency Optimization
**Focus:** Prevent event loop blocking, CPU starvation, and timeout exceptions.
6.1 Audit all routes for blocking synchronous calls (e.g., `time.sleep`, heavy CPU loops).
6.2 Move heavy computational logic (e.g., `CSA` graph traversal) to `ProcessPoolExecutor`.
6.3 Optimize `asyncio.gather` usage to include `return_exceptions=True` globally.
6.4 Fix improper mixing of synchronous SQLAlchemy and Asyncio.
6.5 Implement `anyio` for safer concurrency management where applicable.
6.6 Profile event loop latency and log warnings if loop is blocked > 100ms.
6.7 Optimize WebSocket broadcasters to prevent blocking on slow clients.
6.8 Implement worker process limits tailored to available CPU cores (via Uvicorn/Gunicorn).
6.9 Fix cancellation handling in long-running background tasks.
6.10 Isolate the `feedback_loop` and `behavior_tracker` into dedicated thread pools.
6.11 Optimize ML model inference to release the GIL.
6.12 Add `asyncio.Shield` to critical database commits to prevent corruption on disconnect.
6.13 Optimize Redis async pipelines for bulk insertions.
6.14 Fix race conditions in `JITManager` dependency resolution.
6.15 Implement staggered startups for background tasks to prevent CPU spikes on boot.
6.16 Add limits to `asyncio.Queue` sizes to apply backpressure.
6.17 Fix zombie tasks created by disconnected clients during search.
6.18 Optimize JSON parsing using `orjson` explicitly in the event loop.
6.19 Conduct a full dependency audit to ensure all network libs are async-native.
6.20 Simulate 100% CPU load and verify API responsiveness via prioritization.

## Task 7: Multi-Layer Cache Consistency
**Focus:** Ensure accurate, fast data retrieval without stale or corrupted states.
7.1 Fix L1 (Memory) and L2 (Redis) synchronization race conditions.
7.2 Implement cache invalidation webhooks for admin updates.
7.3 Add explicit versioning to cache keys to survive schema changes.
7.4 Optimize `prewarm_top_routes` to avoid thrashing the DB on startup.
7.5 Implement cache stampede protection (mutex locks) for highly concurrent misses.
7.6 Add TTL jitter to prevent massive simultaneous cache expirations.
7.7 Implement negative caching (cache 404s/Zero-results) with short TTLs.
7.8 Fix serialization errors when reading compressed Redis payloads.
7.9 Optimize memory footprint of the local LRU cache (L1).
7.10 Add graceful fallback to L1 if Redis connection drops.
7.11 Implement an asynchronous background cache refresh mechanism.
7.12 Monitor Redis memory usage and implement aggressive eviction policies.
7.13 Add unique session-level caching for personalized search results.
7.14 Validate cache integrity via periodic background hash checks.
7.15 Fix offline mode detection to cleanly bypass cache when necessary.
7.16 Implement tiered caching for dynamic pricing (1 min TTL) vs static timetables (24 hr TTL).
7.17 Add a cache bypass header (e.g., `X-Bypass-Cache`) for admin debugging.
7.18 Optimize `EmergencyCache` local file writes to be atomic.
7.19 Standardize cache key generation logic centrally.
7.20 Simulate Redis failure and verify system continues operating on L1 + DB.

## Task 8: WebSocket & Real-Time Sync Stability
**Focus:** Fix connection drops, heartbeat failures, and real-time state mismatches.
8.1 Implement robust Ping/Pong heartbeats at the application level.
8.2 Fix `booking_ws` state corruption when a user connects from multiple tabs.
8.3 Optimize broadcasting to group connections into batches.
8.4 Implement automatic reconnection logic on the frontend with exponential backoff.
8.5 Secure WebSockets against unauthorized access via token handshakes.
8.6 Handle abrupt socket closures (`WebSocketDisconnect`) gracefully without logging errors.
8.7 Add rate limiting strictly for incoming WebSocket messages.
8.8 Implement payload compression for heavy real-time tracking updates.
8.9 Fix memory leaks in the Connection Manager's active connections dictionary.
8.10 Add a dead-client pruner that runs every 60 seconds.
8.11 Sync WebSocket state with Redis Pub/Sub for multi-worker scaling.
8.12 Standardize WebSocket event schemas (type, payload, timestamp).
8.13 Implement client-side acknowledgment for critical messages.
8.14 Add fallback to Server-Sent Events (SSE) or long-polling.
8.15 Optimize real-time train tracking ingestion pipeline to reduce latency.
8.16 Add circuit breaking to the ingestion pipeline if upstream GPS feeds fail.
8.17 Ensure SOS alerts bypass standard WebSocket queues for priority delivery.
8.18 Fix race conditions where initial state is sent before socket is fully open.
8.19 Monitor active WebSocket count and alert on anomalies.
8.20 Run a load test with 5,000 concurrent WebSockets broadcasting 1 msg/sec.

## Task 9: Background Worker & ML Model Isolation
**Focus:** Prevent ML inference and background tasks from crashing the main API.
9.1 Move ML Models to a completely isolated process (or microservice).
9.2 Implement a robust task queue (e.g., Celery/ARQ) instead of `asyncio.create_task`.
9.3 Optimize ML model memory loading (lazy loading vs pre-loading).
9.4 Add timeout and fallback to heuristics if ML inference takes > 500ms.
9.5 Fix memory leaks in `eviction_worker` for ML models.
9.6 Optimize `PredictionHub` to batch prediction requests.
9.7 Implement persistent storage for task queue to survive backend restarts.
9.8 Add detailed logging for background task lifecycle (Start, Success, Fail, Retry).
9.9 Implement graceful shutdown for workers (finish current task before exiting).
9.10 Add CPU/GPU pinning for ML processes to avoid starving Uvicorn.
9.11 Refactor `PredictionHub` to use Unix Domain Sockets or Redis for IPC.
9.12 Validate model inputs strictly before passing to the ML engine.
9.13 Add a fallback mechanism if model files are missing or corrupted.
9.14 Implement continuous model monitoring (detecting data drift).
9.15 Optimize the `feedback_loop` DB queries to run in bulk.
9.16 Fix behavior tracker race conditions when updating user profiles.
9.17 Add a dead-letter queue for failed ML predictions.
9.18 Monitor and alert on task queue depth.
9.19 Ensure background tasks release database connections immediately after use.
9.20 Simulate model crash and verify main search API falls back instantly.

## Task 10: Frontend Graceful Degradation & State Sync
**Focus:** Ensure the UI remains responsive and clear even when backend endpoints fail.
10.1 Implement global React Query error handling to catch 500s gracefully.
10.2 Add "Offline Mode" indicators that activate instantly on API timeout.
10.3 Fix `PredictivePreloadService` failing silently and clogging the network tab.
10.4 Optimize frontend polling for bookings to stop when tab is inactive.
10.5 Implement a centralized "System Health" banner based on `/api/health` polling.
10.6 Add retry buttons directly on failed UI components (e.g., Search Card).
10.7 Standardize toast notifications for system errors (prevent spamming).
10.8 Implement local storage fallback for user preferences and recent searches.
10.9 Optimize heavy animations that stutter during API fetch execution.
10.10 Ensure the Telegram bot link flow handles backend unreachability cleanly.
10.11 Implement a queue for offline actions (e.g., SOS triggered while offline).
10.12 Fix Theme toggling to visually persist instantly before writing to local storage.
10.13 Add detailed "Why did this fail?" tooltips for developers/admins in UI.
10.14 Standardize loading skeletons to match final content layouts perfectly.
10.15 Implement client-side input validation to prevent invalid backend requests.
10.16 Add a network speed detector to downgrade image/payload sizes on 3G.
10.17 Fix session expiration edge cases causing infinite redirect loops.
10.18 Optimize Service Worker caching for static assets.
10.19 Add telemetry to capture UI crashes and send them to backend logs.
10.20 Simulate a 10-minute complete backend outage and verify user journey continuity.
