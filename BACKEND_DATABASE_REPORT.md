# Backend & Database Architecture — Concise Report

**Repository**: startupV2
**Generated**: 2026-02-12
**Author**: GitHub Copilot

---

## Executive Summary ✅
The backend has been upgraded to a production-ready, high-performance architecture. Core improvements include an in-memory graph RouteEngine with Redis caching, a normalized PostgreSQL schema (vehicles, segments, users, bookings, payments, reviews), JWT-based authentication, bcrypt password hashing, and a maintained ETL to populate the new schema. The result is a secure, scalable, and low-latency route-finding platform designed for real-world load.

---

## Key Components (at a glance) 🔧
- Framework: `FastAPI` (async, high-throughput)
- Language: Python 3
- ORM / DB: `SQLAlchemy` + PostgreSQL
- Cache: `Redis` (distributed query/result cache)
- Auth: JWT tokens (access control) + bcrypt password hashing
- Route engine: in-memory graph + Dijkstra/A* heuristic
- ETL: `etl/sqlite_to_postgres.py` updated to populate `vehicles`

---

## Database Schema (concise) 🗂️
Primary tables and purpose:

- `stations` — transport hubs (station metadata, coords).
- `vehicles` — vehicle records (train number/operator/model). Replaces string-based operator fields.
- `segments` — graph edges between two stations tied to a `vehicle_id` (seats, times, distance, cost).
- `users` — authenticated accounts (id, email, hashed_password, metadata).
- `bookings` — links a `user_id` to one or more `segments` (status, timestamps).
- `payments` — payment attempts/status linked to a `booking_id` (Razorpay integration).
- `reviews` — user rating + comment for completed `booking_id`.

Primary relational changes:
- Bookings now reference `users` (no redundant user fields).
- Segments reference `vehicles` (stronger normalization).

---

## RouteEngine — Design & Rationale ⚡
- Startup: full `stations` + `segments` load into a persistent, in-memory graph (fast lookups).
- Search: run Dijkstra with an A* heuristic against the in-memory graph for optimal routes.
- Caching: results cached in Redis keyed by search parameters; cache hit returns ms-level responses.
- Benefit: avoids DB latency on every request and enables sub-second route queries at high QPS.

Files: `backend/services/route_engine.py` (core), `backend/services/cache_service.py` (Redis glue).

---

## Authentication & Security 🔐
- JWT for stateless authentication and protected endpoints.
- Passwords hashed with `bcrypt` — no plaintext storage.
- Sensitive endpoints require valid JWT (booking creation, submit review, create payment).
- Principle of least privilege applied at API routes and service layers.

Files: `backend/api/users.py`, token endpoints under `/api/users/token`.

---

## API & Services (important endpoints) 🔄
- `POST /api/users/register` — create account
- `POST /api/users/token` — login (returns JWT)
- `GET /api/search/` — high-performance cached route search
- `POST /api/payments/create_order` — create booking + initiate payment (auth required)
- `POST /api/reviews/` — submit review for booking (auth required)

Service separation: `UserService`, `BookingService`, `PaymentService`, `CacheService`, `RouteEngine`.

---

## ETL & Data Migration 🔁
- `etl/sqlite_to_postgres.py` updated to populate `vehicles` and to link `segments.vehicle_id` correctly.
- Seed scripts available: `backend/seed_stations.py` (and related seeds/tests).
- Migration checklist:
  1. Run migrations / create tables in Postgres
  2. Run ETL to import vehicles, stations, segments
  3. Seed test users/bookings if needed

---

## Testing, Observability & Reliability 📈
- Unit + integration tests present in `backend/tests/` (search, booking, payments, auth).
- Recommended additions: load tests for RouteEngine cold-start and Redis cache hit/miss patterns.
- Observability: add metrics (route latency, cache hit-rate, DB connection pool usage) and structured logs.

---

## Performance & Scaling Notes 💡
- In-memory graph + Redis provide horizontal read-scale for search-heavy workloads.
- Stateful pieces to monitor: memory footprint of graph, Redis throughput, DB write contention for bookings/payments.
- Suggestion: autoscale worker replicas (for RouteEngine reads) and use background job queues for payment reconciliation and booking finalization.

---

## Security & Compliance ⚠️
- Ensure strong JWT secret rotation and short token TTLs + refresh tokens if required.
- PCI: do not store raw payment card data; use Razorpay-hosted flows or tokenization.
- Harden endpoints with rate-limiting (per-IP/user) for public search endpoints.

---

## Recommended Next Steps (prioritized) ▶️
1. Add cache warm-up on app startup and monitor cold-start latency. ✅
2. Add metrics + dashboards (Prometheus + Grafana) for cache hit-rate and route latency. ✅
3. Implement role-based access for admin endpoints and audit logging.  
4. Add end-to-end tests for booking->payment->review flow.  
5. Run a load test targeting Redis and RouteEngine to identify vertical scaling points.

---

## Migration / Deployment Checklist (quick) 📋
- [ ] Apply DB migrations to Postgres
- [ ] Run `etl/sqlite_to_postgres.py` to populate `vehicles` and `segments`
- [ ] Start Redis and configure `CACHE_URL`
- [ ] Seed users (if staging) and run tests in CI
- [ ] Deploy FastAPI app behind ASGI server (uvicorn/gunicorn) and behind a reverse proxy / load balancer

---

## Risks & Mitigations 🔍
- Risk: Memory growth of in-memory graph -> Mitigation: monitor RSS, shard graph if needed.
- Risk: Cache inconsistency after data updates -> Mitigation: implement cache invalidation hooks on DB changes.
- Risk: Long-running booking/payment failures -> Mitigation: implement durable background jobs and reconciliation.

---

## Appendix — Useful repo locations
- Backend routes & models: `backend/models.py`, `backend/api/`*
- Route engine & services: `backend/services/route_engine.py`, `backend/services/cache_service.py`
- ETL: `etl/sqlite_to_postgres.py`
- Tests: `backend/tests/`

---

If you want, I can:
- generate a Mermaid ER diagram to add to this document, or
- create a migration & seed runbook (step-by-step commands) for production deployment.

Which of those should I add next? 
