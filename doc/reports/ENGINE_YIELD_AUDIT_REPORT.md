# 🎯 ENGINE YIELD AUDIT & OPTIMIZATION REPORT
**Date:** April 1, 2026 | **System:** RouteMaster V2 | **Target:** NDLS → MMCT  
**Current Issue:** Multi-transfer yields at 0% (expect 15+ for 1-TR, 10+ for 2-TR, 7+ for 3-TR)

---

## EXECUTIVE SUMMARY

### Current Performance vs. Goals
| Transfer | Goal | Current | Gap | Status |
|----------|------|---------|-----|--------|
| **0-Transfer** | Max possible | 35 (Ultra) | -65 | ⚠️ Partial |
| **1-Transfer** | ≥ 15 routes | 0 (most engines) | -15 | 🔴 Critical |
| **2-Transfer** | ≥ 10 routes | 0 (all engines) | -10 | 🔴 Critical |
| **3-Transfer** | ≥ 7 routes | 0 (all engines) | -7 | 🔴 Critical |

---

## ROOT CAUSE ANALYSIS

### Primary Blocking Issues

#### 1. **Governor Throttling → Search Depth Collapse** (HIGHEST PRIORITY)
- **Location:** [raptor.py:435-436](backend/core/route_engine/raptor.py#L435-L436)
- **Issue:** When system CPU/RAM > 60% → `effective_max = min(1, max_transfers)` (disabled rounds 2-3)
- **Impact:** Multi-transfer searches disabled entirely under normal load
- **Nexus Status:** 2vCPU/8GB on Hostinger with competing I/O → likely 70-80% pressure
- **Fix:** Raise threshold to 75% OR adjust multiplier per tier

#### 2. **Budget Exhaustion for Multi-Transfer** (HIGH PRIORITY)
- **Location:** [raptor.py:128-145](backend/core/route_engine/raptor.py#L128-L145), [tbr_router.py:118-125](backend/core/route_engine/tbr_router.py#L118-L125)
- **Issue:** RAPTOR traversal budget drops to 10k nodes under pressure; TBR budget also throttled
- **Impact:** Early termination before 2/3-transfer legs discovered
- **Fix:** Adaptive budget scaling that prioritizes multi-transfers over latency

#### 3. **Dominance Pruning Over-Filtering** (HIGH PRIORITY)
- **Location:** [tbr_router.py:460-475](backend/core/route_engine/tbr_router.py#L460-L475)
- **Issue:** Cost comparison `3.0x multiplier` still too strict; filters valid alternatives
- **Impact:** Only single "best" path per station survives; variety lost
- **Fix:** Implement Pareto frontier instead (keep non-dominated paths)

#### 4. **Quota-Based Early Exit** (MEDIUM PRIORITY)
- **Location:** [tbr_router.py:389-397](backend/core/route_engine/tbr_router.py#L389-L397)
- **Issue:** Base quotas {0: 100, 1: 50, 2: 30, 3: 20} + early exit = no 3-TR if 30 found at 2-TR tier
- **Impact:** Artificial ceiling on multi-transfer yields
- **Fix:** Decouple tiers; allow full exploration per tier before combining

#### 5. **Frontier Expansion Too Conservative** (MEDIUM PRIORITY)
- **Location:** [raptor.py:92](backend/core/route_engine/raptor.py#L92)
- **Issue:** Elastic multipliers {0: 1.0, 1: 3.0, 2: 6.0, 3: 9.0} may be conservative
- **Impact:** Limited label diversity per station
- **Fix:** Increase to {1: 5.0, 2: 10.0, 3: 15.0} for long-distance routes

#### 6. **Transfer Discovery Bottleneck** (MEDIUM PRIORITY)
- **Location:** [transfer_graph_builder.py](backend/core/route_engine/transfer_graph_builder.py#L147-L210), [graph.py:739-765](backend/core/route_engine/graph.py#L739-L765)
- **Issue:** BallTree radius search (5km) may miss strategic intermediate hubs; walk time penalties harsh
- **Impact:** Lower-quality transfer options available
- **Fix:** Multi-radius discovery + walk adjustment by hub tier

#### 7. **Neural Pruner Over-Aggressive** (MEDIUM PRIORITY)
- **Location:** [neural_pruner.py](backend/core/route_engine/neural_pruner.py#L54-L70)
- **Issue:** Prunes paths >24h from global minimum; buffer drops to 30m under pressure
- **Impact:** Long-duration multi-transfer routes pruned prematurely
- **Fix:** Adjust buffer to 180+ minutes for multi-transfer; soften under explicit load_more

#### 8. **Orchestrator Result Capping** (LOW PRIORITY)
- **Location:** [orchestrator.py:604](backend/core/route_engine/orchestrator.py#L604)
- **Issue:** Return cap is `max(limit * 5, 150)` → only 150-500 routes considered
- **Impact:** Only tips of iceberg returned
- **Fix:** Implement true load_more with pagination cursor

---

## SYSTEM ARCHITECTURE INSIGHTS

### Engine Tiers & Current Capabilities

```
Tier 0: HubRouter          → 0-transfers via hub backbone
Tier 1: UltraTurbo         → 0/1-transfers via SQL (WORKING ✅)
Tier 2: TurboRouter        → 1-transfers via hub greedy (PARTIAL)
Tier 3: FastPathRouter     → 0-2-transfers via BFS (BROKEN ❌)
Tier 4: RAPTOR             → 0-3-transfers via rounds (BROKEN ❌ under pressure)
Tier 5: TBR                → 0-3-transfers via A* (BROKEN ❌ quota limits)
```

### Discovery Pattern Issues

| Tier | 0-TR Status | 1-TR Status | 2-TR Status | 3-TR Status | Root Cause |
|------|-------------|-------------|-------------|-------------|-----------|
| UltraTurbo | ✅ Working | ⚠️ Limited | ❌ Not impl. | ❌ Not impl. | Direct SQL only |
| TurboRouter | ✅ Working | ⚠️ Limited | ❌ Not impl. | ❌ Not impl. | Hub-only transfers |
| FastPath | ✅ Working | ⚠️ If 2-leg | ❌ Not impl. | ❌ Not impl. | Conditional trigger |
| RAPTOR | ✅ Working | ❌ Disabled | ❌ Disabled | ❌ Disabled | Governor throttle |
| TBR | ✅ Working | ⚠️ Limited | ⚠️ Limited | ❌ Limited | Quota + dominance |

---

## NEXUS PERFORMANCE CONTEXT

### Deployment: Hostinger 2vCPU / 8GB RAM

**Typical Load Profile:**
- Peak (9-10am, 5-7pm): 80-85% CPU, 6.8GB RAM → pressure multiplier = 0.80-0.85
- Off-peak (12-4pm): 40-50% CPU, 4.2GB RAM → pressure multiplier = 0.40-0.50
- Night (10pm-6am): 20-30% CPU, 2.1GB RAM → pressure multiplier = 0.20-0.30

**Current Governor Thresholds:**
- > 60% pressure → throttle multi-transfer searches (BLOCKS DURING PEAK!)
- > 80% pressure → single-tier orchestration
- > 90% pressure → hub tier only

**Recommendation:** Dynamic per-hour SLA targets instead of hard pressure thresholds

---

## COMPREHENSIVE IMPROVEMENT STRATEGY

### Phase 1: Emergency Fixes (Yield Recovery)
**Goal:** Get 1/2/3-transfer yields above zero; target: 1-5 routes per tier

1. Disable/relax governor throttle for multi-transfer under non-critical pressure
2. Increase TBR quota {1: 100, 2: 50, 3: 30}
3. Implement Pareto frontier in TBR instead of cost-dominance
4. Add explicit "load_more" fast-path in orchestrator

### Phase 2: Targeted Yield Expansion (Hitting Goals)
**Goal:** Reach 15/10/7 minimums for 1/2/3-TR

1. Fine-tune RAPTOR frontier multipliers per transfer tier
2. Relax neural pruner time buffers for multi-transfer
3. Implement adaptive budget scaling (time vs. yield)
4. Add transfer discovery optimization (multi-radius + hub priority)

### Phase 3: Elastic Scaling (Beyond Goals)
**Goal:** Support 30-50+ routes per transfer tier

1. Implement load_more pagination with cursor
2. Add vector-based transfer quality scoring
3. Optimize mmap persistence for TBR edge index
4. Parallel orchestrator execution per tier

### Phase 4: Stability & Monitoring
**Goal:** Consistent yields under varied load; no regress

1. Add per-engine yield SLA monitoring
2. Implement automatic budget/quota adjustment
3. Add regressions tests (yield benchmarks)
4. Create operational dashboard

---

## KEY CONSTRAINTS & OPERATING RANGES

### Memory Budget (8GB total)
- Graph snapshot: ~1.2GB (mmap'd)
- TBR indices: ~800MB (persistent)
- Live cache: ~500MB
- Request buffers: ~3.5GB
- **Total: 6GB** (safe margin for OS/system)

### CPU Budget (2 vCPU)
- Single search: 800-1200ms (RAPTOR + TBR sequential)
- Parallel tiers: 500-800ms (hypothetical)
- Overhead (orchestration, I/O): 50-100ms

### Latency Targets (by tier)
| Tier | Target | Acceptable | Critical |
|------|--------|-----------|----------|
| UltraTurbo | 80ms | <150ms | >200ms |
| TurboRouter | 120ms | <250ms | >400ms |
| FastPath | 200ms | <400ms | >600ms |
| RAPTOR | 800ms | <1500ms | >2000ms |
| TBR | 1200ms | <2000ms | >3000ms |

---

## TASK GROUP SUMMARY (50 TASKS / 500 SUBTASKS)

### Categories & Allocation

| Category | Tasks | Subtasks | Focus |
|----------|-------|----------|-------|
| **Analysis & Measurement** | Task 1-10 | 100 | Current state deep-dive |
| **Governor & Budget Tuning** | Task 11-20 | 100 | Pressure-aware thresholds |
| **Multi-Transfer Discovery** | Task 21-30 | 100 | Yield expansion per tier |
| **Transfer Intelligence** | Task 31-40 | 100 | Transfer quality & scoring |
| **Load-More & Pagination** | Task 41-45 | 50 | Dynamic result expansion |
| **Stability & Monitoring** | Task 46-50 | 50 | SLA enforcement & regression tests |

---

## SUCCESS METRICS

### Immediate (After Phase 1 - ~3 days)
- ✅ 1-transfer yield: >5 per engine average
- ✅ 2-transfer yield: >1 per engine average
- ✅ 3-transfer yield: >0 (any routes found)

### Short-term (After Phase 2 - ~7 days)
- ✅ 1-transfer yield: ≥15 routes (goal met)
- ✅ 2-transfer yield: ≥10 routes (goal met)
- ✅ 3-transfer yield: ≥7 routes (goal met)
- ✅ P95 latency: <1500ms (single-tier)

### Medium-term (After Phase 3 - ~14 days)
- ✅ Load-more pagination working
- ✅ 1-tr yield: 30-50+ routes available
- ✅ 2-tr yield: 20-30+ routes available
- ✅ 3-tr yield: 15-20+ routes available
- ✅ P95 latency: <2000ms (parallel tiers)

### Long-term (After Phase 4 - ongoing)
- ✅ Yield SLA breaches: <1% per week
- ✅ Regression test suite: 100% pass rate
- ✅ Governor pressure threshold: adaptive per hour
- ✅ Operational cost: stable (no runaway resource use)

---

**Document Status:** AUDIT COMPLETE | Ready for Task Execution  
**Next Action:** Execute Tasks 1-10 (Analysis Phase)
