I will replace the entire content with a full, polished objective document.

---

# Objective — routemaster_agent

Version: 1.0
Date: 2026-02-15

Overview
========

routemaster_agent is an autonomous, production-grade Railway Intelligence Engine: an AI-driven, self-testing data-collection and validation service that extracts train schedules, live running status, and seat/fare availability from web sources (NTES, IRCTC/AskDisha and similar). It produces clean, validated, and versioned records (JSON/CSV and Postgres upserts), captures forensic artifacts (HTML, screenshots, logs), and continuously improves extraction reliability and speed through telemetry and learning.

Purpose and Vision
==================

The purpose of routemaster_agent is to provide RouteMaster with high‑confidence, real‑time railway data so downstream systems (route generation, ETA correction, seat recommendation, pricing analytics) can operate with low latency and high accuracy. The long‑term vision is an autonomous agentic pipeline that performs web navigation, data discovery, extraction, validation and remediation at least 100× faster and more reliably than manual human processes, while producing full traceability for every record.

Core Capabilities (high level)
=============================

- Autonomous website navigation and data discovery (Playwright-driven browser automation with human-like interactions).
- Server-side HTTP/HTML fallbacks (requests + BeautifulSoup) for robustness when browser flows fail.
- Proxy and User‑Agent rotation to minimize blocks and detection.
- Data cleaning, normalization, and schema mapping to a Postgres-compatible data model.
- Change detection and versioned diffs to capture schedule evolution over time.
- Seat/fare verification via secondary sources (AskDisha chatbot / IRCTC flows) to enrich confidence.
- Self-testing TestRunner with artifact capture, retries, headful fallback, and persisted alerts.
- Observability (metrics, logs, persisted alerting) and CI-driven nightly QA runs.

System Objectives — concrete
==========================

1. Intelligent Website Navigation
--------------------------------

The agent must autonomously reach the right page and element to extract data. It should:

- Discover the appropriate entry point (Train Schedule, Spot Your Train, booking chatbot) automatically.
- Perform human-like interactions: randomized typing, hover/scroll, sensible delays.
- Handle dynamic content (wait-for network/DOM signals, incremental loading, infinite lists).
- Detect UI drift and attempt recovery (alternate selectors, semantic search in DOM, server-side fallback).

2. Schedule Extraction
----------------------

From schedule pages extract and normalize:

- Train-level metadata: train_number, train_name, source, destination, type, days_of_run, total_travel_time.
- Per-station rows: sequence, station_name, station_code, day_number, arrival_time, departure_time, halt_minutes, distance_km, platform (if provided).

Validation rules:

- No missing stations, sequences continuous, arrival/departure times sensible, first station distance=0, final departure null.

3. Live Status Extraction
-------------------------

From Spot Your Train / live pages extract:

- current_position, last_arrived_station, last_arrival_time, last_departure_time, running_status, delay_minutes, next_station, eta_next, percent_route_complete, last_updated_ts.

Detect and flag cancellations, partial journeys, diverted routes.

4. Seat Availability & Fare Verification
-----------------------------------------

Automate AskDisha/IRCTC chatbot flows and booking pages to extract:

- Per-class availability (AVAILABLE, RAC, WL), quota, fares, dynamic pricing info, and check timestamps.
- Parse multi‑class/multi‑quota responses and ambiguous chatbot replies.

5. Data Structuring & Storage
----------------------------

All outputs must conform to canonical schema and be storable as:

- JSON payloads for record interchange.
- CSV exports for analytics pipelines.
- Postgres tables: trains_master, train_stations, train_live_status, seat_availability, schedule_change_log, rma_alerts.

6. Data Cleaning & Validation
-----------------------------

The pipeline must:

- Normalize station names and codes, time formats (24h), numeric fields.
- Remove duplicates and inconsistent rows.
- Validate against heuristics and previous DB snapshot; run parity checks (JSON vs CSV vs DB counts).
- On validation failures: capture artifacts, retry extraction with alternate strategies, persist alert.

7. Change Detection & Lineage
----------------------------

- Compare new extracts with the latest persisted snapshot.
- Record diffs: added/removed/changed stations, time shifts, day-of-run changes.
- Persist schedule_change_log entries with full diff and artifacts for audit.

8. Self‑Healing & Robustness
----------------------------

When failures occur (selector misses, partial pages, bot detection):

- Retry with backoff up to MAX_ATTEMPTS.
- Reset browser context, switch to headful with slow_mo, rotate UA and proxy, or use server-side HTML fallback.
- Capture screenshots, full DOM, network logs where possible.
- Persist alerts to DB and optionally external channels (Slack) for ops.

9. Testing, Metrics & Observability
----------------------------------

The TestRunner must run scheduled test suites (nightly or on-demand) that:

- Validate a representative set of trains across zones and classes.
- Produce reliability metrics, selector failure rates, end‑to‑end extraction time distributions.
- Store artifacts in `test_output/YYYYMMDD/<train>` and log structured metrics to `logs/`.

10. Performance & Scale
-----------------------

Initial targets:

- Concurrency: handle batches of 20+ trains with configurable concurrency (default 5).
- Latency: aim for median extraction time < 5s (where possible); provide headful fallback for difficult pages.
- Resilience: minimize silent failures; require explicit alerting for recurring selector spikes.

11. Intelligence, Learning & Adaptation
--------------------------------------

Long-term objectives to make the agent self‑improving:

- Selector adaptation: automatically generate and test alternate selectors when primary fails.
- Semantic extraction: apply heuristic/ML-based parsing to derive fields from noisy HTML (e.g., tableless pages).
- Policy learning: use reinforcement learning or bandit methods to prefer faster, more stable navigation strategies.
- Template inference: cluster page layouts and reuse extraction templates across similar pages.

12. Security, Compliance & Ethics
--------------------------------

- Respect site terms of service and robots policies; rate-limit and backoff to avoid abuse.
- Secure secrets (proxies, DB credentials) in env/config and do not log sensitive data.
- Retain only necessary PII and follow local regulations for user data if any.

13. Operational & Deployment Objectives
--------------------------------------

- Dockerized service with docker-compose for local dev and a production image for deployment.
- CI workflow to run nightly validation tests and upload artifacts.
- Prometheus-compatible metrics, structured logs, and a small dashboard to view alerts and diffs.

14. KPIs and Success Criteria
----------------------------

- Extraction accuracy: > 99% station-level correctness across sampled runs.
- Freshness: data latency < 2 minutes for live-status where feasible.
- Reliability: selector failure rate < 1% and recovery within MAX_ATTEMPTS.
- Throughput: process 1,000 train queries per hour (scale via workers).

Roadmap (next 3 quarters)
=========================

Q1 — Stabilize & Harden
- Finalize schemas, add extension checks (pg_trgm), tighten TestRunner, add archived artifact storage.

Q2 — Intelligence Layer
- Implement selector-adaptation heuristics, basic semantic fallbacks, proxy-health monitoring.

Q3 — Learning & Scale
- Introduce policy learning for navigation, template clustering, S3 artifact persistence, and dashboard.

Appendix — Example JSON Schema (high level)
===========================================

{
  "train_number": "12345",
  "train_name": "EXP SAMPLE",
  "schedule": [{"sequence":1,"station_code":"SRC","arrival":null,"departure":"06:00"}, ...],
  "live_status": {"current_station":"MID","delay_minutes":5,"next_station":"DST"},
  "seat_availability": [{"class":"3A","availability":"AVAILABLE-10","fare":1234.0}],
  "metadata": {"extracted_at":"2026-02-15T12:00:00Z","source":"ntes"}
}

---

This document is intended to be the authoritative objective for `routemaster_agent`. If you want, I can also:

- Produce a one-page investor/exec summary.
- Create a concise README section integrating this objective directly into `routemaster_agent/README.md`.
- Generate a task backlog from the roadmap items and wire them into the repo's `todo.md`.


next_station

expected_arrival_next

route_progress_percent

last_updated_timestamp

Must:

Detect cancellation

Detect partial journey

Detect special running conditions

4️⃣ Seat Availability & Fare Intelligence (AskDisha / IRCTC)

From IRCTC:

Automate:

Open booking page

Trigger AskDisha chatbot

Send query:
"seat availability for train 12345 from NDLS to CNB on 15/02/2026"

Parse chatbot response

Extract:

Class

Available seats

WL status

Fare

RAC

Dynamic pricing

Must handle:

Multiple classes

Flexible date

Chatbot delayed response

UI changes

5️⃣ Intelligent Data Structuring Objective

All extracted data must be structured into:

JSON
{
  "train_number": "",
  "schedule": {},
  "live_status": {},
  "seat_availability": {}
}

CSV

Schedule CSV

Live CSV

Availability CSV

Database (Postgres)

trains_master

train_stations

train_live_status

seat_availability

change_log

6️⃣ Data Cleaning & Validation Objective

The system must:

Normalize station names

Convert times to 24h

Remove duplicate rows

Validate arrival/departure

Check missing values

Ensure numeric fields valid

Compare with previous DB snapshot

Detect schedule change

If inconsistency detected:

Retry extraction

Save artifact

Mark train for review

7️⃣ Self-Healing & Retry Objective

If:

Selector fails

Page partially loads

Bot detection triggered

Unexpected HTML structure

System must:

Retry up to MAX_ATTEMPTS

Reset browser context

Rotate user-agent

Switch proxy

Log detailed error

Capture screenshot + HTML

No silent failures allowed.

8️⃣ Change Detection Objective

Every time schedule extracted:

Compare with previous version:

Station added?

Time changed?

Distance modified?

Running days changed?

If change detected:

Record diff

Update DB

Log change event

Notify monitoring layer

9️⃣ Testing & QA Objective

Testing mode must:

Run multiple train tests

Validate 100% station coverage

Compare JSON vs CSV

Compare DB row count

Save metrics

Store artifacts

Provide reliability score

🔟 Performance Objective

System must:

Handle batch of 20+ trains

Concurrency = 5

Extraction < 5 seconds per train

Cache results (6h TTL)

Avoid rate limit detection

🧠 Intelligence & Learning Objective

The long-term objective is to build a semi-autonomous learning agent.

Future capabilities:

1️⃣ Selector Adaptation

Detect when CSS selector fails

Use alternative DOM search strategies

Fall back to semantic search in HTML

2️⃣ Pattern Recognition

Learn typical schedule structure

Identify abnormal schedule patterns

Detect anomalies

3️⃣ Speed Optimization

Learn fastest DOM path

Cache common train data

Predict page layout changes

4️⃣ Reinforcement Learning Layer (Future)

Reward successful extraction

Penalize selector failure

Optimize navigation strategy

🏆 Strategic Objective for RouteMaster

routemaster_agent becomes the intelligence layer powering:

Route generation

Delay-aware route scoring

Real-time ETA correction

Seat availability ranking

Multi-train route chaining

Confidence-based route ranking

Without this agent:
RouteMaster is static.

With this agent:
RouteMaster becomes dynamic, adaptive, and real-time.

📦 Production Objectives

Modular scrapers

Proxy-ready

UA rotation

Dockerized

API accessible

CI-tested

Nightly QA runs

Observability metrics

Failure artifact storage

Structured logging

Configurable concurrency

🔥 Ultimate Objective

Build an autonomous railway intelligence agent that:

Thinks like a human user

Acts faster than a human

Extracts cleaner data than a human

Validates more strictly than a human

Learns from mistakes

Improves reliability over time

🎯 Final Primary Goals

Maximize data accuracy

Maximize freshness

Minimize silent failures

Provide full traceability

Enable real-time route intelligence

Scale to all trains

Be production-grade and self-evolving