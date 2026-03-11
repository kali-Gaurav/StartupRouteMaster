# Epic 4: Context-Aware Database Connection Pooling

To ensure absolute integration without any "missing gaps" between our new predictive intelligence and the database layer, we must implement these 15 highly specific, unique subtasks. They bridge the gap between "dumb connection pools" and our "Predictive JIT System."

## The 15 High-Priority Subtasks

1. **Subtask 4.1: Lazy Engine Instantiation:** Currently, `session.py` creates SQLAlchemy engines at import time, which blocks the Python interpreter. We will refactor this to only instantiate engines when `jit_manager.ensure_ready("DATABASE")` is triggered.
2. **Subtask 4.2: Predictive Pool Pre-Warming:** When `ShadowWarmer` detects "SEARCH" intent, it won't just initialize the engine; it will proactively fire `SELECT 1` across 5 async connections to complete the TCP handshakes *before* the user's API call hits the router.
3. **Subtask 4.3: Read/Write Multiplexer (CQRS):** Implement a custom SQLAlchemy Session proxy. It will automatically route `SELECT` queries to the lightning-fast local SQLite (`transit_graph.db`) and `INSERT/UPDATE/DELETE` queries to the remote Supabase PostgreSQL database.
4. **Subtask 4.4: Ghost Connection (Write-Behind Fallback):** If the remote Postgres pool is exhausted or down, the multiplexer returns a "Ghost Session". Writes are serialized to Redis, and the API returns `202 Accepted` instead of failing, completely masking DB outages from the user.
5. **Subtask 4.5: Isolated Authentication Pool:** Create a strictly isolated, high-priority connection pool dedicated ONLY to user authentication (JWT verification). This ensures that a massive spike in route searches can never prevent a user from logging in or verifying their identity.
6. **Subtask 4.6: Dynamic Pool Sizing via Telemetry:** Wire the `jit_metrics` directly into the database engine. If `predictions_total` spikes over 500/sec, dynamically increase the SQLAlchemy `max_overflow` limit. If traffic drops, aggressively trim the pool to save memory.
7. **Subtask 4.7: Memory-Aware Connection Reaper:** A background worker that tracks `psutil`. If server RAM exceeds 85%, it forcefully closes idle database connections, sacrificing pool readiness to prevent an Out-Of-Memory (OOM) OS crash.
8. **Subtask 4.8: Query Cost Analyzer & Shedder:** Intercept SQLAlchemy query compilation. If the system is in a `DEGRADED` JIT state (from Epic 1) and a query is deemed "too heavy" (e.g., joining 5 tables), it is instantly rejected with `503 Service Unavailable` rather than locking up a pool connection.
9. **Subtask 4.9: JIT Schema Reflection:** Prevent the expensive `Base.metadata.create_all()` from running on all tables at once. We will lazily reflect schemas only for the models required by the current predictive intent (e.g., only check `Stop` and `Route` tables during a search).
10. **Subtask 4.10: ASGI Lifecycle Binding:** Bind the AsyncSession generation directly to Starlette's `Request` object lifecycle via a custom middleware. If a user closes their browser (Client Disconnect) mid-query, the database transaction is instantly cancelled and the connection is returned to the pool.
11. **Subtask 4.11: Query Batching for Hydration:** When the `PrioritizedHydrationQueue` (Subtask 1.11) triggers, batch all related DB lookups (like fetching 10 different station names) into a single async round-trip using `asyncio.gather` to minimize connection hold time.
12. **Subtask 4.12: Intent-Based Timeout Adjustment:** If the `intent_predictor` says a request is `STATUS` (needs to be instant), set the DB connection timeout to 500ms. If the intent is `BOOKING` (user is willing to wait), allow a 5000ms timeout to ensure transaction safety.
13. **Subtask 4.13: Deadlock Resolution Heuristic:** Monitor concurrent async sessions. If a deadlock is detected in Postgres, the system looks at the JIT intent scores. The connection with the lower "Booking Confidence" score is automatically rolled back to unblock the higher-value user.
14. **Subtask 4.14: Local Replica Sync Worker:** For the Multiplexer (4.3) to work, the local SQLite database must be fresh. Create an isolated background process that streams updates from Postgres to SQLite without taking read locks.
15. **Subtask 4.15: Deep Metrics Integration:** Expose `pool_checked_out`, `pool_overflow`, and `query_latency_ms` to the `jit_metrics` report, allowing the Prometheus health endpoint to monitor DB health alongside prediction accuracy.

---

### Implementation Strategy
By defining these 15 subtasks, we ensure that the JIT intelligence we built in Epic 1 isn't just an isolated module, but directly controls how the database allocates memory, scales, and protects itself.

I will begin by implementing **Subtask 4.1 & 4.2** to integrate the DB initialization directly into the `jit_manager` and `shadow_warmer` correctly, fixing the integration gaps.
