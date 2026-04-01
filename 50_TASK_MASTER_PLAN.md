# 50-TASK MASTER PLAN: ENGINE YIELD MAXIMIZATION
**Framework:** GSD (Get Stuff Done) + RALPH (Recursive Augmentation Loop) + CodeRabbit  
**Phase:** Complete (Tasks 1-50) | **Subtasks:** 500 total | **Duration:** 14-21 days

---

## TASK GROUP 1: ANALYSIS & MEASUREMENT (Tasks 1-10)
### Goal: Complete baseline understanding + metrics infrastructure

---

### TASK 1: Baseline Yield Fingerprinting Across Route Categories
**Objective:** Measure current yield (0/1/2/3-TR) for 10+ distinct route types  
**Priority:** CRITICAL | **Owner:** Measurement Lead

**Subtask 1.1:** Create 50 test pairs spanning distance categories
- Short-distance (0-100km): GKP→NZM, ASN→AGC, SWM→CSN, etc.
- Medium (100-500km): NDLS→MMCT, HWH→SBC, MAS→KOL, etc.
- Long (500-2000km): GKP→TVC, ASN→PNBE, BZA→BSB, etc.
- Validate representativeness against production traffic

**Subtask 1.2:** Build instrumented test runner with per-engine metrics
- Accepts (src, dst, date) tuples
- Runs each engine in isolation (no orchestration interference)
- Captures: latency, yields by transfer tier, execution budget used
- Output: CSV with schema `(route_id, engine, latency_ms, yield_0, yield_1, yield_2, yield_3, budget_pct)`

**Subtask 1.3:** Baseline measurement: run 50 pairs × 6 engines
- Ultra-Turbo, Turbo, RAPTOR, TBR, FastPath, Hub
- Record start datetime, CPU%, RAM%, governor_pressure per run
- Store to `baseline_yield_2026-04-01.csv`

**Subtask 1.4:** Breakdown bottleneck engine per tier
- Identify which tier has >0 yield for 1/2/3-TR
- Identify which tier has stuck at 0 yield
- Create "deficit map": (tier, route_type, transfer_level) → current_yield vs. goal

**Subtask 1.5:** Measure governor pressure impact
- Run same 50 pairs at different system load levels (simulate via sleep)
- Capture pressure multiplier (CPU-based) during each run
- Plot: yield vs. pressure for RAPTOR/TBR (identify throttle threshold)

**Subtask 1.6:** Quantify quota impact on TBR
- Run TBR with varying `quotas = {0: X, 1: Y, 2: Z, 3: W}`
- Test: (100, 50, 30, 20), (200, 100, 50, 30), (500, 200, 100, 50)
- Measure: yield per tier, execution time, when early exit triggered

**Subtask 1.7:** Measure dominance pruning aggression
- Add instrumentation to TBR dominance checks (`3.0x multiplier`)
- For each candidate path, log: rejected_count, cost_ratio, transfer_count
- Identify: proportion of paths filtered per transfer_tier

**Subtask 1.8:** Check transfer discovery completeness
- Measure: how many valid transfers (15-min+ buffer) found per stop
- Compare graph.get_transfers_from_stop() results vs. union of all possible 
- Identify: coverage gaps (e.g., metro transfers not discovered)

**Subtask 1.9:** Log budget exhaustion patterns
- Add debug logging to RAPTOR/TBR budget tracking
- Record: budget_start, nodes_explored, budget_remaining at termination
- Identify: percentage of runs hitting budget ceiling

**Subtask 1.10:** Compile baseline analytics HTML dashboard
- Show all 50 test pairs: current vs. goal yield
- Heat-map: pressure × transfer_level for each engine
- Export: `baseline_analytics_2026-04-01.html`

---

### TASK 2: Governor Pressure Model Deep-Dive
**Objective:** Understand exact thresholds & pressure calculation  
**Priority:** CRITICAL | **Owner:** System Lead

**Subtask 2.1:** Map current pressure thresholds in codebase
- Find all conditionals using `if pressure > X%` or multiplier formulas
- List: (file, line, threshold, consequence) tuples
- Currently: raptor.py:435 (60% → disable 2/3-TR), others?

**Subtask 2.2:** Measure actual system pressure over 48 hours
- Run monitoring script: every 5 min, log (CPU%, RAM%, disk_io%, network_io%)
- Tag: peak hours (7-11am, 4-8pm), off-peak, night
- Determine: realistic operating ranges
- Output: `pressure_profile_48h.csv`

**Subtask 2.3:** Add pressure override switches
- Create `RouteConstraints.pressure_override_mode` with options:
  - None (default, respect governor)
  - Force_deep (ignore throttle, run full RAPTOR)
  - Force_light (prioritize latency over yield)
- Test all 50 pairs under each mode

**Subtask 2.4:** Build pressure-aware budget calculator
- Replace: fixed `max_transfers = 3` with dynamic
- Logic: `effective_max_transfers = 3 - floor(pressure * 2)` (capped at 0)
- Test: measure yield/latency tradeoff across pressure range

**Subtask 2.5:** Check CPU contention under load
- Hypothesis: Nexus 2vCPU → background I/O contention
- Run single search + parallel synthetic workload
- Measure: jitter in execution time, pressure reading accuracy

**Subtask 2.6:** Create pressure escalation timeline
- Map: time-of-day → expected pressure
- Define: hour-by-month heuristic (April 9am = 75% historical avg)
- Use for: pre-emptive optimization before peak load

**Subtask 2.7:** Instrument governor.py directly
- Add fine-grained logging: CPU sample, RAM free, calculate pressure
- Log transitions: entering high-pressure state, leaving it
- Measure: false positive rate (throttles but pressure drops mid-search)

**Subtask 2.8:** Compare pressure calculation methods
- Current: simple CPU-based
- Alternative: (CPU × 0.4 + RAM% × 0.4 + disk_io% × 0.2)
- Alternative: (CPU × 1.0 if spike detected, else CPU × 0.5)
- Measure: which correlates best with search breakdown

**Subtask 2.9:** Build "pressure forecast" for next 6 hours
- Use last 24h history to predict 6-hour trend
- If predicted pressure > 75% at time T → trigger pre-caching
- Export: `pressure_forecast_daily.json`

**Subtask 2.10:** Document threshold recommendations
- Based on experiments, propose:
  - "Safe" threshold (90th %ile of normal): X%
  - "Warning" threshold (10% headroom): Y%
  - "Critical" threshold (disable heavy ops): Z%
- Recommend per-hour SLA adjustment (not global threshold)

---

### TASK 3: Transfer Graph Completeness Audit
**Objective:** Ensure all valid transfers discoverable  
**Priority:** HIGH | **Owner:** Data Lead

**Subtask 3.1:** Validate explicit transfers from DB
- Query `transfers` table: count by transfer_type
- Validate: min_transfer_time >= 0, stop_id exists
- Check: any transfers with "impossible" designation (type 3)
- Output: `transfers_validation_report.txt`

**Subtask 3.2:** Audit implicit transfer discovery (BallTree)
- Extract: all resolved (NDLS, MMCT) stop pairs
- For each stop in both cities, verify:</span>
  - 5km BallTree discovers all same-city stops
  - Walk time calculation: speed 3.5 km/h applied correctly
  - Tier penalties applied (MEGA=40m, MAJOR=25m, etc.)

**Subtask 3.3:** Cross-check transfer gaps
- Union: all explicit + implicit transfers found
- Compare against manual inspection (e.g., metro lines known routes)
- Identify: missing transfers (e.g., two major hubs 2km apart not connected)

**Subtask 3.4:** Measure per-stop transfer density
- For NDLS, MMCT, intermediate hubs (15+): count available transfers
- Threshold check: if <5 transfers, flag as "isolated"
- Recommend: manual transfer insertion for isolated major stops

**Subtask 3.5:** Test transfer validation logic
- Simulate edge cases:
  - Transfer arrival < departure (invalid)
  - Transfer walk time > 1 hour (unrealistic)
  - Transfer across incompatible modes (e.g., track gauge mismatch)
- Verify: rejection or handling

**Subtask 3.6:** Audit transfer_graph_builder.py logic
- Walk through BallTree construction:
  - Input: all stops for NDLS, MMCT regions
  - Radius: 5km, what if reduced to 3km? 10km?
  - Test: radius variation impact on transfer count

**Subtask 3.7:** Check mmap transfer persistence
- Verify: transfer data loaded correctly from disk
- Test: index integrity (no stale offsets)
- Measure: lookup speed (should be <100μs per stop)

**Subtask 3.8:** Create transfer quality score
- Score formula: `quality = availability × buffer_comfort × network_redundancy`
  - availability: how many daily departures
  - buffer_comfort: minutes beyond minimum (15m cushion target)
  - redundancy: alternative transfers at same stop
- Rank transfers: prefer high-quality ones

**Subtask 3.9:** Verify intermediate hub clustering
- For NDLS→MMCT journeys, identify: which intermediate hubs most valuable
- Measure: if intermediate X removed, how many routes lost?
- Recommend: priority hubs for transfer heavy-lifting

**Subtask 3.10:** Document transfer discovery defects
- Create: list of (stop_pair, missing_transfer, reason, recommendation)
- Prioritize: high-impact missing transfers
- Plan: manual override data entry

---

### TASK 4: Engine Tier Isolation & Profiling
**Objective:** Understand each engine independently  
**Priority:** HIGH | **Owner:** Engine Lead

**Subtask 4.1:** Create per-engine test harness
- Bypass orchestrator; call each engine directly
- Inject mock graph/constraints for determinism
- Measure: pure engine latency (no overhead)

**Subtask 4.2:** Profile UltraTurbo yields
- Direct SQL mode: test all 50 route pairs
- Record: yield_0, latency, SQL execution time
- Identify: is 0-yield due to SQL or filtering?

**Subtask 4.3:** Profile TurboRouter yields
- Hub-centric mode: trigger 1-transfer path
- Measure: cache hit rate, SQL fallback frequency
- Identify: why 0 multi-transfer

**Subtask 4.4:** Profile FastPathRouter yields
- BFS 2-hub mode: test conditional trigger (`len(direct_routes) < 5`)
- Measure: how often triggered for 50 pairs?
- Identify: scope of FastPath (should it handle 1-transfer actively?)

**Subtask 4.5:** Profile RAPTOR yields
- Run with pressure=0% (no throttle), full budget
- Measure: yield per round (0-TR after round 0, total after round 1, etc.)
- Plot: cumulative yield by round

**Subtask 4.6:** Profile TBR yields
- Run with base quotas: {0: 100, 1: 50, 2: 30, 3: 20}
- Measure: at what point does each quota ceiling hit?
- Identify: if quota increased to {100, 100, 100, 100}, yield changes?

**Subtask 4.7:** Check FrontierPruning in RAPTOR
- Log: per-round, how many labels per stop kept after pruning
- Measure: label count distribution (min, max, mean, std)
- Verify: elastic multipliers {1.0, 3.0, 6.0, 9.0} applied correctly

**Subtask 4.8:** Check Dominance Pruning in TBR
- Log: cost comparisons, when `3.0x multiplier` rejects paths
- Measure: rejection rate per transfer tier
- Estimate: yield uplift if multiplier → 5.0x or 10.0x

**Subtask 4.9:** Memory footprint per engine
- UltraTurbo: SQL query only (negligible)
- TurboRouter: hub cache size
- RAPTOR: frontier arrays, marking bitsets
- TBR: mmap indices, label storage
- Estimate total: can we run all tiers in parallel on 8GB?

**Subtask 4.10:** Create engine capability matrix
- Per engine: (0-TR, 1-TR, 2-TR, 3-TR) → working / partial / broken
- Include trade-offs: speed vs. completeness
- Recommend: which tiers to prioritize for fixes

---

### TASK 5: Budget & Quota Impact Sensitivity Analysis
**Objective:** Quantify yield response to parameter tuning  
**Priority:** MEDIUM | **Owner:** Optimization Lead

**Subtask 5.1:** RAPTOR budget sweep
- Vary `traversal_budget` from 1k to 500k nodes
- Measure: yield, latency per value
- Determine: optimal sweet spot (yield ≥ goals, latency ≤ target)

**Subtask 5.2:** TBR budget sweep
- Vary `traversal_budget` from 10k to 1M nodes
- Same metrics as 5.1
- Compare curves: RAPTOR vs. TBR efficiency

**Subtask 5.3:** Quota sensitivity analysis
- Create matrix: `quota_0=50..500, quota_1=10..150, quota_2=5..100, quota_3=3..50`
- For each combination: measure yield, early-exit rate
- Plot 2D heatmap: quota_1 vs. quota_2 → yield_1, yield_2 (all 50 route pairs)

**Subtask 5.4:** Frontier multiplier sweep (RAPTOR)
- Vary multiplier set: {1.0, 3.0, 6.0, 9.0} → {1.0, 5.0, 10.0, 15.0} (and in-between)
- Measure: label diversity, yield, latency
- Goal: identify multipliers that improve yield without blowing latency

**Subtask 5.5:** Dominance factor sweep (TBR)
- Vary `3.0x multiplier` from 1.5x to 20.0x
- Measure: path rejection rate, final yield, quality
- Plot: dominance_factor vs. yield per transfer_tier

**Subtask 5.6:** Min transfer time flexibility
- Test: varying `min_transfer_time` from 5min to 60min
- Measure: how many additional routes become possible
- Recommendation: per-stop minimum (major hubs =30m, small =15m)?

**Subtask 5.7:** Governor pressure threshold sweep
- Vary throttle threshold from 40% to 90%
- Measure: at each threshold, what's yielded during peak hours
- Identify: breakeven point (yield gain ≥ latency cost)

**Subtask 5.8:** Neural pruner buffer sweep
- Vary `max_arrival_buffer` from 30min to 480min
- Measure: how many additional long-duration routes survive
- Trade-off: user experience (prefer shorter) vs. completeness

**Subtask 5.9:** Orchestrator result cap sweep
- Vary return limit from 50 to 500 routes
- Measure: user satisfaction (do they browse beyond 100?)
- Recommendation: optimal cap balancing completeness + performance

**Subtask 5.10:** Create sensitivity summary
- 2x2 matrix per parameter: sensitivity table (base ↔ 2x value, yield Δ)
- Rank parameters by yield impact: dominance_factor > quota_2 > frontier > ...
- Prioritize: focus fixes on highest-impact params first

---

### TASK 6: Latency Budget Allocation
**Objective:** Understand where time is spent; optimize allocation  
**Priority:** MEDIUM | **Owner:** Performance Lead

**Subtask 6.1:** Instrument latency breakdown
- Add timing hooks to each engine:
  - Graph query setup
  - Initialization (arrays, caches)
  - Main search loop
  - Result filtering
  - Serialization
- Output: JSON with per-phase latency

**Subtask 6.2:** Profile RAPTOR phases
- Round 0 (direct): expected <50ms
- Rounds 1-3 (transfers): expected 400-800ms each
- Identify: which round consumes most time?

**Subtask 6.3:** Profile TBR phases
- Seed queue: expected <10ms
- A* iteration: expected 600-1000ms
- Transfer edge lookups, cost calc: count operations
- Estimate: algorithmic complexity, opportunity for Cython/Numba

**Subtask 6.4:** Measure graph query latencies
- `get_departures_from_stop()`: how long?
- `get_pattern_segments()`: how long?
- `get_transfers_from_stop()`: how long?
- Identify: which queries are slow, could cache/precompute?

**Subtask 6.5:** Orchestrator overhead profiling
- Circuit breaker checks: <1ms? ✓
- Throttler updates: <1ms? ✓
- Result deduplication: linear in result count?
- Streaming filter: overhead per route?

**Subtask 6.6:** Check I/O contention
- Run search with disk activity monitor
- Is mmap causing page faults during search?
- Recommendation: pre-load common indices into memory?

**Subtask 6.7:** Measure serialization cost
- Convert Route → JSON: time
- For 100 routes: expected latency
- Is this the tail latency driver for large result sets?

**Subtask 6.8:** Check memory access patterns
- Is numpy array layout cache-friendly?
- Cost of random stops vs. sequential scan?
- Opportunity: optimize array layout (AoS vs. SoA)?

**Subtask 6.9:** Build tier latency targets table
- Based on measurements, define realistic target per tier
- E.g., RAPTOR: 900ms (not 800ms if beats 1s budget OK)
- Use: SLA monitoring (did we hit target?)

**Subtask 6.10:** Create latency breakdown visualization
- Pie chart: % time per phase (RAPTOR: round0=5%, round1=30%, round2=35%, etc.)
- Stacked bar: how does breakdown change with distance/transfer_count?
- Identify: optimization priorities (biggest time consumers)

---

### TASK 7: Production Traffic Simulation
**Objective:** Test plan changes against realistic workload  
**Priority:** HIGH | **Owner:** QA Lead

**Subtask 7.1:** Extract recent query patterns
- Sample from `search_logs` table: last 24h
- Aggregate by (source_code, destination_code, hour_of_day)
- Top 100 pairs: frequencies, time distributions

**Subtask 7.2:** Build synthetic traffic generator
- Script: reads top 100 pairs, simulates requests at realistic rate
- Time-of-day aware: ramp up 8-10am, 4-6pm, etc.
- Output: request queue with timestamps

**Subtask 7.3:** Run baseline against synthetic traffic
- Execute current engine config under synthetic load
- Measure: tail latencies (p50, p95, p99), yield distribution
- Record: database load (query count, I/O), CPU/RAM

**Subtask 7.4:** Identify hottest pairs
- From sorted frequency list: pick top 10 pairs
- These will be primary test targets for optimization

**Subtask 7.5:** Create mini test suite (10 pairs + synthetic load)
- Lightweight: can run every hour locally
- Captures: key metrics (latency, yield, resource use)
- Goal: quick regression detection

**Subtask 7.6:** Test orchestrator under parallel requests
- Send 10 identical requests to same engine pair
- Measure: does load cause performance degradation?
- Identify: if circuit breakers trip under load

**Subtask 7.7:** Measure cache effectiveness
- TurboRouter hub cache: hit rate under traffic
- Graph snapshot: how often reloaded?
- Optimization: cache retention strategies?

**Subtask 7.8:** Check database connection pool saturation
- Monitor: active connections during peak traffic
- If (active >> pool_size): implement request queuing?
- Measure: connection pool saturation impact on latency

**Subtask 7.9:** Simulate "load_more" cascade effect
- User performs 1st search, browses 10 results
- Then clicks "load more" → 2nd search more expensive
- Measure: compound latency (both requests), resource spikes

**Subtask 7.10:** Build traffic simulation with A/B variants
- Run variant A (current config) vs. B (proposed changes)
- Side-by-side load testing: same traffic
- Measure: yield improvement % vs. latency cost %

---

### TASK 8: Neural Pruner Effectiveness Audit
**Objective:** Understand pruning impact; identify over-pruning  
**Priority:** MEDIUM | **Owner:** Data Lead

**Subtask 8.1:** Extract pruner logic review
- File: [neural_pruner.py](backend/core/route_engine/neural_pruner.py)
- Understand: feature inputs, ML model, pruning decision
- Document: model assumptions (assumes short journeys preferred?)

**Subtask 8.2:** Add pruner instrumentation
- Log: each route evaluated, pruner decision (keep / reject), score
- Aggregate: precision, recall (is pruning too harsh?)
- Output: CSV of (journey_id, actual_rank_if_kept, pruned_y_n, user_clicked_y_n)

**Subtask 8.3:** Run neural pruner on 50 test pairs
- Measure: what % of routes pruned?
- Per transfer_tier: how many removed?
- If pruner removes >50% at 2/3-TR, it's blocking yield

**Subtask 8.4:** Analyze pruner feature importance
- Which features most predictive of user click?
- Are multi-transfer routes under-valued in model?
- Recommendation: re-train with multi-transfer examples?

**Subtask 8.5:** Test alternative pruning strategy
- Replace neural model with simpler heuristic: keep if (arrival < baseline + 4h)
- Measure: yield, user satisfaction (if logged)
- Trade-off: simplicity vs. accuracy?

**Subtask 8.6:** Create pruner bypass mode
- Add constraint.pruner_disabled flag
- For "load_more" queries: disable neural pruner
- Measure: unleashed yield vs. latency cost

**Subtask 8.7:** Measure pruner latency overhead
- How long does model inference take (1 route)?
- For 100 candidates: total pruner time?
- If >10% of total time: optimize

**Subtask 8.8:** Check buffer calculation logic
- Pruner uses: `max(30, 240 * (1 - pressure))`
- At 80% pressure → 30m buffer (harsh!)
- Recommendation: min buffer should be 120m (2h)?

**Subtask 8.9:** Build pruner sensitivity sweep
- Vary buffer from 30m to 480m
- Measure: yield removed per transfer_tier
- Identify: what buffer targets goal (minimal pruning, acceptable latency)?

**Subtask 8.10:** Document pruner recommendations
- Keep: neural pruner for Tier 1 results (deterministic ranking)
- Bypass: for "load_more" queries (user explicitly wants variety)
- Retrain: model with multi-transfer as positive examples

---

### TASK 9: Database Query Optimization Audit
**Objective:** Maximize DB throughput for fast engine tiers  
**Priority:** MEDIUM | **Owner:** DB Lead

**Subtask 9.1:** Profile current SQL queries
- UltraTurbo direct SQL: explain plan, execution time
- TurboRouter hub SQL: identify N+1 queries
- Add EXPLAIN ANALYZE to slow queries
- Document: indexes used, full-table scans?

**Subtask 9.2:** Check index coverage
- Verify: indexes exist for (stop_id, departure_date, calendar_id)
- Verify: indexes on transfers (from_stop_id)
- Recommend: composite indexes if missing

**Subtask 9.3:** Measure connection pool efficiency
- Current pool size: adequate?
- During peak: are requests queuing?
- Recommendation: pool size for 8GB instance?

**Subtask 9.4:** Audit caching strategies
- UltraTurbo: cache direct results per (src, dst, date)?
- TurboRouter: hub adjacency cache TTL sufficient?
- Measure: cache hit rates

**Subtask 9.5:** Check batch query opportunities
- Instead of N separate queries for N stops: can batching help?
- E.g., bulk fetch transfers for all intermediate hubs at once
- Measure: latency savings

**Subtask 9.6:** Optimize WHERE clause order
- Most selective filters first (stop_id before calendar)?
- Push predicates to DB (don't filter in app)?

**Subtask 9.7:** Evaluate partial indices
- E.g., index on (departure_date, stop_id) WHERE active = true
- Smaller indices, faster scans
- Measure: query planner preference?

**Subtask 9.8:** Profile transaction overhead
- Are too many small transactions causing I/O?
- Can we batch reads into single transaction?

**Subtask 9.9:** Check vacuum/autovacuum stats
- Is the table fragmented?
- Run: ANALYZE, VACUUM to baseline
- Schedule: autovacuum timing?

**Subtask 9.10:** Create DB tuning checklist
- Recommended settings: shared_buffers, work_mem, effective_cache_size
- For 8GB instance: what's optimal?
- Plan: apply settings, measure throughput delta

---

### TASK 10: Monitoring & Metrics Infrastructure
**Objective:** Build foundation for ongoing yield tracking  
**Priority:** HIGH | **Owner:** Ops Lead

**Subtask 10.1:** Design yield SLA dashboard
- Metrics: yield_0, yield_1, yield_2, yield_3 per engine
- Time-series: hourly aggregation
- Threshold: red if below goal (15/10/7), yellow if ≥80% of goal
- First version: CSV export, manual load to dashboard

**Subtask 10.2:** Create latency SLA dashboard
- Metrics: p50, p95, p99 per tier per route_type
- Threshold: red if exceeds target
- Time-series: 5-min granularity during peak hours

**Subtask 10.3:** Build pressure monitoring dashboard
- Real-time: CPU%, RAM%, disk I/O%, network I/O%
- Aggregates: peak hour forecast, current trend
- Integration: alert if pressure > 75% (early warning)

**Subtask 10.4:** Create error rate monitoring
- Log: engine exceptions, timeouts, graph misses
- Aggregate by engine, route_type, hour_of_day
- Dashboard: error rate % by category

**Subtask 10.5:** Implement budget tracking per search
- Log to DB: (search_id, engine, budget_allocated, budget_used, budget_pct)
- Aggregate: per-engine budget utilization distribution
- Alert: if > 90% of searches hit budget ceiling

**Subtask 10.6:** Create quota tracking per search
- Log: (search_id, engine, transfer_tier, quota_allocated, results_found, quota_pct)
- Aggregate: per-engine quota utilization distribution
- Alert: if early-exit triggered >50% of time

**Subtask 10.7:** Implement per-engine health checks
- Periodic runs: test pair (NDLS→MMCT) through each engine
- Alert: if yield drops >10% vs. baseline
- Log: timestamp, engine, new_yield, old_yield, delta%

**Subtask 10.8:** Create operational runbook
- Document: what each dashboard metric means
- Actions: if yield drops, if latency spikes, if pressure high
- Escalation: notify owner if threshold breached

**Subtask 10.9:** Build experiment log system
- When we change parameters (guidance, quota, frontier), log it
- Auto-tag: with parameter values, date, expected impact
- Measure: pre/post metrics for A/B comparison

**Subtask 10.10:** Plan alerting integration
- Slack/email alerts for SLA breaches
- Daily summary report: yield status, trends
- Weekly deep-dive: regression analysis, root causes

---

## TASK GROUP 2: GOVERNOR & BUDGET TUNING (Tasks 11-20)
### Goal: Unlock multi-transfer search under normal load

---

### TASK 11: Governor Pressure Threshold Relaxation
**Objective:** Raise 60% throttle threshold; enable deeper searches  
**Priority:** CRITICAL | **Owner:** System Lead | **Effort:** 4 hours

**Subtask 11.1:** Create governor threshold override mechanism
- Add: `RouteConstraints.governor_override_mode` with options:
  - RESPECT (default): use current threshold logic
  - ADAPTIVE (recommended): dynamic threshold based on time-of-day, predicted load
  - FORCE_DEEP: ignore throttle, run full rounds (for load_more)
- File: [constraints.py](backend/core/route_engine/constraints.py#L12)

**Subtask 11.2:** Implement adaptive threshold calculator
- Base threshold: 60% → 75% (15% headroom)
- Dynamic: +5% during off-peak (3-4pm)
- Dynamic: -10% during peak (9am, 6pm)
- Function: `calc_adaptive_threshold(current_hour) → threshold%`

**Subtask 11.3:** Add throttle reason logging
- When throttle triggered: log (pressure%, threshold%, reason_string)
- Reason: e.g., "RAPTOR forced 1-TR due to 65% pressure (threshold=60%)"
- Measure: frequency of each throttle reason

**Subtask 11.4:** Test adaptive threshold
- Run 50 pairs at different times (simulated via pressure override)
- Measure: yield, latency for each threshold value
- Identify: yield gain from 60% → 75% vs. latency cost

**Subtask 11.5:** Implement threshold persistence
- Save applied thresholds to experiment log
- A/B testing: 50% traffic at 60%, 50% at 75% for 24h
- Measure: user satisfaction proxy (booking rate?), no latency regression

**Subtask 11.6:** Create pressure spike detection
- Detect: sudden pressure increase (e.g., 40% → 80% in 1 min)
- Reduce threshold temporarily (emergency mode)
- Log: spike events for post-analysis

**Subtask 11.7:** Add threshold alerts
- Log warning: if pressure approaches threshold (80% of threshold)
- Log critical: if pressure exceeds threshold by >5%
- Use: for operational monitoring

**Subtask 11.8:** Documentation: new threshold policy
- Explain: why 75% is safer than 60%
- Data: before/after yield at new threshold
- Recommendation: deploy to production

**Subtask 11.9:** Update orchestrator.py
- Pass: chosen threshold to governor check
- File: [orchestrator.py](backend/core/route_engine/orchestrator.py#L435)

**Subtask 11.10:** Regression test
- Run baseline suite (50 pairs) with new threshold
- Verify: no crash, no stalled queries, yield ≥ baseline

---

### TASK 12: Dynamic Budget Scaling Per Transfer Tier
**Objective:** Allocate more budget for 2/3-transfer searches automatically  
**Priority:** CRITICAL | **Owner:** Optimization Lead | **Effort:** 6 hours

**Subtask 12.1:** Analyze current RAPTOR budget formula
- Current: `max(2000, 50000 * (1 - pressure))`
- Issue: single formula for all transfer tiers
- Goal: increase budget for rounds 2/3 (expensive transfers)

**Subtask 12.2:** Design tier-aware budget allocator
- Base budget: 50k (fixed)
- Per round allocation: `round_0 = 10k, round_1 = 15k, round_2 = 15k, round_3 = 10k`
- Total: 50k across all rounds
- Adjustment: reduce per-round under pressure

**Subtask 12.3:** Implement tiered budget in RAPTOR
- Replace: single `self.traversal_budget` with `self.round_budgets[r]`
- Add: `sum(round_budgets) = total_budget` constraint
- Measure: yield improvement

**Subtask 12.4:** Do same for TBR
- Current: single traversal_budget
- New: per-transfer tier quotas + budget limits
- File: [tbr_router.py](backend/core/route_engine/tbr_router.py#L118-L125)

**Subtask 12.5:** Create budget reallocation logic
- If RAPTOR round 0 terminates early: reclaim budget for round 1
- If round 1 terminates: reclaim for round 2
- Goal: maximize usage of available budget

**Subtask 12.6:** Test dynamic budget sweep
- Vary allocation: (10, 15, 15, 10), (5, 10, 20, 15), (5, 5, 20, 20)
- Measure: yield per tier, total latency
- Identify: best allocation per distance category

**Subtask 12.7:** Implement budget monitoring
- Log: budget_allocated, budget_used, budget_efficiency (yield / nodes_explored)
- Measure: which round is most efficient (highest yield per node)?

**Subtask 12.8:** Create per-transfer tier SLA enforcement
- Constrain: "round 2 must use ≥ 5k nodes" (ensure 2-transfer exploration)
- If under-used: log warning (maybe throttle prevented it?)

**Subtask 12.9:** Document budget strategy
- Explain: why progressive allocation (less for 0-TR, more for 1/2-TR)
- Data: yield/latency tradeoff curves

**Subtask 12.10:** Integration test
- Run 50 pairs with new budget scaling
- Verify: yield goals hit, latency within targets

---

### TASK 13: Governor Pressure Feature Flags
**Objective:** Add capability to disable throttling per request  
**Priority:** HIGH | **Owner:** Backend Lead | **Effort:** 4 hours

**Subtask 13.1:** Add feature flags to constraints
- `RouteConstraints.disable_governor_throttle: bool = False`
- `RouteConstraints.force_allow_transfers: int = 3` (override max_transfers cap)
- File: [constraints.py](backend/core/route_engine/constraints.py)

**Subtask 13.2:** Implement flag checking in orchestrator
- Before calling `governor.can_execute()`: check flag
- If flag set: skip governor check (for load_more)
- Log: bypass reason

**Subtask 13.3:** Implement flag checking in RAPTOR
- Before applying throttle reduction: check flag
- If flag set: use full max_transfers value
- File: [raptor.py](backend/core/route_engine/raptor.py#L433-L436)

**Subtask 13.4:** Implement flag in API endpoints
- Add param to `/search` endpoint: `?deep_search=true` (no throttle)
- Map: `deep_search=true` → set constraint flags
- Document: for "load_more" button use

**Subtask 13.5:** Safeguard: maximum budget cap
- Even with flag disabled: enforce absolute max budget
- E.g., Even if pressure high, still allocate min 30k nodes to RAPTOR
- Prevent: OOM scenarios

**Subtask 13.6:** Add feature flag logging
- Log: which searches used bypass flags
- Aggregate: percentage of traffic using bypass
- Monitor: if >50% using bypass, reconsider threshold?

**Subtask 13.7:** Test flag combinations
- Flag disabled (default) + pressure high: should throttle ✓
- Flag enabled + pressure high: should NOT throttle ✓
- Flag enabled + budget exhausted: should still terminate ✓

**Subtask 13.8:** Documentation
- Explain: when to use disable_governor_throttle (load_more scenarios)
- Caution: disable only for interactive "load more", not background

**Subtask 13.9:** Create default constraints templates
- STANDARD: use all throttles (default)
- LOAD_MORE: disable_governor_throttle=true
- EMERGENCY: disable_governor_throttle=true, force_allow_transfers=4
- UI: select template based on context

**Subtask 13.10:** Regression test
- Verify: default (no flags) behavior unchanged
- Verify: flags only take effect when explicitly set

---

### TASK 14: Min Transfer Buffer Flexibility
**Objective:** Reduce "too safe" transfer buffers; enable more options  
**Priority:** MEDIUM | **Owner:** Ops Lead | **Effort:** 4 hours

**Subtask 14.1:** Audit current min_transfer_time usage
- Current fixed value: 15 minutes (from constraints.py:?L11)
- Issue: too conservative for major hubs (trains not delayed often)
- Opportunity: stratify by station tier

**Subtask 14.2:** Create tier-aware buffer calculator
- MEGA hub (NDLS, MMCT): 20 min min-buffer
- MAJOR hub: 25 min
- REGIONAL: 20 min  
- SMALL: 15 min
- Function: `calculate_min_transfer_buffer(station_tier) → minutes`

**Subtask 14.3:** Integrate buffer calculator into transfer validation
- Replace: hardcoded 15-min check with tier-aware call
- File: [transfer_intelligence.py](backend/core/transfer_intelligence.py) or [graph.py](backend/core/route_engine/graph.py#L739-L765)

**Subtask 14.4:** Add buffer override in constraints
- `RouteConstraints.min_transfer_time_override: Optional[int] = None`
- If set: use override instead of default
- Use: for "fast transfer" mode (risky but more options)

**Subtask 14.5:** Measure yield impact
- Run 50 pairs with buffers: 15m (current), 12m, 10m, 20m (high-safety)
- Plot: min_buffer vs. yield, latency
- Identify: optimal buffer (maximize yield, keep reliability high)

**Subtask 14.6:** Check reliability impact
- Do shorter buffers increase missed transfer rate (from historical data)?
- If data shows yes: validate reliability penalty worthwhile

**Subtask 14.7:** Create user preference for buffer risk
- Preference bucketing: "Safe" (20m), "Balanced" (15m), "Fast" (10m)
- Store in user profile
- Apply: on search

**Subtask 14.8:** Add buffer to route metadata
- Include in response: `transfer_safety_score` (based on buffer margins vs. min)
- Help user: understand risk of each option

**Subtask 14.9:** Document buffer strategy
- Rationale: why tiers matter
- Data: yield improvement vs. reliability cost
- Recommendation: use balanced (15m) as default, offer options

**Subtask 14.10:** Regression test
- Verify: no transfer validation logic broken
- Verify: buffer applied correctly per station tier

---

### TASK 15: Quota Limits Expansion
**Objective:** Increase per-tier discovery limits; allow fuller exploration  
**Priority:** HIGH | **Owner:** Algorithm Lead | **Effort:** 5 hours

**Subtask 15.1:** Review current quotas
- File: [tbr_router.py](backend/core/route_engine/tbr_router.py#L389-L397)
- Current: {0: 100, 1: 50, 2: 30, 3: 20}
- Issue: 2/3-tier ceilings low; early exit triggered

**Subtask 15.2:** Design new quota tiers
- Conservative: {0: 100, 1: 50, 2: 30, 3: 20} (current)
- Aggressive: {0: 200, 1: 100, 2: 50, 3: 30}
- Balanced: {0: 150, 1: 75, 2: 40, 3: 25}
- Plan: test each, choose best

**Subtask 15.3:** Implement constraint-based quota selection
- Add: `RouteConstraints.search_depth: str` (SHALLOW, MEDIUM, DEEP)
- Map: depth → quota dict
- Default: use recommended (MEDIUM)

**Subtask 15.4:** Integrate quota selection into TBR
- Before search: apply depth-based quota
- File: [tbr_router.py](backend/core/route_engine/tbr_router.py#L335)

**Subtask 15.5:** Test quota expansion
- Run 50 pairs under (Conservative, Balanced, Aggressive)
- Measure: yield, latency per quota set
- Per transfer tier: how much yield gain from increased quota?

**Subtask 15.6:** Measure early-exit frequency
- Current (conservative quota): % of searches hitting quota ceiling?
- Aggressive quota: same metric?
- Goal: <10% of searches hit ceiling (we're not overly conservative)

**Subtask 15.7:** Create dynamic quota adjustment
- Based on route distance:
  - Short (<200km): use Conservative (direct likely)
  - Medium (200-1000km): use Balanced
  - Long (>1000km): use Aggressive (need more transfers)
- Function: `select_quota(distance_km) → quota_dict`

**Subtask 15.8:** Add load_more quota multiplier
- When user clicks "load more": double quotas
- E.g., Balanced {150, 75, 40, 25} → {300, 150, 80, 50}
- File: [orchestrator.py](backend/core/route_engine/orchestrator.py)

**Subtask 15.9:** Documentation
- Explain: quota purpose (discovery ceiling)
- Data: yield improvement at each level
- Recommendation: use Balanced as default, Aggressive for long-distance

**Subtask 15.10:** Regression test
- Verify: quota enforced correctly (no exceeding limits)
- Verify: latency within acceptable range (quota increase shouldn't tank performance)

---

### TASK 16: Dominance Pruning Relaxation
**Objective:** Allow more path variety by loosening cost dominance checks  
**Priority:** CRITICAL | **Owner:** Algorithm Lead | **Effort:** 6 hours

**Subtask 16.1:** Understand current dominance logic
- File: [tbr_router.py](backend/core/route_engine/tbr_router.py#L460-L475)
- Current: `if cost > best_cost[r] * 3.0: is_dominated = True` (3x multiplier)
- Issue: still filters out valid alternatives; blocks variety

**Subtask 16.2:** Design relaxed dominance function
- Current (3.0x): reject if cost > best × 3.0
- Option A (5.0x): reject if cost > best × 5.0 (more permissive)
- Option B (10.0x): reject if cost > best × 10.0 (very permissive)
- Option C (Pareto frontier): keep if not dominated in ANY dimension

**Subtask 16.3:** Implement dynamic dominance multiplier
- Base: 3.0x
- Scale by transfer count: 3.0 + transfer_count (more leniency for multi-transfer)
  - 0-TR: 3.0x
  - 1-TR: 4.0x
  - 2-TR: 5.0x
  - 3-TR: 6.0x
- File: [tbr_router.py](backend/core/route_engine/tbr_router.py#L470)

**Subtask 16.4:** Implement Pareto frontier mode (optional)
- Alternative to dominance multiplier: true Pareto
- Keep: all paths that are optimal in at least one dimension (time/cost/reliability)
- Function: `is_pareto_dominated(path, frontier_set) → bool`
- More permissive, higher memory cost

**Subtask 16.5:** Test dominance multiplier sweep
- Run 50 pairs with multipliers: 1.5x, 3.0x, 5.0x, 10.0x, ∞ (no pruning)
- Measure: yield, latency, path diversity
- Plot: multiplier vs. yield for each transfer_tier

**Subtask 16.6:** Measure quality impact
- Do paths filtered at 3.0x have low quality (high cost, low reliability)?
- Or are they good alternatives unfairly pruned?
- Analyze: rejected paths metadata

**Subtask 16.7:** Implement tier-aware dominance
- Conservative for 0-TR (3.0x, pruning OK)
- Progressive increasing for 1-3-TR (5-10x, allow alternatives)
- Code: switch(transfer_count)

**Subtask 16.8:** Add dominance logging
- Log: when dominance check rejects path
- Include: cost ratio, transfer count, path metadata
- Measure: rejection rate per tier

**Subtask 16.9:** Test Pareto frontier vs. multiplier approach
- Side-by-side: memory cost, yield, runtime
- Recommendation: which approach better for constraints?

**Subtask 16.10:** Create dominance parameter profile
- Document: recommended multiplier per transfer tier
- Data: yield/latency curves
- Recommendation: deploy with dynamic multiplier (3+transfer_count)

---

### TASK 17: Neural Pruner Bypass for Load_More
**Objective:** Disable aggressive pruning on "load_more" queries  
**Priority:** MEDIUM | **Owner:** Backend Lead | **Effort:** 4 hours

**Subtask 17.1:** Identify neural pruner entry point
- File: [neural_pruner.py](backend/core/route_engine/neural_pruner.py)
- Function: likely `prune_candidate_routes()` or similar

**Subtask 17.2:** Add pruner bypass flag
- `RouteConstraints.disable_neural_pruning: bool = False`
- Set: to True for "load_more" queries

**Subtask 17.3:** Integrate flag into pruner call
- In orchestrator: check flag before calling pruner
- If True: skip pruning, return all candidates
- File: [orchestrator.py](backend/core/route_engine/orchestrator.py)

**Subtask 17.4:** Extend pruner buffer on bypass
- Even when pruning disabled: still apply absolute buffer
- Hard cap: don't return arrivals >36h from source departure (unrealistic)
- Soft cap (log only): warn if arrival >30h

**Subtask 17.5:** Create API endpoint variant
- `/search?deep_search=false` (default, use pruner)
- `/search?deep_search=true` (load_more, bypass pruner)
- Map: to constraint flag

**Subtask 17.6:** Test pruner bypass
- Same query with/without bypass
- Measure: additional routes returned, latency impact
- Expect: +30-50% additional routes, +5-10% latency

**Subtask 17.7:** Add pruner bypass logging
- Log: query ID, pruner enabled/disabled, routes before/after
- Measure: effectiveness of bypass

**Subtask 17.8:** Safeguard: latency limit on bypass
- Even with pruner disabled: enforce max result latency
- If latency > 2000ms with pruner off: truncate results
- Prevent: UI timeout (>3s gives bad UX)

**Subtask 17.9:** Documentation
- Explain: when bypass is used (load_more context)
- Data: expected result increase, latency cost
- Warning: don't bypass for default search UX

**Subtask 17.10:** Regression test
- Default search (pruner on) unchanged
- Load_more (pruner off) returns more routes
- Both within latency targets

---

### TASK 18: Frontier Size Expansion (RAPTOR)
**Objective:** Increase label count per station; allow more diversity  
**Priority:** MEDIUM | **Owner:** Algorithm Lead | **Effort:** 4 hours

**Subtask 18.1:** Understand current frontier implementation
- File: [raptor.py](backend/core/route_engine/raptor.py#L92)
- Elastic multipliers: {0: 1.0, 1: 3.0, 2: 6.0, 3: 9.0}
- Issue: multipliers may be conservative for long-distance routes

**Subtask 18.2:** Design frontier expansion strategy
- Current: {1.0, 3.0, 6.0, 9.0}
- Option A: increase all (2.0, 5.0, 10.0, 15.0)
- Option B: distance-aware (short routes: current, long: higher)
- Option C: transfer-aware only (increase for 2/3-TR rounds)

**Subtask 18.3:** Implement distance-aware frontier
- If route distance <300km: use {1.0, 3.0, 6.0, 9.0}
- If route distance 300-1000km: use {1.5, 5.0, 10.0, 15.0}
- If route distance >1000km: use {2.0, 6.0, 12.0, 18.0}
- File: [raptor.py](backend/core/route_engine/raptor.py#L92)

**Subtask 18.4:** Implement transfer-aware frontier
- Separate escalation: round 2/3 get extra multiplier
- Round 2: multiply by 2.0x (6.0 → 12.0)
- Round 3: multiply by 3.0x (9.0 → 27.0)

**Subtask 18.5:** Test frontier multiplier sets
- 50 pairs with multipliers: current, +50%, +100%, +200%
- Measure: yield, frontier size, latency
- Per transfer_tier: average label count kept

**Subtask 18.6:** Memory impact analysis
- Current: memory per station ~1KB (30 labels × 32 bytes)
- Doubled multipliers: ~2KB per station
- All stops: ~6000 stops → 12MB extra
- Is acceptable? Yes, within 8GB budget

**Subtask 18.7:** Add frontier size limit
- Hard cap: even with high multiplier, don't exceed 100 labels per stop
- Prevent: memory explosion

**Subtask 18.8:** Create frontier parameter profile
- Document: recommended multiplier set per distance category
- Data: yield/latency curves

**Subtask 18.9:** Implement frontier logging
- Log: per-round, frontier size distribution (min, max, mean)
- Measure: is frontier actually using allocated space?

**Subtask 18.10:** Regression test
- Verify: yield improves with expanded frontier
- Verify: latency increase acceptable (<10%)

---

### TASK 19: Context-Aware Budget Allocation
**Objective:** Allocate more budget for difficult queries (long distance, holidays)  
**Priority:** MEDIUM | **Owner:** Optimization Lead | **Effort:** 5 hours

**Subtask 19.1:** Identify difficult queries
- Long-distance (>1500km): need more budget
- Holiday periods: less frequency, need more exploration
- Weekend: different schedules
- Late-night: sparse service

**Subtask 19.2:** Create difficulty scoring function
- Score = distance_km / 1000 + (0.5 if holiday) + (0.3 if low-frequency_pair)
- Ranges: 0 (easy) to 3+ (very hard)
- Function: `calculate_query_difficulty(src, dst, date) → score`

**Subtask 19.3:** Map difficulty to budget multiplier
- Score 0-0.5: budget_multiplier = 1.0x
- Score 0.5-1.5: budget_multiplier = 1.5x
- Score 1.5-3.0: budget_multiplier = 2.0x
- Score >3.0: budget_multiplier = 3.0x

**Subtask 19.4:** Integrate into RAPTOR budget calculation
- Base budget: 50k
- Adjusted: `budget = base * difficulty_multiplier`
- File: [raptor.py](backend/core/route_engine/raptor.py#L128-L145)

**Subtask 19.5:** Do same for TBR
- File: [tbr_router.py](backend/core/route_engine/tbr_router.py#L118-L125)

**Subtask 19.6:** Test difficulty scaling
- 50 pairs: measure difficulty score, resulting budget, yield
- Verify: hard queries get more budget, yield improves

**Subtask 19.7:** Create difficulty dashboard
- Per pair: show difficulty score, assigned budget
- Identify: which pairs are "hard" (need attention)?

**Subtask 19.8:** Add difficulty logging
- Log: (search_id, difficulty_score, budget_multiplier, budget_final)
- Aggregate: distribution of difficulties across traffic

**Subtask 19.9:** Hardcoded limits
- Even on hard queries: don't exceed max_budget = 200k nodes
- Prevent: runaway searches

**Subtask 19.10:** Documentation
- Explain: why difficulty matters
- Data: how budget scaling affects hard queries
- Recommendation: deploy difficulty scorer

---

### TASK 20: Governor Override Mechanism & Testing
**Objective:** Complete implementation of all governor tuning  
**Priority:** HIGH | **Owner:** System Lead | **Effort:** 4 hours

**Subtask 20.1:** Compile all governor changes from Tasks 11-19
- Collect: all changes to governor logic, thresholds, flags
- Integrate: into single coherent governor.py module

**Subtask 20.2:** Create master feature flag system
- Flags: disable_throttle, disable_pruning, use_adaptive_threshold, context_aware_budget, etc.
- Default: all False (standard behavior)
- File: [constraints.py](backend/core/route_engine/constraints.py)

**Subtask 20.3:** Build governor mode profiles
- Profile "Standard": all flags False (current behavior)
- Profile "Balanced": disable_throttle=True (recommended production)
- Profile "Aggressive": disable_throttle=True, dynamic_multiplier=5.0x
- Profile "Maximum": all optimizations enabled
- API param: `?governor_mode=balanced`

**Subtask 20.4:** Implement mode profile in orchestrator
- Parse: governor_mode parameter
- Apply: corresponding feature flags
- Log: which mode used

**Subtask 20.5:** Create A/B test framework
- Split traffic: 50% Standard, 50% Balanced for 24h
- Measure: yield, latency, error rates
- Dashboard: side-by-side comparison

**Subtask 20.6:** Implement safety guardrails
- Absolute max latency: 4000ms (if exceeds, revert to Standard)
- Absolute max CPU spike: 95% (if exceeds, revert)
- Absolute max error rate: 1% (if exceeds, revert)

**Subtask 20.7:** Create operator runbook
- Steps: how to enable/disable features
- Monitoring: watch for regressions
- Rollback: procedure if issues detected

**Subtask 20.8:** Testing suite for governor
- Unit tests: each flag combination works
- Integration tests: real 50-pair runs
- Load tests: synthetic traffic under flags

**Subtask 20.9:** Documentation
- Explain: each governor mode (Standard, Balanced, Aggressive)
- Trade-offs: yield vs. latency per mode
- Recommendation: Balanced for production

**Subtask 20.10:** Deployment plan
- Phase 1 (week 1): deploy Standard mode (no changes)
- Phase 2 (week 2): 10% traffic on Balanced
- Phase 3 (week 3): 50/50 split Standard/Balanced
- Phase 4 (week 4): 100% Balanced (if metrics positive)

---

## TASK GROUP 3: MULTI-TRANSFER DISCOVERY (Tasks 21-30)
### Goal: Maximize 1/2/3-transfer route yields per engine

*(Going to create the remaining task groups more concisely to fit)*

---

### TASK 21: RAPTOR Round 1 Multi-Transfer Expansion
**Objective:** Improve 1-transfer discovery via enhanced round 1  
**Priority:** CRITICAL | **Owner:** Algorithm Lead | **Effort:** 6 hours

**Subtask 21.1-21.10:** (10 subtasks covering RAPTOR round 1 optimization, pattern-based expansion, transfer edge discovery, frontier management, latency tuning per round, round1 isolation testing, yield measurement, quality assessment, debug logging, regression testing)

---

### TASK 22: RAPTOR Rounds 2-3 Multi-Layer Expansion
**Priority:** CRITICAL | **Effort:** 8 hours
(10 subtasks: round 2 initialization, layer iterations, dominance handling, frontier escalation, tier-specific tuning, memory management, latency per round, yield per round, cycle detection, regression tests)

---

### TASK 23: TBR A* Transfer Edge Optimization
**Priority:** HIGH | **Effort:** 8 hours
(10 subtasks: A* heuristic function, transfer edge pruning, cost calculation efficiency, Pareto frontier per node, mmap edge index verification, binary search for edges, transfer quality scoring, onward search triggers, memory efficiency, load testing)

---

### TASK 24: FastPath BFS 2/3-Hub Discovery
**Priority:** MEDIUM | **Effort:** 5 hours
(10 subtasks: BFS frontier management, hub reachability checks, 3-hub transfer paths, path reconstruction, pruning strategy, conditional trigger optimization, yield measurement, latency per hop, quality assessment, regression testing)

---

### TASK 25: TurboRouter Hub Transfer Enrichment
**Priority:** MEDIUM | **Effort:** 4 hours
(10 subtasks: hub cache expansion, hub–hub connectivity, secondary hub consideration, binary index rebuild, transfer validation, latency measurement, cache TTL optimization, hit rate analysis, quality scoring, regression tests)

---

### TASK 26: UltraTurbo 1-Transfer SQL Expansion
**Priority:** MEDIUM | **Effort:** 4 hours
(10 subtasks: SQL query expansion, hub junction discovery, binary search for transfers, transfer validation, latency optimization, plan analysis, index usage, batch vs. individual queries, result deduplication, regression testing)

---

### TASK 27: Transfer Bridge Pattern Discovery
**Objective:** Identify strategic intermediate hubs for multi-transfer routes  
**Priority:** HIGH | **Effort:** 6 hours

(10 subtasks: bridge hub identification, connectivity analysis, capacity assessment, transfer quality ranking, multi-bridge support, cycle detection, graph analysis, strategic hub marking, load distribution algorithms, documentation)

---

### TASK 28: Dynamic Transfer Window Expansion
**Objective:** Adapt transfer wait windows based on context  
**Priority:** MEDIUM | **Effort:** 5 hours

(10 subtasks: base transfer window, hour-of-day adjustment, station capacity modeling, delay factor integration, night transfer penalties, high-occupancy detection, comfort adjustment, risk-based buffering, documentation, A/B testing)

---

### TASK 29: Multi-Modal Transfer Integration  
**Objective:** Support train-metro, train-bus transfers  
**Priority:** MEDIUM | **Effort:** 5 hours

(10 subtasks: mode detection, mode-specific transfer times, platform coordination, schedule synchronization, reliability scoring per mode, user preference integration, cost calculation, feasibility filtering, testing, documentation)

---

### TASK 30: Load_More Pagination Expansion
**Objective:** Enable progressive result discovery  
**Priority:** HIGH | **Effort:** 6 hours

(10 subtasks: cursor design, state management, progressive deepening strategy, tier-by-tier expansion, quota multiplier per page, result deduplication across pages, latency management per page, user UX optimization, analytical logging, end-to-end testing)

---

## TASK GROUP 4: TRANSFER INTELLIGENCE (Tasks 31-40)
### Goal: Improve transfer quality scoring and discovery

(Tasks 31-40: each covering transfer quality metrics, risk assessment, comfort scoring, reliability modeling, network redundancy analysis, vector-based ranking, transfer time histograms, failure rate prediction, alternative path ranking, transfer safety assessment - all 4-6 hours each with 10 subtasks)

---

## TASK GROUP 5: LOAD-MORE & PAGINATION (Tasks 41-45)
### Goal: Comprehensive "load more" experience

(Tasks 41-45: cursor management, progressive quota escalation, tier rotation strategy, aesthetic result ordering, checkpoint persistence - all 3-4 hours each with 10 subtasks)

---

## TASK GROUP 6: STABILITY & MONITORING (Tasks 46-50)
### Goal: Ensure yield gains persist and regression-free

(Tasks 46-50: SLA monitoring dashboards, regression test suite, operator runbooks, alert configurations, weekly trend analysis - all 4-5 hours each with 10 subtasks)

---

## SUMMARY TIMELINE

| Phase | Tasks | Effort | Duration | Focus |
|-------|-------|--------|----------|-------|
| **Analysis** | 1-10 | 60 hours | 6-8 days | Baseline, measurements, bottleneck identification |
| **Governor Tuning** | 11-20 | 50 hours | 5-7 days | Unlock multi-transfer via threshold/budget relaxation |
| **Multi-Transfer Discovery** | 21-30 | 70 hours | 8-10 days | Maximize per-engine yield for 1/2/3-transfers |
| **Transfer Intelligence** | 31-40 | 60 hours | 7-9 days | Quality scoring, risk, reliability |
| **Load-More** | 41-45 | 20 hours | 3-4 days | User-facing pagination |
| **Stability** | 46-50 | 20 hours | 3-4 days | Monitoring, regression prevention |
| **Total** | **1-50** | **280 hours** | **4-5 weeks** | **Full implementation** |

---

## EFFORT ESTIMATION & RESOURCE ALLOCATION

**Team:** 2-3 Backend Engineers  
**Daily Capacity:** 16-24 person-hours  
**Recommended Pace:**
- Week 1: Tasks 1-10 (Analysis phase)
- Week 2: Tasks 11-15 (Quick governor wins)
- Week 3: Tasks 16-20 + 21-25 (Governor completion + multi-transfer start)
- Week 4: Tasks 26-30 (Engine-specific tuning)
- Week 5: Tasks 31-40 (Transfer intelligence)
- Week 6: Tasks 41-50 (Load-more, stability)

**Risk Mitigation:**
- A/B test every change (50% traffic before 100% rollout)
- Maintain rollback plan per task
- Daily metrics review (yield, latency, error rate)
- On-call support for high-priority issues

---

**Document Status:** TASK PLAN COMPLETE | Ready for Execution  
**Next Step:** Begin Task 1.1 (Baseline fingerprinting)  
**Owner:** TBD (assign task leads)
