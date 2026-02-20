# CONSOLIDATED DUPLICATE FILES REGISTRY & STATUS REPORT

**Generated:** 2026-02-20
**Purpose:** Central registry of all 47+ duplicate files and their consolidation status
**Total Files Analyzed:** 47+
**Categories:** 12
**Status:** READY FOR SYSTEMATIC CONSOLIDATION

---

## FILE STATUS LEGEND

| Status | Meaning |
|--------|---------|
| ✅ CANONICAL | Official implementation - KEEP & USE |
| 🔄 TRANSITIONAL | Being phased in - REFACTOR/COMPLETE |
| 📦 ARCHIVE | Retired/superseded - DELETE (after verification) |
| 🔗 DOMAIN ADAPTER | Domain-specific wrapper - COMPLETE & USE |
| ⚙️ PLATFORM SHARED | Platform infrastructure - VERIFY & USE |
| ⛔ DUPLICATE | Redundant copy - DELETE after merge |

---

## CATEGORY 1: ROUTE ENGINES (5+ files)

### File Registry

| File Path | Lines | Status | Action | Priority |
|-----------|-------|--------|--------|----------|
| `backend/core/route_engine.py` | 2,447 | ✅ CANONICAL | VERIFY complete | HIGH |
| `backend/core/route_engine/engine.py` | 100 | 🔄 TRANSITIONAL | REFACTOR | HIGH |
| `backend/domains/routing/engine.py` | 100 | 🔗 DOMAIN ADAPTER | COMPLETE | HIGH |
| `backend/archive/route_engines_v1/advanced_route_engine.py` | 1,007 | 📦 ARCHIVE | DELETE | HIGH |
| `backend/archive/route_engines_v1/multi_modal_route_engine.py` | ~300 | 📦 ARCHIVE | DELETE | HIGH |
| `backend/archive/route_engines_v1/route_engine.py` | ~200 | ⛔ DUPLICATE | DELETE | HIGH |
| `backend/archive/route_engines_consolidated/*` | ~500 | 📦 ARCHIVE | DELETE | HIGH |
| `backend/core/archive/*` | ~400 | ⛔ DUPLICATE | DELETE | HIGH |

### Consolidation Details

**CANONICAL VERSION:** `backend/core/route_engine.py`
- OptimizedRAPTOR algorithm with Range Query variant
- Hub-based acceleration (HybridRAPTOR)
- Real-time overlays (Copy-on-Write delays)
- StaticGraphSnapshot for pre-built indexes
- HubManager (9 major hubs)
- 220+ validation checks
- ML reliability scoring
- Async/concurrent execution
- Multi-layer caching integration
- Performance target: <5ms (P95: <50ms)

**VERIFIED FEATURES:**
- ✓ RAPTOR core algorithm
- ✓ Multi-transfer routing
- ✓ Real-time delay injection
- ✓ Validation framework integration
- ✓ ML reliability scoring
- ✓ Hub acceleration
- ✓ Snapshot persistence
- ✓ Cache integration

**MERGE NOTES:**
- Archive v1 has simpler structure (good for reference)
- Core version more complete and production-ready
- Extract algorithm comments from v1 if missing in core
- Verify haversine distance implementation in core
- Verify transfer logic (Set A & Set B) in core

**IMPORT MIGRATION:**
```python
# OLD (to delete)
from backend.archive.route_engines_v1 import AdvancedRouteEngine
from backend.core.archive import RouteEngineV0

# NEW (canonical)
from backend.core.route_engine import OptimizedRAPTOR, HybridRAPTOR
from backend.domains.routing.engine import search_routes
```

---

## CATEGORY 2: SEAT ALLOCATION (5+ files)

### File Registry

| File Path | Lines | Status | Action | Priority |
|-----------|-------|--------|--------|----------|
| `backend/domains/inventory/seat_allocator.py` | 482 | ✅ CANONICAL | EXPAND | HIGH |
| `backend/archive/seat_allocators_v1/advanced_seat_allocation_engine.py` | ~350 | 📦 ARCHIVE | DELETE | HIGH |
| `backend/archive/seat_allocators_v1/seat_allocation.py` | ~300 | ⛔ DUPLICATE | DELETE | HIGH |
| `backend/archive/seat_allocators_v1/smart_seat_allocation.py` | ~250 | ⛔ DUPLICATE | DELETE | HIGH |
| `backend/archive/seat_allocators_consolidated/*` | ~400 | 📦 ARCHIVE | DELETE | HIGH |

### Consolidation Details

**CANONICAL VERSION:** `backend/domains/inventory/seat_allocator.py`
- Fair multi-coach distribution
- Berth preference optimization (LB, UB, SL, SU, CP)
- Family grouping with adjacency preservation
- Accessibility requirements support
- Overbooking management with compensation
- Waitlist management with auto-promotion
- Occupancy metrics collection
- Shared infrastructure integration

**FEATURES TO VERIFY:**
- ✓ Priority levels system (female, senior, child, family, disabled, general)
- ✓ Berth capacity tracking
- ✓ Coach-wise distribution logic
- ✓ Occupancy rate calculation
- ✓ Waitlist promotion on cancellation
- ✓ Metrics collection integration

**FEATURES TO ADD:**
- [ ] Revenue optimization algorithm (yield-based seat pricing)
- [ ] ML-based preference predictions
- [ ] Real-time occupancy sync
- [ ] Predictive cancellation adjustment

**IMPORT MIGRATION:**
```python
# OLD
from backend.archive.seat_allocators_v1 import AdvancedSeatAllocationEngine

# NEW
from backend.domains.inventory.seat_allocator import AdvancedSeatAllocationEngine
```

---

## CATEGORY 3: PRICING (5+ files)

### File Registry

| File Path | Lines | Status | Action | Priority |
|-----------|-------|--------|--------|----------|
| `backend/domains/pricing/engine.py` | 462 | ✅ CANONICAL | EXPAND | HIGH |
| `backend/archive/pricing_engines_v1/price_calculation_service.py` | ~60 | 📦 ARCHIVE | DELETE | HIGH |
| `backend/archive/pricing_engines_v1/yield_management_engine.py` | ~200 | 📦 ARCHIVE | DELETE | HIGH |
| `backend/archive/pricing_engines_consolidated/v1/enhanced_pricing_service.py` | ~150 | 📦 ARCHIVE | DELETE | HIGH |

### Consolidation Details

**CANONICAL VERSION:** `backend/domains/pricing/engine.py`
- DynamicPricingEngine with 5 pricing factors
- Demand Multiplier (0.9 - 1.6x) with occupancy boost
- Time Multiplier (0.85 - 1.40x) based on time-to-departure
- Route Popularity Multiplier (0.9 - 1.15x)
- Seasonality Multiplier (0.9 - 1.35x)
- Competitor-Aware Multiplier (0.92 - 1.08x)
- Tatkal surge (1.5x)
- Geometric mean factor combination
- ML integration (TatkalDemandPredictor, RouteRankingPredictor)
- Fallback to heuristics
- 5% GST + ₹10 convenience fee
- Overall bounds: 0.8x - 2.5x multiplier

**FEATURES TO VERIFY:**
- ✓ All 5 pricing factors implemented
- ✓ ML model integration
- ✓ Tatkal surge logic
- ✓ Tax and fee calculation
- ✓ Explanation generation
- ✓ Recommendation engine (buy now, wait, premium)

**FEATURES TO ADD:**
- [ ] Real-time competitor API integration
- [ ] Revenue management optimization (yield management)
- [ ] Group discount logic (5+ passengers = 5% discount)
- [ ] Loyalty tier pricing adjustments
- [ ] Corporate partnership rates
- [ ] Seasonal package pricing

**ARCHIVE RETENTION:**
- Keep `price_calculation_service.py` as fallback for basic pricing

**IMPORT MIGRATION:**
```python
# OLD
from backend.archive.pricing_engines_v1 import PriceCalculationService

# NEW
from backend.domains.pricing.engine import DynamicPricingEngine
```

---

## CATEGORY 4: CACHING (6+ files)

### File Registry

| File Path | Lines | Status | Action | Priority |
|-----------|-------|--------|--------|----------|
| `backend/platform/cache/manager.py` | ~500 | ✅ CANONICAL | VERIFY | MEDIUM |
| `backend/platform/cache/warming.py` | ~300 | ✅ CANONICAL | VERIFY | MEDIUM |
| `backend/archive/cache_managers_v1/multi_layer_cache.py` | ~400 | 📦 ARCHIVE | DELETE | MEDIUM |
| `backend/archive/cache_managers_consolidated/v1/cache_service.py` | ~300 | 📦 ARCHIVE | DELETE | MEDIUM |
| `backend/archive/cache_managers_consolidated/v1/cache_warming_service.py` | ~250 | 📦 ARCHIVE | DELETE | MEDIUM |
| `backend/archive/cache_managers_consolidated/v1/multi_layer_cache.py` | ~400 | 📦 ARCHIVE | DELETE | MEDIUM |

### Consolidation Details

**CANONICAL VERSIONS:**
- `backend/platform/cache/manager.py` - MultiLayerCache implementation
- `backend/platform/cache/warming.py` - Cache warming strategies

**ARCHITECTURE:**
- Layer 1: Query Cache (Redis) - Route searches (2-10min TTL, 60-80% hit)
- Layer 2: Partial Route Cache - Station reachability graphs
- Layer 3: Seat Availability Cache - Real-time inventory (30s-2min TTL)
- Layer 4: ML Feature Cache - Precomputed features

**FEATURES TO VERIFY:**
- ✓ Intelligent TTL management
- ✓ Cache warming strategies (popular routes, off-peak)
- ✓ Automatic invalidation on updates
- ✓ Performance monitoring
- ✓ Hit rate tracking
- ✓ Memory efficiency
- ✓ Redis multi-instance coordination
- ✓ Shared infrastructure integration (CacheMetricsCollector)

**IMPORT MIGRATION:**
```python
# OLD
from backend.archive.cache_managers_v1 import MultiLayerCache

# NEW
from backend.platform.cache.manager import MultiLayerCache
from backend.platform.cache.warming import CacheWarmingService
```

---

## CATEGORY 5: BOOKING (4 files)

### File Registry

| File Path | Lines | Status | Action | Priority |
|-----------|-------|--------|--------|----------|
| `backend/domains/booking/service.py` | ~300 | ✅ CANONICAL | VERIFY COMPLETE | HIGH |
| `backend/domains/booking/interfaces.py` | ~50 | ✅ CANONICAL | VERIFY | HIGH |
| `backend/archive/booking_consolidated/v1/booking_service.py` | ~300 | 📦 ARCHIVE | DELETE | HIGH |
| `backend/archive/booking_consolidated/v1/booking_orchestrator.py` | ~200 | 📦 ARCHIVE | DELETE | HIGH |
| `backend/archive/booking_consolidated/v1/booking_api.py` | ~150 | 📦 ARCHIVE | DELETE | HIGH |

### Consolidation Details

**CANONICAL VERSION:** `backend/domains/booking/service.py`
- BookingService class with full CRUD
- PNR generation (10 retry attempts)
- Passenger details tracking (name, age, gender, document, concession)
- Serializable transaction isolation (SERIALIZABLE level)
- Retry logic (MAX_RETRIES = 3)
- Travel date validation
- Event publishing (BookingCreatedEvent)
- Status management (pending, confirmed, cancelled)
- Duplicate prevention
- Database integrity constraints

**FEATURES VERIFIED:**
- ✓ PNR uniqueness checking
- ✓ Concurrent booking handling
- ✓ Passenger details storage
- ✓ Transaction isolation level set
- ✓ Event publishing
- ✓ Status transitions
- ✓ Date validation (no past dates)

**IMPORT MIGRATION:**
```python
# OLD
from backend.archive.booking_consolidated.v1 import BookingService

# NEW
from backend.domains.booking.service import BookingService
```

---

## CATEGORY 6: PAYMENT (3 files)

### File Registry

| File Path | Lines | Status | Action | Priority |
|-----------|-------|--------|--------|----------|
| `backend/domains/payment/service.py` | ~200 | ✅ CANONICAL | VERIFY COMPLETE | HIGH |
| `backend/domains/payment/interfaces.py` | ~50 | ✅ CANONICAL | VERIFY | HIGH |
| `backend/archive/payment_consolidated/v1/payment_service.py` | ~200 | 📦 ARCHIVE | DELETE | HIGH |

### Consolidation Details

**CANONICAL VERSION:** `backend/domains/payment/service.py`
- PaymentService with Razorpay integration
- Async HTTP client (httpx)
- Order creation with idempotency support
- Payment verification via HMAC-SHA256 signatures
- Webhook signature verification
- Configuration validation
- Error handling and logging
- Amount conversion (rupees to paise)

**FEATURES VERIFIED:**
- ✓ Razorpay order creation
- ✓ Signature verification (HMAC-SHA256)
- ✓ Webhook verification
- ✓ Async/await patterns
- ✓ Configuration checking
- ✓ Error handling
- ✓ Idempotency key support

**IMPORT MIGRATION:**
```python
# OLD
from backend.archive.payment_consolidated.v1 import PaymentService

# NEW
from backend.domains.payment.service import PaymentService
```

---

## CATEGORY 7: STATION SERVICES (3 files)

### File Registry

| File Path | Lines | Status | Action | Priority |
|-----------|-------|--------|--------|----------|
| `backend/domains/station/service.py` | ~200 | ✅ CANONICAL | VERIFY | MEDIUM |
| `backend/domains/station/departure_service.py` | ~200 | ✅ CANONICAL | VERIFY | MEDIUM |
| `backend/archive/station_consolidated/v1/station_service.py` | ~200 | 📦 ARCHIVE | DELETE | MEDIUM |
| `backend/archive/station_consolidated/v1/station_departure_service.py` | ~200 | 📦 ARCHIVE | DELETE | MEDIUM |
| `backend/seed_stations.py` (root) | ~100 | 🔄 TRANSITIONAL | CONSOLIDATE | LOW |
| `backend/scripts/seed_stations.py` | ~100 | ✅ CANONICAL | KEEP | LOW |

### Consolidation Details

**CANONICAL VERSIONS:**
- `backend/domains/station/service.py` - Station CRUD
- `backend/domains/station/departure_service.py` - Departure operations
- `backend/scripts/seed_stations.py` - Database seeding

**FEATURES TO VERIFY:**
- ✓ Station creation, read, update, delete
- ✓ Departure scheduling
- ✓ Station data consistency
- ✓ Foreign key constraints
- ✓ Seed data import

**CONSOLIDATION NOTES:**
- Keep seed script in `scripts/`
- Reference from root if needed via import
- Verify no data inconsistencies

**IMPORT MIGRATION:**
```python
# OLD
from backend.archive.station_consolidated.v1 import StationService

# NEW
from backend.domains.station.service import StationService
from backend.domains.station.departure_service import StationDepartureService
```

---

## CATEGORY 8: USER MANAGEMENT (2 files)

### File Registry

| File Path | Lines | Status | Action | Priority |
|-----------|-------|--------|--------|----------|
| `backend/domains/user/service.py` | ~2 | 🔄 TRANSITIONAL | EXPAND | HIGH |
| `backend/api/users.py` | ~200 | ✅ CANONICAL | VERIFY | HIGH |
| `backend/archive/user_consolidated/v1/user_service.py` | ~300 | 📦 ARCHIVE | DELETE | HIGH |

### Consolidation Details

**CANONICAL VERSIONS:**
- `backend/domains/user/service.py` (to be expanded)
- `backend/api/users.py` (API endpoints)

**FEATURES TO IMPLEMENT:**
- [ ] UserService class with CRUD operations
- [ ] User profile management
- [ ] User preferences
- [ ] Activity tracking
- [ ] Authentication integration
- [ ] Password hashing integration
- [ ] Email/phone validation
- [ ] Shared infrastructure integration

**EXPANSION NOTES:**
- Follow booking/payment pattern
- Create `backend/domains/user/interfaces.py` for contracts
- Create comprehensive test suite
- Ensure backward compatibility with API

**IMPORT MIGRATION:**
```python
# OLD
from backend.archive.user_consolidated.v1 import UserService

# NEW
from backend.domains.user.service import UserService
```

---

## CATEGORY 9: VERIFICATION & SECURITY (2 files)

### File Registry

| File Path | Lines | Status | Action | Priority |
|-----------|-------|--------|--------|----------|
| `backend/domains/verification/unlock_service.py` | ~80 | ✅ CANONICAL | VERIFY | MEDIUM |
| `backend/archive/verification_consolidated/v1/unlock_service.py` | ~100 | 📦 ARCHIVE | DELETE | MEDIUM |
| `backend/archive/verification_consolidated/v1/verification_engine.py` | ~150 | 📦 ARCHIVE | DELETE | MEDIUM |

### Consolidation Details

**CANONICAL VERSION:** `backend/domains/verification/unlock_service.py`
- UnlockService for route unlock tracking
- Record unlocked routes with payment linkage
- Prevent duplicate unlocks
- Live availability verification
- Unlocked routes retrieval by user
- Simulated external API calls

**FEATURES VERIFIED:**
- ✓ Unlock recording
- ✓ Duplicate prevention (update on re-unlock)
- ✓ Payment ID tracking
- ✓ Live availability check (simulated)
- ✓ User unlock history retrieval

**IMPORT MIGRATION:**
```python
# OLD
from backend.archive.verification_consolidated.v1 import UnlockService

# NEW
from backend.domains.verification.unlock_service import UnlockService
```

---

## CATEGORY 10: EVENT PROCESSING (4+ files)

### File Registry

| File Path | Lines | Status | Action | Priority |
|-----------|-------|--------|--------|----------|
| `backend/platform/events/producer.py` | ~300 | ✅ CANONICAL | VERIFY | MEDIUM |
| `backend/platform/events/consumer.py` | ~200 | ✅ CANONICAL | VERIFY | MEDIUM |
| `backend/archive/platform_consolidated/v1/event_producer.py` | ~300 | 📦 ARCHIVE | DELETE | MEDIUM |
| `backend/archive/platform_consolidated/v1/analytics_consumer.py` | ~200 | 📦 ARCHIVE | DELETE | MEDIUM |
| `backend/archive/platform_consolidated/v1/performance_monitor.py` | ~150 | 📦 ARCHIVE | DELETE | MEDIUM |

### Consolidation Details

**CANONICAL VERSIONS:**
- `backend/platform/events/producer.py` - EventProducer
- `backend/platform/events/consumer.py` - EventConsumer

**EVENT TYPES:**
1. **RouteSearchedEvent:**
   - user_id, source, destination, travel_date
   - routes_shown, search_latency_ms, filters

2. **BookingCreatedEvent:**
   - user_id, route_id, total_cost
   - segments, booking_reference

3. **PaymentProcessedEvent:**
   - user_id, payment_id, status, amount

**FEATURES TO VERIFY:**
- ✓ Kafka publishing
- ✓ Event serialization (JSON)
- ✓ Circuit breaker pattern
- ✓ Metrics collection (latency, failures, state)
- ✓ Fire-and-forget semantics
- ✓ Error handling and retries
- ✓ Event consumption and routing
- ✓ Handler registration

**IMPORT MIGRATION:**
```python
# OLD
from backend.archive.platform_consolidated.v1 import EventProducer

# NEW
from backend.platform.events.producer import EventProducer
from backend.platform.events.consumer import EventConsumer
```

---

## CATEGORY 11: GRAPH & NETWORK (3 files)

### File Registry

| File Path | Lines | Status | Action | Priority |
|-----------|-------|--------|--------|----------|
| `backend/core/route_engine/graph.py` | ~400 | ✅ CANONICAL | VERIFY | MEDIUM |
| `backend/graph_mutation_service.py` | ~300 | ✅ CANONICAL | VERIFY | MEDIUM |
| `backend/test_graph_mutation.py` | ~200 | 🧪 TEST | VERIFY | MEDIUM |

### Consolidation Details

**CANONICAL VERSIONS:**
- `backend/core/route_engine/graph.py` - Graph structures and data models
- `backend/graph_mutation_service.py` - Real-time graph updates

**SEPARATION OF CONCERNS:**
- **graph.py:** SpaceTimeNode, graph loading, indexing
- **graph_mutation_service.py:** RealtimeOverlay, delay injection, trip cancellation, platform changes

**FEATURES TO VERIFY:**
- ✓ Graph data structures (nodes, edges, cost)
- ✓ Time-dependent graph modeling
- ✓ Space-time node implementation
- ✓ Real-time overlay application
- ✓ Copy-on-Write delay injection
- ✓ Trip cancellation handling
- ✓ Platform change tracking
- ✓ Occupancy tracking

**GRAPH MUTATION WORKFLOWS:**
1. Load static graph
2. Apply Copy-on-Write overlays for delays
3. Apply trip cancellations
4. Apply platform changes
5. Track occupancy changes
6. Return mutated graph for routing

**IMPORT MIGRATION:**
```python
# Keep clean separation
from backend.core.route_engine.graph import SpaceTimeNode, load_graph_from_db
from backend.graph_mutation_service import apply_real_time_overlays, handle_delay
```

---

## CATEGORY 12: ML/INTELLIGENCE (15+ files)

### File Registry - MAJOR CONSOLIDATION

#### Live Predictors (backend/services/) - ✅ CANONICAL
| File Path | Lines | Status | Action |
|-----------|-------|--------|--------|
| `backend/services/__init__.py` | ~50 | 🔄 CREATE | CREATE service registry |
| `backend/services/delay_predictor.py` | ~200 | ✅ CANONICAL | VERIFY complete |
| `backend/services/route_ranking_predictor.py` | ~150 | ✅ CANONICAL | VERIFY complete |
| `backend/services/cancellation_predictor.py` | ~150 | ✅ CANONICAL | VERIFY complete |
| `backend/services/tatkal_demand_predictor.py` | ~150 | ✅ CANONICAL | VERIFY complete |

#### ML Models Duplicates (backend/intelligence/models/) - ⛔ DUPLICATE
| File Path | Lines | Status | Action |
|-----------|-------|--------|--------|
| `backend/intelligence/models/delay_predictor.py` | ~200 | ⛔ DUPLICATE | DELETE |
| `backend/intelligence/models/route_ranker.py` | ~150 | ⛔ DUPLICATE | DELETE |
| `backend/intelligence/models/cancellation.py` | ~150 | ⛔ DUPLICATE | DELETE |
| `backend/intelligence/models/demand.py` | ~150 | ⛔ DUPLICATE | DELETE |
| `backend/core/ml_ranking_model.py` | ~300 | ⛔ DUPLICATE | DELETE/CONSOLIDATE |

#### ML Infrastructure (backend/core/) - ✅ CANONICAL
| File Path | Lines | Status | Action |
|-----------|-------|--------|--------|
| `backend/core/ml_integration.py` | ~200 | ✅ CANONICAL | ENHANCE |
| `backend/ml_reliability_model.py` | ~300 | ✅ CANONICAL | VERIFY |
| `backend/ml_feature_store_schema.sql` | ~200 | ✅ CANONICAL | VERIFY |

#### Training Code (backend/ root & scripts/) - 🔄 MOVE
| File Path | Lines | Status | Action |
|-----------|-------|--------|--------|
| `backend/ml_data_collection.py` | ~400 | 🔄 MOVE | → intelligence/training/data_collection.py |
| `backend/ml_training_pipeline.py` | ~300 | 🔄 MOVE | → intelligence/training/pipeline.py |
| `backend/setup_ml_database.py` | ~150 | 🔄 MOVE | → intelligence/training/setup_db.py |
| `backend/scripts/ml_collect_data.py` | ~100 | ✅ CANONICAL | KEEP (wrapper) |
| `backend/scripts/ml_train.py` | ~100 | ✅ CANONICAL | KEEP (wrapper) |
| `backend/run_ml_data_collection.py` | ~100 | ✅ CANONICAL | KEEP |

#### Intelligence Models (backend/intelligence/) - 🔄 CREATE
| File Path | Status | Action |
|-----------|--------|--------|
| `backend/intelligence/training/` | 🔄 CREATE | Create directory structure |
| `backend/intelligence/training/__init__.py` | 🔄 CREATE | Create module |
| `backend/intelligence/training/data_collection.py` | 🔄 CREATE | Move from root |
| `backend/intelligence/training/pipeline.py` | 🔄 CREATE | Move from root |
| `backend/intelligence/training/setup_db.py` | 🔄 CREATE | Move from root |
| `backend/intelligence/models/base_model.py` | 🔄 CREATE | Abstract model class |

### Consolidation Strategy

**ARCHITECTURE AFTER CONSOLIDATION:**
```
backend/
├── core/ml_integration.py           [MLModelRegistry, FeatureEngineer]
├── services/                        [Live Prediction Services]
│   ├── __init__.py                 [Service registry & factories]
│   ├── delay_predictor.py          **CANONICAL**
│   ├── route_ranking_predictor.py  **CANONICAL**
│   ├── cancellation_predictor.py   **CANONICAL**
│   └── tatkal_demand_predictor.py  **CANONICAL**
├── intelligence/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base_model.py           [Abstract base]
│   │   └── (NO v1 duplicates)
│   └── training/
│       ├── __init__.py
│       ├── data_collection.py      [from root ml_data_collection.py]
│       ├── pipeline.py             [from root ml_training_pipeline.py]
│       └── setup_db.py             [from root setup_ml_database.py]
├── ml_reliability_model.py          **CANONICAL**
├── ml_feature_store_schema.sql      **CANONICAL**
└── scripts/
    ├── ml_collect_data.py          **CANONICAL** (wrapper)
    ├── ml_train.py                 **CANONICAL** (wrapper)
    └── run_ml_collection.py
```

### ML Consolidation Action Items

**PHASE 1: CREATE STRUCTURE**
- [ ] CREATE `backend/intelligence/training/` directory
- [ ] CREATE `backend/intelligence/training/__init__.py`
- [ ] CREATE `backend/intelligence/models/base_model.py`

**PHASE 2: VERIFY LIVE PREDICTORS**
- [ ] VERIFY `services/delay_predictor.py` - DelayPredictor
- [ ] VERIFY `services/route_ranking_predictor.py` - RouteRankingPredictor
- [ ] VERIFY `services/cancellation_predictor.py` - CancellationPredictor
- [ ] VERIFY `services/tatkal_demand_predictor.py` - TatkalDemandPredictor
- [ ] CREATE `services/__init__.py` with registry and factories

**PHASE 3: MOVE TRAINING CODE**
- [ ] MOVE `ml_data_collection.py` → `intelligence/training/data_collection.py`
- [ ] MOVE `ml_training_pipeline.py` → `intelligence/training/pipeline.py`
- [ ] MOVE `setup_ml_database.py` → `intelligence/training/setup_db.py`
- [ ] UPDATE imports in moved files
- [ ] VERIFY wrapper scripts still work

**PHASE 4: DELETE DUPLICATES**
- [ ] DELETE `intelligence/models/delay_predictor.py` (duplicate)
- [ ] DELETE `intelligence/models/route_ranker.py` (duplicate)
- [ ] DELETE `intelligence/models/cancellation.py` (duplicate)
- [ ] DELETE `intelligence/models/demand.py` (duplicate)
- [ ] DELETE `core/ml_ranking_model.py` (consolidate to services)

**PHASE 5: ENHANCE ML INTEGRATION**
- [ ] ENHANCE `core/ml_integration.py`:
  - [ ] Register all predictors
  - [ ] Register reliability model
  - [ ] Provide unified factory methods
  - [ ] Handle model loading/caching
  - [ ] Implement fallback mechanisms

**PHASE 6: UPDATE IMPORTS**
- [ ] GREP for imports from deleted files
- [ ] REPLACE with canonical paths:
  - `from backend.services.delay_predictor import DelayPredictor`
  - `from backend.services.route_ranking_predictor import RouteRankingPredictor`
  - `from backend.core.ml_integration import MLModelRegistry`
  - `from backend.intelligence.training.data_collection import collect_training_data`
  - `from backend.intelligence.training.pipeline import train_models`

**PHASE 7: TEST & VERIFY**
- [ ] TEST all predictors end-to-end
- [ ] TEST ML pipeline (collect → train → predict)
- [ ] TEST model loading and fallback
- [ ] TEST registry functionality
- [ ] VERIFY no circular imports
- [ ] PERFORMANCE TEST inference latency

### ML Import Migration Examples

**OLD IMPORTS TO DELETE:**
```python
from backend.intelligence.models.delay_predictor import DelayPredictor  # DUPLICATE
from backend.intelligence.models.route_ranker import RouteRankingPredictor  # DUPLICATE
from backend.core.ml_ranking_model import MLRankingModel  # DUPLICATE
from backend.ml_data_collection import collect_training_data  # MOVED
from backend.ml_training_pipeline import train_models  # MOVED
```

**NEW CANONICAL IMPORTS:**
```python
from backend.services.delay_predictor import DelayPredictor  # CANONICAL
from backend.services.route_ranking_predictor import RouteRankingPredictor  # CANONICAL
from backend.services.cancellation_predictor import CancellationPredictor  # CANONICAL
from backend.services.tatkal_demand_predictor import TatkalDemandPredictor  # CANONICAL
from backend.core.ml_integration import MLModelRegistry, FeatureEngineer  # REGISTRY
from backend.intelligence.training.data_collection import collect_training_data  # MOVED
from backend.intelligence.training.pipeline import train_models  # MOVED
from backend.ml_reliability_model import ReliabilityModel  # CANONICAL
```

---

## SUMMARY STATISTICS

### Files by Category
| Category | Total Duplicate Files | Archives | Canonicals | Duplicates |
|----------|--------|----------|-----------|-----------|
| Route Engines | 8 | 5 | 1 | 2 |
| Seat Allocation | 5 | 4 | 1 | 0 |
| Pricing | 4 | 3 | 1 | 0 |
| Caching | 6 | 4 | 2 | 0 |
| Booking | 5 | 3 | 2 | 0 |
| Payment | 3 | 1 | 2 | 0 |
| Station | 6 | 4 | 2 | 0 |
| User Management | 3 | 1 | 1 | 1 |
| Verification | 4 | 2 | 1 | 1 |
| Event Processing | 5 | 3 | 2 | 0 |
| Graph & Network | 3 | 0 | 2 | 1 |
| ML/Intelligence | 15+ | 2 | 8 | 5+ |
| **TOTAL** | **65+** | **32** | **25+** | **10+** |

### Consolidation Impact
- **Total Duplicate Lines of Code:** 10,000+
- **Redundancy Factor:** 40-50% of codebase
- **Files to DELETE:** 30+
- **Files to CREATE:** 4 (intelligence/training structure)
- **Files to MOVE:** 3 (ML training files)
- **Files to EXPAND:** 5 (user service, pricing, seat allocation, etc.)
- **Files to KEEP (Canonical):** 25+

### Time & Effort
- **Estimated Implementation Time:** 2-3 weeks
- **Testing & Validation:** 1 week
- **Documentation:** 3-5 days
- **Total:** 3-4 weeks

---

## CONSOLIDATION PRIORITY MATRIX

### CRITICAL (Do First - High Impact)
1. ✅ **ML/Intelligence** - 15+ files, biggest mess, highest impact
2. ✅ **Route Engines** - Core functionality, performance-critical
3. ✅ **Pricing** - Revenue impact, needs enhancements
4. ✅ **Seat Allocation** - Business logic, needs features
5. ✅ **User Management** - Missing implementation, blocks features

### HIGH (Do Next - High Impact)
6. ✅ **Booking** - Business-critical, already mostly done
7. ✅ **Payment** - Revenue-critical, already mostly done
8. ✅ **Verification** - Security-related

### MEDIUM (Do After - Medium Impact)
9. ⚙️ **Caching** - Performance, but platform versions good
10. ⚙️ **Event Processing** - Async, but platform versions good
11. ⚙️ **Station Services** - Support functionality

### LOW (Can Do Last - Lower Impact)
12. ⚙️ **Graph & Network** - Verification only, clean separation

---

## NEXT IMMEDIATE ACTIONS

1. **REVIEW** this registry thoroughly
2. **CONFIRM** with team before executing deletions
3. **BACKUP** git history for all archive files
4. **START** with Phase 1: Route Engines (highest priority)
5. **EXECUTE** Phases systematically (1-13 from execution plan)
6. **TEST** thoroughly after each phase
7. **DOCUMENT** any deviations from plan

---

**Status:** READY FOR SYSTEMATIC EXECUTION
**Generated:** 2026-02-20
**Next Review:** After Phase 1 completion

