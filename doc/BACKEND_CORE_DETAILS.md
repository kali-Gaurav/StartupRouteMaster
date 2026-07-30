# Backend/Core Folder Detailed Documentation

This document captures the complete ideas, architecture and implementation details for every file and submodule under `backend/core`.
It is intended as a standalone reference covering the server‑side core logic of the project.

---

## 📁 Directory Overview

`backend/core` contains the shared engines, utilities, validation framework and support code used by the backend services.  Key responsibilities include route computation, caching, live updates, validation, feature detection, and common helpers.

Core packages and files:

- `base_engine.py`          – engine blueprint and feature detector
- `data_structures.py`     – shared enums and dataclasses
- `route_engine.py`        – main RAPTOR routing engine (plus subpackage `route_engine/`)
- `segment_detail.py`      – journey segment data structures
- `utils.py`               – utility classes (cache keys, occupancy, error handling)
- `realtime_event_processor.py` – real‑time event handling
- `validator/`             – modular validation framework + individual validator modules
- Other supporting modules (metrics, ML integration, etc.) referenced by core but not detailed here.


---

## 🧩 Core Files and Concepts

### `base_engine.py`

**Blueprint for all backend engines.**

- **EngineStatus** enum: `INITIALIZING`, `READY`, `DEGRADED`, `UNAVAILABLE`.
- **FeatureDetector** class: performs capability checks (API availability, config flags, network connectivity). Results stored in `features` map.
  - `detect_feature(name, check_fn)`: runs check fn and logs result.
  - `get_mode()` returns `EngineMode.OFFLINE|HYBRID|ONLINE` based on ratio of available features.
  - `get_status()` returns detailed report.
- **BaseEngine** abstract class (inherits ABC): manages engine lifecycle.
  - Attributes: `engine_name`, `engine_type`, `status`, `mode`, `feature_detector`, `metrics`, `config`.
  - `startup()` orchestrates feature detection, post‑startup hook, sets status to READY.
  - `shutdown()` placeholder for cleanup.
  - Engine subclasses override `detect_available_features()` and `_post_startup()`.

This class centralises logging, health checks, metrics collector, and feature gating for engines such as routing, pricing, inventory, cache, etc.


### `data_structures.py`

Defines shared enums and dataclasses used across engines.  For example:

- `EngineMode` enum (OFFLINE/HYBRID/ONLINE) used by `FeatureDetector`.
- Any other simple data types reused in different modules.


### `route_engine.py` (root file + subpackage)

**High‑performance multi-transfer route engine** implementing the RAPTOR algorithm with extensive optimizations.

Key features and ideas:

- **Dataclasses**:
  - `SpaceTimeNode`: node in time‑dependent graph (stop, timestamp, arrival/departure).
  - `RouteSegment`: single train journey leg (trip id, stations, times, duration, distance, fare, etc.) with helpers and backward‑compat conversion.
  - `TransferConnection`: transfer info between trains including duration, station scores, platforms.
  - `Route`: entire route composed of segments and transfers; computes totals and provides helpers like `get_all_stations()`.
  - `RouteConstraints`: search constraints and weights (max journey time, transfers, reliability weighting, range‑RAPTOR, safety options).

- The file itself contains ~2 400 lines of code implementing:
  - Pre‑computed route patterns, time‑dependent graph infrastructure, and transfer graphs.
  - Algorithms for scanning departure windows (range‑RAPTOR), frequency‑aware sizer, and reliability injection.
  - Real‑time delay injection via overlay structures.
  - Caching layers (`multi_layer_cache`), parallel query execution using `ThreadPoolExecutor`, and result ranking with ML models.
  - Utilities for geographic fallback (haversine distance) and SQLAlchemy database interactions.
  - Integration with `ValidationManager` and `PerformanceValidator` to enforce correctness.

- `route_engine/` subpackage hosts modular helpers, validators, and smaller components referenced by the main engine (details not expanded here but they support the complex algorithm). 

This engine targets latencies <5 ms for typical queries and high throughput – it is production‑grade with multi‑objective scoring and personalization hooks.


### `segment_detail.py`

Defines portable journey segment structures used by higher layers and external APIs.

- `SegmentDetail`: all metadata about a journey leg (stations, times, platforms, availability, fares) with `to_dict()`.
- `JourneyOption`: wraps multiple `SegmentDetail` instances to represent a complete itinerary, plus totals and flags.

These classes unify data representation across routes, pricing, and availability engines.


### `utils.py`

General-purpose helpers used throughout backend/core:

- **CacheKeyGenerator**
  - Creates consistent keys for caching route queries, availability, occupancy, ML features.
  - Methods: `generate_key`, `route_query_key`, `availability_key`, `occupancy_key`, `ml_features_key` which build composite strings hashed for compactness.

- **OccupancyCalculator**
  - Functions to compute occupancy rate, available seats, human-readable occupancy level, and suggested price multiplier for dynamic pricing.

- **error_handler decorator**\n  - Wraps functions to catch exceptions, log them at a configurable level, and return a `default_return` value.

Utilities centralise recurrent patterns and avoid duplication across engines.


### `realtime_event_processor.py`

Provides a simple event‑driven engine for processing real‑time updates (delays, cancellations).  Key ideas:

- **RealtimeEventProcessor** class
  - Initialized with a `RailwayRouteEngine` instance and DB session factory.
  - `process_events()` fetches all events, translates them into overlay updates and TrainState records, deletes processed events, and commits.
  - Updates engine overlay via `engine.apply_realtime_updates()` and persists to `TrainState` table.
  - Supports delay and cancellation logic with status updates and platform numbers.

This module simulates a streaming update pipeline and is part of Phase‑5 real-time engine in project docs.


### `validator/` subpackage

Modular, extensible validation framework used by engines to verify data integrity, performance, security, and other concerns.

#### `validation_manager.py` (core of the system)

- Defines enums `ValidationProfile` (QUICK, STANDARD, FULL, CUSTOM) and `ValidationCategory` (e.g., ROUTE_LOGIC, REAL_TIME, API_SECURITY, ...).
- Dataclasses `ValidationResult` and `ValidationReport` capture individual and aggregated outcomes.
- `ValidatorRegistry` holds registrations for categories and instances; pre‑defines profile‑to‑category mappings.
- `ValidationManager` orchestrates execution:
  - `register_all_validators()` populates the registry.
  - `validate(config, profile, specific_categories)` runs all `validate_*` methods on relevant validators based on the supplied config and profile, producing a report with success rate and durations.
  - Reports track history and allow filtering by profile or explicit categories.

The design emphasises decoupling validators from the routing engine, easy extension, and configurable validation runs.

#### Individual validator modules

Each file under `validator/` implements validations for a particular area. Some examples (not exhaustive):

- `route_validators.py` – checks route logic (transfer times, impossible connections). 
- `resilience_validators.py` – chaos and failure recovery tests. 
- `production_validators.py` – readiness checks like configuration sanity, resource limits. 
- `performance_validators.py` – latency/bandwidth thresholds. 
- `data_integrity_validators.py` – ensures database consistency. 
- `fare_availability_validators.py` – verifies pricing and availability rules. 
- `api_security_validators.py` – validates rate limits, authentication. 
- `ai_ranking_validators.py` – ensures ML ranking behaves correctly. 
- `live_validators.py` – real‑time data correctness. 
- `multimodal_validators.py` – checks handling of different transport modes.

Each validator exposes methods like `validate_<check>()` which return `ValidationResult` objects.

Together these components provide a structured, profile‑driven validation pipeline that can be run during testing, deployment, or at runtime to maintain engine health.


### Other supporting modules (briefly)

- `metrics.py` – metrics collectors used by engines.
- `ml_integration.py` and `ml_ranking_model.py` – glue for machine‑learning models integrated into the routing/pricing logic.
- `engines/` and `managers/` directories contain additional backend infrastructure used by the core engines.


---

### ✅ Summary

The `backend/core` folder encapsulates the heart of the server-side logic:

- A robust engine blueprint (`BaseEngine`) with feature detection and lifecycle management.
- A feature-rich RAPTOR-based route engine capable of real-time updates and ML ranking.
- Shared data structures and utility helpers for caching, occupancy and error handling.
- A realtime event processor for delay/cancellation streams.
- A comprehensive, modular validation architecture covering logic, performance, security and production readiness.

This documentation can be used for onboarding backend developers, understanding architectural choices, or as part of formal project documentation.

Let me know if you'd like this file linked in other documentation or exported to other formats.