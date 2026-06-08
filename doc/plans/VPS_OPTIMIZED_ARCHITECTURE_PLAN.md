# RouteMaster V2: Advanced VPS-Optimized Architecture Plan (20x20)

This plan is specifically engineered for a VPS hosting environment (like Hostinger), focusing on dynamic scaling, cost-efficiency, and absolute resilience. It ensures we never over-consume idle resources and gracefully handle extreme traffic spikes without crashing.

## Task 1: Dynamic Event Loop & ASGI Resource Management
**Focus: Real-time CPU and Asyncio monitoring to drive auto-scaling.**
1.1 Implement Event Loop Latency Monitor (measures `asyncio.sleep(0)` delay).
1.2 Expose real-time CPU/RAM metrics to ASGI state for middleware access.
1.3 Implement adaptive request timeout logic (shorter timeouts during high load).
1.4 Create a "System Overload" global state flag triggered by hardware metrics.
1.5 Implement dynamic worker process sizing (via Gunicorn/Uvicorn programmatic hooks).
1.6 Build a priority queue system for ASGI requests (SOS > Search > Background).
1.7 Implement connection shedding (drop lowest-priority connections when RAM > 95%).
1.8 Optimize `uvloop` configuration for maximum VPS networking performance.
1.9 Isolate heavy CPU tasks to dedicated `ProcessPoolExecutor` with max worker limits.
1.10 Add jitter to startup tasks to prevent CPU thrashing on container restart.
1.11 Implement graceful degradation: disable non-critical routes during high load.
1.12 Create a "Maintenance Mode" toggle that allows active sessions to finish.
1.13 Optimize chunk sizes in `StreamingResponse` based on current network I/O wait.
1.14 Implement connection limiters at the ASGI level (max 10,000 concurrent).
1.15 Add watchdog thread to detect deadlocked Uvicorn workers and auto-restart them.
1.16 Implement Keep-Alive timeout tuning based on current connection count.
1.17 Build an emergency "Drop All" route for admin intervention during DDoS.
1.18 Optimize Starlette task groups to prevent memory bloat during massive concurrency.
1.19 Implement adaptive body size limits (reject large payloads instantly during high load).
1.20 Run extreme fuzzing: 50k concurrent connections with random drops to verify stability.

## Task 2: Memory-Aware Database Pooling & GC Tuning
**Focus: Preventing OOM (Out Of Memory) errors by actively managing DB connections and Python Garbage Collection.**
2.1 Implement dynamic SQLAlchemy pool sizing (scales up on load, scales down on idle).
2.2 Create a memory-pressure hook that aggressively triggers `gc.collect()`.
2.3 Configure SQLite/Postgres to use dynamic memory mapped limits (mmap size).
2.4 Implement a "Ghost Connection" killer for idle DB sessions > 60 seconds.
2.5 Optimize SQLAlchemy `yield_per` for massive DB queries to stream results.
2.6 Switch to explicit `gc.disable()` during heavy routing, followed by manual collection.
2.7 Implement a Read-Replica connection pool logic (if utilizing multiple SQLite files).
2.8 Add DB lock timeout strategies with exponential backoff retries.
2.9 Implement statement caching in SQLAlchemy to reduce compilation overhead.
2.10 Use Python's `__slots__` strictly across all ORM and Data models.
2.11 Monitor DB connection queue latency; trigger load shedding if wait > 2s.
2.12 Optimize `aiosqlite` thread pool sizes for VPS vCPU counts.
2.13 Implement transparent query batching (combine multiple small reads).
2.14 Add pre-ping checks only during low traffic; disable during surges to save latency.
2.15 Build an emergency DB reset endpoint that cleanly disposes and rebuilds pools.
2.16 Optimize database file fragmentation via scheduled vacuuming tasks.
2.17 Implement bounded LRU caches for frequently accessed static tables (Stations).
2.18 Handle `OperationalError: database is locked` with non-blocking async retries.
2.19 Implement strict transaction boundaries to ensure locks are held < 50ms.
2.20 Simulate 99% RAM usage and verify pool shrinks gracefully without dropping active queries.

## Task 3: Adaptive Multi-Layer Caching Engine
**Focus: Shifting load between RAM (L1) and Redis (L2) dynamically to save compute and bandwidth.**
3.1 Implement L1 (RAM) size limits based on `psutil.virtual_memory().available`.
3.2 Dynamically bypass Redis (L2) if Redis latency exceeds 50ms (fail to L1/DB).
3.3 Implement probabilistic cache expiration (XFetch) to prevent stampedes.
3.4 Add payload compression (Zstandard/LZ4) to Redis values to save memory.
3.5 Build an intelligent pre-warmer that only runs during off-peak hours (2 AM).
3.6 Implement "Stale-While-Revalidate": serve old cache while fetching new in background.
3.7 Add cache tiering: User-specific (Redis) vs Global Data (L1 RAM).
3.8 Implement dynamic TTLs: high traffic routes get longer TTLs automatically.
3.9 Use Redis Pipeline/MGET for all bulk cache retrievals.
3.10 Build an LRU eviction listener to log what is being pushed out of RAM.
3.11 Implement negative caching with short TTLs for 404s/Invalid searches.
3.12 Handle Redis connection drops with immediate, silent fallback to DB.
3.13 Implement local emergency JSON file cache for catastrophic Redis+DB failures.
3.14 Group cache keys by "Hub" for efficient batch invalidation.
3.15 Monitor Redis memory usage; trigger aggressive eviction via API if > 80%.
3.16 Optimize cache key generation string allocations (use hashing).
3.17 Implement "Cost-Aware Caching" - prioritize caching expensive RapidAPI results.
3.18 Serve raw bytes from Redis directly to ASGI response to bypass JSON serialization.
3.19 Add cache hit/miss ratio monitoring per endpoint.
3.20 Simulate Redis crash, high RAM, and verify system gracefully degrades to DB.

## Task 4: Intelligent Load Shedding & Traffic Shaping
**Focus: Protecting the VPS by intelligently rejecting or delaying traffic during surges.**
4.1 Implement a Token Bucket rate limiter that shares state via Redis.
4.2 Add "Surge Levels" (Normal, Elevated, High, Critical) that adjust automatically.
4.3 Level 1 (Elevated): Disable complex graph routing; only return cached/direct routes.
4.4 Level 2 (High): Disable ML predictions and background tasks.
4.5 Level 3 (Critical): Return 503 for all unauthenticated searches; prioritize SOS/Bookings.
4.6 Implement client-side retry delay headers (`Retry-After: X`) dynamically.
4.7 Add IP-based penalty boxes for rapid, repeated failures or 404s.
4.8 Implement Queue-based traffic shaping (hold requests for up to 5s if workers full).
4.9 Provide "Fast-Lane" access for VIP/Premium users via JWT claims.
4.10 Build a lightweight Web Application Firewall (WAF) middleware for bad actors.
4.11 Monitor network bandwidth (RX/TX) and throttle streaming endpoints if saturated.
4.12 Implement API quota limits mapped to Hostinger VPS monthly transfer limits.
4.13 Serve an ultra-lightweight static HTML "System Busy" page for extreme cases.
4.14 Implement heuristic bot detection based on user-agent and request patterns.
4.15 Add geo-fencing (rate limit regions known for scraping).
4.16 Create dynamic CAPTCHA triggers for suspicious search volumes.
4.17 Implement graceful WebSocket shedding (disconnect oldest idle clients).
4.18 Use `HTTP 429` effectively with localized Redis counters to prevent DB hits.
4.19 Build an Admin Dashboard toggle to manually override surge levels.
4.20 Load test with 10k requests/sec and ensure valid users get through while others get 503s/429s.

## Task 5: Route Engine JIT & Memory Mapping
**Focus: Optimizing the heavy graph algorithms to use minimal VPS RAM and CPU.**
5.1 Migrate massive routing arrays (CSA/RAPTOR) to `numpy.memmap` (Disk-backed RAM).
5.2 Implement lazy loading of the graph: only load segments requested by the user.
5.3 Build a memory-mapped LRU cache for route intersections.
5.4 Optimize `UnifiedRoutingOrchestrator` to stop searching instantly once 5 good routes are found.
5.5 Implement C-extensions or Cython for the core RAPTOR traversal loop.
5.6 Release memory-mapped files immediately when system load > 85%.
5.7 Pre-calculate and store static inter-hub distances during the build step.
5.8 Implement heuristic bounds (A* search) to prune the search tree early.
5.9 Batch parallel route queries together if they share the same source hub.
5.10 Build a "Nightly Route Compiler" that pre-bakes the top 50,000 routes to disk.
5.11 Optimize Python `datetime` math in the inner loop using integer timestamps.
5.12 Implement a shared memory segment across Uvicorn workers for the graph.
5.13 Add CPU-instruction level profiling to find the hottest loop in RAPTOR.
5.14 Prevent "Thundering Herd" on JIT graph load via file-based mutex locks.
5.15 Implement a disk-based fallback routing engine if RAM is exhausted.
5.16 Compress the graph dataset on disk using Snappy for fast reads.
5.17 Add yield-yielding in the async loop during heavy graph traversal to prevent blocking.
5.18 Restrict multi-day expansion based on available CPU (skip if load > 70%).
5.19 Build a dedicated `/api/routes/health` to check if the graph is fully mapped.
5.20 Verify routing engine scales down memory footprint to < 50MB when idle.

## Task 6: ML Model Lazy Loading & Inference Batching
**Focus: Managing the high memory cost of ML models dynamically.**
6.1 Implement ONNX Runtime for faster, lower-memory inference.
6.2 Load models into RAM *only* when a prediction is requested.
6.3 Unload models from RAM if unused for > 5 minutes.
6.4 Batch multiple prediction requests from different users into a single inference call.
6.5 Use quantized models (INT8/FP16) to reduce size and improve speed on CPU.
6.6 Implement a caching layer specifically for prediction results (TTL: 6 hours).
6.7 Add a timeout to ML inference; fallback to statistical averages if it takes > 200ms.
6.8 Disable ML processing entirely during Level 2 Surge.
6.9 Expose model memory usage to the global telemetry dashboard.
6.10 Implement background threaded loading to prevent blocking the ASGI loop.
6.11 Add input validation to prevent tensor shape mismatch crashes.
6.12 Handle out-of-bounds categorical variables gracefully.
6.13 Build a model fallback chain (Complex Model -> Simple Heuristic -> Default Value).
6.14 Isolate the ML Python environment (if possible) or strictly manage dependencies.
6.15 Periodically test inference accuracy in the background.
6.16 Pre-warm the most common predictions during off-peak hours.
6.17 Use `ProcessPoolExecutor` specifically for heavy numpy/pandas preprocessing.
6.18 Track prediction drift and log anomalies for retraining.
6.19 Create an API endpoint to manually trigger model eviction/reload.
6.20 Simulate high request volume and ensure ML inference never starves API routing.

## Task 7: External API Cost-Optimization & Batching
**Focus: Minimizing API costs (RapidAPI/Rappid) while maximizing data freshness.**
7.1 Implement aggressive local caching of external API results (Redis + DB).
7.2 Batch availability requests (e.g., fetch multiple trains in one call if API supports it).
7.3 Predict when a seat status will change and only poll API when a change is probable.
7.4 Implement strict Daily/Monthly API Quota counters in Redis.
7.5 Stop polling external APIs if quota reaches 95%; fallback to historical data entirely.
7.6 Use Webhooks (if supported by upstream) instead of polling.
7.7 Implement "Optimistic Updates": show cached data instantly, fetch in background.
7.8 Identify "Dead Zones" (times when IRCTC/Upstream is down) and halt all API calls.
7.9 Route non-critical searches (e.g., browsing) to local DB only; use API only on intent to book.
7.10 Track and log the exact cost ($) of each API endpoint in telemetry.
7.11 Implement an API Key rotation manager to spread load across free tiers safely.
7.12 Handle upstream 500s with immediate Circuit Breaker tripping.
7.13 Add exponential backoff for 429 Too Many Requests from upstream.
7.14 Group duplicate API requests from different users into a single outbound request.
7.15 Store failed request payloads in a dead-letter queue for offline analysis.
7.16 Implement custom header parsing to track upstream rate limit headers (`X-RateLimit-Remaining`).
7.17 Scrape public non-API sources for status updates as a free fallback (if legally/technically viable).
7.18 Monitor upstream latency; if it doubles, switch to stale-cache mode.
7.19 Alert admins via Telegram when API quotas hit 80%.
7.20 Simulate RapidAPI hard outage and verify 0% failure rate on user searches.

## Task 8: Resilient WebSocket & Real-Time Sync
**Focus: Handling thousands of concurrent connections efficiently on a single VPS.**
8.1 Upgrade WebSocket backend to use `uvwebsockets` for native C performance.
8.2 Implement aggressive Ping/Pong keep-alives (drop unresponsive clients in 15s).
8.3 Use Redis Pub/Sub to multiplex real-time data to specific channels (e.g., `train:12002`).
8.4 Broadcast updates in batches (every 1 second) rather than per-event.
8.5 Compress all WebSocket payloads (JSON -> MsgPack or gzip).
8.6 Prevent concurrent tab connections for the same user (limit 1 WS per IP/Session).
8.7 Monitor active WS count; gracefully close older connections if hitting OS FD limits.
8.8 Implement a robust reconnect mechanism on the frontend with jittered backoff.
8.9 Handle `WebSocketDisconnect` cleanly without polluting logs.
8.10 Offload WS broadcasting to a dedicated background task, freeing up request workers.
8.11 Ensure SOS WebSockets bypass all limiters and get absolute priority.
8.12 Add token-based authentication to the WS handshake to prevent unauthorized holding.
8.13 Implement binary frame transmission instead of text for large tracking datasets.
8.14 Throttle incoming messages from clients (max 2 msgs/sec).
8.15 Add server-side buffer limits; if client can't receive fast enough, drop them.
8.16 Sync client-side clock with server time via WS payload.
8.17 Create an admin WS channel for real-time system monitoring.
8.18 Use localized memory Pub/Sub if Redis is unavailable.
8.19 Periodically log the total number of connected clients and bandwidth used.
8.20 Simulate 10,000 WebSocket connections on a 1GB VPS and ensure memory stays stable.

## Task 9: Async File I/O & Static Asset Optimization
**Focus: Preventing disk I/O bottlenecks and optimizing delivery of assets.**
9.1 Replace all `open()` calls with `aiofiles` to prevent blocking the event loop.
9.2 Ensure `/media` and static files are served via Nginx/Caddy in production, not Uvicorn.
9.3 If using Uvicorn for statics, implement robust `Cache-Control` and `ETag` headers.
9.4 Pre-gzip and pre-brotli all static assets (HTML/JS/CSS) during the build step.
9.5 Implement a memory cache for frequently accessed small files (e.g., config JSONs).
9.6 Optimize Loki/Promtail log writes to be asynchronous and buffered.
9.7 Write temporary files to RAM disk (`/dev/shm`) instead of physical SSD for speed.
9.8 Use `sendfile()` syscall via Starlette where possible for zero-copy transfers.
9.9 Implement strict size limits on user uploads (if any) and stream directly to disk.
9.10 Add asynchronous SQLite backup mechanism that doesn't lock the main DB.
9.11 Profile disk I/O using `iostat`; alert if wait times exceed 100ms.
9.12 Move snapshot saving/loading to a separate process to avoid blocking ASGI.
9.13 Use lightweight file formats (Parquet/Arrow) for internal analytical data dumps.
9.14 Implement automatic cleanup of temporary files (Cron/Background task).
9.15 Serve a placeholder image instantly if the primary asset is loading slowly.
9.16 Ensure `emergency_cache.json` reads are strictly non-blocking.
9.17 Add file integrity checks (MD5/SHA256) upon loading critical snapshots.
9.18 Implement lazy-loading of large dictionaries/mappings in code.
9.19 Monitor inode usage on the VPS to prevent "No space left on device" errors.
9.20 Simulate a 100% disk usage scenario and ensure the API returns 500 gracefully without corrupting files.

## Task 10: Dynamic Payload Compression & Serialization
**Focus: Optimizing network bandwidth and CPU cost of parsing data.**
10.1 Globally replace `json` with `orjson` for 10x faster serialization.
10.2 Dynamically enable/disable GZip based on payload size AND current CPU load (skip if CPU > 90%).
10.3 Implement Brotli compression for supported clients (higher compression ratio).
10.4 Strip nulls, empty lists, and default values from API responses to reduce size.
10.5 Use MessagePack for internal microservice/Redis communication.
10.6 Pre-serialize static API responses (e.g., station lists) and cache the byte string.
10.7 Implement streaming JSON responses for massive datasets using `orjson.Fragment`.
10.8 Enforce strict Pydantic `exclude_unset=True` globally.
10.9 Map long dictionary keys to short aliases for massive arrays.
10.10 Ensure proper `Content-Length` headers are set whenever possible to help client parsing.
10.11 Optimize frontend API clients to accept and parse compressed data natively.
10.12 Strip all human-readable debug strings from production payloads.
10.13 Implement chunked transfer encoding explicitly for route streams.
10.14 Profile serialization overhead; flag any endpoint taking > 10ms to serialize.
10.15 Use simple Python dictionaries instead of deep class hierarchies right before serialization.
10.16 Add an `Accept-Encoding` parser to optimally choose compression per client.
10.17 Validate that compressed responses are fully compatible with reverse proxies.
10.18 Ensure error responses are never compressed to guarantee delivery.
10.19 Cache the compressed version of the payload directly in Redis.
10.20 Measure bandwidth savings across 10,000 requests to verify compression ROI.

## Task 11: Background Task Scaling & Prioritization
**Focus: Ensuring maintenance tasks never compete with active user searches.**
11.1 Integrate a lightweight task queue (ARQ or RQ) specifically for Redis.
11.2 Implement dynamic background worker pools (pause workers when HTTP load is high).
11.3 Assign priorities: SOS (0) > Payments (1) > Sync (2) > Cleanup (3).
11.4 Ensure background tasks release database sessions immediately.
11.5 Implement a global "Task Registry" to prevent duplicate background jobs running.
11.6 Add execution timeouts to all background tasks (kill if stuck > 5 mins).
11.7 Schedule heavy DB analytics (Pool Scaler, Feedback Loop) strictly to off-peak cron.
11.8 Implement task batching: wait for 10 items or 5 seconds before processing DB writes.
11.9 Log background task metrics (Success/Fail/Duration) to Prometheus.
11.10 Add dead-letter queues for failed Webhooks and Payment Verifications.
11.11 Isolate memory-heavy background tasks to a separate container/process.
11.12 Build a `/api/admin/tasks` dashboard to monitor and kill runaway tasks.
11.13 Implement graceful worker shutdown (finish current job before exiting).
11.14 Add random delays to recurring tasks to avoid thundering herds.
11.15 Ensure asyncio `create_task` is tracked in a strong reference set to prevent premature GC.
11.16 Implement exponential backoff for failed webhook deliveries.
11.17 Monitor task queue size; trigger alerts if backlog grows > 1000 items.
11.18 Offload email/SMS/Telegram notifications to the lowest priority queue.
11.19 Implement idempotency in all background tasks (safe to run twice).
11.20 Spike the task queue with 50,000 jobs and verify HTTP API latency remains under 200ms.

## Task 12: Zero-Downtime Reloads & Config State
**Focus: Seamless deployments and dynamic configuration updates without dropping users.**
12.1 Configure Uvicorn/Gunicorn for pre-forking and seamless worker restarts (`--reload-delay`).
12.2 Implement a dynamic configuration manager that reads from DB/Redis without restarting.
12.3 Use ASGI Lifespan to gracefully drain active requests before shutting down.
12.4 Ensure long-running WebSocket connections receive a "Server Restarting" signal to reconnect cleanly.
12.5 Implement a robust Health Check endpoint for load balancers to trust.
12.6 Add `/api/admin/reload-config` endpoint to flush config caches instantly.
12.7 Version API endpoints clearly to allow multiple versions running simultaneously.
12.8 Store critical state (circuit breakers, surge levels) in Redis, not RAM, so it survives restarts.
12.9 Optimize startup time (JIT) to be under 2 seconds to minimize worker spin-up delay.
12.10 Use environment variables strictly for secrets, DB for feature flags.
12.11 Implement a "warmup" ping script that hits the new worker before adding it to rotation.
12.12 Capture and log `SIGTERM`/`SIGINT` signals natively.
12.13 Ensure database connection pools are closed gracefully on shutdown to prevent connection leaks on DB side.
12.14 Automate DB migrations (Alembic) in CI/CD before the new app code starts.
12.15 Ensure schema changes are backward-compatible (no dropping columns) for N-1 version support.
12.16 Add a commit hash endpoint `/api/version` to verify deployment success.
12.17 Prevent JIT heavy loading during standard worker reloads (use shared memory).
12.18 Implement readiness probes distinct from liveness probes.
12.19 Use `SIGHUP` for graceful Uvicorn termination.
12.20 Simulate 5 rolling deployments during active 100 req/sec load and verify 0 dropped requests.

## Task 13: Distributed Circuit Breakers & Fallback Heuristics
**Focus: Globalizing resilience across multi-worker deployments.**
13.1 Upgrade `RoutingCircuitBreaker` to sync state via Redis across all Uvicorn workers.
13.2 Add a half-open state that allows exactly 1 request through to test recovery.
13.3 Implement localized fallbacks (e.g., if RapidAPI down, return heuristic estimate).
13.4 Build specific circuit breakers for Database, Cache, External APIs, and Payment Gateway.
13.5 Track circuit breaker trips in Grafana with immediate Telegram alerts.
13.6 Implement fallback pricing logic based on historical averages if live fare fails.
13.7 Return a `Cache-Control: no-store` header when serving fallback data.
13.8 Add a "Degraded State" banner trigger to the frontend via API meta-data.
13.9 Ensure circuit breakers fail *closed* (secure) for payments, but *open* (available) for searches.
13.10 Log the exact exception that tripped the breaker in the state object.
13.11 Add an admin endpoint to manually force a circuit breaker open/closed.
13.12 Implement a "Trip Cascade" prevention: if DB is down, don't overwhelm cache.
13.13 Ensure Circuit Breaker logic uses minimal CPU (lock-free structures).
13.14 Write unit tests specifically for state transitions (Closed -> Open -> Half -> Closed).
13.15 Use sliding window counters (e.g., failures per 10 seconds) instead of absolute counts.
13.16 Implement strict timeouts specifically for the circuit breaker status check.
13.17 Provide detailed user-facing error messages explaining the degraded service.
13.18 Ensure Payment webhooks bypass certain breakers to avoid losing transaction states.
13.19 Optimize the Redis check to use `pipeline` to save network trips.
13.20 Simulate a flapping external API (up/down every 2s) and ensure breaker stabilizes the system.

## Task 14: SQLite/Postgres VPS IOPS Optimization
**Focus: Maximize database read/write throughput on limited VPS NVMe/SSD.**
14.1 Force SQLite `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;`.
14.2 Optimize Postgres `shared_buffers` and `work_mem` for VPS RAM limits.
14.3 Implement connection-level read-only vs read-write routing.
14.4 Use `INSERT ... ON CONFLICT` (Upsert) to reduce read-modify-write cycles.
14.5 Batch all telemetry and logging writes into 100-record chunks.
14.6 Ensure all Foreign Keys have covering indexes for fast joins.
14.7 Remove all `SELECT *` in the codebase; explicitly query only needed columns.
14.8 Implement partial indices for boolean flags (e.g., `WHERE is_active = 1`).
14.9 Optimize the RapidAPI DB caching to use `JSON` columns efficiently.
14.10 Run `PRAGMA optimize;` or Postgres `VACUUM ANALYZE` weekly.
14.11 Store large JSON blobs in Redis instead of relational DB to save IOPS.
14.12 Use integer IDs for all primary/foreign keys instead of UUIDs where possible.
14.13 Configure Alembic to support async migrations safely.
14.14 Monitor slow queries (> 50ms) and log the EXPLAIN query plan.
14.15 Use SQLAlchemy `undefer` and `load_only` to control eager loading precisely.
14.16 Implement soft-deletes (`is_deleted=True`) to avoid fragmentation.
14.17 Set strict connection timeouts at the driver level to prevent hang-ups.
14.18 Optimize `get_stations_near_me` using proper spatial indexes (PostGIS or SpatiaLite).
14.19 Disable SQLAlchemy auto-flush during massive batch imports.
14.20 Load test 10,000 concurrent complex reads and ensure IO wait remains < 10%.

## Task 15: Pagination & Cursor Optimization for Massive Datasets
**Focus: Fast and memory-efficient navigation of thousands of routes/stations.**
15.1 Replace all `OFFSET/LIMIT` queries with Keyset (Cursor) pagination.
15.2 Implement an encrypted cursor string (Base64 encoded `timestamp|id`).
15.3 Add `has_next_page` boolean dynamically without needing a `COUNT(*)` query.
15.4 Limit maximum page size strictly to 50 items.
15.5 Cache the total count of popular queries separately to avoid DB hits.
15.6 Implement cursor pagination specifically for the `SearchService` route list.
15.7 Standardize the frontend to handle cursor structures seamlessly.
15.8 Add bi-directional cursors (`before` and `after`) for chat/SOS logs.
15.9 Ensure indexes perfectly match the sort order of the cursor.
15.10 Validate cursor payloads strictly to prevent SQL injection or decoding errors.
15.11 Implement infinite scrolling on the frontend supported by the backend load-more.
15.12 Handle stale cursors gracefully (if an item was deleted).
15.13 Add a maximum depth limit to pagination to prevent scraper abuse.
15.14 Optimize station autocomplete to use `LIKE 'Prefix%'` with index support.
15.15 Implement client-side sorting/filtering of paginated data where logical.
15.16 Log pagination depth requests; analyze if users ever go past page 3.
15.17 Pre-fetch page 2 in the background for ultra-fast perceived performance.
15.18 Ensure memory footprint is constant O(1) regardless of pagination depth.
15.19 Document the cursor specification clearly in Swagger/OpenAPI.
15.20 Simulate requesting page 1,000 via cursor vs offset and compare latency.

## Task 16: ETag & Client-Side Caching Integration
**Focus: Offloading read traffic entirely to the user's browser.**
16.1 Implement automatic `ETag` generation based on payload hashing.
16.2 Add middleware to intercept `If-None-Match` headers and return `304 Not Modified`.
16.3 Apply strict `Cache-Control: max-age=3600, public` to static station data.
16.4 Ensure dynamic user data (Profile, Bookings) uses `Cache-Control: no-cache`.
16.5 Generate ETags specific to User ID to prevent cross-user leakage.
16.6 Update the React frontend `TanStack Query` to respect 304 responses natively.
16.7 Use Weak ETags (`W/"hash"`) where byte-for-byte matching isn't critical.
16.8 Add `Last-Modified` headers to all immutable datasets (GTFS timetables).
16.9 Ensure reverse proxies (Nginx/Traefik) are configured to pass cache headers.
16.10 Implement `Vary: Accept-Encoding` to prevent caching gzipped data for non-gzip clients.
16.11 Force cache invalidation on the client via versioned URL parameters (`/api/v2/...`).
16.12 Handle browser aggressive caching edge cases (Safari/Chrome differences).
16.13 Monitor 304 response rates in Observability logs to measure efficiency.
16.14 Apply client-side caching to ML prediction models if requested multiple times.
16.15 Implement a Service Worker strategy on the frontend for offline assets.
16.16 Use `stale-while-revalidate` Cache-Control directives for non-critical live data.
16.17 Add a manual "Refresh Data" button on the UI that bypasses ETags.
16.18 Ensure CORS headers allow ETag exposure (`Access-Control-Expose-Headers`).
16.19 Optimize ETag hashing to use `xxhash` or `murmurhash` for speed.
16.20 Verify network payload size drops to 0 bytes when reloading an unchanged route list.

## Task 17: Disk Space & Log Rotation Management
**Focus: Preventing VPS crashes due to filled NVMe/SSD drives.**
17.1 Implement strict Logrotate rules for Uvicorn and Custom logs (max 50MB per file).
17.2 Compress old logs automatically using gzip.
17.3 Set a maximum retention policy of 7 days for local logs.
17.4 Build an automated cleaner for old SQLite WAL files.
17.5 Implement a cleanup background task for orphaned `/media/sos` files.
17.6 Add a system metric endpoint tracking `/` disk space percentage.
17.7 Trigger an alert if disk space falls below 20% available.
17.8 Prevent file uploads (if any) if disk space is critical.
17.9 Rotate and compress the `emergency_cache.json` and graph snapshots daily.
17.10 Ensure Redis AOF/RDB persistence is configured to not exhaust disk space.
17.11 Offload old logs to a remote object store (S3/Cloudflare R2) automatically.
17.12 Clean up Docker dangling volumes and images in the deployment script.
17.13 Implement quotas for user-generated content size.
17.14 Monitor `tmpfs` usage if utilizing memory-mapped files.
17.15 Configure Promtail to drop logs gracefully if backend Loki is unreachable.
17.16 Automate clearing of `__pycache__` and `.pytest_cache` in production.
17.17 Use `ncdu` in deployment checks to map largest directories.
17.18 Implement graceful degradation: disable logging to disk if space < 5%.
17.19 Ensure database backups do not infinitely pile up locally.
17.20 Fill a dummy disk partition to 100% and verify the system remains operational (read-only).

## Task 18: Telemetry Sampling & Low-Overhead Observability
**Focus: Gaining insights without the telemetry itself slowing down the system.**
18.1 Implement dynamic sampling: log 100% of errors, but only 5% of 200 OKs.
18.2 Automatically increase sampling rate to 100% when Surge Level > Normal.
18.3 Group repetitive warnings into a single summary log every 60 seconds.
18.4 Use UDP instead of TCP for log shipping to Loki/Datadog to prevent blocking.
18.5 Disable debug-level logs entirely in production; rely on structured INFO.
18.6 Ensure Prometheus metrics endpoint (`/api/metrics`) is blazing fast.
18.7 Remove large payload dumps from logs; only log Request IDs and Status.
18.8 Add user-context (`user_id`, `role`) to logs cleanly via ContextVars.
18.9 Profile the `ObservabilityMiddleware` to ensure < 0.5ms overhead.
18.10 Track `p95` and `p99` latency explicitly in Prometheus.
18.11 Set up automated Grafana alerts for error spikes > 2% per minute.
18.12 Ensure sensitive data (Passwords, PII, Tokens) is heavily masked before logging.
18.13 Implement correlation IDs across Frontend -> Gateway -> ML Services.
18.14 Track specific UI interaction events via a lightweight beacon endpoint.
18.15 Add slow-query logging at the SQLAlchemy engine level.
18.16 Use OpenTelemetry standards for tracing if migrating to microservices.
18.17 Map exception types cleanly in Grafana dashboards for quick triage.
18.18 Create an API endpoint to temporarily enable DEBUG logging without restart.
18.19 Ensure memory tracing (`tracemalloc`) is disabled by default.
18.20 Simulate 5,000 req/sec and verify logging pipeline uses < 5% CPU.

## Task 19: Security & Rate Limiting Optimization
**Focus: Defending against abuse with absolute minimal compute cost.**
19.1 Move IP Rate Limiting out of Python and into Nginx/Traefik where possible.
19.2 Optimize `RateLimitMiddleware` to use Redis Lua scripts for atomicity and speed.
19.3 Implement localized rate limiting (memory) if Redis drops.
19.4 Add strict input validation (Regex) on all search parameters before parsing.
19.5 Restrict payload sizes (`max_content_length`) at the ASGI layer.
19.6 Enforce `Helmet`-style security headers (`X-Frame-Options`, `HSTS`).
19.7 Block malicious User-Agents instantly using a highly optimized Trie structure.
19.8 Implement JWT expiration and short-lived access tokens with refresh rotation.
19.9 Prevent timing attacks by using constant-time string comparisons for auth.
19.10 Add CORS origin verification that strictly checks the Origin header against a whitelist.
19.11 Disable FastAPI interactive docs (`/docs`) in strict production mode.
19.12 Implement CSRF protection for any state-mutating endpoints.
19.13 Add automated Dependency scanning (Dependabot/Snyk) to the CI pipeline.
19.14 Track failed login attempts and apply progressive lockouts (1m, 5m, 1hr).
19.15 Ensure Database connection strings and secrets are never logged.
19.16 Implement honeypot/tar-pit routes to trap and delay automated scanners.
19.17 Use `argon2` or optimized `bcrypt` parameters suited for the VPS CPU.
19.18 Strip server identification headers (`Server: uvicorn`).
19.19 Monitor authentication endpoint latency to detect brute-force attempts.
19.20 Run automated OWASP ZAP scans against the backend and resolve all findings.

## Task 20: System Watchdog & Self-Healing
**Focus: Ultimate 24x7 autonomy; the system must fix itself.**
20.1 Build a master Watchdog cron job that checks `/api/health` independently.
20.2 If Watchdog detects 3 failures, automatically restart the systemd service/container.
20.3 Implement an auto-recovery script that clears `/tmp` and restarts if RAM is exhausted.
20.4 Ensure the ML prediction hub auto-reconnects if IPC/Socket drops.
20.5 Add a background integrity checker that verifies DB schemas on boot.
20.6 Automate the download of fresh GTFS data if local files are corrupted.
20.7 Create a fallback "Safe Mode" configuration that disables all complex features.
20.8 Monitor SSL Certificate expiry and trigger certbot renewal automatically.
20.9 Implement a dead-man's switch for the ASGI worker pool.
20.10 Send a "System Recovered" Telegram alert with crash diagnostics.
20.11 Create a backup of `railway_data.db` daily and keep the last 3 copies.
20.12 Automate the restoration of the DB from backup if corruption is detected.
20.13 Implement graceful degradation of the UI if the backend goes fully offline (PWA offline mode).
20.14 Track uptime SLA internally and expose it on a public status page.
20.15 Configure Docker Restart Policies (`unless-stopped`) correctly.
20.16 Build a script to automatically map and ban IPs causing 500 errors repeatedly.
20.17 Ensure all state files (`.pkl`, `.npz`) are written atomically (write to `.tmp` then `mv`).
20.18 Implement a Chaos Monkey script in staging to continuously test self-healing.
20.19 Add heartbeat endpoints for every individual microservice/component.
20.20 Simulate a full VPS hard reboot (kill power) and verify the system returns to 100% functionality without human intervention within 60 seconds.
