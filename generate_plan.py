import textwrap

plan = """# RouteMaster 10X Evolution: Intelligent Routing Integration Plan

This document outlines the step-by-step integration of advanced transit algorithms (Dynamic Transfer Window, Station Frontier Filtering, Trip-Based Routing) into the existing RouteMaster system WITHOUT refactoring the core architecture. The goal is progressive enhancement and strict verification.

## Task 1: Waiting-Time Controlled Foundation (Dynamic Models)
Goal: Establish the core definitions and models for dynamic waiting time calculations, ensuring no disruption to existing fixed-time logic.
1.1 Define `DynamicWaitConfig` schema for minimum/maximum wait thresholds.
1.2 Implement `calculate_journey_duration(src, dst)` heuristic.
1.3 Create `compute_dynamic_window(journey_time, base_wait, beta)` logic.
1.4 Implement unit tests for linear and exponential beta curve wait limits.
1.5 Integrate dynamic wait definitions into `route_engine/models.py`.
1.6 Build `TransferWindow` dataclass for holding wait bounds.
1.7 Inject `TransferWindow` into `engine.py` context payload.
1.8 Create `waiting_time_evaluator(arrival_time, departure_time)` utility.
1.9 Write 10 hard tests: Edge cases crossing midnight for waiting evaluator.
1.10 Write 10 hard tests: Extremely short journeys vs extremely long journeys.
1.11 Implement station-size modifiers (e.g., Delhi = larger max wait).
1.12 Integrate station sizes from `stops` table into memory map.
1.13 Create `NightWaitPenalty` calculator (penalizing 01:00-04:00 waits).
1.14 Apply penalties safely via a configurable scoring hook.
1.15 Add caching for `station_size_modifier` to prevent DB hits.
1.16 Define maximum total waiting ratio (e.g., wait / travel < 0.4).
1.17 Implement validation function `is_valid_transfer(arrival, departure, context)`.
1.18 Hook `is_valid_transfer` as an optional filter in `TurboRouter`.
1.19 Run verification script testing 10 hard multi-day routing scenarios.
1.20 Finalize Task 1 and benchmark overhead (must be < 2ms per check).

## Task 2: Integration of Transfer Window Expansion logic
Goal: Gradually apply transfer windows in multi-transfer searches (Progressive Expansion).
2.1 Define 3 search phases (Phase 1: Strict, Phase 2: Moderate, Phase 3: Relaxed).
2.2 Create `ExpansionPhase` enum and configuration maps.
2.3 Modify search orchestrator to track current phase.
2.4 Inject strict `max_wait` overrides in Phase 1 (e.g., max 1 hour).
2.5 Update RAPTOR core transfer check to use Phase context.
2.6 Write 10 hard tests: Ensure Phase 1 rejects valid Phase 2 routes.
2.7 Implement automatic progression from Phase 1 to Phase 2 if routes < 5.
2.8 Implement Phase 2 to Phase 3 progression.
2.9 Ensure no duplicate routes are generated across phases.
2.10 Add `phase_found` tag to result segments for tracing.
2.11 Verify phase progression on high-traffic corridors (e.g., Delhi-Mumbai).
2.12 Verify phase progression on obscure low-traffic corridors.
2.13 Optimize transfer iteration by pre-sorting departures.
2.14 Implement early exit in transfer loop if departure > dynamic_max_wait.
2.15 Implement binary search for finding first valid departure in transfer.
2.16 Add 10 hard tests for binary search bounds across midnight.
2.17 Integrate progressive expansion into `csa_kernel.py` safely.
2.18 Validate backward compatibility with existing `limit` parameter.
2.19 Run memory leak test on Phase expansion loops.
2.20 Finalize Task 2: Validate 20% reduction in average searched routes.

## Task 3: Station Frontier Pruning (Core Data Structures)
Goal: Define the memory structures for keeping only the best routes per station.
3.1 Define the Dominance criteria (Arrival, Transfers, Wait Quality).
3.2 Create `FrontierRoute` dataclass representing a node in the frontier.
3.3 Implement `ParetoFrontier` class per station.
3.4 Implement `dominates(route_a, route_b)` logic.
3.5 Write 10 hard tests: Multi-dimensional Pareto dominance checks.
3.6 Implement `add_to_frontier(route)` with worst-route eviction.
3.7 Add configurable `max_routes_per_station` (default 5).
3.8 Implement strict arrival time dominance override.
3.9 Implement wait quality penalty in dominance calculation.
3.10 Create a global `FrontierManager` to hold states during search.
3.11 Write 10 hard tests for global `FrontierManager` isolation.
3.12 Implement fast cleanup/reset for `FrontierManager` between queries.
3.13 Implement debug tracing for evicted routes.
3.14 Optimize `dominates` math (use integer minutes, bitwise flags).
3.15 Compare performance: list iteration vs sorted heap for frontiers.
3.16 Implement sorted heap implementation of `ParetoFrontier`.
3.17 Create metrics tracker for "pruned routes" vs "kept routes".
3.18 Verify frontier memory usage with 7,000 stations.
3.19 Test with simulated 1M routes to ensure sub-millisecond pruning.
3.20 Finalize Task 3: Lock API for Frontier Pruning.

## Task 4: Station Frontier Filtering Integration in Search (RAPTOR)
Goal: Safely inject Station Frontier logic into the active RAPTOR/TurboRouter paths.
4.1 Map `FrontierManager` initialization to start of RAPTOR query.
4.2 Identify the exact point in `raptor.py` where a trip arrives at a station.
4.3 Inject `is_dominated = frontier.add_to_frontier(new_arrival)`.
4.4 Skip subsequent transfer generation if `is_dominated` is True.
4.5 Write 10 hard integration tests: RAPTOR with/without frontier parity.
4.6 Ensure direct trains (0 transfers) bypass or seed the frontier perfectly.
4.7 Handle edge case: same arrival time, different train (keep both or tie-break).
4.8 Ensure station frontier respects passenger class (e.g., Sleeper vs 3AC).
4.9 Map class constraints to the dominance function.
4.10 Track total routes dropped by frontier during a live query.
4.11 Create integration test: Complex multi-hub route (e.g., KOTA->CBE).
4.12 Adjust `max_routes_per_station` dynamically based on hub size.
4.13 Handle circular route detection via frontier histories.
4.14 Combine Task 2 (Expansion) and Task 4 (Frontier) loops safely.
4.15 Verify no regression in direct route latency.
4.16 Load test RAPTOR with 10 concurrent requests and Frontiers enabled.
4.17 Add logging hooks to track bottleneck stations (high eviction rates).
4.18 Run exhaustive correctness test: Frontier vs Brute Force RAPTOR.
4.19 Tune dominance weights to match empirical "best routes".
4.20 Finalize Task 4: Production-ready station frontier pruning.

## Task 5: Trip-Based Routing (TBR) - Preprocessing & Graph Construction
Goal: Prepare the foundational datasets for TBR without touching live RAPTOR.
5.1 Extract unique train sequences (trips) from `schedules` table.
5.2 Assign `trip_id` and internal binary index to each sequence.
5.3 Write script `generate_tbr_trips.py` to compile trips offline.
5.4 Define `TransferEdge` schema (From Trip, To Trip, Station, Wait).
5.5 Create `build_transfer_graph.py` logic to link intersecting trips.
5.6 Implement spatial/station-cluster linkage for transfers.
5.7 Apply the `dynamic_max_wait` logic from Task 1 during transfer edge creation!
5.8 Write 10 hard tests: Graph builder crossing midnight schedules.
5.9 Serialize transfer graph into highly optimized binary format.
5.10 Write `TbrDataBuffer` class to load binary graph into memory.
5.11 Verify memory footprint of `TbrDataBuffer` (< 500MB).
5.12 Implement `get_reachable_trips(source_station)`.
5.13 Implement `get_transfers(current_trip, current_station)`.
5.14 Optimize graph: Prune universally dominated transfer edges.
5.15 Implement footprint reduction using Pyroaring bitmaps for trip stations.
5.16 Create real-time updater for delayed trains in TBR graph (Skeleton).
5.17 Write 10 hard tests: Validating cyclic transfers don't infinite loop.
5.18 Export TBR graph metrics (edges, nodes, density).
5.19 Compare TBR transfer count against RAPTOR transfer matrix.
5.20 Finalize Task 5: Graph successfully loads in <2 seconds.

## Task 6: TBR Engine Core Implementation
Goal: Build the `TbrRouter` class operating purely on trips.
6.1 Define `TbrState` tracking active trips and path history.
6.2 Implement `TbrRouter.find_routes(src, dst)` skeleton.
6.3 Step 1: Initialize trip boarding at source station.
6.4 Step 2: Traverse trip stops linearly.
6.5 Step 3: Check destination reachability on active trip.
6.6 Step 4: Expand transfers to next trips.
6.7 Implement BFS/Dijkstra loop over trip edges.
6.8 Integrate dynamic waiting windows natively into transfer expansion.
6.9 Write 10 hard tests: TBR finding direct trains.
6.10 Write 10 hard tests: TBR finding 1-transfer trains.
6.11 Implement strict 3-transfer limit in TBR state.
6.12 Optimize inner loop using struct unpacking and memory views.
6.13 Ensure TBR handles multi-day routing gracefully.
6.14 Handle day-masking in TBR (Train operates on Mon/Wed).
6.15 Implement Trip Frontier Filtering (like Station Frontier but for Trips).
6.16 Add Early Arrival Problem optimizations.
6.17 Validate TBR outputs against pure RAPTOR outputs.
6.18 Benchmark: Ensure TBR is at least 5x faster than pure RAPTOR.
6.19 Add detailed timing telemetry to TBR phases.
6.20 Finalize Task 6: TBR Core fully functional and tested.

## Task 7: Bridging TBR and Existing RAPTOR Systems
Goal: Create a seamless, fail-safe Hybrid system.
7.1 Define `HybridRouter` that orchestrates TBR and RAPTOR.
7.2 Route queries with distance > 500km default to TBR.
7.3 Route short queries (< 500km) to TBR first, fallback to RAPTOR.
7.4 Implement fallback if TBR finds 0 routes (safety net).
7.5 Create shared response formatting so frontend sees no difference.
7.6 Map TBR internal paths to `Journey` and `Segment` Pydantic schemas.
7.7 Write 10 hard tests: Format parity between TBR and RAPTOR.
7.8 Validate availability predictions work identically on TBR routes.
7.9 Ensure fare calculation logic plugs into TBR segments perfectly.
7.10 Implement dual-execution mode for shadow testing (run both, log diffs).
7.11 Create script to run 10,000 random shadow queries.
7.12 Analyze shadow test mismatches and patch graph sync issues.
7.13 Add feature flag `USE_TBR_ENGINE` in config.
7.14 Hook up caching layer to TBR responses.
7.15 Optimize database hydration for TBR (fetch schedule names/data).
7.16 Ensure Redis fallback applies to TBR identically.
7.17 Inject cluster-routing capabilities into TBR source/dest definitions.
7.18 Validate edge cases where train spans 4+ days.
7.19 Create comprehensive dashboard for Hybrid Engine metrics.
7.20 Finalize Task 7: Hybrid system is live in shadow mode.

## Task 8: Enhanced Passenger Comfort Rules & Journey Context
Goal: Apply smart constraints from the conversation.
8.1 Introduce `JourneyContext` to pass user preferences.
8.2 Implement penalty logic for "Night Waiting".
8.3 Add "Station Quality Weighting" to transfer selection.
8.4 Give priority to high-tier trains (Rajdhani/Shatabdi) in dominance.
8.5 Penalize routes where Wait > 40% of Travel.
8.6 Provide "Comfort Score" in final response JSON.
8.7 Add UI-facing flags (e.g., `is_night_wait`, `is_comfortable_transfer`).
8.8 Write 10 hard tests: Scoring logic strictly separating bad routes.
8.9 Apply comfort rules to RAPTOR Expansion Phases.
8.10 Apply comfort rules to TBR Trip Frontiers.
8.11 Adjust minimum wait dynamically based on physical station platform sizes (if available).
8.12 Integrate ML delay predictions into waiting time windows (Dynamic buffer).
8.13 Adjust wait buffer based on source train's average delay.
8.14 Implement `strict_mode` toggle to force high-comfort routes only.
8.15 Add fallback to low-comfort if high-comfort is exhausted.
8.16 Create logging for "dropped due to passenger comfort".
8.17 Write tests simulating 5 hour delays to ensure wait window shifts.
8.18 Verify performance impact of comfort rule checks.
8.19 Update `scorer.py` to handle `JourneyContext` natively.
8.20 Finalize Task 8: Highly empathetic routing achieved.

## Task 9: Performance Optimization & Memory Management
Goal: Squeeze maximum speed out of the new system.
9.1 Profile TBR graph loading and optimize with `mmap`.
9.2 Convert pure Python transfer checks to Cython or Numba.
9.3 Optimize Frontier sorting algorithms.
9.4 Implement shared memory architecture for Gunicorn workers.
9.5 Write 10 hard tests: Race conditions in shared memory graph updates.
9.6 Remove redundant DB calls during hydration phase.
9.7 Compress `Segment` JSON sizes for network transit.
9.8 Add Redis pipelining for availability checks on large frontiers.
9.9 Implement heuristic "A* style" distance estimates to prune trips heading backwards.
9.10 Precalculate haversine distances for all station pairs.
9.11 Add Geographic directional filtering to TBR.
9.12 Test memory leak over 24 hours of sustained 100 req/sec.
9.13 Tune Python Garbage Collector for large static graphs.
9.14 Move heavy static data to read-only views.
9.15 Create automated daily script to rebuild TBR graphs with new GTFS.
9.16 Verify zero-downtime hot-swapping of TBR graphs.
9.17 Add Kubernetes liveness probes for graph readiness.
9.18 Implement batch-query capability for ML system pipelines.
9.19 Benchmark against target: <50ms P99 latency.
9.20 Finalize Task 9: Production-grade performance achieved.

## Task 10: Nationwide Production Deployment & 10X Hard-Core Testing
Goal: Final validation across the full Indian Railways network.
10.1 Compile massive test suite of 1,000 notoriously difficult routes.
10.2 Execute Phase 1: Correctness verification against old RAPTOR.
10.3 Execute Phase 2: Performance validation (5x speedup verified).
10.4 Execute Phase 3: Memory footprint validation (< 1GB per worker).
10.5 Implement automated rollback trigger if latency spikes.
10.6 Run chaos engineering tests (Redis down, DB slow).
10.7 Verify TBR fallback gracefully degraded.
10.8 Ensure dynamic window expansion correctly bounds edge-case queries.
10.9 Final code review of `TbrRouter` and `FrontierManager`.
10.10 Create technical documentation: "RouteMaster TBR & Frontier Architecture".
10.11 Write 10 Hard Tests: Complete system end-to-end.
10.12 Final API schema lock and documentation update.
10.13 Deploy to staging.
10.14 Run 24-hour shadow load test on staging.
10.15 Review staging logs for unexpected behavior.
10.16 Activate `USE_TBR_ENGINE = True` in production config.
10.17 Monitor real-time telemetry for 4 hours post-launch.
10.18 Conduct post-mortem analysis of any unhandled query patterns.
10.19 Cleanup legacy, obsolete pure-RAPTOR dead code paths.
10.20 Sign-off: The 10X Routing Engine Evolution is complete.
"""

with open("ROUTEMASTER_10X_EVOLUTION_PLAN.md", "w", encoding="utf-8") as f:
    f.write(plan)

print("Plan successfully generated.")
