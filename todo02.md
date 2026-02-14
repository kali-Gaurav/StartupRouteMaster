# RouteMaster — Top 30 High‑Priority Technical Tasks

This task list is derived from a deep-dive audit (routing, payment, ETL, chat agent, data layer). Tasks are ordered by priority (P0, P1, P2) and include quick descriptions and where to implement.

## P0 — Critical (must fix before 1k+ concurrent users)

1. Implement full RAPTOR optimizations in `backend/services/route_engine.py` — per-stop route indices, binary-search boarding, Pareto pruning, unit + perf tests. (Priority: P0)
2. Replace time-expanded Dijkstra with the RAPTOR production path for transit segments and update tests. (P0)
3. Move in‑memory graph cache from local pickle to shared cache (Redis/RedisJSON or object store) with versioning and HMAC signing. (P0)
4. Make RouteEngine horizontally scalable: stateless search workers + shared graph cache; add readiness probe. (P0)
5. Implement robust Redis-based seat-locking with owner token, TTL, and Lua CAS; integrate in `create_order`/`verify`. (P0)
6. Enforce DB-level invariants to prevent double-booking (unique/index + transactional checks on bookings). (P0)
7. Change `_DummyLock` to *not* silently succeed for distributed locks; fail critical operations when Redis is unavailable. (P0)
8. Harden seat-lock release: verify lock owner before deletion (atomic release). (P0)
9. Add `POST /api/payments/webhook` handler (signature verify + idempotent processing + enqueue work). (P0)
10. Replace blocking `requests` with `httpx.AsyncClient` (or run in threadpool) in async endpoints; add circuit breakers and strict timeouts. (P0)

## P1 — High (important for correctness, resilience, observability)

11. Enforce GatewayValidator for AI tool-calls in `backend/api/chat.py`; require auth, rate limits and audit logs. (P1)
12. Implement chat session summarization and token-budgeted context retention (persist compact summaries in Redis). (P1)
13. Fix station geospatial query & distance computation; add missing imports/Float casting and unit tests. (P1)
14. Improve station autocomplete performance — add `pg_trgm` trigram index or external search. (P1)
15. Remove N+1 queries in admin endpoints — rewrite as JOIN or use eager loading. (P1)
16. Add GIST index on `stations.geom` and validate SRID; add migration. (P1)
17. Implement coordinated cache invalidation after ETL (Redis pub/sub notification). (P1)
18. Add circuit breakers + fail‑open fallbacks for external APIs (OpenRouter, Razorpay) with cached responses for search. (P1)
19. Make Redis in‑mem fallback strict (non-distributed features should be disabled in prod). (P1)
20. Improve payment reconciliation worker: add webhook-first approach, reduce polling windows and exponential backoff. (P1)

## P1 — Data & Inventory (continued)

21. Add seat inventory model/table + atomic upsert workflows; sync with external partners and reconcile. (P1)
22. Add RouteEngine startup/readiness gating and background warm-up to avoid race conditions. (P1)
23. Add Prometheus metrics and dashboards (search latency, cache hits, lock contention, webhook errors). Define SLOs and alerts. (P1)
24. Add API rate-limiting (gateway or middleware) for `/api/search`, `/chat`, `/api/payments`. (P1)

## P2 — Important but lower priority

25. Offload CPU-bound search work from request threads — threadpool, microservice, or compiled hot-paths. (P2)
26. Return compact route summaries (avoid sending full JSON every time); lazy-load details. (P2)
27. Enforce idempotency for webhook/payment processing and add DB upserts. (P2)
28. Introduce message queue for decoupling booking/payment flows (retryable, durable). (P2)
29. Implement SAGA/compensation for multi-step flows (unlock → payment → external booking). (P2)
30. Add automated load/perf tests (k6/Locust) to CI asserting p95 < 100ms for search. (P2)

---

Notes:
- See `backend/services/route_engine.py`, `backend/api/payments.py`, `backend/services/cache_service.py`, `backend/etl/sqlite_to_postgres.py`, `backend/api/chat.py` for related code locations.
- I can implement any of these tasks (example: Redis seat locking + tests & migration). Tell me which task to pick first.
