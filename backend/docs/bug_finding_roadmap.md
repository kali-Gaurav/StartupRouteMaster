# 🐞 RouteMaster Bug-Hunting Roadmap (25 Macro-Scale Features)

This document outlines the 25 most critical macro-scale features of the RouteMaster ecosystem that require deep investigative testing and hardening.

| ID | Feature Area | Description | Priority |
| :--- | :--- | :--- | :--- |
| **01** | **Unified Routing Orchestrator** | Central logic for multi-engine orchestration and result blending. | **CRITICAL** |
| 02 | **RAPTOR Engine (v3)** | Round-based Pareto discovery with elastic frontiers. | **CRITICAL** |
| 03 | **UltraTurbo Direct & Hop** | SQL-based sub-100ms greedy routing. | HIGH |
| 04 | **Trip-Based Routing (TBR)** | Edge-graph based transfer discovery. | HIGH |
| 05 | **Nexus Resource Governor** | Load-shedding, adaptive throttling, and 503-prevention. | **CRITICAL** |
| 06 | **Real-time Scraper (NTES)** | Live delay fetching and error-resilient parsing. | MEDIUM |
| 07 | **Seat Availability & Fares** | Quota-aware availability and fare calculation pipeline. | HIGH |
| 08 | **Multi-Modal Hub Clusters** | Station grouping logic (e.g., NDLS/NZM/ANVT). | MEDIUM |
| 09 | **Financial Ledger (Audit)** | Parity checks, hash-chain integrity, and transaction atomicity. | **CRITICAL** |
| 10 | **SOS Lifecycle Management** | End-to-end emergency alerting and trigger logic. | **CRITICAL** |
| 11 | **Guardian Protocol** | Proactive location-based monitoring. | HIGH |
| 12 | **Station Search / Auto-Complete** | Spatial ranking, fuzzy matching, and latency optimization. | MEDIUM |
| 13 | **Chatbot Intent NLP Brain** | Local + Remote NLP for travel intent categorization. | HIGH |
| 14 | **WebSocket Layer (Streaming)** | Stream stability, frame-drops, and heartbeat resilience. | MEDIUM |
| 15 | **User Auth (Supabase/JWT)** | Token expiry, multi-session collisions, and ACLs. | HIGH |
| 16 | **Search Pre-Warmer (Ghost)** | Graph-loading JIT and cold-start optimization. | MEDIUM |
| 17 | **Multi-Layer Cache (L1/L2)** | Redis/Local-Mem consistency and TTL drift. | HIGH |
| 18 | **Neural Pruning Model** | Pruning model reliability and "False Negative" prevention. | MEDIUM |
| 19 | **Predictive Delay Engine** | ML model accuracy and historical data drift. | MEDIUM |
| 20 | **ETL & GTFS Lifecycle** | Data integrity during weekly graph updates. | MEDIUM |
| 21 | **Circuit Breaker System** | Rapid-fail performance and fallback consistency. | HIGH |
| 22 | **Observability Metrics** | Prometheus/Grafana accuracy and alert-noise reduction. | MEDIUM |
| 23 | **Telegram Mini-App Integration** | Session handoff and WebView state persistence. | LOW |
| 24 | **Frontend State (TanStack)** | Query invalidation and stale-data re-fetching logic. | MEDIUM |
| 25 | **Cyber-Security (Sentinel)** | SSL expiry, patch versioning, and endpoint hardening. | MEDIUM |

---

# 🔎 Feature #1: Unified Routing Orchestrator
## 50 Granular Sub-Task TODOs for Bug Discovery & Enforcement

The Orchestrator is the central brain. We will test every micro-logic branch independently.

### 🧪 Stage 1: Initialization & Request Integrity (1-10)
1. **[TODO-01] Strict Pydantic Schema**: Force `RoutingRequest` validation on every entry point to prevent `KeyError` at runtime.
2. **[TODO-02] Station Resolve Guard**: Implement explicit check for `None` from `resolve_stations` and return descriptive `404` metadata.
3. **[TODO-03] Cluster ID Hash Uniqueness**: Verify that `src_cluster_ids` are unique and sorted to optimize SQL `IN` clauses.
4. **[TODO-04] Default Persona Fallback**: Verify that a request without a persona defaults to `Standard` with pre-defined weights.
5. **[TODO-05] lazy-Engine Warmup Check**: Ensure heavy engines (TBR/RAPTOR) are fully loaded before searching or skipped if cold.
6. **[TODO-06] Session Context Isolation**: Verify that `_owned_session` is strictly localized and closed in all failure modes.
7. **[TODO-07] TraceID Propagation**: Ensure `correlation_id` is present in every log line from Orchestrator -> Engines -> Hydration.
8. **[TODO-08] Graph Snapshot Verifier**: Verify the Orchestrator doesn't start a search if the Graph timestamp is > 7 days old.
9. **[TODO-09] Resource Semaphore Pressure**: Test behavior when `_global_resource_sem` is saturated (11+ concurrent heavy queries).
10. **[TODO-10] Thread/Process Pool Health**: Monitor `ROUTING_POOL` for deadlocks during high-concurrency surge.

### ⚡ Stage 2: Concurrent Execution & Adaptive Control (11-20)
11. **[TODO-11] Elastic Task staggering**: Verify `asyncio.sleep(0.005 * priority)` correctly orders engine execution.
12. **[TODO-12] Remaining Deadline Inheritance**: Check that `remaining_timeout` is passed to all sub-engines for internal pruning.
13. **[TODO-13] Engine Timeout Truncation**: Force an engine to hit its `0.9 * timeout` limit and verify the Orchestrator survives.
14. **[TODO-14] TaskGroup Error Shielding**: Verify that one engine's catastrophic crash doesn't cancel siblings in the `asyncio.TaskGroup`.
15. **[TODO-15] Partial Result Streaming**: Verify that `stream_all_tiers` yields results as they arrive, not in one final block.
16. **[TODO-16] Orphaned Engine Cleanup**: Verify that if a user cancels a request, all background engine tasks are physically stopped.
17. **[TODO-17] Progress callback Throttling**: Cap `on_progress` calls to once per 100ms to avoid UI thread starvation.
18. **[TODO-18] High-Res Latency Telemetry**: Verify `latency_ms` calculation against external wall-clock measurements.
19. **[TODO-19] Surge Level Logic**: Trigger `Level.CRITICAL` and verify RAPTOR is skipped automatically.
20. **[TODO-20] Governor Stat Jitter**: Ensure `get_stats()` doesn't add significant latency to the routing startup.

### 🧩 Stage 3: Result Merging & Deduplication (21-30)
21. **[TODO-21] Journey ID Hash Entropy**: Search for routes with same trains but different stop sequences to ensure ID uniqueness.
22. **[TODO-22] Segment-Level Data Collision**: Verify that the merge logic keeps the segment with the most metadata (Live info > GTFS).
23. **[TODO-23] Multi-Engine Discovery Attribution**: Verify `discovered_by` set contains names of every engine that found the journey.
24. **[TODO-24] Score Tie-Breaking Logic**: Ensure that if two routes have identical scores, the one with fewer transfers is preferred.
25. **[TODO-25] Station De-aliasing logic**: Verify `NDLS` and `NZM` cross-discovery doesn't group them into the same journey ID.
26. **[TODO-26] Empty Result propagation**: Test that 0-result searches return `[]` and not `None` or `500`.
27. **[TODO-27] Sorting Monotonicity (Fast)**: For `FAST` persona, verify results are strictly sorted by `total_duration`.
28. **[TODO-28] Sorting Monotonicity (Budget)**: For `BUDGET` persona, verify results are strictly sorted by `total_cost`.
29. **[TODO-29] Limit-Based Early Exit**: If 50 results are found, verify the Orchestrator doesn't trigger extra "Relaxed" phases.
30. **[TODO-30] Deduplication Memory Leak**: Monitor RAM usage after 1000 merged results to ensure `unique_map` is cleared.

### 🧪 Stage 4: Hydration & Business Logic (31-40)
31. **[TODO-31] Real-time Delay propagation**: Verify timestamps are updated correctly in `RouteSegment` metadata.
32. **[TODO-32] Transfer Guard Invalidation**: Ensure routes become invalid if a live delay shrinks a transfer to < 5 minutes.
33. **[TODO-33] Platform Heuristic Accuracy**: Verify "Historical" vs "Live" platform labels in segment metadata.
34. **[TODO-34] Amenity Flag verification**: Test if `12XXX` Rajdhani/Shatabdi trains get `has_pantry=True`.
35. **[TODO-35] Dynamic Fare Calculation**: Verify fallback pricing (200 + durability/2) matches expected range.
36. **[TODO-36] Night-time Wait Penalty**: Verify 1.5x score penalty for transfers between 01:00 and 04:00 AM.
37. **[TODO-37] Multi-Station City Hassle**: Test the `2000` point penalty for city station changes (e.g. NDLS to ANVT).
38. **[TODO-38] Reliability Badge thresholds**: High (>0.9), Average, and Critical (<0.8 after delay).
39. **[TODO-39] Journey Story Template Drift**: Verify that `journey_story` parts (Overnight, Very Fast, etc) aren't redundant.
40. **[TODO-40] Integrity Check cost-resets**: Ensure cost never settles at `0.0` or `None` in the final output.

### 🛡️ Stage 5: Resilience & Final Optimization (41-50)
41. **[TODO-41] Circuit Breaker Triage**: Verify that a `Timeout` increments the circuit differently than a `RuntimeError`.
42. **[TODO-42] Engine Throttler PID Check**: Verify `throttlers` correctly reduce the search breadth after a latency spike.
43. **[TODO-43] Circular Path detection**: Prune routes where a station is visited twice (A -> B -> A).
44. **[TODO-44] GTFS Date Crossover logic**: Verify searching for a train at 23:55 doesn't break daily calendar logic.
45. **[TODO-45] Large Response Serialization**: Verify JSON serialization performance for responses with 250+ segments.
46. **[TODO-46] Redis L2 Cache drift**: Ensure cache TTL is aligned with the Scraper's update frequency.
47. **[TODO-47] Model Inference Latency**: Verify `journey_story_model.predict_sync` doesn't exceed 10ms per route.
48. **[TODO-48] Hydration Stats Transparency**: Check that each route contains the `hydration_stats` for latency auditing.
49. **[TODO-49] Empty Leg Pruning**: Ensure `Route.validate()` catches segments with 0 duration or SRC==DST.
50. **[TODO-50] Final Frontend Parity**: Verify the Orchestrator output strictly matches the `SearchResponse` schema used in the UI.
