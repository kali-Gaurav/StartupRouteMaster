# 🛡️ Task 01: Unified Routing Orchestrator Hardening (Audit & Plan)

The objective is to fix all logical bugs across the routing engines and ensure "Discovery Yield" meets the SLA for multi-transfer routing (Target: 15/10/5).

## 🚀 25 Strategic Hardening Tasks

### 🧪 [Phase 1] Core Engine Logic & Stabilization (Tasks 01-10)
| Task | ID | Milestone | Description | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **01** | `RO-001` | **Graph Self-Healing** | Ensure `BaseRoutingEngine` handles `None` graph pointers in all methods via IoC fallback. | **CRITICAL** |
| **02** | `RO-002` | **Station Expansion** | Fix `src_ids` vs `src_id` mismatch in `RAPTOR` Round 0 to search all stations in a metropolitan cluster. | **HIGH** |
| **03** | `RO-003` | **Direct-SQL Fallback** | Implement automatic fallback in `TurboRouter` to query `UltraTurbo` (SQL) if Binary Index returns zero results. | **DONE** |
| **04** | `RO-004` | **Transfer Wait Window** | Fix `RAPTOR` fixed 15min transfer time; use `DynamicWaitConfig` from `request.constraints` to allow wider windows. | **DONE** |
| **05** | `RO-005` | **Async Thread Safety** | Audit all `asyncio.to_thread` calls in engines for potential race conditions during graph relocation. | **MED** |
| **06** | `RO-006` | **Bloom Detection** | Fix bitset overflow in `SearchRoute.v_bloom` for very long paths with >128 stations. | **LOW** |
| **07** | `RO-007` | **Pruning Threshold** | Tune `_global_min_arrival_mins` in `RAPTOR`; ensure it doesn't prune valid diverse routes prematurely. | **DONE** |
| **08** | `RO-008` | **TBR Edge Cache** | Verify `tbr_edge_builder` correctly persists transfer edges for ALL stop pairs in a cluster, not just base IDs. | **DONE** |
| **09** | `RO-010` | **FastPath BFS Depth** | Expand `FastPathRouter` to search up to 2-transfers when 0-TR yield is below the "Diversity Threshold" (10 routes). | **MED** |
| **10** | `RO-011` | **Reliability Scoring** | Integrate `reliability_scores` into `TBR` A* search cost function to prioritize on-time trains. | **MED** |

### 📊 [Phase 2] Data Integrity & Yield Audit (Tasks 11-18)
| Task | ID | Milestone | Description | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **11** | `RO-012` | **Bitset Verification** | Rebuild `_trip_reachability_bitset` using recursive DFS to ensure 100% reachability visibility (currently only ~1% coverage). | **CRITICAL** |
| **12** | `RO-013` | **Binary Fiber Index** | Standardize `V4` struct (16-bytes) for ALL engines; currently engines mix V3 and V4. | **HIGH** |
| **13** | `RO-014` | **Metro-Hub Remap** | Fix `HubTier0` to treat `NDLS`, `ANVT`, `NZM` as a single logical Hub for tier-0 discovery. | **HIGH** |
| **14** | `RO-015` | **Calendar Date Masking** | Audit `rebuild_turbo_index.py` for correct bitmasking of periodic trains (e.g. only Mon/Wed). | **HIGH** |
| **15** | `RO-016` | **Distance Continuity** | Fix zero-distance legs in results; ensure `dist_m` is cumulative across segments for correct fare calculation. | **MED** |
| **16** | `RO-017` | **Pattern Compression** | Validate `StaticGraphSnapshot` pattern deduplication; ensure no loss of unique departure timings. | **LOW** |
| **17** | `RO-018` | **Fare Coverage** | Link `precompute_all_fares.py` outputs into the search results for real-time pricing without SQL calls. | **MED** |
| **18** | `RO-019` | **Stale Trip Cleanup** | Implement automated cleanup of orphaned `stop_times` without corresponding `trips` in index scripts. | **MED** |

### 🌪️ [Phase 3] Performance & Orchestration (Tasks 19-25)
| Task | ID | Milestone | Description | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **19** | `RO-020` | **Results Blending** | Optimize orchestrator's `deduplicate_all`; sort final results by `GeneralizedCost` (Time + Cost + Wait). | **HIGH** |
| **20** | `RO-021` | **Circuit Breaker** | Tune `EngineCircuitBreaker` thresholds; prevent one slow engine from delaying the entire streaming response. | **HIGH** |
| **21** | `RO-022` | **Adaptive Budgeting** | Dynamically scale `traversal_budget` based on request load (Elastic Scaling). | **MED** |
| **22** | `RO-023` | **JIT Pre-warming** | Warm the `_hub_adj_cache` in the background for common source stations (NDLS, MMCT, HWH). | **LOW** |
| **23** | `RO-024` | **Parallel Hydration** | Move `_hydrate_route` into a `ProcessPoolExecutor` to avoid blocking the Event Loop for large result sets. | **HIGH** |
| **24** | `RO-025` | **SLA Verification** | Script to verify 1.2s SLA for 2-transfer journeys; automate performance regression tests. | **CRITICAL** |
| **25** | `RO-026` | **Real-time Re-routing** | Trigger a fresh `RAPTOR` search automatically if a primary train is marked `CANCELLED` during overlay sync. | **CRITICAL** |

---

## 🛠️ Task RO-001 (Unified Graph Self-Healing) - DONE
*   **Audit**: Analyzed `RAPTOR`, `FastPath`, and `TBR`.
*   **Finding**: Engines fail if `request.graph` is null.
*   **Fix**: Standardize `__init__` to carry `graph` pointer and `find_routes` to self-hydrate.

## 🛠️ Task RO-002 (RAPTOR Station Expansion Yield) - DONE
*   **Audit**: `RAPTOR` Round 0 only uses the first ID in the cluster.
*   **Fix**: Iterate over `src_cluster_ids` in Round 0.
