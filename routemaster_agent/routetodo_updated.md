# RouteMaster backlog — actionable TODO (aligned to objective.md & recent work)

**Last update:** 2026-02-15 — reflects completed work (proxy auto-disable, Prometheus metrics, `/metrics` endpoint) and next priorities.

## Snapshot — current state
- Stable: NTES scrapers, Playwright manager, ProxyManager (auto-disable), selector-heuristic fallback, TestRunner with artifact capture.
- Observability: Prometheus metrics implemented and exposed at `/metrics`.
- Next goal: convert observability → action: dashboards, alerts, selector harness, and artifact persistence.

---

## Sprint priorities (ordered)
1. Grafana dashboards + alert rules — **P0** (in-progress)
2. Selector-testing harness (CSS/XPath generator + evaluator) — **P0** (next)
3. Selector adaptation engine & selector cache — **P1**
4. S3 artifact persistence for CI/nightly runs — **P1**
5. Dashboard UI for alerts/diffs & Grafana wiring — **P2**
6. Integration tests for metrics & alerts — **P2**

---

## Work items (actionable, with acceptance criteria)

### A. Grafana dashboards + Prometheus alert rules (P0)
- Why: make extraction reliability visible and alert on regressions.
- Deliverables:
  - `monitoring/grafana/dashboards/routemaster_observability.json` (panels: extraction latency p50/p95, extraction success rate, proxy health, RAPTOR runtime p50/p95, selector failure rate)
  - Provisioning: add to `monitoring/grafana/dashboards/route_master_dashboards.yml`.
  - Prometheus alert rules in `monitoring/prometheus/rules.yml` for:
    - Extraction success rate < 95% (5–10m window)
    - Proxy disabled fraction > 50% (5m)
    - RAPTOR p95 runtime > 200ms (5m)
- Acceptance criteria:
  - Dashboard loads in local compose/dev environment and panels show metrics from `/metrics`.
  - Alerts appear in Prometheus Alertmanager when simulated (or metric thresholds exceeded).
  - PR includes JSON dashboard + unit test/validation steps in README.
- Estimate: 2–3 days

### B. Selector-testing harness (CSS / XPath generator + evaluator) (P0)
- Purpose: automatically generate & evaluate alternate selectors, pick the most robust, and persist into `selector_cache.json`.
- Files to add:
  - `routemaster_agent/scrapers/selector_generator.py` (candidate generation)
  - `routemaster_agent/scrapers/selector_tester.py` (evaluation harness)
  - `routemaster_agent/scrapers/selector_cache.json` (runtime store)
- Integration: NTESAgent fallback uses harness when primary selector fails; successful candidate replaces cached selector and increments selector stability metric.
- Acceptance: harness returns ranked selectors and reduces retries for flaky selectors by ≥30% on test set.
- Estimate: 3–4 days

### C. Selector adaptation engine (learning & cache) (P1)
- Persist selector successes/failures, re-test cached selectors nightly, expose selector_stability_score metric.
- Acceptance: weekly health report shows selector stability improving for sampled trains.
- Estimate: 2 weeks (incl. tests)

### D. S3 artifact persistence (CI & nightly) (P1)
- Add S3 upload in TestRunner; wire CI nightly workflow to upload `test_output/` artifacts and publish manifest link.
- Env vars: `RMA_S3_BUCKET`, standard `AWS_` credentials.
- Acceptance: artifacts reachable from S3 with stable URLs included in nightly test summary alert.
- Estimate: 2–3 days

### E. Dashboard UI for alerts/diffs (P2)
- Small Grafana panels + optional micro-UI linking to artifacts and DB alert entries.
- Acceptance: clickable link from dashboard to artifact URLs and raw diff JSON.
- Estimate: 4–6 days

### F. Integration & CI tests for metrics/alerts (P2)
- Validate `rules.yml` contains expected alert expressions; add smoke tests for `/metrics` and dashboard provisioning files.
- Acceptance: CI validates alert rule presence and `/metrics` returns Prometheus content.
- Estimate: 2 days

---

## Immediate next actions (what I'll do next)
- Add Prometheus alert rules for: extraction success <95%, proxy disabled fraction >50%, RAPTOR p95 >200ms — small, testable change. (DONE)
- Create Grafana dashboard JSON skeleton and wire provisioning entry. (next)
- After dashboards/alerts are in, begin the `selector-testing harness` implementation.

---

## Notes / constraints
- Keep metrics labels low-cardinality; use `train_number` only where necessary.
- Persist selectors/artifacts with TTL and retention policy for cost control.

---

## Decision points for you
- Approve S3 bucket name/policy for artifact persistence or I will implement with `RMA_S3_BUCKET` env var stub.
- Confirm alerting severity/paging rules (default: `critical` for extraction success/proxy-health).

---

If this looks good I will (A) add the Grafana dashboard JSON next and then (B) implement the selector-testing harness. Want me to start building the Grafana dashboard now?