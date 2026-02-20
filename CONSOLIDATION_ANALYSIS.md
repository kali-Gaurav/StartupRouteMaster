# CONTENT-LEVEL CONSOLIDATION ANALYSIS

**Date**: 2026-02-20
**Task**: Identify duplicate code logic across 4 consolidated engines and merge into ultimate versions
**Status**: Analysis Complete

---

## FILES ANALYZED

1. **domains/routing/engine.py** (407 lines) - RailwayRouteEngine
2. **domains/inventory/seat_allocator.py** (521 lines) - AdvancedSeatAllocationEngine
3. **domains/pricing/engine.py** (487 lines) - DynamicPricingEngine
4. **platform/cache/manager.py** (504 lines) - MultiLayerCache

**Total**: 1,919 lines of code across 4 consolidated engines

---

## 🔍 DUPLICATE CODE PATTERNS IDENTIFIED

### 1. DATACLASS-BASED CONFIGURATION (Found In: All 4 files)
**Lines**: ~100 lines duplicated across files

```python
# routing/engine.py - UserContext, RouteConstraints
# inventory/seat_allocator.py - PassengerPreference, SeatAllocationResult, Coach
# pricing/engine.py - PricingContext, DynamicPricingResult
# cache/manager.py - RouteQuery, AvailabilityQuery, CacheMetrics

# Pattern: @dataclass with to_dict() method appearing 4+ times
# Opportunity: Extract to shared core/data_structures.py
```

**Impact**: HIGH - Eliminates config class duplication
**Lines saved**: ~60 lines
**Consolidation**: Move to `core/data_structures.py`

---

### 2. ENUM-BASED STATUS TRACKING (Found In: All 4 files)
**Lines**: ~80 lines duplicated

```python
# inventory/seat_allocator.py - BerthType, SeatStatus enums
# pricing/engine.py - Implicit status in flags
# cache/manager.py - Implicit status in metrics
# routing/engine.py - Mode detection logic (OFFLINE/HYBRID/ONLINE)

# Pattern: Enum-based state management
# Opportunity: Consolidate into shared core/enums.py
```

**Impact**: MEDIUM - Better type safety and consistency
**Lines saved**: ~40 lines
**Consolidation**: Move to `core/enums.py`

---

### 3. METRICS & ANALYTICS (Found In: seat_allocator + cache)
**Lines**: ~80 lines duplicated

```python
# cache/manager.py (Lines 40-59):
@dataclass
class CacheMetrics:
    hits, misses, sets, deletes, evictions
    @property
    def hit_rate(self) -> float  # calculate percentage

# seat_allocator.py (Lines 477-492):
def get_occupancy_stats() -> Dict
def get_coach_wise_breakdown() -> List[Dict]
# Similar percentage-based calculations

# Opportunity: Consolidate metrics strategy
```

**Impact**: MEDIUM - Enables unified monitoring across engines
**Lines saved**: ~40 lines
**Consolidation**: Create `core/metrics.py` with abstract Metrics base class

---

### 4. ML MODEL INTEGRATION PATTERN (Found In: routing + pricing)
**Lines**: ~60 lines duplicated

```python
# pricing/engine.py (Lines 94-107):
def __init__(self):
    self.demand_predictor = TatkalDemandPredictor()
    self.route_ranker = RouteRankingPredictor()
    try:
        self.demand_predictor.load_from_file()
        self.route_ranker.load_from_file()
        self.is_ready = True
    except Exception as e:
        logger.warning(f"ML models not available: {e}")
        self.is_ready = False

# routing/engine.py (Lines 96-104):
# Does similar model initialization
# Both have fallback patterns when models unavailable

# Opportunity: Extract to shared MLModelManager
```

**Impact**: HIGH - Standardizes ML integration across system
**Lines saved**: ~40 lines
**Consolidation**: Create `core/ml_integration.py`

---

### 5. FEATURE FLAG & MODE DETECTION (Found In: routing + pricing)
**Lines**: ~70 lines duplicated

```python
# routing/engine.py (Lines 109-165):
def _detect_available_features(self):
def _log_startup_status(self):
# Shows: OFFLINE → HYBRID → ONLINE mode detection with feature flags

# pricing/engine.py (Lines 385-387):
if not use_ml or not self.dynamic_engine.is_ready:
    return self.base_engine.calculate_final_price(route, user_type)

# Both implement fallback logic based on available features

# Opportunity: Extract feature detection/logging to base engine
```

**Impact**: MEDIUM - Ensures consistent feature detection
**Lines saved**: ~35 lines
**Consolidation**: Move to `core/base_engine.py`

---

### 6. EXPLANATION GENERATION (Found In: pricing)
**Lines**: ~60 lines of sophisticated logic

```python
# pricing/engine.py (Lines 313-359):
def _generate_explanation(self, context, factors, multiplier) -> str
def _get_booking_recommendation(self, multiplier, demand_score) -> str

# Both create human-readable outputs from computed factors
# Opportunity: Create utility for other engines to generate explanations
```

**Impact**: LOW - Pricing-specific, but pattern useful elsewhere
**Lines saved**: ~0 (stay in pricing, enhance for reuse)
**Enhancement**: Add explanations to seat allocation and caching

---

### 7. CACHE KEY GENERATION (Found In: cache)
**Lines**: ~50 lines sophisticated logic

```python
# cache/manager.py (Lines 71-77, 90-93):
def cache_key(self) -> str:
    key_data = f"{self.from_station}:{self.to_station}:{self.date.isoformat()}"
    return f"route:{hashlib.md5(key_data.encode()).hexdigest()[:16]}"

# Similar patterns in multiple query types
# Opportunity: Create cache_key_generator utility
```

**Impact**: LOW - Cache-specific, but pattern useful for other engines
**Lines saved**: ~20 lines
**Enhancement**: Create `core/utils/cache_keys.py`

---

### 8. OCCUPANCY & AVAILABILITY CALCULATION (Found In: seat_allocator + cache)
**Lines**: ~40 lines duplicated

```python
# seat_allocator.py (Lines 477-511):
def get_occupancy_stats() -> Dict:
    return {
        'total_seats': total_seats,
        'occupied_seats': occupied,
        'occupancy_rate': occupied / max(total_seats, 1),
        ...
    }

# cache/manager.py (Lines 278-310):
async def get_availability(self, query) -> Optional[Dict]
# Similar availability calculations

# Opportunity: Create shared occupancy calculator
```

**Impact**: MEDIUM - Ensures consistent calculations
**Lines saved**: ~30 lines
**Consolidation**: Move calculation logic to `core/utils/occupancy.py`

---

### 9. ERROR HANDLING & LOGGING PATTERN (Found In: All 4 files)
**Lines**: ~100 lines duplicated

```python
# ALL FILES have this pattern:
try:
    # operation
except Exception as e:
    logger.error(f"Error doing X: {e}")
    return None / default_value

# Opportunity: Create @error_handler decorator
```

**Impact**: LOW - Best practice already applied, decorator helpful for new code
**Lines saved**: ~20 lines (future code)
**Enhancement**: Create `core/utils/error_handlers.py` with decorators

---

### 10. ASYNC/AWAIT PATTERNS (Found In: routing + cache)
**Lines**: ~50 lines duplicated

```python
# Both use:
import asyncio
await asyncio.sleep(interval_seconds)
await self.redis.get(key)
await self.redis.setex(key, ttl, data)

# Both have initialization patterns
temp = await self.method()
self.state = temp

# Opportunity: Create async utilities/base classes
```

**Impact**: LOW - Already using async properly
**Enhancement**: Document async patterns in shared base

---

## 📊 CONSOLIDATION SUMMARY

| Pattern | Found In | Lines | Priority | Target File |
|---------|----------|-------|----------|-------------|
| Dataclasses | All 4 | ~100 | HIGH | `core/data_structures.py` |
| Enums | All 4 | ~80 | MEDIUM | `core/enums.py` |
| ML Integration | routing + pricing | ~60 | HIGH | `core/ml_integration.py` |
| Feature Flags | routing + pricing | ~70 | MEDIUM | `core/base_engine.py` |
| Metrics | seat + cache | ~80 | MEDIUM | `core/metrics.py` |
| Cache Keys | cache | ~50 | LOW | `core/utils/cache_keys.py` |
| Occupancy Calc | seat + cache | ~40 | MEDIUM | `core/utils/occupancy.py` |
| Error Handling | all 4 | ~100 | LOW | `core/utils/error_handlers.py` |
| Async Patterns | routing + cache | ~50 | LOW | `core/base_engine.py` |
| Explanations | pricing | ~60 | LOW | `core/utils/explanations.py` |

**Total Lines Consolidateable**: ~630 lines (~33% of current codebase)

---

## 🎯 ULTIMATE CONSOLIDATION STRATEGY

### Phase 1: Extract Shared Core Infrastructure (2 hours)
1. Create `core/data_structures.py` - All dataclasses
2. Create `core/enums.py` - All status enums
3. Create `core/metrics.py` - Metrics base class
4. Create `core/ml_integration.py` - ML model manager
5. Create `core/base_engine.py` - Base engine class

### Phase 2: Create Shared Utilities (1 hour)
1. Create `core/utils/cache_keys.py`
2. Create `core/utils/occupancy.py`
3. Create `core/utils/error_handlers.py`
4. Create `core/utils/explanations.py`

### Phase 3: Update 4 Engines (2 hours)
1. Update `domains/routing/engine.py` - Import shared, extend base engine
2. Update `domains/inventory/seat_allocator.py` - Use shared dataclasses, extend base
3. Update `domains/pricing/engine.py` - Use shared ML integration, dataclasses
4. Update `platform/cache/manager.py` - Use shared metrics, utils

### Phase 4: Testing & Validation (1 hour)
1. Unit tests for shared modules
2. Integration tests for updated engines
3. Performance benchmarks

---

## 💡 ADVANCED ENHANCEMENTS (Beyond Deduplication)

### 1. Pipeline Pattern
Implement unified processing pipeline across all engines:
```python
# core/pipeline.py
class ProcessingPipeline:
    def __init__(self):
        self.stages = []

    async def execute(self, context):
        # Run all stages in order
        for stage in self.stages:
            context = await stage(context)
        return context
```

### 2. Strategy Factory Pattern
Unified strategy selection for complex decisions:
```python
# core/strategies.py
class StrategyFactory:
    strategies = {
        'pricing': {
            'dynamic': DynamicPricingEngine,
            'base': BasePriceCalculationService
        },
        'seating': {
            'fair': FairDistributionStrategy,
            'family': FamilyGroupingStrategy
        }
    }
```

### 3. Cost-Benefit-Risk Framework
Unified decision framework across engines:
```python
# core/decision_framework.py
class DecisionFramework:
    def evaluate(self, context):
        cost = self.calculate_cost(context)
        benefit = self.calculate_benefit(context)
        risk = self.calculate_risk(context)
        return (benefit - cost) / (1 + risk)
```

### 4. Observability Enhancement
Unified monitoring/tracing:
```python
# core/observability.py
class TraceContext:
    request_id: str
    stage: str
    duration_ms: float
    metrics: Dict
    explanation: str
```

---

## ⚠️ CRITICAL NOTES

### What NOT to Consolidate
- **Business Logic**: Each engine has unique algorithms (RAPTOR vs pricing factors vs seat allocation)
- **Domain Models**: Seat allocation doesn't need pricing logic
- **Dependencies**: Don't force shared dependencies if not needed

### What SHOULD be Shared
- **Infrastructure**: Metrics, caching, ML integration patterns
- **Data Structures**: Query configs, result formats
- **Utilities**: Key generation, occupancy calculation
- **Base Patterns**: Error handling, logging, feature detection

### Backward Compatibility
- All shared modules use absolute imports: `from backend.core.data_structures import ...`
- Existing imports in engines continue to work
- No breaking changes to public APIs

---

## 📈 EXPECTED OUTCOMES

After consolidation:

**Code Metrics**:
- Reduce from 1,919 → 1,300 lines (~33% reduction)
- Increase shared infrastructure from 0 → 600 lines (well-organized core)
- Each engine becomes 150-300 lines (core logic only)

**Quality Metrics**:
- 100% test coverage for shared modules
- Zero code duplication (DRY principle)
- Consistent error handling across system
- Unified observability and metrics

**Maintenance**:
- Changes to shared logic affect all engines automatically
- Bug fixes in utilities propagate instantly
- New engines reuse established patterns
- Easier onboarding for new developers

**Performance**:
- No performance penalty (same algorithms)
- Better cache key generation → improved hit rates
- Unified metrics enable optimization opportunities
- ML model integration can be optimized once

---

## 🚀 NEXT STEPS

1. **User Approval**: Confirm consolidation strategy
2. **Create Shared Core**: Extract infrastructure modules
3. **Update Engines**: Refactor to use shared code
4. **Test**: Verify all functionality unchanged
5. **Commit**: Clean, consolidated codebase
6. **Document**: Update architecture documentation

---

**Status**: ANALYSIS COMPLETE - Ready for Implementation Phase

