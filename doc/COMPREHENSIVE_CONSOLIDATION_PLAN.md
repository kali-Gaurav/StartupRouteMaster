# COMPREHENSIVE CONSOLIDATION PLAN - ALL 12 CATEGORIES

**Date:** 2026-02-20
**Status:** SYSTEMATIC ANALYSIS IN PROGRESS
**Total Categories:** 12
**Total Duplicate Files:** 47+
**Estimated Lines of Duplicate Code:** 10,000+

---

## CATEGORY 1: ROUTE ENGINES

### DUPLICATES FOUND:
- **FILE #1:** `backend/archive/route_engines_v1/advanced_route_engine.py` (1,007 lines)
  - Features: RAPTOR algorithm, A* router, Yen's k-shortest paths, transfer logic, basic caching
  - Algorithms: RAPTOR, A*, Transfer Validator, Yen's Algorithm
  - Cons: No real-time support, no ML integration, no validation framework, single-threaded

- **FILE #2:** `backend/archive/route_engines_v1/multi_modal_route_engine.py`
  - Features: Multi-modal support (train, bus, flight)
  - Status: RETIRED

- **FILE #3:** `backend/archive/route_engines_v1/route_engine.py`
  - Status: RETIRED duplicate

- **FILE #4:** `backend/archive/route_engines_consolidated/*` (multiple versions)
  - Status: CONSOLIDATED but RETIRED

- **FILE #5:** `backend/core/route_engine.py` (2,447 lines) **CANONICAL**
  - Features: OptimizedRAPTOR with multi-layer caching, real-time overlays, hub acceleration, ML integration, validation framework, async execution, snapshot manager
  - Algorithms: RAPTOR with Range Query, Hub-RAPTOR, Copy-on-Write overlays, Bitset deduplication, Pareto dominance pruning
  - Status: PRODUCTION-READY

- **FILE #6:** `backend/core/route_engine/engine.py` (100 lines)
  - Features: Modular wrapper, backward compatibility
  - Status: TRANSITIONAL

- **FILE #7:** `backend/domains/routing/engine.py` (100 lines) **DOMAIN ADAPTER**
  - Features: Imports from core, incomplete implementation
  - Status: NEEDS COMPLETION

### CONSOLIDATION PLAN:
```
KEEP (Ultimate Version): backend/core/route_engine.py
DOMAIN ADAPTER: backend/domains/routing/engine.py (refactor to complete)
MERGE FROM: archive versions (capture unique features if any)
ARCHIVE TO: archive/route_engines_v1/ (already archived)
DELETE: backend/archive/route_engines_consolidated/
DELETE: backend/core/archive/ (old versions)
```

### KEY FEATURES IN ULTIMATE VERSION (backend/core/route_engine.py):
- OptimizedRAPTOR with validation integration
- Real-time graph mutation (Copy-on-Write delays)
- StaticGraphSnapshot with pre-built indexes
- HybridRAPTOR hub-based acceleration (9 major hubs)
- Multi-layer caching (Redis integration)
- ML reliability scoring
- Frequency-aware Range-RAPTOR sizing
- Async/parallel execution
- 220+ validation checks (RT-001 to RT-220)

### UNIQUE CODE TO PRESERVE:
- ✓ Set A & Set B transfer logic (from v1)
- ✓ Haversine distance calculation pattern (verify in core)
- ✓ Clean dataclass definitions (already in core)

### ACTION ITEMS:
- [ ] VERIFY `backend/core/route_engine.py` is production-ready
- [ ] COMPLETE `backend/domains/routing/engine.py` imports
- [ ] DELETE `backend/archive/route_engines_*` (all versions)
- [ ] DELETE `backend/core/archive/` old versions
- [ ] UPDATE all imports to use `core/route_engine.py`
- [ ] TEST consolidated version end-to-end

---

## CATEGORY 2: SEAT ALLOCATION & INVENTORY

### DUPLICATES FOUND:
- **FILE #1:** `backend/archive/seat_allocators_v1/advanced_seat_allocation_engine.py`
  - Features: Fair multi-coach distribution, berth preference optimization, family grouping, accessibility, overbooking, waitlist management
  - Algorithms: Fair Distribution, Preference Matching, Family Grouping, Overbooking
  - Size: ~350 lines
  - Status: RETIRED

- **FILE #2:** `backend/archive/seat_allocators_v1/seat_allocation.py`
  - Status: RETIRED duplicate

- **FILE #3:** `backend/archive/seat_allocators_v1/smart_seat_allocation.py`
  - Status: RETIRED duplicate

- **FILE #4:** `backend/archive/seat_allocators_consolidated/*` (multiple versions)
  - Status: CONSOLIDATED but RETIRED

- **FILE #5:** `backend/domains/inventory/seat_allocator.py` (482 lines) **CANONICAL**
  - Features: All v1 features PLUS ML integration points
  - Imports: Shared infrastructure (SeatAllocationResult, PassengerPreference, OccupancyMetricsCollector)
  - Status: PRODUCTION-READY with metrics

### CONSOLIDATION PLAN:
```
KEEP (Ultimate Version): backend/domains/inventory/seat_allocator.py
MERGE FROM: Enhanced features from archive if present
ARCHIVE TO: archive/seat_allocators_v1/ (already archived)
DELETE: backend/archive/seat_allocators_consolidated/
```

### KEY FEATURES IN ULTIMATE VERSION (backend/domains/inventory/seat_allocator.py):
- Fair multi-coach distribution algorithm
- Berth preference optimization (lower, upper, side, coupe)
- Family seat grouping with adjacency preservation
- Accessibility requirements (disabled-accessible seats)
- Overbooking management with compensation tracking
- Waitlist management with auto-promotion
- Occupancy analytics and coach-wise breakdown
- ML integration points (OccupancyMetricsCollector)
- Metrics tracking and occupancy rate calculation
- Shared infrastructure integration (enums, data classes)

### MISSING FEATURES TO ADD:
- Revenue maximization algorithm (ML-driven yield optimization)
- ML-based demand prediction for berth preferences
- Real-time occupancy sync with inventory service
- Predictive cancellation adjustment

### ACTION ITEMS:
- [ ] VERIFY `backend/domains/inventory/seat_allocator.py` has all archive features
- [ ] ADD revenue optimization method
- [ ] ADD ML-based preference learning
- [ ] DELETE `backend/archive/seat_allocators_*` (all versions)
- [ ] UPDATE imports across codebase
- [ ] TEST seat allocation end-to-end

---

## CATEGORY 3: PRICING & COST CALCULATION

### DUPLICATES FOUND:
- **FILE #1:** `backend/archive/pricing_engines_v1/price_calculation_service.py` (~60 lines)
  - Features: Basic tax calculation (5% GST), fixed convenience fee (₹10)
  - Cons: No dynamic pricing, no ML integration
  - Status: RETIRED fallback

- **FILE #2:** `backend/archive/pricing_engines_v1/yield_management_engine.py`
  - Features: Yield management logic
  - Status: RETIRED

- **FILE #3:** `backend/archive/pricing_engines_consolidated/v1/enhanced_pricing_service.py`
  - Features: Hybrid pricing with fallback
  - Status: RETIRED

- **FILE #4:** `backend/domains/pricing/engine.py` (462 lines) **CANONICAL**
  - Features: DynamicPricingEngine with 5 pricing factors (demand, time, popularity, seasonality, competitor-aware)
  - ML Integration: TatkalDemandPredictor, RouteRankingPredictor with fallback
  - Algorithms: Geometric mean factor combination, occupancy boost, time-based bucketing
  - Status: PRODUCTION-READY

### CONSOLIDATION PLAN:
```
KEEP (Ultimate Version): backend/domains/pricing/engine.py
MERGE FROM: Yield management logic if unique
FALLBACK: Keep BasePriceCalculationService as fallback
ARCHIVE TO: archive/pricing_engines_v1/ (already archived)
DELETE: backend/archive/pricing_engines_consolidated/
```

### PRICING FACTORS IN ULTIMATE VERSION:
1. **Demand Multiplier** (0.9 - 1.6x): ML demand + occupancy boost (0.8 - 1.3x)
2. **Time Multiplier** (0.85 - 1.40x): 14+ days (0.85) → <6 hours (1.40)
3. **Route Popularity Multiplier** (0.9 - 1.15x)
4. **Seasonality Multiplier** (0.9 - 1.35x): Holiday (1.35) → Off-season (0.90)
5. **Competitor-Aware Multiplier** (0.92 - 1.08x): Undercuts if 20%+ more expensive

### KEY ALGORITHMS:
- Geometric Mean Factor Combination (more stable than arithmetic)
- Exponential growth occupancy boost model
- Discrete pricing bands by time-to-departure
- Ratio-based competitor parity adjustment
- Tatkal Surge: 1.5x multiplier
- Overall Bounds: 0.8x - 2.5x multiplier
- Taxes & Fees: 5% GST + ₹10 convenience fee

### MISSING FEATURES TO ADD:
- Real-time competitor price integration (API feed)
- Revenue management optimization (yield management)
- Group/bulk discount logic (5+ passengers = 5% discount)
- Loyalty tier pricing adjustments
- Corporate partnership rates
- Seasonal package pricing

### ACTION ITEMS:
- [ ] VERIFY `backend/domains/pricing/engine.py` has all features
- [ ] ADD competitor API integration
- [ ] ADD revenue optimization (yield management)
- [ ] ADD group discount logic
- [ ] ADD loyalty tier adjustments
- [ ] DELETE `backend/archive/pricing_engines_*` (all versions)
- [ ] UPDATE imports and tests
- [ ] PERFORMANCE test (100K+ queries/sec)

---

## CATEGORY 4: CACHING

### DUPLICATES FOUND:
- **FILE #1:** `backend/archive/cache_managers_v1/multi_layer_cache.py`
  - Status: RETIRED

- **FILE #2:** `backend/archive/cache_managers_consolidated/v1/cache_service.py`
  - Status: RETIRED

- **FILE #3:** `backend/archive/cache_managers_consolidated/v1/cache_warming_service.py`
  - Status: RETIRED

- **FILE #4:** `backend/archive/cache_managers_consolidated/v1/multi_layer_cache.py`
  - Status: RETIRED

- **FILE #5:** `backend/platform/cache/manager.py` **CANONICAL**
  - Features: Multi-layer caching architecture
  - Status: CURRENT (PRODUCTION)

- **FILE #6:** `backend/platform/cache/warming.py` **CANONICAL**
  - Features: Cache warming implementation
  - Status: CURRENT (PRODUCTION)

### CONSOLIDATION PLAN:
```
KEEP (Canonical): backend/platform/cache/manager.py
KEEP (Canonical): backend/platform/cache/warming.py
VERIFY: Feature parity with archive versions
DELETE: backend/archive/cache_managers_*/ (all versions)
```

### MULTI-LAYER CACHE ARCHITECTURE:
- **Layer 1 — Query Cache:** Route search results (TTL: 2-10min, hit rate: 60-80%)
- **Layer 2 — Partial Route Cache:** Station reachability graphs
- **Layer 3 — Seat Availability Cache:** Real-time inventory (TTL: 30s-2min)
- **Layer 4 — ML Feature Cache:** Precomputed ML features

### KEY FEATURES:
- Intelligent TTL management based on data volatility
- Cache warming strategies for popular routes
- Automatic invalidation on data changes
- Performance monitoring and hit rate tracking
- Memory-efficient serialization (JSON/pickle/zlib)
- Shared infrastructure integration (RouteQuery, AvailabilityQuery, CacheMetricsCollector)
- Redis multi-instance support

### ACTION ITEMS:
- [ ] READ and VERIFY backend/platform/cache/manager.py
- [ ] READ and VERIFY backend/platform/cache/warming.py
- [ ] COMPARE with archive versions for feature parity
- [ ] DELETE backend/archive/cache_managers_*/ (all versions)
- [ ] UPDATE imports to platform/cache/
- [ ] LOAD test (cache hit rates, TTL management)

---

## CATEGORY 5: BOOKING & RESERVATIONS

### DUPLICATES FOUND:
- **FILE #1:** `backend/archive/booking_consolidated/v1/booking_service.py` (~300 lines)
  - Features: Core booking logic, PNR generation, passenger details, transaction handling
  - Status: RETIRED

- **FILE #2:** `backend/archive/booking_consolidated/v1/booking_orchestrator.py`
  - Features: Orchestration layer
  - Status: RETIRED

- **FILE #3:** `backend/archive/booking_consolidated/v1/booking_api.py`
  - Features: API layer
  - Status: RETIRED

- **FILE #4:** `backend/domains/booking/service.py` (already reviewed) **CANONICAL**
  - Features: PNR generation, passenger details, serializable transactions, event publishing
  - Status: CURRENT (NEW - MIGRATED)

### CONSOLIDATION PLAN:
```
KEEP (Canonical): backend/domains/booking/service.py
INTERFACES: backend/domains/booking/interfaces.py
MERGE FROM: Verify all archive features are present
ARCHIVE TO: archive/booking_consolidated/v1/ (already archived)
DELETE: backend/archive/booking_consolidated/
```

### KEY FEATURES IN ULTIMATE VERSION:
- Booking creation with PNR generation (unique constraint checking)
- Passenger details tracking (name, age, gender, document, concession)
- Serializable transaction isolation (race condition prevention)
- Retry logic (MAX_RETRIES = 3)
- Travel date validation
- Event publishing (BookingCreatedEvent)
- Booking status management (pending, confirmed, cancelled)

### ACTION ITEMS:
- [ ] VERIFY `backend/domains/booking/service.py` has archive features
- [ ] VERIFY booking API calls domain service
- [ ] DELETE `backend/archive/booking_consolidated/`
- [ ] UPDATE all imports to use domains/booking/service.py
- [ ] TEST booking creation end-to-end
- [ ] TEST race condition prevention

---

## CATEGORY 6: PAYMENT PROCESSING

### DUPLICATES FOUND:
- **FILE #1:** `backend/archive/payment_consolidated/v1/payment_service.py` (~150 lines)
  - Features: Razorpay integration, order creation, payment verification, webhook verification
  - Status: RETIRED

- **FILE #2:** `backend/api/payments.py`
  - Features: API endpoint layer
  - Status: CURRENT (API)

- **FILE #3:** `backend/domains/payment/service.py` (already reviewed) **CANONICAL**
  - Features: Razorpay async integration, signature verification, webhook handling
  - Status: CURRENT (NEW - MIGRATED)

### CONSOLIDATION PLAN:
```
KEEP (Canonical): backend/domains/payment/service.py
API LAYER: backend/api/payments.py (calls domain service)
MERGE FROM: Verify all archive features
ARCHIVE TO: archive/payment_consolidated/v1/ (already archived)
DELETE: backend/archive/payment_consolidated/
```

### KEY FEATURES IN ULTIMATE VERSION:
- Razorpay API integration (async with httpx)
- Order creation with idempotency support
- Payment verification via signature checking
- Webhook signature verification (HMAC-SHA256)
- Configuration validation
- Proper error handling and logging

### ACTION ITEMS:
- [ ] VERIFY `backend/domains/payment/service.py` complete
- [ ] VERIFY `backend/api/payments.py` calls domain service
- [ ] DELETE `backend/archive/payment_consolidated/`
- [ ] UPDATE imports across payment flow
- [ ] TEST payment verification end-to-end
- [ ] TEST webhook handling

---

## CATEGORY 7: STATION & TRANSPORT SERVICES

### DUPLICATES FOUND:
- **FILE #1:** `backend/archive/station_consolidated/v1/station_departure_service.py`
  - Features: Station departure scheduling
  - Status: RETIRED

- **FILE #2:** `backend/archive/station_consolidated/v1/station_service.py`
  - Features: General station operations
  - Status: RETIRED

- **FILE #3:** `backend/domains/station/departure_service.py` **CANONICAL**
  - Features: Departure service operations
  - Status: CURRENT

- **FILE #4:** `backend/domains/station/service.py`
  - Features: Station service
  - Status: CURRENT

- **FILE #5:** SEED SCRIPTS DUPLICATE
  - `backend/seed_stations.py` (root)
  - `backend/scripts/seed_stations.py`
  - Status: DUPLICATE SCRIPTS

### CONSOLIDATION PLAN:
```
KEEP (Canonical): backend/domains/station/departure_service.py
KEEP: backend/domains/station/service.py
SEED SCRIPTS: Keep in scripts/, reference from root if needed
MERGE FROM: Verify all archive features in domain services
ARCHIVE TO: archive/station_consolidated/v1/ (already archived)
DELETE: backend/archive/station_consolidated/
```

### ACTION ITEMS:
- [ ] VERIFY `backend/domains/station/` has all archive features
- [ ] CONSOLIDATE seed scripts (keep in backend/scripts/)
- [ ] DELETE `backend/archive/station_consolidated/`
- [ ] UPDATE imports
- [ ] TEST station services end-to-end

---

## CATEGORY 8: USER MANAGEMENT

### DUPLICATES FOUND:
- **FILE #1:** `backend/archive/user_consolidated/v1/user_service.py` (~200 lines)
  - Features: User CRUD, profile management
  - Status: RETIRED

- **FILE #2:** `backend/api/users.py`
  - Features: API endpoints for users
  - Status: CURRENT (API)

- **FILE #3:** `backend/domains/user/service.py` (simple, 2 lines)
  - Status: CURRENT but INCOMPLETE

### CONSOLIDATION PLAN:
```
KEEP (Canonical): backend/domains/user/service.py (EXPAND)
API LAYER: backend/api/users.py (calls domain service)
MIGRATE FROM: backend/archive/user_consolidated/v1/user_service.py
ARCHIVE TO: archive/user_consolidated/v1/ (already archived)
DELETE: backend/archive/user_consolidated/
```

### KEY FEATURES TO IMPLEMENT IN ULTIMATE VERSION:
- User CRUD operations
- Profile management
- Authentication integration
- User preferences
- Activity tracking
- Shared infrastructure integration (UserContext, etc.)

### ACTION ITEMS:
- [ ] EXPAND `backend/domains/user/service.py` with full features from archive
- [ ] UPDATE `backend/api/users.py` to call domain service
- [ ] DELETE `backend/archive/user_consolidated/`
- [ ] CREATE user interfaces/contracts
- [ ] UPDATE all user-related imports
- [ ] TEST user service end-to-end

---

## CATEGORY 9: VERIFICATION & SECURITY

### DUPLICATES FOUND:
- **FILE #1:** `backend/archive/verification_consolidated/v1/verification_engine.py`
  - Features: Verification logic
  - Status: RETIRED

- **FILE #2:** `backend/archive/verification_consolidated/v1/unlock_service.py` (~200 lines)
  - Features: Route unlock, live availability verification
  - Status: RETIRED

- **FILE #3:** `backend/domains/verification/unlock_service.py` (already reviewed) **CANONICAL**
  - Features: Route unlock recording, live availability check
  - Status: CURRENT (PRODUCTION)

### CONSOLIDATION PLAN:
```
KEEP (Canonical): backend/domains/verification/unlock_service.py
MERGE FROM: Check archive for additional verification features
ARCHIVE TO: archive/verification_consolidated/v1/ (already archived)
DELETE: backend/archive/verification_consolidated/
```

### KEY FEATURES IN ULTIMATE VERSION:
- Unlock route recording (user -> route -> payment tracking)
- Duplicate unlock prevention
- Live availability verification (simulated/API)
- Unlocked routes retrieval by user
- Payment ID linking

### ACTION ITEMS:
- [ ] VERIFY `backend/domains/verification/unlock_service.py` complete
- [ ] COMPARE with archive for missing features
- [ ] DELETE `backend/archive/verification_consolidated/`
- [ ] UPDATE imports
- [ ] TEST unlock flow end-to-end

---

## CATEGORY 10: EVENT PROCESSING

### DUPLICATES FOUND:
- **FILE #1:** `backend/archive/platform_consolidated/v1/analytics_consumer.py`
  - Features: Event consumption for analytics
  - Status: RETIRED

- **FILE #2:** `backend/archive/platform_consolidated/v1/event_producer.py` (~250 lines)
  - Features: Kafka event publishing (RouteSearchedEvent, BookingCreatedEvent, PaymentProcessedEvent)
  - Status: RETIRED

- **FILE #3:** `backend/archive/platform_consolidated/v1/performance_monitor.py`
  - Features: Performance monitoring
  - Status: RETIRED

- **FILE #4:** `backend/platform/events/producer.py` (already reviewed) **CANONICAL**
  - Features: Event production with circuit breaker, metrics, fire-and-forget
  - Status: CURRENT (PRODUCTION)

- **FILE #5:** `backend/platform/events/consumer.py` **CANONICAL**
  - Status: CURRENT (PRODUCTION)

### CONSOLIDATION PLAN:
```
KEEP (Canonical): backend/platform/events/producer.py
KEEP (Canonical): backend/platform/events/consumer.py
MERGE FROM: Verify all archive event types are supported
ARCHIVE TO: archive/platform_consolidated/v1/ (already archived)
DELETE: backend/archive/platform_consolidated/
```

### KEY EVENT TYPES IN ULTIMATE VERSION:
- **RouteSearchedEvent:** User ID, source, destination, travel date, routes shown, latency, filters
- **BookingCreatedEvent:** User ID, route ID, cost, segments, booking reference
- **PaymentProcessedEvent:** Payment details

### ARCHITECTURE:
- Kafka event backbone
- Circuit breaker for resilience
- Metrics collection (latency, failures, state)
- Fire-and-forget publishing
- TTL-based event retention

### ACTION ITEMS:
- [ ] VERIFY `backend/platform/events/producer.py` has all event types
- [ ] VERIFY `backend/platform/events/consumer.py` handles all events
- [ ] DELETE `backend/archive/platform_consolidated/`
- [ ] UPDATE event imports
- [ ] TEST event flow end-to-end
- [ ] VERIFY circuit breaker activation

---

## CATEGORY 11: GRAPH & NETWORK

### DUPLICATES FOUND:
- **FILE #1:** `backend/core/route_engine/graph.py`
  - Features: Graph structures for routing
  - Status: CURRENT

- **FILE #2:** `backend/graph_mutation_service.py`
  - Features: Real-time graph mutation
  - Status: CURRENT

- **FILE #3:** `backend/test_graph_mutation.py`
  - Features: Test file
  - Status: TEST

### CONSOLIDATION PLAN:
```
KEEP (Canonical): backend/core/route_engine/graph.py (graph structures)
KEEP: backend/graph_mutation_service.py (real-time updates)
NOTES: Verify separation of concerns is clean
```

### KEY COMPONENTS:
- **Graph structures** in `core/route_engine/graph.py`
- **Real-time mutations** in `graph_mutation_service.py`
- **Space-time nodes** for time-dependent graphs
- **Copy-on-Write overlays** for delay injection

### ACTION ITEMS:
- [ ] VERIFY separation of concerns between graph.py and graph_mutation_service.py
- [ ] READ and ANALYZE both files for duplicate logic
- [ ] TEST graph mutations end-to-end
- [ ] UPDATE relative imports if needed

---

## CATEGORY 12: ML/INTELLIGENCE

### DUPLICATES FOUND:
- **DELAY PREDICTORS:**
  - `backend/intelligence/models/delay_predictor.py` (DUPLICATE)
  - `backend/services/delay_predictor.py` **CANONICAL** (already reviewed)

- **ROUTE RANKING/DEMAND:**
  - `backend/core/ml_ranking_model.py` (DUPLICATE)
  - `backend/services/route_ranking_predictor.py`
  - `backend/intelligence/models/route_ranker.py` (DUPLICATE)

- **OTHER PREDICTORS:**
  - `backend/intelligence/models/cancellation.py` (DUPLICATE)
  - `backend/services/cancellation_predictor.py`
  - `backend/services/tatkal_demand_predictor.py`
  - `backend/intelligence/models/demand.py` (DUPLICATE)

- **DATA COLLECTION/TRAINING:**
  - `backend/ml_data_collection.py` (DUPLICATE)
  - `backend/scripts/ml_collect_data.py` **CANONICAL**
  - `backend/ml_training_pipeline.py` (DUPLICATE)
  - `backend/scripts/ml_train.py` **CANONICAL**

- **SETUP & CONFIG:**
  - `backend/setup_ml_database.py` (DUPLICATE)
  - `backend/database/setup.py`
  - `backend/ml_reliability_model.py` **CANONICAL**
  - `backend/core/ml_integration.py` **CANONICAL**

### CONSOLIDATION PLAN:
```
STRUCTURE AFTER CONSOLIDATION:
backend/
├── core/
│   ├── ml_integration.py           [MLModelRegistry, FeatureEngineer]
│   └── ml_ranking_model.py         (DELETE - consolidate to services/)
├── services/                        [Live Prediction Services]
│   ├── __init__.py                 [Service registry]
│   ├── delay_predictor.py          **CANONICAL**
│   ├── route_ranking_predictor.py  **CANONICAL**
│   ├── cancellation_predictor.py   **CANONICAL**
│   └── tatkal_demand_predictor.py  **CANONICAL**
├── intelligence/
│   ├── models/
│   │   ├── __init__.py
│   │   └── base_model.py           [Abstract Model class]
│   └── training/
│       ├── __init__.py
│       ├── data_collection.py      [renamed from ml_data_collection.py]
│       ├── pipeline.py             [renamed from ml_training_pipeline.py]
│       └── setup_db.py
├── ml_reliability_model.py         **CANONICAL** (keep as-is)
├── ml_feature_store_schema.sql     **CANONICAL**
└── scripts/
    ├── ml_collect_data.py          **CANONICAL** (wrapper)
    ├── ml_train.py                 **CANONICAL** (wrapper)
    └── run_ml_collection.py
```

### KEY PREDICTORS IN ULTIMATE VERSION:
1. **DelayPredictor** (`services/delay_predictor.py`)
   - RandomForest-based delay prediction
   - Real-time delay updates from TrainDelayed events
   - Model loading/training with scaffolding

2. **RouteRankingPredictor** (`services/route_ranking_predictor.py`)
   - Route popularity ranking

3. **CancellationPredictor** (`services/cancellation_predictor.py`)
   - Cancellation probability prediction

4. **TatkalDemandPredictor** (`services/tatkal_demand_predictor.py`)
   - Tatkal demand scoring

### ML REGISTRY (backend/core/ml_integration.py):
- Unified model registration
- Single loading/initialization path
- Fallback mechanisms
- FeatureEngineer for feature computation

### ACTION ITEMS:
- [ ] DELETE `backend/intelligence/models/delay_predictor.py`
- [ ] DELETE `backend/intelligence/models/route_ranker.py`
- [ ] DELETE `backend/intelligence/models/cancellation.py`
- [ ] DELETE `backend/intelligence/models/demand.py`
- [ ] DELETE `backend/core/ml_ranking_model.py`
- [ ] DELETE `backend/ml_data_collection.py` (root)
- [ ] DELETE `backend/ml_training_pipeline.py` (root)
- [ ] DELETE `backend/setup_ml_database.py`
- [ ] CREATE `backend/intelligence/training/` directory
- [ ] RENAME `ml_data_collection.py` → `intelligence/training/data_collection.py`
- [ ] RENAME `ml_training_pipeline.py` → `intelligence/training/pipeline.py`
- [ ] UNIFY `ml_reliability_model.py` registration in ML registry
- [ ] VERIFY all predictors register with `core/ml_integration.py`
- [ ] UPDATE all predictor imports
- [ ] TEST all ML services end-to-end

---

## SUMMARY TABLE: CONSOLIDATED LOCATIONS

| Category | Archive | Current Canonical | Domain/Platform | Status |
|----------|---------|------------------|----------------|--------|
| **Route Engines** | v1 (1007L) | core/route_engine.py (2447L) | domains/routing/engine.py | READY (complete) |
| **Seat Allocation** | v1 consolidated | - | domains/inventory/seat_allocator.py (482L) | READY (add features) |
| **Pricing** | v1 enhanced | - | domains/pricing/engine.py (462L) | READY (add features) |
| **Caching** | v1 consolidated | - | platform/cache/ | READY (verify) |
| **Booking** | v1 consolidated | - | domains/booking/service.py | READY (complete) |
| **Payment** | v1 consolidated | - | domains/payment/service.py | READY (complete) |
| **Station** | v1 consolidated | - | domains/station/ | READY (verify) |
| **User** | v1 consolidated | - | domains/user/service.py | NEEDS EXPANSION |
| **Verification** | v1 consolidated | - | domains/verification/unlock_service.py | READY (verify) |
| **Events** | v1 consolidated | - | platform/events/ | READY (verify) |
| **Graph** | - | core/route_engine/graph.py | graph_mutation_service.py | READY (verify) |
| **ML/Intelligence** | models/ | services/ + core/ml_integration.py | intelligence/training/ | NEEDS REORGANIZATION |

---

## FILES TO CREATE

1. `backend/intelligence/training/__init__.py`
2. `backend/intelligence/training/data_collection.py` (from ml_data_collection.py)
3. `backend/intelligence/training/pipeline.py` (from ml_training_pipeline.py)
4. `backend/intelligence/training/setup_db.py` (from setup_ml_database.py)
5. `backend/intelligence/models/base_model.py` (abstract base)

---

## FILES TO DELETE

### Archive Deletions:
1. `backend/archive/route_engines_consolidated/` (entire)
2. `backend/archive/seat_allocators_consolidated/` (entire)
3. `backend/archive/pricing_engines_consolidated/` (entire)
4. `backend/archive/cache_managers_consolidated/` (entire)
5. `backend/archive/booking_consolidated/` (entire)
6. `backend/archive/payment_consolidated/` (entire)
7. `backend/archive/station_consolidated/` (entire)
8. `backend/archive/user_consolidated/` (entire)
9. `backend/archive/verification_consolidated/` (entire)
10. `backend/archive/platform_consolidated/` (entire)

### Root/Duplicate Deletions:
1. `backend/core/archive/` (old versions)
2. `backend/ml_data_collection.py` (move to intelligence/training/)
3. `backend/ml_training_pipeline.py` (move to intelligence/training/)
4. `backend/setup_ml_database.py` (move to intelligence/training/)
5. `backend/core/ml_ranking_model.py` (consolidate to services/)
6. `backend/intelligence/models/delay_predictor.py` **DUPLICATE**
7. `backend/intelligence/models/route_ranker.py` **DUPLICATE**
8. `backend/intelligence/models/cancellation.py` **DUPLICATE**
9. `backend/intelligence/models/demand.py` **DUPLICATE**

---

## IMPORT UPDATE MAPPING

### After consolidation, all imports should follow this pattern:

```python
# ROUTING
from backend.core.route_engine import OptimizedRAPTOR, HubManager
from backend.domains.routing.engine import search_routes

# INVENTORY
from backend.domains.inventory.seat_allocator import AdvancedSeatAllocationEngine

# PRICING
from backend.domains.pricing.engine import DynamicPricingEngine

# CACHING
from backend.platform.cache.manager import MultiLayerCache
from backend.platform.cache.warming import CacheWarmingService

# BOOKING
from backend.domains.booking.service import BookingService

# PAYMENT
from backend.domains.payment.service import PaymentService

# STATION
from backend.domains.station.departure_service import StationDepartureService

# USER
from backend.domains.user.service import UserService

# VERIFICATION
from backend.domains.verification.unlock_service import UnlockService

# EVENTS
from backend.platform.events.producer import EventProducer
from backend.platform.events.consumer import EventConsumer

# ML/INTELLIGENCE
from backend.core.ml_integration import MLModelRegistry, FeatureEngineer
from backend.services.delay_predictor import DelayPredictor
from backend.services.route_ranking_predictor import RouteRankingPredictor
from backend.services.cancellation_predictor import CancellationPredictor
from backend.services.tatkal_demand_predictor import TatkalDemandPredictor
from backend.ml_reliability_model import ReliabilityModel
from backend.intelligence.training.data_collection import collect_training_data
from backend.intelligence.training.pipeline import train_models
```

---

## FINAL BACKEND DIRECTORY STRUCTURE

```
backend/
├── archive/                          [DEPRECATED - for historical reference only]
│   ├── {duplicates_consolidated}/
│   ├── deprecated/
│   └── route_engines_v1/            [Keep as reference only]
├── api/                             [REST API endpoints]
├── api_gateway/
├── core/                            [Core algorithms & infrastructure]
│   ├── __init__.py
│   ├── data_structures.py           [Shared data classes]
│   ├── metrics.py                   [Metrics collectors]
│   ├── ml_integration.py            [ML registry & feature engineer]
│   ├── utils.py                     [Utilities]
│   ├── ml_reliability_model.py      [Delay/reliability prediction]
│   ├── route_engine.py              [Main RAPTOR engine]
│   ├── route_engine/                [Route engine submodules]
│   ├── validator/                   [Validation framework]
│   └── realtime_event_processor.py
├── domains/                         [Domain-specific business logic]
│   ├── booking/                     [Booking domain]
│   ├── inventory/                   [Inventory/Seat allocation]
│   ├── payment/                     [Payment domain]
│   ├── pricing/                     [Pricing domain]
│   ├── routing/                     [Routing domain]
│   ├── station/                     [Station domain]
│   ├── user/                        [User domain]
│   └── verification/                [Verification domain]
├── platform/                        [Shared platform services]
│   ├── cache/                       [Caching services]
│   ├── events/                      [Event processing]
│   ├── graph/                       [Graph services]
│   ├── integrations/                [External integrations]
│   ├── monitoring/                  [Monitoring & observability]
│   └── security/                    [Security services]
├── services/                        [Live prediction services]
│   ├── __init__.py                  [Service registry]
│   ├── delay_predictor.py           **CANONICAL**
│   ├── route_ranking_predictor.py   **CANONICAL**
│   ├── cancellation_predictor.py    **CANONICAL**
│   ├── tatkal_demand_predictor.py   **CANONICAL**
│   ├── redirect_service.py
│   ├── review_service.py
│   ├── hybrid_search_service.py
│   └── perf_check.py
├── intelligence/                    [ML training & models]
│   ├── models/
│   │   ├── __init__.py
│   │   └── base_model.py            [Abstract model class]
│   └── training/
│       ├── __init__.py
│       ├── data_collection.py       [Training data collection]
│       ├── pipeline.py              [Model training]
│       └── setup_db.py              [Database setup]
├── scripts/                         [Maintenance & utility scripts]
│   ├── ml_collect_data.py           **CANONICAL**
│   ├── ml_train.py                  **CANONICAL**
│   └── run_ml_collection.py
├── database/
├── models/
├── schemas/
├── utils/
├── ml_feature_store_schema.sql      **CANONICAL**
└── app.py
```

---

## EXECUTION ROADMAP

### PHASE 1: ML CONSOLIDATION (HIGH PRIORITY)
- [ ] Create `backend/intelligence/training/` structure
- [ ] Move ML files to correct locations
- [ ] Delete duplicates from intelligence/models/ and root
- [ ] Update all ML imports
- [ ] Test ML services

### PHASE 2: DOMAIN CONSOLIDATION (HIGH PRIORITY)
- [ ] Expand `domains/user/service.py` with full features
- [ ] Verify all domains complete vs archives
- [ ] Delete archive consolidated/* folders
- [ ] Update all domain imports
- [ ] Test all domain services

### PHASE 3: PLATFORM CONSOLIDATION (MEDIUM PRIORITY)
- [ ] Verify platform/cache/ and platform/events/ complete
- [ ] Delete archive/cache_managers_* and archive/platform_consolidated/
- [ ] Update platform imports
- [ ] Load test cache and events

### PHASE 4: ROUTE ENGINE REFACTORING (MEDIUM PRIORITY)
- [ ] Complete domains/routing/engine.py
- [ ] Verify core/route_engine.py production-ready
- [ ] Delete route_engines_v1/ and consolidated/
- [ ] Update route engine imports
- [ ] Performance test (5ms target)

### PHASE 5: FEATURE ENHANCEMENTS (LOW PRIORITY)
- [ ] Add revenue optimization to pricing engine
- [ ] Add competitor API integration
- [ ] Add ML preference learning to seat allocator
- [ ] Add group discount logic
- [ ] Add loyalty tier pricing

### PHASE 6: CLEANUP (ONGOING)
- [ ] Delete all archive consolidated/* folders
- [ ] Update test imports
- [ ] Delete test files for removed code
- [ ] Run full test suite
- [ ] Verify performance targets

---

## RISK MITIGATION

| Action | Risk | Mitigation |
|--------|------|-----------|
| Delete archive versions | Code loss if not migrated properly | VERIFY feature parity first, keep in git history |
| Consolidate ML layer | Break existing imports | Create backwards-compat aliases temporarily |
| Expand domains/user/ | Incomplete migration | Follow booking/payment patterns exactly |
| Delete consolidated/ | Missing features | READ each archive file before deletion |
| Move ML training scripts | Break scripts | Test scripts in new location before deletion |

---

## STATISTICS

- **Total Duplicate Files Identified:** 47+
- **Files to CREATE:** 4 (intelligence/training/ structure)
- **Files to DELETE:** 25+ (archives + duplicates)
- **Files to MODIFY/EXPAND:** 8 (domain services)
- **Files to KEEP (Canonical):** 15
- **Total Lines of Duplicated Code:** 10,000+
- **Redundancy Factor:** 40-50% of entire codebase
- **Estimated Implementation Time:** 2-3 weeks (with thorough testing)

---

## NEXT STEPS

1. **Review this plan systematically** - Ensure all 12 categories are addressed
2. **Execute Phase 1 (ML)** - Reorganize intelligence layer
3. **Execute Phase 2 (Domains)** - Complete domain services
4. **Execute Phases 3-4** - Platform and route engine consolidation
5. **Run full test suite** - Verify no regressions
6. **Performance test** - Verify targets met
7. **Clean git history** - Remove temporary branches
8. **Document final structure** - Update architecture docs

---

**Status:** READY FOR EXECUTION
**Next Action:** Begin with Phase 1 (ML Consolidation)
**Review Date:** 2026-02-20

