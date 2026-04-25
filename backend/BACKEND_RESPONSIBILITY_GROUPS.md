# Backend Responsibility Groups

## Purpose

This document breaks the backend into small ownership groups so we can upgrade the system without missing hidden dependencies, mock/real integration gaps, or production integrity failures.

How to use this file:

1. Pick one group at a time.
2. Audit every file listed in that group before changing code.
3. Replace mock paths with real integrations where needed.
4. Add validation, retry, logging, and tests for that group before merging.
5. Run end-to-end verification only after the group contract is stable.

Important scope note:

- I grouped **implementation-facing backend files** into 4-5 item clusters.
- I intentionally separated **generated artifacts, logs, binary indexes, ticket PDFs, virtual environments, caches, and temporary traces** into a final appendix because they should be regenerated or observed, not hand-maintained as product logic.
- For very large repetitive areas such as tests and migration families, I use precise file patterns so we still cover the whole backend without turning this plan into an unreadable dump.

---

## Group 01: Application Bootstrap

Files:

- `backend/app.py`
- `backend/config.py`
- `backend/dependencies.py`
- `backend/background_worker.py`
- `backend/__init__.py`

Responsibility:

- Own app startup, dependency wiring, global configuration, and process boot sequence.
- Remove hidden circular imports and implicit defaults.
- Ensure dev, test, and production environments resolve the same core dependencies.
- Verify the app fails fast when env vars, secrets, or infrastructure are missing.

Definition of done:

- Startup is deterministic.
- Config is validated at launch.
- Background worker initialization is safe and observable.

---

## Group 02: Runtime and Deployment Entry Points

Files:

- `backend/gunicorn_conf.py`
- `backend/run_dev.py`
- `backend/run_dev.bat`
- `backend/start.sh`
- `backend/Procfile`

Responsibility:

- Standardize local and production process launch behavior.
- Remove drift between Windows, shell, and process manager startup flows.
- Ensure worker count, timeouts, ports, and import paths match real deployment assumptions.
- Confirm graceful shutdown and health probing behavior.

Definition of done:

- Every entry point starts the same app contract.
- No environment-specific startup surprises remain.

---

## Group 03: Packaging and Dependency Control

Files:

- `backend/pyproject.toml`
- `backend/requirements.txt`
- `backend/requirements_dev.txt`
- `backend/runtime.txt`
- `backend/railpack.json`

Responsibility:

- Align package management, Python version, and runtime packaging.
- Remove duplicate or conflicting dependency declarations.
- Separate production-only, dev-only, and optional packages.
- Lock tooling needed for reproducible CI and professor demo environments.

Definition of done:

- Fresh environment setup is reproducible.
- Runtime package set is minimal and valid.

---

## Group 04: Container and Platform Deployment

Files:

- `backend/Dockerfile`
- `backend/Dockerfile.prod`
- `backend/nixpacks.toml`
- `backend/alembic.ini`
- `backend/README.md`

Responsibility:

- Make build, migration, and deployment expectations explicit.
- Align container image startup with actual production bootstrap steps.
- Ensure migration tooling is invoked consistently in deploy workflows.
- Keep operational docs synchronized with the real deployment path.

Definition of done:

- Docker and platform deploys use the same assumptions.
- Migration and startup instructions are production-safe.

---

## Group 05: Root Diagnostics and Sanity Utilities

Files:

- `backend/check_*.py`
- `backend/diagnose_*.py`
- `backend/list_*.py`
- `backend/probe_db.py`
- `backend/clear_station_cache.py`

Responsibility:

- Consolidate one-off health scripts into a trustworthy diagnostic toolbox.
- Remove stale scripts that target outdated schemas or fake data layouts.
- Standardize output format so debugging production issues is faster.
- Mark which scripts are read-only and which mutate state.

Definition of done:

- Every retained script has a clear purpose, safe execution contract, and current schema awareness.

---

## Group 06: Root Verification and Audit Scripts

Files:

- `backend/finalize_db.py`
- `backend/final_verify_search.py`
- `backend/engine_diagnostic.py`
- `backend/nexus_master_audit.py`
- `backend/nexus_chaos_audit.py`

Responsibility:

- Review final verification scripts that are supposed to prove readiness.
- Ensure each script tests real invariants, not old assumptions or happy-path mocks.
- Align audit output with current database, routing, payment, and nexus flows.
- Decide which scripts become CI jobs and which remain manual tools.

Definition of done:

- Audit results are trustworthy and actionable.
- Readiness scripts match current architecture.

---

## Group 07: API Surface Core

Files:

- `backend/api/__init__.py`
- `backend/api/dependencies.py`
- `backend/api/middleware.py`
- `backend/api/status.py`
- `backend/api/system/__init__.py`

Responsibility:

- Own shared API dependency injection, middleware policy, and system endpoint wiring.
- Enforce consistent auth, rate limiting, correlation IDs, and error shapes.
- Make sure every router receives the same request-scoped services and tracing fields.

Definition of done:

- Cross-cutting API behavior is centralized and consistent.

---

## Group 08: API Auth and User Access

Files:

- `backend/api/auth.py`
- `backend/api/users.py`
- `backend/api/v2/user.py`
- `backend/api/v2/admin_auth.py`
- `backend/api/vault.py`

Responsibility:

- Close login, identity, admin access, and secret access gaps.
- Remove mixed auth assumptions between v1/v2 routes and service layer.
- Validate token parsing, role checks, and failure handling.
- Confirm vault access is audited and not exposed through weak route wiring.

Definition of done:

- User and admin authorization rules are explicit, tested, and consistent.

---

## Group 09: API Search Core

Files:

- `backend/api/search.py`
- `backend/api/unified_search.py`
- `backend/api/integrated_search.py`
- `backend/api/routes.py`
- `backend/api/stations.py`

Responsibility:

- Own search request contracts, routing inputs, station resolution, and unified response shape.
- Remove duplicate endpoint logic and inconsistent search parameter handling.
- Ensure all routes call real engines or clearly flagged fallbacks.
- Add proper validation for dates, station codes, pagination, filters, and null responses.

Definition of done:

- Search APIs resolve through one reliable contract with clean error semantics.

---

## Group 10: API Search Evolution Layers

Files:

- `backend/api/v2/search.py`
- `backend/api/v3/search.py`
- `backend/api/v3/model_search.py`
- `backend/api/v3/transit.py`
- `backend/api/v3/system.py`

Responsibility:

- Compare v2 and v3 search generations and remove capability drift.
- Define which version is authoritative for production.
- Verify model-assisted search does not bypass validation or resilience layers.
- Align system metadata endpoints with actual engine health.

Definition of done:

- Versioned search routes have a documented ownership boundary and no silent divergence.

---

## Group 11: API Real-Time and Live Channels

Files:

- `backend/api/realtime.py`
- `backend/api/v2/realtime.py`
- `backend/api/v2/live.py`
- `backend/api/websockets.py`
- `backend/api/chat_ws.py`

Responsibility:

- Own live updates, WebSocket contracts, and stream lifecycle management.
- Verify reconnect behavior, subscription limits, and auth on persistent channels.
- Prevent stream handlers from depending on mock events or stale in-memory state.
- Standardize payload schemas, heartbeat behavior, and backpressure handling.

Definition of done:

- Real-time endpoints are authenticated, observable, and resilient under disconnects.

---

## Group 12: API Booking and Journey Actions

Files:

- `backend/api/bookings.py`
- `backend/api/v2/booking.py`
- `backend/api/v2/booking_ws.py`
- `backend/api/v3/bookings.py`
- `backend/api/routemaster_integration.py`

Responsibility:

- Own booking submission, booking status, booking stream updates, and external route/booking coordination.
- Validate idempotency, seat state transitions, and external orchestration contracts.
- Remove fake success responses where a real booking integration is missing.
- Ensure booking endpoints degrade safely when providers fail.

Definition of done:

- Booking APIs reflect real backend state and provider outcomes.

---

## Group 13: API Payments and Finance

Files:

- `backend/api/payments.py`
- `backend/api/bank_webhooks.py`
- `backend/api/admin_refunds.py`
- `backend/api/admin_reconciliation.py`
- `backend/api/v2/finance_v2.py`

Responsibility:

- Own payment initiation, webhook ingestion, refunds, and reconciliation admin flows.
- Seal integrity gaps between API requests, ledger writes, and bank/provider callbacks.
- Confirm every state transition is auditable and replay-safe.
- Remove mock settlement shortcuts and define real failure semantics.

Definition of done:

- Payment-facing APIs are idempotent, signed where needed, and ledger-backed.

---

## Group 14: API SOS, Safety, and Emergency Access

Files:

- `backend/api/sos.py`
- `backend/api/v3/sos.py`
- `backend/api/telegram_bot.py`
- `backend/api/voice_v1.py`
- `backend/api/voice_triage.py`

Responsibility:

- Own SOS triggers, voice triage, and messaging escalation entry points.
- Validate emergency flows against real dispatch/reporting services.
- Ensure safety endpoints never depend on optional mocks without explicit fallback labels.
- Confirm latency, retry, and alerting behavior for critical incidents.

Definition of done:

- Emergency requests are routed through real, observable escalation paths.

---

## Group 15: API Operations, Admin, and Analytics

Files:

- `backend/api/admin.py`
- `backend/api/analytics_v1.py`
- `backend/api/v2/admin.py`
- `backend/api/v2/monitoring.py`
- `backend/api/v3/nexus_dashboard.py`

Responsibility:

- Own admin dashboards, observability endpoints, and operational introspection.
- Enforce strong access control and remove accidental exposure of internal state.
- Align dashboard numbers with actual metrics, not cached assumptions or stale reports.

Definition of done:

- Admin and analytics APIs are secure and match backend truth.

---

## Group 16: API Support, Reviews, and Workflow Edges

Files:

- `backend/api/chat.py`
- `backend/api/reviews.py`
- `backend/api/tasks.py`
- `backend/api/battery_mode.py`
- `backend/api/flow.py`

Responsibility:

- Clean up non-core product APIs that can still break user flow.
- Verify chat/session routing, review persistence, background task dispatch, and lightweight mode behavior.
- Standardize response contracts and make hidden dependencies visible.

Definition of done:

- Secondary APIs no longer bypass service-layer validations.

---

## Group 17: API Extended Product Modules

Files:

- `backend/api/revenue_management.py`
- `backend/api/tatkal.py`
- `backend/api/sathi.py`
- `backend/api/v2/credits.py`
- `backend/api/v2/notifications.py`

Responsibility:

- Own monetization-adjacent and product extension flows.
- Check that Tatkal, credits, notifications, and partner features all hit real services and durable state.
- Remove placeholder return payloads and define compensating behavior for failed downstream actions.

Definition of done:

- Extended product endpoints are real-service-backed and testable end to end.

---

## Group 18: API Experimental and Control Routes

Files:

- `backend/api/v2/agent.py`
- `backend/api/v2/agents.py`
- `backend/api/v2/debug.py`
- `backend/api/v3/governor.py`
- `backend/api/v3/scraper_controller.py`

Responsibility:

- Own experimental orchestration, debug exposure, and control-plane endpoints.
- Restrict or remove unsafe routes before production.
- Ensure controllers for agents and scrapers honor auth, audit, and rate limits.

Definition of done:

- No debug or control path can accidentally bypass production guardrails.

---

## Group 19: Core Container and Lifecycle

Files:

- `backend/core/container.py`
- `backend/core/context.py`
- `backend/core/lifespan.py`
- `backend/core/lifespan_simple.py`
- `backend/core/control_plane.py`

Responsibility:

- Own service registration, lifecycle startup/shutdown, and app-wide dependency context.
- Remove hidden singleton usage and startup ordering bugs.
- Ensure critical services start in the correct order and stop gracefully.

Definition of done:

- Core lifecycle is explicit, observable, and deterministic.

---

## Group 20: Core Routing Foundation

Files:

- `backend/core/unified_route_engine.py`
- `backend/core/unified_planner.py`
- `backend/core/base_engine.py`
- `backend/core/frontier.py`
- `backend/core/segment_detail.py`

Responsibility:

- Own the high-level routing abstraction and planner contract.
- Define which engine is canonical and which components are support layers.
- Eliminate duplicated route assembly logic and mismatched result schemas.

Definition of done:

- Routing foundation has one clear orchestration path and one contract.

---

## Group 21: Core Route Engine Kernel

Files:

- `backend/core/route_engine/base.py`
- `backend/core/route_engine/engine.py`
- `backend/core/route_engine/orchestrator.py`
- `backend/core/route_engine/builder.py`
- `backend/core/route_engine/compiler.py`

Responsibility:

- Own the main route computation pipeline and composition boundaries.
- Review how inputs are transformed into graph queries and hydrated journeys.
- Verify thread safety, cache dependency, and fallbacks for missing graph data.

Definition of done:

- Kernel execution path is stable, measurable, and not dependent on side effects.

---

## Group 22: Core Route Engine Performance Layer

Files:

- `backend/core/route_engine/turbo_router.py`
- `backend/core/route_engine/ultra_turbo.py`
- `backend/core/route_engine/fast_router.py`
- `backend/core/route_engine/neural_pruner.py`
- `backend/core/route_engine/throttler.py`

Responsibility:

- Own the fast-path routing stack and performance-sensitive heuristics.
- Confirm performance optimizations do not skip correctness checks.
- Benchmark hot paths against realistic station pairs and time windows.
- Define when slower but safer fallback engines should take over.

Definition of done:

- Fast engines are measurably better and still correct under edge cases.

---

## Group 23: Core Route Engine Graph and Transfer Logic

Files:

- `backend/core/route_engine/graph.py`
- `backend/core/route_engine/transfer_graph_builder.py`
- `backend/core/route_engine/transfer_intelligence.py`
- `backend/core/route_engine/reachability.py`
- `backend/core/route_engine/regions.py`

Responsibility:

- Own graph topology, transfer relationships, and reachability math.
- Audit assumptions about station linkage, transfer windows, and regional segmentation.
- Confirm data files and in-memory structures stay aligned.

Definition of done:

- Graph data structures and transfer logic are internally consistent.

---

## Group 24: Core Route Engine Scoring and Ranking

Files:

- `backend/core/route_engine/scoring.py`
- `backend/core/route_engine/scorer.py`
- `backend/core/route_engine/reliability.py`
- `backend/core/route_engine/station_quality.py`
- `backend/core/route_engine/hub_scoring.py`

Responsibility:

- Own ranking, reliability weighting, and quality heuristics.
- Remove magic constants that are not backed by product logic or test coverage.
- Align ranking logic with ML features, availability confidence, and user-facing expectations.

Definition of done:

- Score outputs are explainable, stable, and regression-tested.

---

## Group 25: Core Route Engine Multimodal and Constraints

Files:

- `backend/core/route_engine/multimodal_engine.py`
- `backend/core/route_engine/hybrid_engine.py`
- `backend/core/route_engine/interlining_engine.py`
- `backend/core/route_engine/constraints.py`
- `backend/core/route_engine/constraints_engine.py`

Responsibility:

- Own multimodal search, mode mixing, and route constraints.
- Verify bus/train blending does not create impossible or unsafe itineraries.
- Make constraints explicit for time, transfers, fare, and availability.

Definition of done:

- Multimodal outputs obey consistent feasibility rules.

---

## Group 26: Core Route Engine Data Access and Hydration

Files:

- `backend/core/route_engine/data_provider.py`
- `backend/core/route_engine/direct_index.py`
- `backend/core/route_engine/hydration.py`
- `backend/core/route_engine/snapshot_manager.py`
- `backend/core/route_engine/zonal_loader.py`

Responsibility:

- Own how routing pulls index data, snapshots, and hydrated journey details.
- Check stale snapshot risks and missing binary/regenerated data handling.
- Ensure zone loading and detail hydration cannot silently disagree.

Definition of done:

- Data access paths are versioned, validated, and observable.

---

## Group 27: Core Route Engine Advanced Builders

Files:

- `backend/core/route_engine/tbr_router.py`
- `backend/core/route_engine/tbr_edge_builder.py`
- `backend/core/route_engine/tbr_structures.py`
- `backend/core/route_engine/rake_linkage.py`
- `backend/core/route_engine/backbone_compiler.py`

Responsibility:

- Own TBR-specific and advanced precomputation structures.
- Validate edge indexes and specialized builders against live schema/data assumptions.
- Remove any dead experimental paths that no longer feed production search.

Definition of done:

- Specialized routing builders are clearly required, correct, and maintainable.

---

## Group 28: Core Middleware and Protection

Files:

- `backend/core/middleware/engine.py`
- `backend/core/middleware/rate_limit.py`
- `backend/core/middleware/guardian.py`
- `backend/core/middleware/observability.py`
- `backend/core/middleware/unified_engine.py`

Responsibility:

- Own request protection, instrumentation, and gateway-level policy.
- Ensure middleware order is correct and compatible with FastAPI lifecycle.
- Prevent double logging, broken request bodies, and uncaught auth bypasses.

Definition of done:

- Middleware stack is minimal, composable, and production-safe.

---

## Group 29: Core Auth and Identity Internals

Files:

- `backend/core/auth/provider.py`
- `backend/core/auth/permissions.py`
- `backend/core/auth/supabase_client.py`
- `backend/core/auth/utils.py`
- `backend/core/auth/integrity.py`

Responsibility:

- Own internal identity provider integration and permission evaluation.
- Verify Supabase and local auth logic do not drift.
- Ensure permission checks are centralized and testable.

Definition of done:

- Auth internals produce one trusted identity/permission model.

---

## Group 30: Core Validation Framework

Files:

- `backend/core/validator/validation_manager.py`
- `backend/core/validator/data_integrity_validators.py`
- `backend/core/validator/production_validators.py`
- `backend/core/validator/api_security_validators.py`
- `backend/core/validator/graph_validation_pipeline.py`

Responsibility:

- Own the validation framework used to certify readiness.
- Deduplicate overlapping validators and define a real promotion gate.
- Ensure validators read from current data sources and current route engine paths.

Definition of done:

- Validation results are trustworthy and promotable to CI/CD gates.

---

## Group 31: Core Validation Specialties

Files:

- `backend/core/validator/route_validators.py`
- `backend/core/validator/resilience_validators.py`
- `backend/core/validator/performance_validators.py`
- `backend/core/validator/fare_availability_validators.py`
- `backend/core/validator/ai_ranking_validators.py`

Responsibility:

- Own route, resilience, performance, fare, and AI-specific acceptance rules.
- Align specialty validators with the subsystems they certify.
- Remove validators that only assert mock outputs.

Definition of done:

- Specialty validators reflect real production expectations.

---

## Group 32: Core Nexus Platform

Files:

- `backend/core/nexus/bootstrapper.py`
- `backend/core/nexus/spine.py`
- `backend/core/nexus/state.py`
- `backend/core/nexus/synapse.py`
- `backend/core/nexus/watchdog.py`

Responsibility:

- Own the main nexus backbone, state coordination, and self-healing supervision.
- Decide what nexus is responsible for versus service orchestration.
- Validate restart behavior, state persistence, and degraded-mode operation.

Definition of done:

- Nexus platform has explicit boundaries and predictable recovery behavior.

---

## Group 33: Core Nexus Operational Domains

Files:

- `backend/core/nexus/cache/*.py`
- `backend/core/nexus/search/*.py`
- `backend/core/nexus/security/*.py`
- `backend/core/nexus/financial/*.py`
- `backend/core/nexus/audit/*.py`

Responsibility:

- Review nexus domain submodules as a platform layer, not as isolated scripts.
- Confirm cache, search interception, security agents, financial rollback, and audit logic all use the same state contract.
- Eliminate shadow logic that duplicates service behavior without clear ownership.

Definition of done:

- Each nexus domain supports the platform without competing with the normal service layer.

---

## Group 34: Core ML and Monitoring

Files:

- `backend/core/ml_integration.py`
- `backend/core/ml_ranking_model.py`
- `backend/core/ml_models/*.py`
- `backend/core/monitoring.py`
- `backend/core/system_monitor.py`

Responsibility:

- Own internal ML hookups, model loading, and system monitoring.
- Verify serialized model assets are version-compatible and safe to load.
- Make monitoring metrics actionable for routing, payments, and infra incidents.

Definition of done:

- Core ML and monitoring are bounded, observable, and not silently stale.

---

## Group 35: Database Foundation

Files:

- `backend/database/base.py`
- `backend/database/session.py`
- `backend/database/config.py`
- `backend/database/models.py`
- `backend/database/manager.py`

Responsibility:

- Own DB engine creation, session lifecycle, config, and primary ORM model surface.
- Remove inconsistent session usage and unsafe transaction boundaries.
- Confirm model definitions match migrations and runtime expectations.

Definition of done:

- Database foundation is schema-aligned and transaction-safe.

---

## Group 36: Database Scaling and Reliability

Files:

- `backend/database/batcher.py`
- `backend/database/multiplexer.py`
- `backend/database/partition_manager.py`
- `backend/database/circuit_breaker.py`
- `backend/database/sync_worker.py`

Responsibility:

- Own batching, partitioning, high-load query control, and DB resilience behavior.
- Validate these helpers against the actual production database footprint.
- Remove “advanced” infrastructure that is not actually wired into live flows.

Definition of done:

- Database scaling utilities are either proven and integrated or clearly retired.

---

## Group 37: Database Domain Models and Docs

Files:

- `backend/database/sathi_models.py`
- `backend/database/seat_inventory_models_stub.py`
- `backend/database/analyzer.py`
- `backend/database/README.md`
- `backend/database/partitioning_architecture.md`

Responsibility:

- Own special domain tables, inventory model gaps, and DB architecture docs.
- Replace stub model behavior with real schema ownership decisions.
- Ensure documentation matches actual runtime usage.

Definition of done:

- No stub model remains ambiguous; schema docs are current.

---

## Group 38: Migrations and Schema Evolution

Files:

- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/*.py`
- `backend/alembic/README`
- `backend/migrate_to_r2.py`

Responsibility:

- Own migration execution, migration hygiene, and data movement assumptions.
- Review every migration family for duplicate heads, irreversible risk, and stale schema intent.
- Confirm current models can be built from a clean migration history.

Definition of done:

- Schema evolution is reproducible from zero and safe for production rollout.

---

## Group 39: ETL and Data Import

Files:

- `backend/etl/*.py`
- `backend/scripts/build_*.py`
- `backend/scripts/precompute_*.py`
- `backend/scripts/rebuild_*.py`
- `backend/scripts/segment_graph.py`

Responsibility:

- Own large-scale data import, precomputation, and graph/index generation.
- Separate canonical build pipelines from experimental or obsolete generators.
- Ensure generated artifacts have provenance, versioning, and validation checks.

Definition of done:

- Data build pipeline can be rerun cleanly and produces verified assets.

---

## Group 40: Data and Generated Index Assets

Files:

- `backend/data/*.json`
- `backend/data/*.bin`
- `backend/data/*.npz`
- `backend/data/*.pkl`
- `backend/data/graph_segments/*.npz`

Responsibility:

- Treat these as generated/runtime support assets, not primary hand-edited code.
- Track which script generates each asset and which services consume it.
- Add checksum/version metadata where missing.

Definition of done:

- Every binary asset has a source pipeline and compatibility expectations.

---

## Group 41: Provider Gateway Layer

Files:

- `backend/providers/gateway.py`
- `backend/providers/models.py`
- `backend/providers/config.py`
- `backend/providers/base_provider_client.py`
- `backend/providers/circuit_breaker.py`

Responsibility:

- Own provider abstraction, resilience, and response normalization.
- Verify provider failover, timeout handling, and schema translation.
- Ensure mock and real provider paths share the same interface.

Definition of done:

- Provider gateway is stable and consistent across integrations.

---

## Group 42: Provider Clients and Adapter Edge

Files:

- `backend/providers/clients/*.py`
- `backend/providers/tests/test_gateway.py`
- `backend/adapters/train_adapter.py`
- `backend/services/providers/*.py`
- `backend/services/rapidapi_provider.py`

Responsibility:

- Own external provider clients, adapters, and service-facing provider wrappers.
- Close fake/live mismatch for RapidAPI, NTES scraping, multimodal mocks, and factory dispatch.
- Add contract tests for provider response mapping and error handling.

Definition of done:

- Real and mock provider connections are interchangeable through one contract.

---

## Group 43: Service Search and Routing Orchestration

Files:

- `backend/services/search_service.py`
- `backend/services/search/main.py`
- `backend/services/search/engine.py`
- `backend/services/hybrid_search_service.py`
- `backend/services/route_engine.py`

Responsibility:

- Own service-layer orchestration around route search and search result assembly.
- Remove duplication between core engine logic and service wrappers.
- Ensure caching, ranking, and provider calls happen in a predictable order.

Definition of done:

- Search services expose one clean orchestration surface for the API layer.

---

## Group 44: Service Booking Stack

Files:

- `backend/services/booking_service.py`
- `backend/services/booking_verification_service.py`
- `backend/services/booking_queue_service.py`
- `backend/services/booking/*.py`
- `backend/services/orchestration/booking_orchestrator.py`

Responsibility:

- Own booking lifecycle, verification, queueing, and orchestration.
- Close integrity gaps between reserve, confirm, rollback, and queue replay flows.
- Make external booking provider dependencies explicit and testable.

Definition of done:

- Booking stack is idempotent and rollback-safe.

---

## Group 45: Service Payments, Ledger, and Settlement

Files:

- `backend/services/payment_service.py`
- `backend/services/ledger_service.py`
- `backend/services/settlement_service.py`
- `backend/services/reconciliation_service.py`
- `backend/services/finance/*.py`

Responsibility:

- Own the money path from payment initiation to ledger posting and settlement.
- Eliminate integrity gaps between webhook receipt, ledger writes, and reconciliation.
- Add replay protection, balance invariants, and recovery procedures.

Definition of done:

- Financial state is auditable and consistent after success and failure paths.

---

## Group 46: Service Refunds, Credits, and Commission

Files:

- `backend/services/refund_service.py`
- `backend/services/credit_service.py`
- `backend/services/commission_service.py`
- `backend/services/commission_settlement_job.py`
- `backend/services/commission_audit_bot.py`

Responsibility:

- Own refunds, user credits, and commission accounting.
- Confirm negative balances, partial refunds, and post-settlement corrections are safe.
- Ensure commission rules match product and ledger contracts.

Definition of done:

- Refund and commission logic can be explained, audited, and recovered.

---

## Group 47: Service Inventory, Seats, and Availability

Files:

- `backend/services/inventory_service.py`
- `backend/services/seat_availability.py`
- `backend/services/seat_availability_service.py`
- `backend/services/seat_verification.py`
- `backend/services/inventory/availability_service.py`

Responsibility:

- Own seat state, inventory synchronization, and availability truth.
- Replace mock seat assumptions with a consistent real-source strategy.
- Verify reconciliation between provider data, DB snapshots, and API output.

Definition of done:

- Seat availability is internally consistent and provider-aware.

---

## Group 48: Service Station, PNR, and Journey State

Files:

- `backend/services/station_service.py`
- `backend/services/station_search_service.py`
- `backend/services/station_departure_service.py`
- `backend/services/pnr_service.py`
- `backend/services/pnr_verification_service.py`

Responsibility:

- Own station lookup, departure intelligence, and PNR verification.
- Validate station search indexes against route-engine and DB truth.
- Define how PNR data is fetched, cached, rechecked, and exposed.

Definition of done:

- Station and PNR services use validated data paths and clear freshness rules.

---

## Group 49: Service Real-Time Ingestion

Files:

- `backend/services/realtime_ingestion/*.py`
- `backend/services/live_status_service.py`
- `backend/services/delay_service.py`
- `backend/services/delay_predictor.py`
- `backend/core/realtime_event_processor.py`

Responsibility:

- Own live feed ingestion, parsing, delay propagation, and live status computation.
- Replace brittle or fake feed assumptions with explicit source handling.
- Validate clock skew, retry policy, and out-of-order event behavior.

Definition of done:

- Real-time ingestion is resilient and traceable from source event to API output.

---

## Group 50: Service Notifications and Communications

Files:

- `backend/services/notification_service.py`
- `backend/services/telegram_service.py`
- `backend/services/telegram_dispatcher.py`
- `backend/services/telecom_service.py`
- `backend/services/email_tasks.py`

Responsibility:

- Own outbound messaging, alert delivery, and communication failure handling.
- Ensure all channels use real providers or are clearly marked disabled.
- Add retry, deduplication, and delivery status tracking.

Definition of done:

- Notification channels are reliable, observable, and not silently dropped.

---

## Group 51: Service SOS and Emergency Backend

Files:

- `backend/services/sos_service.py`
- `backend/services/emergency/*.py`
- `backend/services/alert_service.py`
- `backend/services/verification_orchestrator.py`
- `backend/services/verification_engine.py`

Responsibility:

- Own emergency response coordination, escalation, connectivity checks, and incident verification.
- Confirm alert, report, dispatch, and firewall-linked flows work with real dependencies.
- Remove any emergency path that only simulates external escalation.

Definition of done:

- Emergency backend paths are operationally meaningful and end-to-end verifiable.

---

## Group 52: Service Auth, Identity, and Vault

Files:

- `backend/services/auth/*.py`
- `backend/services/identity_service.py`
- `backend/services/user_service.py`
- `backend/services/vault_service.py`
- `backend/services/credential_vault.py`

Responsibility:

- Own service-layer identity, device fingerprinting, secret usage, and user profile operations.
- Align with API and core auth contracts.
- Ensure vault access is minimized, audited, and not copied into ad hoc helpers.

Definition of done:

- Identity and secret flows are centralized and secure.

---

## Group 53: Service Safety, Fraud, and Risk

Files:

- `backend/services/fraud_service.py`
- `backend/services/fraud_detection_service.py`
- `backend/services/behavior_tracker.py`
- `backend/services/user_bloom_filter.py`
- `backend/services/prediction_hub.py`

Responsibility:

- Own fraud scoring, risk features, and suspicious behavior detection.
- Validate signal collection paths and ensure scores affect real decisions.
- Remove dead risk logic that does not feed enforcement or review flows.

Definition of done:

- Risk signals are connected to real policy and measurable outcomes.

---

## Group 54: Service Pricing, Revenue, and Yield

Files:

- `backend/services/pricing_service.py`
- `backend/services/price_calculation_service.py`
- `backend/services/enhanced_pricing_service.py`
- `backend/services/yield_management_engine.py`
- `backend/core/pricing/fare_calculator.py`

Responsibility:

- Own pricing rules, enhanced pricing logic, and yield management.
- Align pricing services with route engine fare calculations and provider fares.
- Ensure all pricing decisions are reproducible and testable.

Definition of done:

- Pricing outputs are internally consistent and do not depend on opaque fallbacks.

---

## Group 55: Service Cache, Warmup, and Snapshot Control

Files:

- `backend/services/cache_service.py`
- `backend/services/cache_warming_service.py`
- `backend/services/search_prewarmer.py`
- `backend/services/shadow_warmer.py`
- `backend/services/snapshot_service.py`

Responsibility:

- Own service-side caching and prewarm behavior.
- Prevent stale cache poisoning and accidental divergence from source-of-truth services.
- Define cache invalidation rules for search, station, PNR, and inventory data.

Definition of done:

- Cache layers improve performance without hiding correctness failures.

---

## Group 56: Service Analytics, Monitoring, and Audit

Files:

- `backend/services/analytics/main.py`
- `backend/services/analytics_consumer.py`
- `backend/services/audit_service.py`
- `backend/services/performance_monitor.py`
- `backend/services/monitoring_scheduler.py`

Responsibility:

- Own analytics ingestion, audit streaming, and service-level observability.
- Make sure metrics and analytics consumers reflect real business/system events.
- Remove zombie consumers and unbounded background loops.

Definition of done:

- Monitoring and analytics are useful for operations, not just noisy logs.

---

## Group 57: Service Intelligence and ML

Files:

- `backend/services/intelligence_service.py`
- `backend/services/intelligence/*.py`
- `backend/services/ml/*.py`
- `backend/microservices/ml_service/main.py`
- `backend/models/reliability_features.json`

Responsibility:

- Own intelligence features, drift detection, retraining hooks, and ML-serving assumptions.
- Verify whether ML is embedded, service-local, or microservice-backed in production.
- Add version and fallback rules for model artifacts.

Definition of done:

- ML features are explicit, versioned, and safe to disable if degraded.

---

## Group 58: Service Agents and Autonomous Helpers

Files:

- `backend/services/agents/*.py`
- `backend/workers/orchestrator.py`
- `backend/api/v2/agents.py`
- `backend/api/v2/agent.py`
- `backend/docs/orchestrator_hardening_tasks.md`

Responsibility:

- Own all internal agents, orchestration, and autonomous operational helpers.
- Identify which agents are real production automations versus idea-stage scaffolding.
- Add permissions, rate limits, and kill switches for any agent that can mutate state.

Definition of done:

- Agents operate under explicit governance and do not create hidden side effects.

---

## Group 59: Service Scraper and External Data Capture

Files:

- `backend/scraper/*.py`
- `backend/services/scraper/*.py`
- `backend/microservices/search_service/main.py`
- `backend/microservices/route_service/main.py`
- `backend/microservices/gateway/main.py`

Responsibility:

- Own scraping, search collection, and route/gateway microservice edges.
- Clarify which data comes from scraper pipelines versus direct provider APIs.
- Add anti-fragility, captcha handling, throttling, and legal/compliance notes.

Definition of done:

- External collection paths are explicit, resilient, and bounded.

---

## Group 60: Shared Libraries and Schemas

Files:

- `backend/shared/*.py`
- `backend/microservices/shared/*.py`
- `backend/microservices/shared/models/*.py`
- `backend/schemas/*.py`
- `backend/routers/booking_verification_router.py`

Responsibility:

- Own shared configs, logging, auth helpers, and schema contracts reused across services.
- Prevent schema drift between API, service, provider, and microservice layers.
- Make shared modules stable and dependency-light.

Definition of done:

- Shared contracts are canonical and reused consistently.

---

## Group 61: Tasks and Worker Execution

Files:

- `backend/tasks/*.py`
- `backend/workers/*.py`
- `backend/core/celery_app.py`
- `backend/core/service_discovery.py`
- `backend/core/resource_monitor.py`

Responsibility:

- Own async task execution, scheduled jobs, worker pools, and task health.
- Verify background task queues use durable semantics and real retry/backoff logic.
- Remove ad hoc worker behavior that bypasses standard orchestration.

Definition of done:

- Background execution is discoverable, retriable, and operationally safe.

---

## Group 62: Utility Layer

Files:

- `backend/utils/*.py`
- `backend/core/utils.py`
- `backend/core/performance.py`
- `backend/core/rate_limit.py`
- `backend/core/resilience.py`

Responsibility:

- Own general-purpose helpers, throttling primitives, resilience wrappers, and utility abstractions.
- Split true shared utilities from business logic hiding in helper modules.
- Remove duplicate implementations for logging, encryption, time, rate limiting, and response formatting.

Definition of done:

- Utility layer is coherent, minimal, and not a dumping ground.

---

## Group 63: Tests for API and Integration Contracts

Files:

- `backend/tests/test_*api*.py`
- `backend/tests/test_status*.py`
- `backend/tests/test_reviews.py`
- `backend/tests/test_chat_sessions.py`
- `backend/tests/integration/*.py`

Responsibility:

- Own API-facing test coverage and integration contract verification.
- Ensure tests use realistic fixtures and current response schemas.
- Promote the highest-value API tests to CI gates.

Definition of done:

- Public API contracts are covered by trustworthy automated tests.

---

## Group 64: Tests for Routing, Graph, and Search Correctness

Files:

- `backend/tests/test_route_*.py`
- `backend/tests/test_raptor*.py`
- `backend/tests/test_turbo_router.py`
- `backend/tests/test_station_*.py`
- `backend/tests/verify_search_v3.py`

Responsibility:

- Own route correctness, graph integrity, and search engine behavior tests.
- Align these tests with the actual canonical engine, not retired code paths.
- Add edge-case coverage for transfers, overlaps, timing, and deduplication.

Definition of done:

- Routing correctness tests protect the real engine in production use.

---

## Group 65: Tests for Payments, Booking, and Ledger Integrity

Files:

- `backend/tests/test_payment*.py`
- `backend/tests/verify_payment_pipeline.py`
- `backend/tests/verify_ledger*.py`
- `backend/tests/verify_commission_ledger.py`
- `backend/tests/booking_orchestrator.py`

Responsibility:

- Own the finance/booking integrity test wall.
- Cover payment replay, rollback, booking partial failure, and ledger consistency.
- Turn one-off verifiers into repeatable automated checks where possible.

Definition of done:

- Financial and booking invariants are protected by repeatable tests.

---

## Group 66: Tests for Resilience, Security, and Operations

Files:

- `backend/tests/test_resilience*.py`
- `backend/tests/verify_security.py`
- `backend/tests/verify_firewall.py`
- `backend/tests/verify_deployment_health.py`
- `backend/tests/stress_*.py`

Responsibility:

- Own resilience, security, deployment, and stress verification.
- Define which tests are smoke, which are pre-release, and which are chaos-only.
- Ensure these tests assert real protection behavior rather than log output.

Definition of done:

- Operational safety tests are categorized and runnable with clear expectations.

---

## Group 67: Tests for Task-Series Verification Packs

Files:

- `backend/tests/verify_task_*.py`
- `backend/tests/verify_mvp_task_*.py`
- `backend/tests/verify_32_*.py`
- `backend/tests/verify_todo11_staggering.py`
- `backend/tests/task_1_baseline_runner.py`

Responsibility:

- Own the large accumulated verification pack created during iterative development.
- Deduplicate overlapping tasks and map each test to a current subsystem owner.
- Archive tests that no longer match real architecture.

Definition of done:

- Task-series verification files are curated into a meaningful regression suite.

---

## Group 68: Tests for Chaos, Audit, and Performance

Files:

- `backend/tests/*audit*.py`
- `backend/tests/*chaos*.py`
- `backend/tests/*benchmark*.py`
- `backend/tests/*load*.py`
- `backend/tests/performance_density_audit.py`

Responsibility:

- Own non-functional verification for chaos, audit, load, and benchmark behavior.
- Decide which scenarios become scheduled validation jobs and which stay manual.
- Tie performance thresholds to target production expectations.

Definition of done:

- Non-functional tests are prioritized, measurable, and not just historical leftovers.

---

## Group 69: Docs, Runbooks, and Readiness Notes

Files:

- `backend/docs/*.md`
- `backend/PRODUCTION_VERIFICATION_*.md`
- `backend/VERIFICATION_*.md`
- `backend/TEST_ANALYSIS_REPORT.md`
- `backend/way.md`

Responsibility:

- Own internal backend docs, hardening plans, runbooks, and readiness notes.
- Reconcile docs with the actual architecture and retained services.
- Remove roadmap drift so contributors know what is real versus aspirational.

Definition of done:

- Documentation reflects the code we actually run and the sequence we actually follow.

---

## Group 70: Scratch, Experimental, and Triage Material

Files:

- `backend/scratch/*.py`
- `backend/issue.md`
- `backend/AiBrain.md`
- `backend/verify_telegram_logic.py`
- `backend/backend/*.json`

Responsibility:

- Own experimental files, ad hoc triage scripts, and temporary internal notes.
- Decide what should be promoted into real tests/tools and what should be archived.
- Prevent scratch logic from silently becoming production dependency.

Definition of done:

- Experimental work is either integrated cleanly or isolated clearly.

---

## Appendix A: Generated or Runtime Artifacts to Track, Not Hand-Own as Feature Groups

These files should be documented and validated, but usually not edited as source-of-truth product logic:

- Virtual environments and caches: `backend/.venv/**`, `backend/venv/**`, `backend/__pycache__/**`, `backend/.pytest_cache/**`
- Runtime logs and traces: `backend/*.txt`, `backend/*.log`, `backend/startup.err`, `backend/output.txt`, `backend/diag_output.txt`, `backend/profiler_out.txt`, `backend/tmp_db_trace.txt`
- Binary or local-only data stores: `backend/*.db`, `backend/*.mmap`
- Binary graph/index assets: `backend/data/**/*.bin`, `backend/data/**/*.npz`, `backend/data/**/*.pkl`
- Generated media output: `backend/media/tickets/*.pdf`

Rule:

- Do not assign feature implementation work directly to these artifacts.
- Instead, assign ownership to the group that generates or consumes them.

---

## Appendix B: Recommended Execution Order

If we want the cleanest path to impress your professor, work in this order:

1. Group 01-06: bootstrap, deployment, diagnostics, and audit truth.
2. Group 35-40: database, migrations, ETL, and generated asset provenance.
3. Group 41-47: providers, booking, payments, ledger, inventory.
4. Group 07-18: API cleanup after service contracts are stable.
5. Group 19-34: core routing, middleware, validation, nexus, ML.
6. Group 48-62: support services, agents, workers, utilities, shared schemas.
7. Group 63-70: convert verification sprawl into a reliable release gate.

---

## Appendix C: Standard Checklist for Every Group

For each group, complete this checklist:

- Confirm every file is still used.
- Identify mock paths, fake data, and TODO implementations.
- Trace all external dependencies.
- Verify request and response contracts.
- Add structured logging and metrics.
- Add timeout, retry, and circuit-breaker behavior where needed.
- Check transaction boundaries and idempotency.
- Add or repair automated tests.
- Run one happy path and one failure path end to end.
- Write a short closure note describing what became production-ready.
