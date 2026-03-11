# 🚀 10X ULTRA-ROUTING MASTER PLAN (DEEP ARCHITECTURE)
**Objective:** Guarantee destination arrival by generating a massive pool of routes using an exact "Order of Techniques," leveraging a shared Segment-Level Cache Matrix, and distilling results into strict utility buckets.

## 🧠 CORE ARCHITECTURE: THE ORDER OF TECHNIQUES
1. **The Segment Memory Matrix (L1 Cache):** Instantly check Redis for individual legs.
2. **Ultra-Turbo Direct (Tier 0):** Raw SQL (No ORM), bitwise execution for instant direct fetches.
3. **Hub-Spoke 1-Transfer (Tier 1):** Fast-path intersection of major geographic hubs.
4. **RAPTOR BFS 2-Transfer (Tier 2):** Algorithmic search for non-obvious 2-transfer routes.
5. **Deep RAPTOR 3-Transfer (Tier 3):** Fallback search triggered *only* to guarantee a path if Tiers 0-2 yield low results.

## 🪣 THE STRICT BUCKETING REQUIREMENT
1. **Top 3 Fastest Confirmed:** Real-time verified seats > 0.
2. **Top 10 Fastest Total:** Pure speed, regardless of seat status.
3. **Top 5 Optimal:** Mathematical balance of Speed + Cost + Reliability.
4. **10 Alternative Sorted:** Remaining structurally different routes.

---

## 📋 THE 25 HIGH-LEVEL TASKS

### EPIC 1: ULTRA-TURBO DIRECT ENGINE (Tasks 1-5)

*   **Task 1:** Build the Raw SQL Ultra-Turbo Direct Fetcher (Bypass ORM).
    * 1.1 Define the minimal result shape for a direct route leg (departure, arrival, service_id, days_of_run bitmask, seat availability fields).
    * 1.2 Write a raw, parameterized SQL query that selects only the columns needed for fast in-memory routing.
    * 1.3 Add support for runtime filters (origin, destination, travel_date, preferred class, seat availability thresholds).
    * 1.4 Implement caching of prepared SQL templates to avoid repeated parsing.
    * 1.5 Add a lightweight Python wrapper that returns `__slots__`-based route records for downstream routing logic.
    * 1.6 Implement a dedicated raw connection pool decoupled from SQLAlchemy (aiosqlite / raw driver) for Ultra-Turbo.
    * 1.7 Implement cursor-based streaming (`fetchmany`) to process large results without RAM spikes.
    * 1.8 Encode `days_of_run` logic as bitwise filters inside the query to reject non-running services.
    * 1.9 Add a date-expansion trigger that automatically queries `travel_date ± 1` when direct yield is low.
    * 1.10 Pre-resolve station alias clusters in the database before querying for stops.
    * 1.11 Add direction pruning via `stop_sequence` bounds to avoid reverse/backtracking trains.
    * 1.12 Map DB tuples directly into a `FastSegment` struct (no dict allocations) for memory efficiency.
    * 1.13 Exclude cancelled services using an `AND NOT EXISTS` join against `cancelled_trains` or equivalent.
    * 1.14 Compute a telescopic fare estimate in SQL (duration-based multiplier) so no Python loop is required.
    * 1.15 Wrap the entire execution in a timeout circuit breaker (`asyncio.wait_for`) to protect the pipeline.

*   **Task 2:** Implement Bitwise `days_of_run` Decoding & Date Expansion.
    * 2.1 Define a compact representation for `days_of_run` (e.g., bitmask for Mon-Sun + holiday flags).
    * 2.2 Implement a fast decoder utility that takes a query date and returns whether the service runs that day.
    * 2.3 Implement date expansion (e.g., `travel_date ± N days`) to prefetch adjacent days in a single query batch.
    * 2.4 Add unit tests for edge cases (leap year, DST transitions, multi-day running trains).
    * 2.5 Support `calendar_dates` exceptions (additions/closures) and integrate into the bitmask logic.
    * 2.6 Add a precomputed bitmask column (or materialized view) to accelerate SQL filtering.
    * 2.7 Provide a utility to generate bitmask values from full schedule exports.
    * 2.8 Build validation checks to detect bitmask inconsistency with real calendar data.
    * 2.9 Expose a debug endpoint that can render human-readable availability for a service.
    * 2.10 Define how multi-day trains (overnight) map into `days_of_run` evaluation.
    * 2.11 Ensure time zone correctness when mapping local departure dates to UTC or server date.
    * 2.12 Add caching for decoder results per query date for repeated lookups.
    * 2.13 Handle missing calendar data gracefully with fallback strategies.
    * 2.14 Add synthetic data generators for fuzz testing bitmask edge cases.
    * 2.15 Document the bitmask schema and update any data ingestion pipelines accordingly.

*   **Task 3:** Build the C-Struct / `__slots__` Memory Optimizer for Route Objects.
    * 3.1 Design a minimal `RouteLeg` representation using `__slots__` and typed fields (int/float/str).
    * 3.2 Implement an allocation factory to reuse objects where safe (pooling, object reuse patterns).
    * 3.3 Ensure the route objects are compatible with caching layers (Redis/pickle safe) and `__hash__` stable.
    * 3.4 Benchmark memory usage vs plain dataclasses and record results in `EPIC 1` verification docs.
    * 3.5 Add optional debug-mode objects (dataclasses) for easier development and introspection.
    * 3.6 Provide a conversion layer between lightweight structs and external JSON/graph formats.
    * 3.7 Add performance telemetry for object instantiation rates and GC pressure.
    * 3.8 Ensure objects are immutable once created to simplify caching and deduplication.
    * 3.9 Provide a `from_db_row()` helper to map raw rows to struct instances consistently.
    * 3.10 Add support for optional fields (e.g., fare, seat availability) without blowing up memory.
    * 3.11 Implement safe pooling with size caps and eviction to avoid unbounded growth.
    * 3.12 Add a `__repr__` / `to_dict` method for debugging without heavy allocations.
    * 3.13 Validate struct field typing and ranges (e.g., time in minutes within 0-1440).
    * 3.14 Add a non-allocating iterator for streaming route segments in tight loops.
    * 3.15 Document usage patterns and integration points for consumer components.

*   **Task 4:** Integrate `cancelled_trains` Pruning at the DB Query Level.
    * 4.1 Identify the authoritative source of cancelled train records (table / feed / flag).
    * 4.2 Incorporate an anti-join (NOT EXISTS) in the Ultra-Turbo SQL query to exclude cancelled services.
    * 4.3 Add a nightly refresh job that updates the cancelled trains list used for query filtering.
    * 4.4 Add a strict fallback: if the cancelled list is missing, fall back to a conservative route set rather than returning incorrect confirmations.
    * 4.5 Support both train-level and leg-level cancellations (partial cancellations).
    * 4.6 Add telemetry to detect cancellations that affect active user queries.
    * 4.7 Implement an alert if the cancellation feed hasn’t updated within a configured SLA.
    * 4.8 Add a manual override mechanism for emergency un-cancelling of routes.
    * 4.9 Ensure cancellation checks are scoped to the requested travel date and do not over-filter.
    * 4.10 Add regression tests that inject cancelled IDs and verify they disappear from results.
    * 4.11 Track cancellation source (feed name, timestamp) for audit and debugging.
    * 4.12 Provide a diagnostic endpoint to query why a given route was filtered.
    * 4.13 Handle stale cancellation entries (expired or superseded) gracefully.
    * 4.14 Validate cancellation data integrity (e.g., duplicate or malformed train IDs).
    * 4.15 Include cancellation logic in the verification suite so it’s always exercised.

*   **Task 5:** Epic 1 Hardcore 15-Point Verification Suite.
    * 5.1 Define 15 verification points covering correctness, performance, and edge cases.
    * 5.2 Implement unit tests for raw SQL results vs ORM results (parity check).
    * 5.3 Add integration tests that exercise the full Ultra-Turbo path end-to-end.
    * 5.4 Add performance regression tests (queries per second / latency).
    * 5.5 Add data validation tests for `days_of_run` decoding and `cancelled_trains` pruning.
    * 5.6 Document expected behavior and failure modes in `EPIC 1` verification doc.
    * 5.7 Add synthetic dataset tests for extreme schedules (e.g., high-frequency routes).
    * 5.8 Add fault-injection tests (DB timeouts, malformed rows) to verify fail-safe behavior.
    * 5.9 Verify caching semantics (raw pool, prepared statements, and L1 cache hits).
    * 5.10 Verify time-based triggers (date expansion, timeout breaker) behave as expected.
    * 5.11 Validate memory footprint targets under a representative load.
    * 5.12 Add regression monitors for query plan changes (via EXPLAIN plans).
    * 5.13 Document the expected route count thresholds for tier promotion.
    * 5.14 Add a daily automated run (CI job) that ensures task 1 remains within performance SLAs.
    * 5.15 Capture and report metrics for all assertion points (for ops dashboards).

### EPIC 2: FASTPATH & HUB-SPOKE ENGINES (Tasks 6-10)

*   **Task 6:** Pre-compute Geographic Hub Intersections on JIT Startup.
    * 6.1 Define the set of major geographic hub stations and the criteria for inclusion.
    * 6.2 Build a lightweight in-memory hub-graph representation for fast hub-to-hub lookup.
    * 6.3 Schedule a JIT startup job to precompute hub intersections and persist them for fast queries.
    * 6.4 Add telemetry to validate hub intersection cache hit rates.
    * 6.5 Implement a fallback path if hub data is missing (e.g., use RAPTOR over all stations).
    * 6.6 Ensure the hub graph updates when new hub stations are added.
    * 6.7 Add a configuration switch to enable/disable hub-spoke optimization.
    * 6.8 Validate hub intersections against real historical traffic patterns.
    * 6.9 Introduce a “hub score” metric to weight stronger hubs higher.
    * 6.10 Expose a diagnostic endpoint to view hub intersection counts and hit/miss ratios.
    * 6.11 Add fast-reload support so hub graph can update without restarting services.
    * 6.12 Implement mutexing to prevent concurrent recomputation during startup.
    * 6.13 Add unit tests that verify intersection generation correctness.
    * 6.14 Add regression tests that ensure hub intersections don’t regress after code changes.
    * 6.15 Document the hub selection strategy and update criteria.

*   **Task 7:** Implement Strict Time-Travel Physics (Layover Min 30m, Max 480m).
    * 7.1 Establish configurable constants for minimum/maximum layover and connection windows.
    * 7.2 Enforce layover constraints in the routing engine (including Hub-Spoke and RAPTOR paths).
    * 7.3 Add safeguards for overnight transfers / terminal changes.
    * 7.4 Add test coverage for layover edges (tight connections, long waits, cross-midnight connections).
    * 7.5 Ensure layover rules are applied consistently across all routing tiers.
    * 7.6 Implement layover violation logging for debugging and telemetry.
    * 7.7 Add support for special layover rules on high-speed / long-distance routes.
    * 7.8 Add configuration for exceptions (e.g., guaranteed transfers at certain hubs).
    * 7.9 Validate layovers against real itinerary data to ensure realism.
    * 7.10 Ensure time calculations respect timezone differences between stations.
    * 7.11 Add a “strict mode” option that enforces layover rules even more aggressively.
    * 7.12 Provide a utility to compute feasible connection windows for a given route.
    * 7.13 Add tests for boundary conditions (exactly 30m / exactly 480m).
    * 7.14 Document layover physics and how it interacts with multi-day wrapping.
    * 7.15 Add monitoring to detect spikes in rejected connection attempts.

*   **Task 8:** Resolve Station Aliases (e.g., NDLS vs DLI) in Multi-Leg Routing.
    * 8.1 Build an alias mapping table (canonical station code → aliases) from official datasets.
    * 8.2 Normalize incoming origin/destination inputs to canonical codes before routing.
    * 8.3 Ensure alias resolution is applied consistently across all routing tiers and caching layers.
    * 8.4 Add regression tests for known alias pairs and ambiguous station names.
    * 8.5 Build a tool to detect and merge duplicated stations in the dataset.
    * 8.6 Add heuristics to prefer canonical codes in user-facing output.
    * 8.7 Ensure alias resolution covers legacy and new station codes.
    * 8.8 Expose a diagnostic endpoint for alias resolution and mapping.
    * 8.9 Implement a mechanism to fallback to original code if canonical mapping fails.
    * 8.10 Add unit tests for case-insensitive and whitespace-cleaning input.
    * 8.11 Document the alias mapping source and update process.
    * 8.12 Add a periodic validation job to ensure alias table stays in sync with official sources.
    * 8.13 Add a “forced alias” override for emergency corrections.
    * 8.14 Add integration tests to ensure alias mapping doesn’t alter route geometry.
    * 8.15 Track alias mapping usage and measure impact on query results.

*   **Task 9:** Implement Telescopic Fare Approximation at the SQL Level.
    * 9.1 Define a fare bucket model (e.g., base fare + distance multipliers + class multipliers).
    * 9.2 Implement a fast SQL projection that approximates fare ranges without joining full fare tables.
    * 9.3 Add optional “refine” step to fetch exact fare for top candidate routes.
    * 9.4 Add validation tests comparing approximated to actual fares for sample routes.
    * 9.5 Add support for different fare classes (sleeper, AC, etc.) in the approximation.
    * 9.6 Expose a confidence score for the approximate fare.
    * 9.7 Allow tuning of approximation factors based on historical error.
    * 9.8 Add a fallback to query full fare tables if approximation is insufficient.
    * 9.9 Profile the SQL projection for performance and index usage.
    * 9.10 Document the approximation formula and its assumptions.
    * 9.11 Add unit tests for edge-case fare values (very short/very long distances).
    * 9.12 Ensure currency/locale handling is correct for fare displays.
    * 9.13 Add telemetry for approximation accuracy over time.
    * 9.14 Add an optimization to cache fare approximation results per segment.
    * 9.15 Add regression tests validating the refine step does not degrade performance.

*   **Task 10:** Epic 2 Hardcore 15-Point Verification Suite.
    * 10.1 Define 15 verification points covering hub-spoke correctness, layover rules, and fare approximation accuracy.


    
    * 10.2 Implement unit tests for hub intersection generation and alias normalization.
    * 10.3 Add integration tests exercising the full fast-path and hub-spoke engine end-to-end.
    * 10.4 Add performance and correctness regression tests for hub-spoke query latencies.
    * 10.5 Document expected behavior and failure modes in `EPIC 2` verification doc.
    * 10.6 Add synthetic route datasets to validate hub-spoke vs RAPTOR decisions.
    * 10.7 Add failover tests to ensure system falls back when hub data is missing.
    * 10.8 Validate layover enforcement across generated hub-spoke routes.
    * 10.9 Add accuracy validation for telescopic fare approximation in hub-spoke results.
    * 10.10 Add stress tests to measure hub-spoke engine under high concurrency.
    * 10.11 Add monitoring for hub-spoke cache hit rates and stale data.
    * 10.12 Add tests to validate correct handling of station aliases in hub-spoke flows.
    * 10.13 Add regression tests for configuration toggles (e.g., disable hub-spoke optimization).
    * 10.14 Add documentation of common failure modes and recovery steps.
    * 10.15 Integrate these tests into CI so they run on every relevant PR.

### EPIC 3: RAPTOR & DEEP DISCOVERY (Tasks 11-15)

*   **Task 11:** Upgrade RAPTOR to track strict Multi-Leg Journey IDs.
    * 11.1 Define a canonical Multi-Leg Journey ID format (e.g., hash of ordered legs + dates).
    * 11.2 Update RAPTOR data structures to attach the Journey ID to each candidate path.
    * 11.3 Ensure ID stability across reruns (same input should produce same ID for same route).
    * 11.4 Use Journey IDs for downstream deduplication and telemetry.
    * 11.5 Add a method to canonicalize leg ordering for ID generation.
    * 11.6 Ensure the journey ID embeds key invariants (source, dest, dates, class)
    * 11.7 Add an API to query route history by journey ID.
    * 11.8 Add tests verifying that equivalent journeys get identical IDs.
    * 11.9 Add debugging output for ID generation failures.
    * 11.10 Avoid collisions by including a salt/version in the hash.
    * 11.11 Store journey IDs in cache alongside route results.
    * 11.12 Add telemetry to count deduped routes per query.
    * 11.13 Add support for journey ID versioning to allow future schema changes.
    * 11.14 Document how journey IDs map to user-facing itineraries.
    * 11.15 Ensure ID generation is fast enough for high-query QPS.

*   **Task 12:** Build the Dynamic Depth Trigger (2-T to 3-T escalation).
    * 12.1 Define escape conditions for 2-transfer search (e.g., results < threshold, low reliability).
    * 12.2 Implement a trigger that enables 3-transfer deep search only when needed.
    * 12.3 Add telemetry to record trigger activations and resulting route quality improvements.
    * 12.4 Add configuration knobs for depth thresholds and evaluation windows.
    * 12.5 Ensure trigger runs asynchronously so it doesn't block initial response.
    * 12.6 Add a guardrail to prevent runaway 3-transfer explosion.
    * 12.7 Add a “fast-fail” path when 3-transfer route depth exceeds allowable time.
    * 12.8 Add unit tests for the trigger logic under various load profiles.
    * 12.9 Add monitoring to detect when the trigger is firing too often.
    * 12.10 Add a “minimum quality” metric that must be met for 3-T results.
    * 12.11 Add a mechanism to cache 3-T results for reuse in subsequent requests.
    * 12.12 Add documentation to explain why 3-T search was invoked for a query.
    * 12.13 Evaluate the impact of 3-T results on bucket distribution (fastest/optimal).
    * 12.14 Add a debug mode that forces 3-T search for all queries to validate coverage.
    * 12.15 Add integration tests ensuring 3-T results integrate correctly into final output.

*   **Task 13:** Implement Pareto-Frontier Deduplication (Speed vs. Cost vs. Transfers).
    * 13.1 Define the objective axes (e.g., travel time, fare, transfer count, reliability score).
    * 13.2 Implement Pareto frontier filtering to remove dominated routes.
    * 13.3 Ensure deterministic sorting for stable output when metrics tie.
    * 13.4 Add tests validating correct pruning across edge-case metric distributions.
    * 13.5 Add support for custom objective weights for different user profiles.
    * 13.6 Add a secondary pass for near-Pareto filtering to preserve diversity.
    * 13.7 Add telemetry to report how many routes are pruned per query.
    * 13.8 Ensure Pareto filter is efficient and uses O(n log n) where possible.
    * 13.9 Add an option to disable Pareto filtering for debugging.
    * 13.10 Add support for transforming metrics (e.g., logarithmic scale) before comparison.
    * 13.11 Ensure compatibility with pre-bucketed results (fastest / confirmed / optimal).
    * 13.12 Add tests to ensure no valid route is dropped due to identical metrics.
    * 13.13 Add documentation describing the Pareto model and how to interpret it.
    * 13.14 Add a “bucketing” stage that applies Pareto filtering within each bucket.
    * 13.15 Track Pareto reduction ratios as a health metric.

*   **Task 14:** Handle Cross-Midnight and Multi-Day Journey Wrapping.
    * 14.1 Define a clear time model (local time, timezone handling, date rollovers).
    * 14.2 Implement journey timestamp normalization for legs crossing midnight.
    * 14.3 Ensure layover rules and connection windows respect multi-day wrapping.
    * 14.4 Add tests for journeys that span date boundaries and multi-day running trains.
    * 14.5 Add utilities to display human-readable start/end dates for wrapped journeys.
    * 14.6 Ensure bucket logic treats wrapped journeys correctly (e.g., “next day”).
    * 14.7 Add schedule consistency checks across day boundaries.
    * 14.8 Add support for journeys exceeding 24h and properly roll their dates.
    * 14.9 Add a “day offset” metadata field to all route results.
    * 14.10 Add tests for zone shifts and DST transitions impacting cross-midnight legs.
    * 14.11 Ensure route continuity even if the journey spans multiple calendar days.
    * 14.12 Add a mechanism to flag and filter out absurdly long day offsets.
    * 14.13 Document how clients should interpret multi-day itineraries.
    * 14.14 Add a “wrap normalization” step in the caching pipeline for consistent keying.
    * 14.15 Add monitoring to detect growing numbers of multi-day routes (potential schedule issues).

*   **Task 15:** Epic 3 Hardcore 15-Point Verification Suite.
    * 15.1 Define 15 verification points covering deep discovery correctness and edge cases.
    * 15.2 Implement unit tests for journey ID stability and Pareto frontier filtering.
    * 15.3 Add integration tests exercising full RAPTOR depth escalation and wrapping behavior.
    * 15.4 Add performance regression tests for deep search time and memory usage.
    * 15.5 Document expected behavior and failure modes in `EPIC 3` verification doc.
    * 15.6 Add synthetic datasets to validate cross-midnight and multi-day journeys.
    * 15.7 Add tests for trigger-based escalation (2-T -> 3-T) and result quality.
    * 15.8 Verify that Pareto filtering does not remove required routes.
    * 15.9 Add stress test for 3-T path explosion.
    * 15.10 Validate out-of-memory guardrails under deep search.
    * 15.11 Add tests ensuring cross-midnight computations remain correct under heavy load.
    * 15.12 Verify bucket assignments remain stable across repeated runs.
    * 15.13 Add reporting for number of routes generated per query.
    * 15.14 Add a “golden dataset” regression test suite for RAPTOR outputs.
    * 15.15 Automate daily self-checks to detect drift in routing quality.

### EPIC 4: SEGMENT MEMORY MATRIX (Tasks 16-20)

*   **Task 16:** Design the Deterministic Segment Hash (`Train_From_To_Date_Class`).
    * 16.1 Define the canonical segment key components and normalization rules.
    * 16.2 Implement a stable hash function that is collision-resistant and consistent across runs.
    * 16.3 Ensure the hash supports date-based sharding and multi-class variants.
    * 16.4 Document the schema for Redis keys and TTL strategy.
    * 16.5 Implement a serialization format for hash keys (JSON/compact binary) for portability.
    * 16.6 Add a validator to detect hash collisions in production.
    * 16.7 Add tooling to compute segment hashes for historical archives.
    * 16.8 Ensure the hash is stable across code upgrades (add versioning if needed).
    * 16.9 Add unit tests for hash determinism across a wide variety of segment inputs.
    * 16.10 Ensure the hash is cheap to compute and avoids heavy cryptographic ops.
    * 16.11 Add a mechanism to embed metadata (e.g., class, date) in the cache key.
    * 16.12 Add a debug mode to display human-readable key components.
    * 16.13 Add documentation on how to interpret cache keys for debugging.
    * 16.14 Add an eviction strategy tied to segment freshness and schedule updates.
    * 16.15 Add a migration plan for changing hash schemas.

*   **Task 17:** Build the Redis Cache Interceptor for RapidAPI/Rappid.
    * 17.1 Define cache key generation strategy using segment hash and query params.
    * 17.2 Implement a cache interceptor layer that checks Redis before invoking the routing engine.
    * 17.3 Implement cache write-back logic and cache stampede protection.
    * 17.4 Add monitoring for cache hit/miss rates and eviction patterns.
    * 17.5 Add support for multiple cache tiers (hot/warm/cold) in Redis.
    * 17.6 Validate cache consistency across multiple API instances.
    * 17.7 Add a feature flag to enable/disable caching per environment.
    * 17.8 Add instrumentation to record cache latency and impact on response times.
    * 17.9 Implement per-request cache bypass for forced fresh results.
    * 17.10 Ensure cached payloads are brand/version aware to avoid stale schema issues.
    * 17.11 Add a cache warming endpoint for manual preloading.
    * 17.12 Add a tool to snapshot and inspect cached entries.
    * 17.13 Add AAA (auth) enforcement around cache keys (if required).
    * 17.14 Add a TTL management policy for popular vs rare segments.
    * 17.15 Add tests verifying cache correctness under concurrent access.

*   **Task 18:** Implement Asynchronous "Lookahead" Cache Warming.
    * 18.1 Define lookahead window policies (e.g., +1 day, +2 days for popular corridors).
    * 18.2 Build worker logic to precompute and cache segments during low-traffic windows.
    * 18.3 Ensure lookahead warming respects rate limits and does not overload DB.
    * 18.4 Add telemetry to measure warming effectiveness (hit rate delta, latency improvement).
    * 18.5 Add a priority system for which corridors to warm.
    * 18.6 Add a feedback loop to adjust warming based on real traffic patterns.
    * 18.7 Add a dry-run mode to validate warming without writing cache.
    * 18.8 Add safety guards to avoid warming obsolete segments.
    * 18.9 Add a report summarizing warmed segments and hit rate improvements.
    * 18.10 Add tests to validate warming doesn't corrupt cached data.
    * 18.11 Ensure warmers are idempotent and can be retried safely.
    * 18.12 Add a method to pause/resume warming activities.
    * 18.13 Add logging for warming failures and retries.
    * 18.14 Add a mechanism to adapt warming scope based on system load.
    * 18.15 Document the lookahead warming policy and how to tune it.

*   **Task 19:** Build the Historical Database Fallback for missing cache.
    * 19.1 Define schema for storing historical segment results and freshness metadata.
    * 19.2 Implement fallback logic that reads from historical store when cache miss occurs.
    * 19.3 Add safety checks to avoid returning stale or expired data.
    * 19.4 Add migration/retention policy for the historical store.
    * 19.5 Add a mechanism to mark historical data as “archived” or “expired.”
    * 19.6 Add tests verifying fallback selection criteria under various staleness thresholds.
    * 19.7 Add a manual refresh mechanism to rehydrate cache from history.
    * 19.8 Add metrics for historical fallback utilization.
    * 19.9 Add a data purging pipeline to keep the historical store bounded.
    * 19.10 Add documentation on which historical data is safe to serve.
    * 19.11 Add a warning system for when historical fallback returns low-confidence data.
    * 19.12 Ensure historical store is queryable without full table scans.
    * 19.13 Add a tooling script to migrate old historical records during schema changes.
    * 19.14 Add a validation job to check historical data integrity periodically.
    * 19.15 Add a “commit log” that records when historical entries were used.

*   **Task 20:** Epic 4 Hardcore 15-Point Verification Suite.
    * 20.1 Define 15 verification points covering cache correctness and lookahead behaviors.
    * 20.2 Implement unit tests for segment hashing, cache interceptor, and warming logic.
    * 20.3 Add integration tests validating cache + fallback end-to-end.
    * 20.4 Add performance regression tests to observe latency improvements and cache pressure.
    * 20.5 Document expected behavior and failure modes in `EPIC 4` verification doc.
    * 20.6 Add synthetic cache load tests to simulate cache stampedes.
    * 20.7 Add tests that validate cache key uniqueness and collision safety.
    * 20.8 Add tests for cache expiration and TTL correctness.
    * 20.9 Add tests that verify fallback is used only when appropriate.
    * 20.10 Add tests that validate lookahead warming doesn’t interfere with production traffic.
    * 20.11 Add monitoring for cache fill rates and stale hits.
    * 20.12 Add regression tests to prevent silent cache bypasses.
    * 20.13 Add a sanity check to validate that cache keys are deterministic across runs.
    * 20.14 Add documentation for debugging cache misses in production.
    * 20.15 Add a scheduled audit job that checks cache/historical data alignment.

### EPIC 5: BUCKETING, API & STRESS TESTING (Tasks 21-25)

*   **Task 21:** Build the "Top 3 Confirmed" Deep Verification Isolator.
    * 21.1 Define the exact criteria for a route to qualify as “confirmed” (real-time seat checks, price lock, etc.).
    * 21.2 Design a verification isolate that re-checks the top candidate routes against live availability.
    * 21.3 Implement parallel verification calls with bounded concurrency.
    * 21.4 Implement a retry/backoff strategy for flaky availability services.
    * 21.5 Capture and log verification latency and success rate.
    * 21.6 Provide a way to fall back to “best effort” when verification service is down.
    * 21.7 Add tests to validate that only confirmed routes are returned in this bucket.
    * 21.8 Add metrics to track what percentage of candidate routes pass verification.
    * 21.9 Add a feature flag to enable/disable deep verification without redeploy.
    * 21.10 Add a timeout for verification calls to keep control on response times.
    * 21.11 Ensure verification can be run asynchronously without blocking user response.
    * 21.12 Add a “confidence” score to confirmed routes based on recency of verification.
    * 21.13 Design a fallback path in case verification infrastructure is under maintenance.
    * 21.14 Document the verifiers’ input/output contracts.
    * 21.15 Add an audit log of verification decisions for post-mortem analysis.

*   **Task 22:** Build the "Shallow Verification" Batcher for the remaining pool.
    * 22.1 Define criteria for shallow vs deep verification (e.g., top N vs rest).
    * 22.2 Implement a batch verifier that checks seat availability at lower fidelity.
    * 22.3 Optimize for throughput using bulk API endpoints where available.
    * 22.4 Add throttling to avoid overwhelming external services.
    * 22.5 Add fallback heuristics when shallow checks fail (e.g., assume available).
    * 22.6 Add metrics for shallow verification hit rate and error rate.
    * 22.7 Ensure shallow verification results are merged back into the route pool consistently.
    * 22.8 Add tests to validate shallow verification correctness and performance.
    * 22.9 Add a “best-effort” mode for shallow verification under heavy load.
    * 22.10 Add a configuration option to adjust batch size and timeouts.
    * 22.11 Track how often routes move from shallow to deep verification.
    * 22.12 Ensure shallow verification supports multi-leg itinerary checks.
    * 22.13 Document the expected accuracy tradeoffs of shallow verification.
    * 22.14 Add a monitoring dashboard showing verification queue latency.
    * 22.15 Add a backpressure mechanism to avoid overwhelming the core routing system.

*   **Task 23:** Implement the Optimal Scoring Formula & Bucket Aggregation.
    * 23.1 Define the scoring formula that balances speed, cost, reliability, and transfers.
    * 23.2 Implement a bucket aggregation pipeline that builds the four required buckets.
    * 23.3 Ensure bucket assignments are deterministic and stable across runs.
    * 23.4 Add a customizable weight vector for different user profiles.
    * 23.5 Add a normalization step to compare heterogeneous metrics (minutes vs currency).
    * 23.6 Add tests to validate correct bucket placement for representative cases.
    * 23.7 Add a smoothing algorithm to prevent bucket churn on minor metric changes.
    * 23.8 Add telemetry to show the distribution of routes among buckets.
    * 23.9 Ensure the “Alternative” bucket contains structurally diverse routes.
    * 23.10 Add a mechanism to certify that the top-3 confirmed bucket always references verified routes.
    * 23.11 Add a fallback to ensure at least one route is returned even if all verifications fail.
    * 23.12 Document the scoring formula and how to interpret scores.
    * 23.13 Add a way to recalculate bucket membership without rerunning full search.
    * 23.14 Add a debug mode to output scoring breakdown per route.
    * 23.15 Add a regression test to ensure bucket sizes (3/10/5/10) are respected.

*   **Task 24:** Compress Payload (Brotli/Gzip) & Handle Circuit Breakers.
    * 24.1 Add middleware to compress JSON payloads using Brotli and fall back to Gzip.
    * 24.2 Ensure compression is only applied when payload size exceeds a threshold.
    * 24.3 Add circuit breaker logic around downstream services (verification, pricing).
    * 24.4 Add health checks and a “circuit state” endpoint for observability.
    * 24.5 Add support for per-route circuit breakers vs global circuit breaker.
    * 24.6 Add a retry budget that limits retries to avoid cascading failures.
    * 24.7 Add tests for compressed payload correctness and size savings.
    * 24.8 Add tests for circuit breaker state transitions (open/half-open/closed).
    * 24.9 Add monitoring for compressed payload throughput and error rates.
    * 24.10 Add decompression safeguards to prevent zip bomb attacks.
    * 24.11 Add configuration for compression levels and allowed encodings.
    * 24.12 Add a fallback to return uncompressed payload for incompatible clients.
    * 24.13 Document API expectations around compression and circuit breaker behavior.
    * 24.14 Add a tuning guide for selecting circuit breaker thresholds.
    * 24.15 Add a dashboard showing circuit breaker events and recovery times.

*   **Task 25:** Ultimate 15-Point End-to-End System Audit & Stress Test.
    * 25.1 Define 15 audit points spanning all tiers (Ultra-Turbo → Deep RAPTOR → Bucketing).
    * 25.2 Build an end-to-end test harness that can replay real-world query logs.
    * 25.3 Add stress tests that simulate peak traffic (QPS, concurrency) and measure latency.
    * 25.4 Add failure injection tests (DB timeouts, Redis failures, downstream outages).
    * 25.5 Add tests that validate end-to-end latency tail (p99, p999).
    * 25.6 Add load tests that verify the system stays within memory and CPU budgets.
    * 25.7 Add tests that validate consistency of returned buckets over time.
    * 25.8 Add a canary pipeline that runs daily and alerts on regression.
    * 25.9 Add an audit report generator that captures key metrics and anomalies.
    * 25.10 Add a “blast radius” analysis for each component (which failures affect which buckets).
    * 25.11 Add documentation on how to interpret audit findings and remediate.
    * 25.12 Add a way to promote audit findings into actionable tickets.
    * 25.13 Add an automated smoke check for major deployments.
    * 25.14 Add a “chaos day” plan for exercising resilience under controlled failures.
    * 25.15 Add a final executive summary template for stakeholder reporting.
