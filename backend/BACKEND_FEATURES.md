# RouteMaster — Backend Feature Inventory

Comprehensive, categorized list of all backend features and where they are implemented. Use this as the single source-of-truth for backend capabilities, endpoints and the modules to inspect or extend. ✅

---

## Summary
- Scope: entire `backend/` folder (APIs, services, core engines, ML, workers, integrations).
- Purpose: developer-facing inventory for onboarding, reviews, and roadmap planning.

---

## Table of contents
1. Core application
2. Routing & Search
3. Booking & Seat Inventory
4. Payments & Reconciliation
5. Real-time operations & Graph mutation
6. Machine Learning & Analytics
7. Admin, ETL & Ops
8. Caching, performance & observability
9. Integrations & microservices
10. Notifications, chat & UX flows
11. DB, migrations & seed data
12. Tests, dev tools & scripts
13. API router / endpoint summary
14. Where to look (key files)
15. Next steps

---

## 1) Core application 🔧
- FastAPI app startup, middleware, CORS, rate-limiter and Prometheus instrumentation.
  - File: `backend/app.py`
  - Features: app lifecycle hooks, FastAPI-Cache (Redis), scheduled monthly ETL, worker start/stop.

## 2) Routing & Search 🧭
- Multi-modal routing engine (optimized RAPTOR + multi-modal improvements).
  - Files: `backend/route_engine.py`, `backend/core/multi_modal_route_engine.py`
  - Features: time-dependent graph, transfers, ML ranking, personalization, caching, journey reconstruction.
- Search API & station autocomplete.
  - Files: `backend/api/search.py`, `backend/api/integrated_search.py`, `backend/services/hybrid_search_service.py`
  - Features: single/connecting/multi-city/circular searches, fuzzy station resolution, nearby search, journey reconstruction service.

## 3) Booking & Seat Inventory 🎟️
- Seat availability, quotas, segment overlap detection, waitlist & seat-locking.
  - File: `backend/availability_service.py`, `backend/seat_inventory_models.py`
- Booking API + distributed transaction orchestrator (Saga pattern).
  - Files: `backend/booking_api.py`, `backend/booking_orchestrator.py`
  - Features: asynchronous booking processing, background tasks, PNR generation, booking status/cancel, waitlist promotion, seat allocation strategies.
- Seat allocation algorithms & strategies.
  - Files: `backend/services/seat_allocation.py`, `backend/services/smart_seat_allocation.py`

## 4) Payments & Reconciliation 💳
- Payment order creation, verification, webhook handling and unlock-payments.
  - Files: `backend/api/payments.py`, `backend/services/payment_service.py`
- Reconciliation worker and revenue reports.
  - Files: `backend/worker.py`, `backend/api/admin.py`, `backend/api/revenue_management.py`

## 5) Real-time operations & Graph mutation ⚡
- Train state store (Redis + DB), graph mutation engine for delays/cancellations/occupancy.
  - Files: `backend/train_state_service.py`, `backend/graph_mutation_engine.py`, `backend/graph_mutation_service.py`
- External sources integration (NTES, GPS) and background polling.
- WebSocket push for live updates.
  - Files: `backend/api/websockets.py`, `backend/api/graph-mutation` endpoints (see `graph_mutation_service.py`).

## 6) Machine Learning & Analytics 📈
- Feature extraction, feature store, dataset builder, model training pipeline.
  - File: `backend/ml_training_pipeline.py`, `backend/ml_data_collection.py`
- Predictors: delay/cancellation/tatkal/route-ranking.
  - Files: `backend/services/delay_predictor.py`, `backend/services/tatkal_demand_predictor.py`, `backend/services/route_ranking_predictor.py`
- Event consumer + Kafka analytics pipeline.
  - Files: `backend/services/analytics_consumer.py`, `start_analytics_consumer.py`

## 7) Admin, ETL & Ops 🛠️
- Admin APIs (ETL sync, reload graph, disruptions, commission reconciliation).
  - File: `backend/api/admin.py`
- Scheduled ETL cron job (monthly) configured in `backend/app.py`.

## 8) Caching, performance & observability ⚡
- Multi-layer caching (Redis + in-memory + file), cache warming, route & availability cache.
  - File: `backend/services/multi_layer_cache.py`, `backend/services/cache_warming_service.py`
- Prometheus metrics / Instrumentation.
  - File: `backend/app.py` (+ various `backend/utils/metrics.py` usage)

## 9) Integrations & microservices 🔌
- gRPC microservice mode (inventory/locking) and optional external microservices.
- Redis, Kafka, S3, payment gateway integrations.
  - Files: `backend/microservices/`, `backend/services/payment_service.py`, `backend/notification_service/`

## 10) Notifications, Chat & UX flows 💬
- Chat assistant with tool-calling & session storage (OpenRouter integration).
  - File: `backend/api/chat.py`
- SOS alerts, flow tracker, reviews, and user-facing endpoints.
  - Files: `backend/api/sos.py`, `backend/api/flow.py`, `backend/api/reviews.py`

## 11) Database & migrations 🗄️
- SQLAlchemy models, Alembic migrations, DB seeders.
  - Files/folders: `backend/models.py`, `backend/alembic/`, `seed_stations.py`, `backend/database.py`

## 12) Tests, dev tools & scripts 🧪
- Unit & integration tests and mock servers.
  - Folders: `backend/tests/`, `mock_api_server.py`, `concurrency_load_tester.py`, `simple_load_test.py`
- Docker + compose and dev config files.
  - Files: `Dockerfile`, `docker-compose*.yml`

---

## 13) API router / endpoint summary (major routers)
- `GET /` — root / basic info (`backend/app.py`)
- `POST /api/search/` — route search (`backend/api/search.py`)
- `POST /api/v2/search/unified` — integrated unified search (`backend/api/integrated_search.py`)
- `POST /api/v1/booking/availability` — check availability (`backend/booking_api.py`)
- `POST /api/v1/booking/book` — submit booking request (`backend/booking_api.py`)
- `GET /api/v1/booking/status/{pnr_number}` — booking status (`backend/booking_api.py`)
- `POST /api/v1/booking/cancel/{pnr_number}` — cancel booking (`backend/booking_api.py`)
- `POST /api/v1/booking/payment/webhook` — payment webhook (`backend/booking_api.py`)
- `POST /api/payments/create_order` & `POST /api/payments/webhook` — payments (`backend/api/payments.py`)
- `POST /api/v1/graph-mutation/delay` — apply delay (`backend/graph_mutation_service.py`)
- `POST /api/sos/` — trigger SOS (`backend/api/sos.py`)
- `POST /chat/` & chat tools — AI assistant (`backend/api/chat.py`)
- `GET /api/health`, `/api/health/ready`, `/api/health/live` — health probes (`backend/api/status.py`)
- WebSocket: `/ws/sos` and `/api/search/ws` (search websocket) (`backend/api/websockets.py`, `backend/api/search.py`)

> Note: many routers expose additional helper endpoints (stations autocomplete, admin ETL, disruptions, flow status, etc.) — see "Where to look" below.

---

## 14) Where to look (key files by feature)
- App entry, startup, metrics: `backend/app.py`
- Route engine & algorithms: `backend/route_engine.py`, `backend/core/multi_modal_route_engine.py`
- Search APIs: `backend/api/search.py`, `backend/api/integrated_search.py`
- Booking & orchestration: `backend/booking_api.py`, `backend/booking_orchestrator.py`
- Availability & inventory: `backend/availability_service.py`, `backend/seat_inventory_models.py`
- Graph mutation & train state: `backend/train_state_service.py`, `backend/graph_mutation_engine.py`, `backend/graph_mutation_service.py`
- ML pipeline & predictors: `backend/ml_training_pipeline.py`, `backend/services/delay_predictor.py`
- Caching: `backend/services/multi_layer_cache.py`, `backend/services/cache_service.py`
- Payments & reconciliation: `backend/api/payments.py`, `backend/services/payment_service.py`, `backend/worker.py`
- Chat / AI assistant: `backend/api/chat.py`
- Admin & ETL: `backend/api/admin.py`, `backend/etl/`
- Tests & tools: `backend/tests/`, `mock_api_server.py`, `concurrency_load_tester.py`

---

## 15) Next steps (pick one)
1. Generate a machine-readable OpenAPI / endpoints inventory (detailed path/method/params). ✅
2. Create a `docs/` page or README summarizing features for stakeholders. ✅
3. Add missing unit/integration tests for core modules (I can propose a prioritized list). ✅

Reply with the number (1 / 2 / 3) or "none" and I will proceed.

---

_Last updated: 2026-02-19 — generated from workspace `backend/` folder._
