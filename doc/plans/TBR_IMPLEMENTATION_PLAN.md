# Trip-Based Routing (TBR) Implementation & Integration Plan

This document outlines the comprehensive 20-Task evolution plan to implement, integrate, audit, and optimize a state-of-the-art **Trip-Based Routing (TBR)** engine into the RouteMaster system. TBR shifts the search paradigm from exploring stations to exploring contiguous trips, yielding 5x-20x performance improvements for large railway networks.

## Phase 1: Conceptualization & Data Structures

### Task 1: TBR Theoretical Framework & Data Modeling
*   **1.1 [Implementation]** Define `TripNode` and `TripEdge` dataclasses tailored for minimal memory footprint.
*   **1.2 [Analysis]** Analyze the memory footprint of `TripNode` vs the existing `RouteSegment` architecture.
*   **1.3 [Audit]** Audit the existing GTFS `stop_times` structure to map `trip_id` to contiguous sequence arrays.
*   **1.4 [Implementation]** Design the `TransferGraph` schema to store precomputed connections between trips.
*   **1.5 [Verification]** Verify DB schema compatibility with high-speed `MemMap` indexing.
*   **1.6 [Performance]** Optimize dataclass `__slots__` for `TripNode` to eliminate dictionary overhead and reduce RAM usage.
*   **1.7 [Implementation]** Draft the `TripBasedRouter` class skeleton, extending the base engine interface.
*   **1.8 [Audit]** Audit interface requirements for seamless IoC integration in `route_engine.py`.
*   **1.9 [Analysis]** Analyze the theoretical complexity (Big-O) of TBR vs RAPTOR for worst-case topological pairs.
*   **1.10 [Improvement]** Idea: Utilize NumPy structured arrays for contiguous Trip-to-Trip adjacency storage.

### Task 2: In-Memory Trip Representation & Indexing
*   **2.1 [Implementation]** Build `TripSequenceIndex`: an O(1) mapping of `stop_id` -> list of `(trip_id, sequence_index)`.
*   **2.2 [Audit]** Audit `builder.py` to extract and vectorize trips without breaking existing RAPTOR dependencies.
*   **2.3 [Verification]** Verify fast O(1) array slicing to retrieve all future stops of a boarded trip.
*   **2.4 [Implementation]** Implement the `trip_stop_times` dense 2D array (TID -> array of absolute timestamps).
*   **2.5 [Performance]** Convert string times to integer seconds-from-epoch for rapid SIMD operations.
*   **2.6 [Analysis]** Analyze CPU Cache Line misses during sequential trip traversal using python profilers.
*   **2.7 [Improvement]** Group trips by `pattern_id` to compress identical stop sequences into single logical routes.
*   **2.8 [Implementation]** Formulate logic to handle midnight crossovers in continuous trip representations.
*   **2.9 [Audit]** Audit edge cases for circular routes or ultra-long trips crossing > 48h.
*   **2.10 [Verification]** Develop unit tests for sequence retrieval using known long-haul trains (e.g., Vivek Express).

### Task 3: Precomputed Transfer Graph Foundation
*   **3.1 [Implementation]** Define the core `compute_trip_transfers(tid_a, tid_b, station_id)` worker function.
*   **3.2 [Analysis]** Analyze the combinatorics: 13k trips * 13k trips is computationally explosive; strategy required.
*   **3.3 [Improvement]** Restrict transfer precomputation exclusively to Major Hubs and spatial proximity clusters.
*   **3.4 [Implementation]** Build a spatial index (KDTree) for identifying viable foot transfers between different trips at nearby stations.
*   **3.5 [Audit]** Audit dynamic wait time bounds (e.g., 15m to 6h) to aggressively prune invalid temporal edges.
*   **3.6 [Verification]** Verify that computed transfer edges strictly adhere to minimum station connection times.
*   **3.7 [Performance]** Utilize `asyncio.TaskGroup` or `multiprocessing` to parallelize the static transfer graph generation.
*   **3.8 [Implementation]** Store the resulting edges in a Sparse Matrix or optimized adjacency list.
*   **3.9 [Analysis]** Conduct memory profiling of the loaded adjacency list during engine boot.
*   **3.10 [Improvement]** Compress transfer durations and constraints into packed 16-bit integers to save RAM.

## Phase 2: Graph Building & ETL

### Task 4: Transfer Graph Generation Pipeline (ETL)
*   **4.1 [Implementation]** Add `_build_tbr_graph_sync` to `builder.py` to execute the ETL pipeline.
*   **4.2 [Verification]** Verify successful extraction of Leg 1 -> Leg 2 temporal combinations.
*   **4.3 [Audit]** Audit database locking and memory spikes during massive SQL JOINs for transfer generation.
*   **4.4 [Implementation]** Vectorize the transfer logic using highly optimized pandas or raw SQLite window functions.
*   **4.5 [Performance]** Implement batch inserts to save transfer links to disk efficiently.
*   **4.6 [Analysis]** Analyze the I/O bottleneck during graph saving and loading.
*   **4.7 [Improvement]** Migrate static transfer tables to memory-mapped files (`mmap`) for instantaneous JIT loading.
*   **4.8 [Implementation]** Cross-reference calendar active dates to filter out invalid daily transfers.
*   **4.9 [Audit]** Audit for missing transfers involving infrequent (weekly/bi-weekly) trains.
*   **4.10 [Verification]** Ensure the TBR graph builder produces a transfer yield matching or exceeding standard RAPTOR.

### Task 5: Hub-Aware Transfer Graph Optimization
*   **5.1 [Implementation]** Restrict internal `Trip-to-Trip` precomputed transfers exclusively to Tier 1/2 hubs managed by `hub_manager`.
*   **5.2 [Analysis]** Analyze the reduction in global edge count (targeting a > 90% reduction).
*   **5.3 [Verification]** Verify that route yield for pairs like NDLS->MMCT remains identical despite hub-only transfers.
*   **5.4 [Implementation]** Add a fast fallback dynamic transfer computation for edge cases at remote/rural stations.
*   **5.5 [Performance]** Benchmark the memory load time of the Hub-restricted graph vs the Full unstructured graph.
*   **5.6 [Audit]** Audit whether dropping small-station transfers negatively impacts the "Budget" or "Rural" personas.
*   **5.7 [Improvement]** Precompute exact transfer walking times utilizing platform coordinates where available.
*   **5.8 [Implementation]** Assign a "transfer cost penalty" to edges based inversely on station size and facilities.
*   **5.9 [Analysis]** Review the existing `hub_connectivity_index` to seed the TBR graph dynamically.
*   **5.10 [Verification]** Check the exactness of transfers at multi-terminal metropolitan cities (e.g., NDLS to NZM transfers).

### Task 6: Dynamic Overlay & Real-Time Sync for TBR
*   **6.1 [Implementation]** Adapt `RealtimeOverlay` to intercept and dynamically modify TBR trip traversals.
*   **6.2 [Audit]** Audit the cascade effect: how a cancelled trip dynamically breaks precomputed transfer edges.
*   **6.3 [Verification]** Verify that a cancelled `Train B` correctly invalidates the `Train A -> Train B` edge in memory.
*   **6.4 [Implementation]** Implement delay propagation: if `Train A` is late, invalidate the edge if the remaining buffer < `min_wait`.
*   **6.5 [Performance]** Utilize bitwise AND operations for lightning-fast cancellation checks during the inner traversal loop.
*   **6.6 [Analysis]** Analyze the latency impact of querying the real-time overlay on the raw TBR speed.
*   **6.7 [Improvement]** Cache "safe" transfers that possess a > 2-hour buffer, making them immune to minor delay checks.
*   **6.8 [Implementation]** Formulate logic to dynamically inject "Tatkal special" or holiday trains into the live Trip Graph.
*   **6.9 [Audit]** Audit for memory leaks occurring during high-frequency overlay updates.
*   **6.10 [Verification]** Test real-time delay injection scripts and verify yield accuracy adjusts accordingly.

### Task 7: Graph Persistence & Memory Mapping (MemMap)
*   **7.1 [Implementation]** Serialize the `TransferGraph` using `numpy.savez_compressed` for rapid cold starts.
*   **7.2 [Implementation]** Implement `MemMapManager` integration specifically for TBR adjacency and sequence lists.
*   **7.3 [Analysis]** Analyze page-fault overhead when accessing randomized trip sequences directly from NVMe disk.
*   **7.4 [Audit]** Audit Windows file-locking issues (PermissionError) during MemMap replacement and apply timestamp versioning.
*   **7.5 [Performance]** Align trip numpy arrays to 64-byte boundaries for optimal CPU hardware prefetching.
*   **7.6 [Verification]** Verify that an orchestrator snapshot reload completes in < 50ms.
*   **7.7 [Improvement]** Implement a dual-buffer (Active/Standby) snapshot strategy to ensure zero-downtime background updates.
*   **7.8 [Implementation]** Store Trip sequences as a flat 1D array with offset indexing, eliminating python object overhead.
*   **7.9 [Audit]** Audit serialization compatibility and exactness across python runtime versions.
*   **7.10 [Verification]** Cross-validate loaded MemMap data randomly against the source SQLite DB to ensure integrity.

## Phase 3: Core TBR Algorithm Implementation

### Task 8: TBR Engine Initialization & Worker Setup
*   **8.1 [Implementation]** Create the `TripBasedRouter` class, strictly inheriting from the Base Engine architecture.
*   **8.2 [Implementation]** Register `TripBasedRouter` correctly in the `UnifiedRoutingOrchestrator` pipeline.
*   **8.3 [Audit]** Audit memory sharing configurations between RAPTOR, FastPath, and TBR workers to prevent RAM bloat.
*   **8.4 [Verification]** Verify the correct asynchronous dependency injection of the `TimeDependentGraph`.
*   **8.5 [Performance]** Implement object pooling (flyweight pattern) for TBR `SearchState` objects to eliminate garbage collection pauses.
*   **8.6 [Analysis]** Analyze python GIL impact and CPU core affinity for the TBR worker thread during parallel execution.
*   **8.7 [Improvement]** Architect separation of I/O bound checks (DB hydration) from purely CPU bound tasks (Graph traversal).
*   **8.8 [Implementation]** Initialize the TBR instance with strictly defined `max_transfers` and a fail-safe `traversal_budget`.
*   **8.9 [Audit]** Ensure the robust `_safe_fromtimestamp` utility is natively propagated to the TBR engine.
*   **8.10 [Verification]** Execute an empty dry-run test to baseline the raw initialization and teardown latency.

### Task 9: Step 1 & 2 - Source Trip Discovery & Boarding
*   **9.1 [Implementation]** Implement the critical `_get_source_trips(source_id, time_window)` function.
*   **9.2 [Implementation]** Natively handle `METRO_GROUPS` expansion for source station boarding (boarding multiple nearby stations simultaneously).
*   **9.3 [Performance]** Utilize binary search (`bisect`) on sorted departure arrays to instantly find trips departing after `start_time`.
*   **9.4 [Audit]** Audit the handling of active trips that started their journey yesterday but reach the source station today.
*   **9.5 [Verification]** Verify that 100% of all possible departing trips from a major hub like NDLS are captured within the window.
*   **9.6 [Analysis]** Analyze the initial search frontier size (Number of initially boarded trips) to predict memory load.
*   **9.7 [Improvement]** Heuristic: Sort the initially boarded trips by their projected arrival time at the destination to guide the search.
*   **9.8 [Implementation]** Instantiate a lightweight `TripRoute` tracker for each successfully boarded train.
*   **9.9 [Audit]** Check for and prune duplicate trip boardings occurring across expanded metro clusters.
*   **9.10 [Verification]** Ensure the exact handling of initial boarding delays cross-referenced via the Realtime Overlay.

### Task 10: Step 3 - Forward Trip Traversal & Dominance
*   **10.1 [Implementation]** Implement continuous forward scan logic: once boarded, logically "jump" directly to the destination or transfer hubs.
*   **10.2 [Implementation]** Deeply integrate `Trip Reachability Bitset` (O(1) boolean check to see if a trip ever hits the destination).
*   **10.3 [Performance]** If `bitset == True`, immediately extract the segment, yield the route, and terminate that specific branch.
*   **10.4 [Analysis]** Measure the exact branch pruning efficiency of the bitset in the TBR context (expect massive reduction).
*   **10.5 [Audit]** Audit the safety of arrival time extraction from the flattened Trip sequence array.
*   **10.6 [Verification]** Verify that the direct routes discovered by TBR exactly match those found by the UltraTurbo direct SQL.
*   **10.7 [Implementation]** Implement `FrontierManager` strict dominance pruning based on a Pareto frontier of `(arrival_time, transfers)`.
*   **10.8 [Improvement]** Track `global_min_arrival` continuously to aggressively prune ongoing trips that arrive too late.
*   **10.9 [Audit]** Ensure fuzzy timestamp matching (± 2s) is utilized during sequence matching to avoid python float precision drops.
*   **10.10 [Verification]** Stress test traversal performance on ultra-long monolithic routes (e.g., Kanyakumari to Shri Mata Vaishno Devi Katra).

### Task 11: Step 4 - Transfer Edge Exploration
*   **11.1 [Implementation]** Implement the core `_explore_transfers(current_trip, current_stop)` logic.
*   **11.2 [Implementation]** Perform lightning-fast lookups against the precomputed adjacency list for `current_trip`.
*   **11.3 [Performance]** Filter the adjacency list dynamically on the fly based on absolute `arrival_time` + `min_wait`.
*   **11.4 [Analysis]** Analyze the branching factor (out-degree) of trips arriving at super-hubs like Itarsi or Kanpur.
*   **11.5 [Audit]** Audit the transfer logic to ensure it strictly prevents "backtracking" to previously visited geographical regions.
*   **11.6 [Verification]** Verify cycle detection strictly prevents endless loops (e.g., Trip A -> Trip B -> Trip A).
*   **11.7 [Improvement]** Use SIMD/NumPy vectorized operations to mask out invalid or dominated transfers in bulk.
*   **11.8 [Implementation]** Apply station-size aware waiting windows (5m, 10m, 15m) directly within the TBR edge resolution.
*   **11.9 [Audit]** Check if platform changes (e.g., PF 1 to PF 10) are correctly penalized in the transfer duration model.
*   **11.10 [Verification]** Benchmark 1-transfer route yields against the raw Turbo 1T SQL baseline to ensure parity.

### Task 12: Multi-Round Transfer Orchestration (TBR-RAPTOR Hybrid)
*   **12.1 [Implementation]** Construct the robust `while transfers < max_transfers:` outer orchestration loop.
*   **12.2 [Implementation]** Implement a robust BFS queue for trip state management across rounds.
*   **12.3 [Performance]** Optimize the queue using `collections.deque` or a min-heap priority queue based on heuristic scoring.
*   **12.4 [Analysis]** Conduct comparative profiling of standard BFS vs A* (Dijkstra) traversal speeds specifically for the TBR graph.
*   **12.5 [Audit]** Audit the strict enforcement of the `traversal_budget` limits to definitively prevent infinite hangs.
*   **12.6 [Verification]** Verify that precisely 2-transfer and 3-transfer complex routes are successfully generated.
*   **12.7 [Improvement]** Implement a geographical heuristic (A* proxy) guided by the remaining Euclidean distance to the destination.
*   **12.8 [Implementation]** Capture full state lineage (parent pointers) to reconstruct the exact `Route` object segments later.
*   **12.9 [Audit]** Ensure memory isn't leaking from un-garbage-collected orphaned `SearchState` nodes in long searches.
*   **12.10 [Verification]** Validate that `TimeoutError` propagation gracefully interrupts the deep loops and returns partial results.

## Phase 4: Advanced TBR Optimizations

### Task 13: Journey ID & Deep Deduplication for TBR
*   **13.1 [Implementation]** Implement `_hydrate_tbr_route` to seamlessly convert raw TBR `SearchState` data into rich `Route` objects.
*   **13.2 [Implementation]** Generate standardized, deterministic `journey_id` signatures for TBR routes matching the rest of the system.
*   **13.3 [Performance]** Avoid redundant n+1 SQL queries during hydration by heavily relying on the `FastSegment` pool.
*   **13.4 [Analysis]** Analyze the specific intersection and overlap between TBR discovered routes and FastPath/RAPTOR routes.
*   **13.5 [Audit]** Audit if structurally identical trips running on different days are mistakenly merged or incorrectly deduplicated.
*   **13.6 [Verification]** Verify the deduplication algorithm successfully eliminates 100% of identical trip sequences.
*   **13.7 [Improvement]** Enhance deduplication to actively retain the variant exhibiting the lowest latency or lowest cost.
*   **13.8 [Implementation]** Implement safety nets to map missing `station_name` strings via `stop_cache` during the hydration phase.
*   **13.9 [Audit]** Perform a sweep for `NoneType` errors in mathematical duration/fare calculations post-hydration.
*   **13.10 [Verification]** Run the hydrated routes through `score_route_sync` to ensure complete schema compatibility.

### Task 14: Station-Size Aware Waiting Window Filtering
*   **14.1 [Implementation]** Port the nuanced `DynamicWaitConfig` logic natively into the deep TBR traversal loops.
*   **14.2 [Implementation]** Inject the `SearchPhase` context (Strict, Moderate, Relaxed) dynamically into the TBR wait bounds.
*   **14.3 [Performance]** Pre-calculate complex beta-scaling exponential curves into a lookup table to completely avoid `math.pow` in inner loops.
*   **14.4 [Analysis]** Empirically measure the difference in route yield variance between Strict (tight connections) and Relaxed phases.
*   **14.5 [Audit]** Audit if excessively long layovers (>12h) are correctly identified, penalized, or aggressively dropped.
*   **14.6 [Verification]** Verify that overnight layovers toggle the `is_night_wait` boolean flag accurately.
*   **14.7 [Improvement]** Architect a feature to allow premium users to override max wait time thresholds dynamically per request.
*   **14.8 [Implementation]** Algorithmically restrict ultra-tight transfers (< 10m) if the destination station's `facilities_score` is poor.
*   **14.9 [Audit]** Ensure all default configuration values are safely extracted using the robust `or default` pattern to prevent crashes.
*   **14.10 [Verification]** Verify via logs that all `TypeError` exceptions originating from `None` configuration values are eliminated.

### Task 15: Trip Reachability Bitsets Integration
*   **15.1 [Implementation]** Directly wire `graph.can_reach_destination()` into the absolute innermost loop of the TBR transfer check.
*   **15.2 [Implementation]** Support `METRO_GROUPS` natively in the bitset check (e.g., checking if the trip hits any of 5 bits).
*   **15.3 [Performance]** Utilize standard bitwise OR `|` operations to evaluate multiple destination targets simultaneously in one CPU cycle.
*   **15.4 [Analysis]** Micro-profile the nanosecond-level latency of the bitset check utilizing python `timeit`.
*   **15.5 [Audit]** Audit if the hardcoded `NUM_STOPS` limit (e.g., 32768) safely encompasses all recent station GTFS additions.
*   **15.6 [Verification]** Rigorously verify that absolutely no false negatives exist in the reachability bitset logic.
*   **15.7 [Improvement]** Implement an advanced `Hub Reachability Bitset` (e.g., Can Trip A reach Major Hub X eventually?).
*   **15.8 [Implementation]** Introduce aggressive pruning to drop trips entirely if they don't hit the destination OR a predefined major hub.
*   **15.9 [Audit]** Ensure internal bitset word indices match the exact integer ID offsets present in the normalized `stops` table.
*   **15.10 [Verification]** Benchmark complex 3-transfer search times specifically comparing with and without bitset integration.

### Task 16: Persona-Based Scoring & Yield Ranking
*   **16.1 [Implementation]** Ensure TBR outputs fully hydrated objects that natively support `score_route_sync`.
*   **16.2 [Implementation]** Pre-calculate highly accurate fares during the hydration stage utilizing `calculate_fares_batch`.
*   **16.3 [Performance]** Vectorize duration, layover, and distance aggregations across the entire generated batch.
*   **16.4 [Analysis]** Analyze TBR's innate ability to discover hyper-optimized "Budget" routes versus high-speed "Fast" routes.
*   **16.5 [Audit]** Audit the scoring algorithm to ensure it doesn't artificially inflate scores making multi-transfer routes look better than directs.
*   **16.6 [Verification]** Verify the 'Emergency' persona strictly prioritizes the absolute earliest departure time above all else.
*   **16.7 [Improvement]** Stream TBR-generated routes into the `MLMicroservice` pipeline for advanced predictive reliability scoring.
*   **16.8 [Implementation]** Tag all TBR generated routes explicitly with `metadata["engine"] = "tbr_v1"` for downstream analytics.
*   **16.9 [Audit]** Ensure all potential mathematical fallback logic in the scoring module handles `None` or zeroes gracefully.
*   **16.10 [Verification]** Visually and programmatically verify the final sorted output order aligns with persona expectations.

## Phase 5: Integration, Audit & Performance

### Task 17: UnifiedRoutingOrchestrator Integration
*   **17.1 [Implementation]** Add `self.tbr_router` class initialization seamlessly to the `route_engine.py` core instantiation.
*   **17.2 [Implementation]** Create a dedicated, parallel `asyncio.create_task` for TBR within `orchestrator.py` `stream_all_tiers`.
*   **17.3 [Performance]** Fine-tune asyncio timeout inheritances: Provide TBR with a 30% larger relative time budget compared to standard RAPTOR.
*   **17.4 [Analysis]** Implement telemetry to track execution trace latencies specifically comparing TBR against FastPath.
*   **17.5 [Audit]** Audit the global resource semaphores (`_global_resource_sem`) to ensure TBR doesn't cause thread starvation or DB locks.
*   **17.6 [Verification]** Verify the Orchestrator successfully merges, deduplicates, and ranks TBR routes alongside UltraTurbo results.
*   **17.7 [Improvement]** Implement Dynamic Engine Dispatch: Programmatically skip the RAPTOR task entirely if TBR rapidly discovers > 50 routes.
*   **17.8 [Implementation]** Propagate the `skip_heavy` flag logic to dynamically disable TBR execution on memory-constrained servers.
*   **17.9 [Audit]** Ensure Exception groups (`asyncio.TaskGroup`) correctly isolate isolated TBR failures from crashing the entire response stream.
*   **17.10 [Verification]** Run the standard suite of integration regression tests.

### Task 18: System-Wide TBR Solo Audit & Yield Verification
*   **18.1 [Implementation]** Create a standalone, highly detailed `verify_tbr_solo.py` diagnostic test script.
*   **18.2 [Implementation]** Test Scenario: NDLS -> MMCT (Long Haul, extremely high density, complex hub layout).
*   **18.3 [Performance]** Assert critically that TBR successfully completes the complex NDLS->MMCT traversal in < 150ms.
*   **18.4 [Analysis]** Statistically compare the TBR route yield against the established RAPTOR yield (Expectation: TBR is higher or equal).
*   **18.5 [Audit]** Deeply audit the specific sequential Trip IDs returned to ensure they physically and temporally connect in reality.
*   **18.6 [Verification]** Test Scenario: MS -> MAS (Ultra-Short Haul terminal, expect 0 or direct-only behavior).
*   **18.7 [Improvement]** Programmatically tune the `traversal_budget` limits based strictly on the empirical solo audit findings.
*   **18.8 [Implementation]** Test Scenario: BPL -> RKMP (Micro transit, edge case for routing).
*   **18.9 [Audit]** Intentionally trigger timeouts to check for robust `TimeoutError` handling and graceful degradation logic.
*   **18.10 [Verification]** Output all detailed trace logs and route structures to `tbr_audit_v1.log`.

### Task 19: Combined Engine Performance Benchmarking
*   **19.1 [Implementation]** Update the core `audit_engines.py` script to include the new `TBR` component column.
*   **19.2 [Implementation]** Execute a full-scale run: `python audit_engines.py > engine_audit_v17.log`.
*   **19.3 [Performance]** Analyze the total Orchestrator end-to-end time (Goal: < 500ms target across all 5 parallel engines).
*   **19.4 [Analysis]** Determine the route overlap ratio: Calculate exactly how many totally unique routes TBR added to the final pool.
*   **19.5 [Audit]** Identify statistically if TBR and RAPTOR are performing massive amounts of duplicate computational work.
*   **19.6 [Verification]** Scan logs to ensure absolutely zero `NameError`, `TypeError`, or `AttributeError` tracebacks are present.
*   **19.7 [Improvement]** Strategic Decision: Disable traditional RAPTOR permanently if TBR proves consistently >10x faster and 100% topologically accurate.
*   **19.8 [Implementation]** Implement native memory profiling (`tracemalloc`) during the combined run to monitor garbage collection.
*   **19.9 [Audit]** Check for RAM spikes specifically caused by holding multiple large graph memory-maps in RAM simultaneously.
*   **19.10 [Verification]** Confirm the new `METRO_GROUPS` unified expansion logic functions flawlessly within the TBR environment.

### Task 20: TBR Edge-Case Handling & Production Readiness
*   **20.1 [Implementation]** Implement logic to handle "Circular Trips" safely (e.g., Delhi Ring Railway routes).
*   **20.2 [Implementation]** Handle "same-station overtakes" (e.g., Train A waits on a loop line while superfast Train B passes).
*   **20.3 [Performance]** Implement strict LRU caching specifically tailored for TBR's unique repeated graph lookup signatures.
*   **20.4 [Analysis]** Review system `SurgeLevel` degradation behavior under simulated high QPS load tests.
*   **20.5 [Audit]** Audit system log verbosity; strictly reduce internal DEBUG logs to INFO to prevent disk IO bottlenecks in production.
*   **20.6 [Verification]** Test engine behavior when the source `transit_graph.db` is completely empty or missing.
*   **20.7 [Improvement]** Add specific Prometheus observability metrics tracking `tbr_nodes_explored` and `tbr_branch_prunes`.
*   **20.8 [Implementation]** Add extensive Python Docstrings formally explaining the Trip-Based mathematical model to future maintainers.
*   **20.9 [Audit]** Conduct a final, comprehensive security sweep (ensuring no hardcoded DB credentials or secrets are exposed).
*   **20.10 [Verification]** Finalize the deployment PR and update the master `SYSTEM_EVOLUTION_REPORT.md` tracking document.