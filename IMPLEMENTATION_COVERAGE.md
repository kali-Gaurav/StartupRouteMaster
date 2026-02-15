# Implementation coverage vs Advanced Railway Intelligence Engine Design

This document maps the design ideas from `Advanced_Railway_Intelligence_Engine_Design.md` to what is actually implemented (or partially implemented) in this repository's backend, and lists work completed during the current audit session.

> Note: file paths refer to the repository root in this workspace. "Implemented" below means there is code and/or configuration in the repo; "Partial" means scaffolding or MVP exists but production-grade capabilities are missing; "Not implemented" means no meaningful implementation found.

## High-level summary

- Architecture paradigm: Microservices + event-driven (design). Repo: present (multiple service folders, `docker-compose.yml`, `k8s/`) — PARTIAL (scaffolding and many services present).
- Route search engine: RAPTOR-based engine is implemented and actively tested — IMPLEMENTED (backend/services/route_engine.py).
- Data-store: Postgres/PostGIS referenced in config and k8s/docker-compose; some parts still use or reference SQLite/legacy — PARTIAL.
- Streaming: Kafka is present/used in compose, k8s and scraper service — PARTIAL (Kafka present but production tuning and multi-broker HA not fully implemented).
- Reinforcement learning service: `rl_service` exists and is referenced in manifests and deploy scripts — PARTIAL (service skeleton and TF build steps exist; full ML pipeline unclear).
- ETL/scrapers: scraper_service and ETL scripts exist — PARTIAL (scrapers & ETL present; orchestration (Airflow/Spark) not present).

## Detailed mapping (design item → repo status)

### 1) API Gateway, Microservices, and Orchestration

- Design: API gateway (Envoy/Nginx), stateless microservices, k8s manifests, CI/CD
- Repo evidence:
  - `docker-compose.yml` and `docker-compose.dev.yml` include services and PostGIS/Kafka (dev orchestration).
  - `k8s/` contains Kubernetes manifests for Postgres, Kafka, rl-service, route-service, etc.
  - Service folders: `backend/`, `scraper_service/`, `rl_service/`, `route_service/` (scaffolds).
- Status: PARTIAL — orchestration manifests and Dockerfiles present. Production-grade gateway, comprehensive CI/CD pipelines, ingress/routing hardening, and advanced autoscaling policies are not fully implemented.

Relevant files:
- `docker-compose.yml`, `docker-compose.dev.yml`
- `k8s/*.yaml`
- `backend/`, `scraper_service/`, `rl_service/` directories

### 2) Route Search (RAPTOR, A*, MCSP)

- Design: RAPTOR as primary multi-modal routing algorithm, Pareto optimization, per-stop indices, binary-search boarding, support for day offsets and transfers.
- Repo evidence & status:
  - `backend/services/route_engine.py` — RAPTOR MVP implemented with per-route indices, binary-search boarding, Pareto pruning, day-offset handling. Recent hardening and test fixes applied in this session (deterministic label keys, departure normalization, metrics instrumentation).
  - Unit tests added: `backend/tests/test_raptor_engine.py`, `backend/tests/test_raptor_transfers.py` to verify single-leg, Pareto, transfer-window and overnight behavior — IMPLEMENTED (core algorithm and tests).
  - Benchmark script `scripts/raptor_benchmark.py` exists and was extended to gather runtime and metric summaries — IMPLEMENTED (benchmarking harness added).
- Remaining gaps: advanced MCSP variants (Yen, k-shortest), A* heuristic integration and large-scale performance tuning (pruning, label limits) need further work for production scale — PARTIAL.

Files changed/created in session:
- `backend/services/route_engine.py` — deterministic label keys, departure normalization, metrics counters, disabled pubsub by default for tests.
- `backend/tests/test_raptor_engine.py`, `backend/tests/test_raptor_transfers.py` — new tests.
- `scripts/raptor_benchmark.py` — metrics collection and JSON output.

### 3) Database & Spatial (Postgres/PostGIS)

- Design: PostgreSQL + PostGIS for stations, GIST indexes, spatial queries.
- Repo evidence & status:
  - `docker-compose.yml` and `k8s/postgres.yaml` reference `postgis/postgis:15-3.3` and migration SQL `migration.postgres.sql` exists — PARTIAL (infra scaffold present).
  - Some code and docs reference `routemaster.db` (SQLite) and migration helpers (ETL scripts) — indicates migration path exists but full migration & read-replicas/sharding not completed — PARTIAL.

Files of interest:
- `migration.postgres.sql`, `k8s/postgres.yaml`, `docker-compose.yml`
- `routemaster_agent/database/models.py` (SQLAlchemy models) — used for test/ETL scaffolding.

### 4) Streaming / ETL / Scrapers

- Design: Kafka-based data ingestion (scrapers → Kafka → ETL → Postgres), orchestration (Airflow), feature pipelines.
- Repo evidence & status:
  - `scraper_service/` contains a Kafka-capable scraper skeleton and `requirements.txt` includes `confluent-kafka` — PARTIAL.
  - `scripts/etl_*` and `backend/etl/` exist as ETL scaffolding (sqlite_to_postgres, loaders) — PARTIAL.
  - No Airflow/DAGs or Spark/Flink jobs found — NOT IMPLEMENTED (or outside repo).

Files of interest:
- `scraper_service/*`, `backend/etl/`, `scripts/sqlite_to_postgres.py` (ETL helpers)

### 5) Reinforcement Learning & ML

- Design: RL ranking service, feature store (Feast), model registry, offline/online training, A/B testing.
- Repo evidence & status:
  - `rl_service/` exists and is referenced in `docker-compose` and `k8s` manifests; deploy script mentions TensorFlow build — PARTIAL.
  - No evidence of a production feature store (Feast), model registry, or distributed training pipelines in repo — NOT IMPLEMENTED (major ML infra missing).

Files of interest:
- `backend/rl_service` (scaffold), deploy scripts in `scripts/deployment` reference RL image build.

### 6) Observability, Monitoring & Security

- Design: Prometheus, Grafana, Jaeger, centralized logging, WAF, OAuth, SIEM.
- Repo evidence & status:
  - `monitoring/` includes Prometheus config snippets and `prometheus.yml` — PARTIAL.
  - `k8s/` manifests exist but end-to-end observability pipelines and security hardening are not fully implemented — PARTIAL/NOT IMPLEMENTED for production-grade security.

Files of interest:
- `monitoring/prometheus/*`, `k8s/*` manifests

### 7) Operational features (sharding, Tatkal queue, concurrency controls)

- Design: DB sharding, high-throughput queue, distributed locks, Saga pattern for bookings, optimistic/pessimistic locking.
- Repo evidence & status:
  - No complete sharding implementation found; booking and seat-inventory tables exist in various backends but distributed patterns are not present — NOT IMPLEMENTED / PARTIAL at best.


## Actions completed during this session (explicit changes made)

- Stabilized RAPTOR implementation:
  - Replaced Python hash() dependent label keys with deterministic string keys for labels in `backend/services/route_engine.py`.
  - Fixed departure minute normalization using `departure_day_offset`/`arrival_day_offset` to correctly support overnight departures.
  - Ensured per-route departure lists are sorted for deterministic binary-search boarding.
  - Disabled automatic Redis Pub/Sub listener startup by default (tests/dev) unless `ROUTEENGINE_ENABLE_PUBSUB=1` is set.
  - Added lightweight per-search instrumentation counters (`_last_metrics`) to help benchmark and find hotspots.

- Tests & benchmarks added:
  - Tests: `backend/tests/test_raptor_engine.py`, `backend/tests/test_raptor_transfers.py` (cover direct routes, Pareto, transfer windows, day-offsets).
  - Benchmark: `scripts/raptor_benchmark.py` extended to capture and print aggregated metrics (labels generated, binary-search calls, rounds processed, etc.).

- Ran benchmark (example): `python scripts/raptor_benchmark.py --stations 200 --route-length 4 --queries 200`
  - Output (example): JSON summary containing median/avg/max runtimes and metric aggregates.

## Remaining high-priority gaps (to reach production-grade as per design)

1. Full ML infra: Feature Store, model registry, automated training pipelines, A/B testing harness, online inference scaling — NOT IMPLEMENTED.
2. Production-grade streaming: multi-broker Kafka with replication, connector configs, consumer group tuning, schema registry — PARTIAL.
3. Database scale-out: partitioning/sharding, read-replicas, strong seat-inventory concurrency patterns for Tatkal rush — NOT IMPLEMENTED.
4. Observability & security: end-to-end tracing, alerting playbooks, WAF and SIEM integration, OAuth/OIDC flows — PARTIAL/NOT IMPLEMENTED.
5. Advanced routing algorithms & optimizations: A* heuristics, bidirectional search, MCSP for richer Pareto/frontier control (scalability pruning rules) — PARTIAL.
6. Orchestration & runbooks: production deployment manifests, chaos testing, DR runbooks — PARTIAL/NOT IMPLEMENTED.

## Suggested next steps (actionable)

1. Run extended benchmark (dense networks and higher MAX_TRANSFERS) to expose label explosion and round growth. If labels per stop grow consistently > 20, implement label cap pruning.
2. Implement stronger dominance pruning and optional cap on labels per stop per round (configurable).
3. Add memory/time-per-round instrumentation and histogram of labels-per-stop in the benchmark.
4. Prioritize a Postgres/PostGIS migration plan: full schema migrations, GIST indexes, and ETL automation.
5. Define ML infra requirements (Feast, MLFlow, Seldon/KServe) and scaffold minimal components for online inference.

----

If you want, I can run an extended benchmark now (suggested: stations=2000, route-length=8, queries=1000, MAX_TRANSFERS=3), or start implementing the label-pruning changes described above.
