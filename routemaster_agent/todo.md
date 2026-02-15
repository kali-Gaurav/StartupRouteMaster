# routemaster_agent Backlog (generated from objective)

## Q1 — Stabilize & Harden
- [ ] Finalize DB schemas and add Alembic migrations
- [x] Add extension checks (pg_trgm) in DB init (done)
- [x] Tighten TestRunner and artifact capture (done)
- [x] Add archived artifact storage (done)

## Q2 — Intelligence Layer
- [ ] Implement selector-adaptation heuristics (basic heuristics implemented)
- [ ] Add proxy-health monitoring background job (basic monitor implemented)
- [ ] Add proxy pool health dashboard and metrics
- [ ] Implement semantic extraction fallbacks (ML/heuristics)

## Q3 — Learning & Scale
- [ ] Introduce policy learning for navigation
- [ ] Template clustering and selector reuse
- [ ] S3 artifact persistence and lifecycle management
- [ ] Build a dashboard for alerts/diffs and operational metrics

## Technical tasks
- [ ] Improve TestRunner concurrency and performance
- [ ] Add unit/integration tests for monitor and selector adapt modules
- [ ] Add CI job to persist nightly artifacts to S3
- [ ] Harden proxy rotation and pool management (auto disable unhealthy proxies)
- [ ] Add Prometheus metrics endpoints and instrument critical operations

## Ops
- [ ] Configure secrets: RMA_SLACK_WEBHOOK_URL, RMA_DATABASE_URL
- [ ] Set up nightly GitHub Action secrets and artifact storage


*Generated from `routemaster_agent/objective.md`.*
