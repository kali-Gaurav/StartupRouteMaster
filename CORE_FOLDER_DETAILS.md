# Core Folder Detailed Documentation

This document describes the complete ideas and implementations of each file in the `core` packages of the repository. The workspace contains two separate core areas:

- `routemaster_agent/core` – autonomous UI agent components
- `backend/core` – backend engines and utilities

## 🧠 `routemaster_agent/core`

### `__init__.py`
- Empty file marking it as a Python package.

### `navigator_ai.py`

A smart, adaptive element locator and navigator for Playwright pages. Key ideas:

- **NavigatorAI class** encapsulates logic to find and interact with UI elements without hard‑coded selectors.
- Strategies for element location:
  1. **Registry lookup**: consults `selector_registry` for primary and backup selectors when a `page_type` is provided, recording successes/failures for learning.
  2. **DOM label association**: searches `<label>` elements and associated inputs by `for` attribute or sibling relationships.
  3. **Visual detection**: uses a `GeminiClient` to analyse a screenshot and detect form fields with matching labels; clicks coordinates or `data-testid` if available.
  4. **Semantic DOM search**: examines placeholder, `aria-label`, `name`, and other attributes in inputs to match the requested label.
  5. **Fallback heuristics**: includes generic selectors, mapping of known patterns, etc.
- Caches `navigation_memory` successes and tracks `failed_attempts` for adaptive behaviour.
- Logs extensively and records selector outcomes for retraining.

### `extractor_ai.py`

Handles multi‑strategy data extraction from pages with confidence scoring.

- **ExtractionAI class** with fields:
  - `gemini`: for reasoning-based extraction.
  - `vision`: a `VisionAI` instance for OCR and layout analysis.
  - `extraction_cache` and `field_strategies` to remember what worked best.
- Methods:
  - `extract_with_confidence(page, schema)`: given a mapping of field names to expected types, tries strategies in order: CSS selectors, semantic DOM search, visual/OCR, Gemini reasoning; aggregates results, sorts by confidence, validates values, and returns detailed info including alternatives and validation status.
  - `extract_structured_data(page, structure_hint)`: asks Gemini to infer a JSON schema from screenshot+HTML, then extracts using the above method.
- Provides caching and logging of extraction steps.

### `decision_engine.py`

Autonomous decision-making about data validity and storage.

- **DecisionEngine class** with optional Gemini client for complex verdicts.
- `decide_data_validity(extracted_data, data_type)`: examines extraction results for missing fields, low confidence, validation failures, and returns a recommendation (STORE/REVIEW/DISCARD/INVESTIGATE) along with issues and confidence score.
- `decide_storage_action(extracted_data, existing_data)`: compares new and existing records, determines if the record is new, duplicate, update, or a conflict alert by calculating change significance and detecting suspicious changes.
- Internal helpers (`_compare_data`, `_calculate_change_significance`, `_has_suspicious_changes`) manage the comparisons.

### `vision_ai.py`

Visual analysis of page screenshots using Gemini vision API.

- **VisionAI class** with cache for detected layouts.
- `analyze_page_structure(page)`: returns tables, forms, buttons, text regions, layout type and confidence by sending screenshot to Gemini or falling back to HTML analysis.
- `detect_table_structure(page, hint)`: inspects HTML `<table>` elements or uses visual detection for non-HTML tables, returning headers, rows, column info, pagination hints, etc.
- `locate_data_field(page, field_name, context)`: finds the location of a specific field either via HTML attribute matching or visual detection.
- `detect_form_fields(page)`: enumerates all form fields with labels, types, placeholders, and locations using the Gemini vision API.

### `scroll_intelligence.py`

Utilities for handling scrolling and pagination.

- **ScrollIntelligence class** provides static helpers:
  - `detect_load_more_buttons(page)`: scans buttons/links for keywords like "load more" and returns selectors.
  - `auto_click_load_more(page, max_clicks, wait_ms)`: automatically clicks discovered buttons.
  - `perform_infinite_scroll(page, item_selector, max_scrolls, scroll_step, idle_rounds)`: scrolls until no new content appears, optionally tracking an item selector.
  - `auto_paginate(page, max_pages)`: iterates through pagination controls.
  - `detect_end_of_list(page, item_selector, attempts, wait_ms)`: determines if further scrolling yields new items.

### `runtime_adapter.py`

Adapter exposing the core reasoning controller to schedulers or task runners.

- **RuntimeReasoningAdapter class** wraps `ReasoningController`.
- Handles optional skill registry path, timeout protection (default 15s), telemetry logging, and fallback to Gemini actions on timeouts or errors.
- Provides asynchronous `initialize()` (no-op) and `execute_task(task_definition)`.

### `reasoning_loop.py`

Implements a full reasoning cycle for autonomous tasks.

- **ReasoningLoop class** orchestrates the cycle: OBSERVE ➜ THINK ➜ DECIDE ➜ ACT ➜ VERIFY ➜ STORE ➜ LEARN.
- Composes the navigator, vision, extractor and decision modules.
- Tracks memory (paths, layouts, strategies) and execution history.
- Detailed methods `_observe`, `_think`, `_decide`, `_act`, `_verify`, `_learn` implement each stage and log outcomes.
- Supports error recovery during action phase and learning from success/failure.

### `reasoning_controller.py`

Skill-first reasoning engine with Gemini fallback.

- **ReasoningController class**:
  - `infer_context(page)`: uses VisionAI to analyse page structure or heuristics to guess context (e.g., `'ntes_schedule'`).
  - `reason_and_act(page, task, threshold)`: retrieves skills via `SkillRetriever`, selects top skill with score ≥ threshold, executes with `SkillExecutor`, updates skill metrics, and falls back to Gemini if necessary.
  - `_update_skill_score(skill_id, success, alpha)`: updates EMA success rate in the skill registry JSON atomically.
- Ensures robust decision flow with logging and concurrency protection.

### Markdown notes

Two additional documents provide architectural guidance:

- `todoagent.md`: comprehensive design, training strategy, phase‑wise roadmap for the autonomous UI agent.
- `statusagent.md`: current state assessment and step‑by‑step roadmap to production readiness.

## ⚙️ `backend/core`

### `__init__.py`
- Package marker for backend core utilities.

### `base_engine.py`

Blueprint for engine implementations.

- **FeatureDetector class**: detects available features, computes an overall `EngineMode` (OFFLINE/HYBRID/ONLINE), and reports status.
- **BaseEngine abstract class**: common engine behaviour – status, startup/shutdown, metrics, feature detection, health checks, logging, configuration. Contains placeholder `_post_startup` for subclasses, and uses `EngineStatus` enum.

### `data_structures.py`
- Defines shared dataclasses and enums (e.g. `EngineMode`).

### `route_engine.py` & subpackage `route_engine/`

High-performance RAPTOR routing engine.

- Contains dataclasses for graph nodes and route elements (`SpaceTimeNode`, `RouteSegment`, `TransferConnection`, `Route`, `RouteConstraints`).
- Implements optimized multi-transfer routing with caching, parallel queries, ML ranking, reliability weighting, range‑RAPTOR, and real-time updates.
- Extensive code (2 400 lines) with helper functions and integration points for validation and ML models.
- `route_engine/` submodules further decompose functionality (not detailed here).

### `segment_detail.py`

Unified journey segment structures.

- `SegmentDetail` and `JourneyOption` dataclasses capturing all metadata for legs and complete journeys.
- `to_dict()` helpers for serialization.

### `utils.py`

Shared helpers used across engines.

- `CacheKeyGenerator`: consistent cache key generation for routes, availability, occupancy, and ML features.
- `OccupancyCalculator`: occupancy/availability rate calculations, human-readable levels, price multiplier logic.
- `error_handler` decorator for uniform exception logging and default returns.

### `realtime_event_processor.py`

Realtime event handling for delay/cancellation updates.

- **RealtimeEventProcessor class** processes `RealtimeData` events, updates the `RailwayRouteEngine` overlay, updates persistent `TrainState` records, and deletes processed events.
- Supports event translation, session management, and basic persistence logic.

### `validator/` sub-package

Holds validation manager and specific validators (route, resilience, production, performance). These enforce data integrity and business rules.

### Other supporting modules

- `metrics.py`, `ml_integration.py`, `ml_ranking_model.py`, as well as directories `engines/` and `managers/` contain additional backend support code referenced by core engines; specifics are beyond this document but they contribute to logging, metrics, ML and engine coordination.

---

This markdown file serves as a detailed, self‑contained report describing the ideas and implementation in every file under both core packages. It can be used for onboarding, documentation, or architectural overview.