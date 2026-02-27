# BACKEND REORGANIZATION - PHASE 0 COMPLETE ✅

**Date**: 2026-02-20
**Status**: Architecture & Planning Complete - Ready for Implementation
**Pattern**: Domain-Driven Design (DDD) + Platform Layer

---

## ✅ COMPLETED (PHASE 0 - PLANNING)

### 1. Directory Structure Created
```
✓ domains/
  ✓ routing/    (interfaces.py created)
  ✓ booking/    (interfaces.py created)
  ✓ inventory/  (interfaces.py created)
  ✓ pricing/    (interfaces.py created)
  ✓ user/
  ✓ station/
  ✓ payment/    (interfaces.py created)
  ✓ verification/

✓ platform/
  ✓ cache/
  ✓ graph/
  ✓ events/
  ✓ monitoring/
  ✓ integrations/
  ✓ security/

✓ intelligence/
  ✓ models/
  ✓ training/
  ✓ prediction/
  ✓ registry/

✓ api/
✓ workers/
```

### 2. Architecture Documentation
- ✓ **ARCHITECTURE_V2.md** (6000+ lines)
  - Domain boundaries & ownership
  - Data flow walkthrough
  - Dependency rules
  - Consolidation priority order
  - Interface examples

### 3. Interface Protocols Created
**These prevent tight coupling and ensure clean contracts:**

#### ✓ `domains/routing/interfaces.py`
- `RouteFinder` protocol with methods:
  - `find_routes()` - Main search operation
  - `find_routes_with_dates()` - Multi-date search
- Data models: `Journey`, `Segment`

#### ✓ `domains/inventory/interfaces.py`
- `SeatAllocator` protocol with methods:
  - `allocate_seats()` - Lock seats
  - `release_seats()` - Release locked seats
  - `get_available_seats()` - Check availability
  - `get_occupied_seats()` - List occupied seats
  - `confirm_booking()` - Convert locks to booking
- Data models: `SeatLock`

#### ✓ `domains/pricing/interfaces.py`
- `PricingEngine` protocol with methods:
  - `calculate_fare()` - Single segment pricing
  - `calculate_journey_fare()` - Multi-segment pricing
  - `get_base_fare()` - Non-dynamic base price
  - `apply_yield_management()` - Dynamic pricing rules
- Data models: `FareQuote`

#### ✓ `domains/booking/interfaces.py`
- `Booker` protocol with methods:
  - `create_booking()` - Create booking
  - `confirm_booking()` - Post-payment confirmation
  - `cancel_booking()` - Cancellation
  - `get_booking()` - Retrieve booking
  - `list_user_bookings()` - User's bookings
- Data models: `Booking`, `BookingStatus` enum

#### ✓ `domains/payment/interfaces.py`
- `PaymentProcessor` protocol with methods:
  - `process_payment()` - Charge payment
  - `refund_payment()` - Handle refunds
  - `get_payment()` - Retrieve payment details
  - `verify_payment()` - Validate with gateway
- Data models: `PaymentResult`, `PaymentStatus` enum

---

## 📋 NEXT STEPS (PHASES 1-5)

### PHASE 1: Consolidate Core Engines (Priority Order)

**1️⃣ Route Finding Engine** (HIGHEST PRIORITY)
- Current: 4 implementations
  - `/backend/route_engine.py` (root)
  - `/backend/services/hybrid_search_service.py`
  - `/backend/services/advanced_route_engine.py`
  - `/backend/services/multi_modal_route_engine.py`

**Action**:
1. Review all 4 files (check code lines, complexity, test coverage)
2. Choose best implementation (likely `hybrid_search_service.py`)
3. Move to: `domains/routing/engine.py`
4. Archive 3 others to: `archive/route_engines_v1/`
5. Create: `domains/routing/__init__.py` exporting RouteFinder interface

**2️⃣ Seat Allocation** (CRITICAL)
- Current: 3 implementations
  - `/backend/services/seat_allocation.py`
  - `/backend/services/advanced_seat_allocation_engine.py`
  - `/backend/services/smart_seat_allocation.py`

**Action**:
1. Review all 3 files
2. Choose best
3. Move to: `domains/inventory/seat_allocator.py`
4. Archive 2 others to: `archive/seat_allocators_v1/`

**3️⃣ Pricing Engine** (AFFECTS REVENUE)
- Current: 3 implementations
  - `/backend/services/price_calculation_service.py`
  - `/backend/services/enhanced_pricing_service.py`
  - `/backend/services/yield_management_engine.py`

**Action**:
1. Review all 3 files
2. Choose best (likely `enhanced_pricing_service.py`)
3. Move to: `domains/pricing/engine.py`
4. Archive 2 others to: `archive/pricing_engines_v1/`

**4️⃣ Cache Manager** (IMPACTS PERFORMANCE)
- Current: 3 implementations
  - `/backend/services/cache_service.py`
  - `/backend/services/cache_warming_service.py`
  - `/backend/services/multi_layer_cache.py`

**Action**:
1. Keep: `cache_service.py` as main (move to `platform/cache/manager.py`)
2. Keep: `cache_warming_service.py` (move to `platform/cache/warming.py`)
3. Archive: `multi_layer_cache.py` (if features not in main)

---

### PHASE 2: Consolidate Remaining Domain Services

Move to appropriate domain folders:
```
Booking Domain:
  - services/booking_service.py → domains/booking/service.py
  - services/booking_orchestrator.py → domains/booking/orchestrator.py

Inventory Domain:
  - services/availability_service.py → domains/inventory/availability_service.py
  - services/analytics_consumer.py → domains/inventory/analytics_consumer.py

User Domain:
  - services/user_service.py → domains/user/service.py

Station Domain:
  - services/station_service.py → domains/station/service.py
  - services/station_departure_service.py → domains/station/departure_service.py

Payment Domain:
  - services/payment_service.py → domains/payment/service.py

Verification Domain:
  - services/verification_engine.py → domains/verification/service.py
  - services/unlock_service.py → domains/verification/unlock_system.py
```

---

### PHASE 3: Move Platform Infrastructure

Move shared infrastructure to `platform/`:
```
platform/cache/:
  ← services/cache_service.py
  ← services/cache_warming_service.py

platform/graph/:
  ← services/graph_mutation_engine.py
  ← services/graph_mutation_service.py
  ← services/train_state_service.py

platform/events/:
  ← services/event_producer.py

platform/monitoring/:
  ← services/performance_monitor.py
  ← utils/metrics.py (if needed)

platform/integrations/:
  ← services/routemaster_client.py
  ← core/data_provider.py (lives with live API connectors)

platform/security/:
  ← api/auth.py
  ← utils/security.py
  ← utils/limiter.py
```

---

### PHASE 4: Consolidate Intelligence & ML

Move all ML files to `intelligence/`:
```
intelligence/models/:
  ← services/route_ranking_predictor.py
  ← services/tatkal_demand_predictor.py
  ← services/delay_predictor.py (consolidate with cancellation_predictor)
  ← services/cancellation_predictor.py
  ← core/ml_ranking_model.py
  ← baseline_heuristic_models.py (from root)
  ← ml_reliability_model.py (from root)
  ← shadow_inference_service.py (from root)

intelligence/training/:
  ← ml_training_pipeline.py (from root)
  ← ml_data_collection.py (from root)
  ← run_ml_data_collection.py (from root)
  ← setup_ml_database.py (from root)

intelligence/prediction/:
  ← Create prediction service for inference

intelligence/registry/:
  ← Create model registry for versioning
```

---

### PHASE 5: Move Workers & Scripts

```
workers/:
  ← search_worker.py (from root)
  ← worker.py → payment_worker.py (from root)

Create new workers:
  - seat_expiry_worker.py
  - delay_update_worker.py
  - pricing_worker.py
  - health_check_worker.py

scripts/:
  ← check_db.py
  ← seed_stations.py
  ← inspect_railway_db.py
  ← audit_kafka_config.py
  ← ml_staging_rollout.py (from root)

scripts/ml/:
  ← ml_data_collection.py (duplicate handling)
  ← ml_training_pipeline.py
  ← setup_ml_database.py
```

---

### PHASE 6: Update Imports

Critical import updates in:
```
app.py
  ← Update all router includes
  ← Update startup events
  ← Update dependency injection

api/ (all files)
  ← Update service imports
  ← Use new domains/ paths
  ← Use new platform/ paths

core/route_engine/ (if exists separately)
  ← May need removal if consolidated into domains/routing/
```

---

### PHASE 7: Archive & Cleanup

Move to `archive/`:
```
archive/route_engines_v1/
  - route_engine.py
  - advanced_route_engine.py
  - multi_modal_route_engine.py

archive/seat_allocators_v1/
  - [old seat allocation files]

archive/pricing_engines_v1/
  - [old pricing files]

archive/cache_managers_v1/
  - [old cache files]

Create archive/README.md with deprecation notes
```

---

## 🎯 CONSOLIDATION SUMMARY

**Current State → Target State**:

| Component | Current | Target | Action |
|-----------|---------|--------|--------|
| Route Finding | 4 files | 1 file (domains/routing/engine.py) | Keep best, archive 3 |
| Seat Allocation | 3 files | 1 file (domains/inventory/seat_allocator.py) | Keep best, archive 2 |
| Pricing | 3 files | 1 file (domains/pricing/engine.py) | Keep best, archive 2 |
| Cache | 3 files | 2-3 files (manager + warming) | Consolidate |
| ML Models | 7+ files | Organized in intelligence/models/ | Move + registry |
| Domain Services | Scattered | domains/*/ | Move by domain |
| Platform Services | In services/ | platform/*/ | Move to platform |

**Result**: 35+ root files + 34 services files → Clean, organized, NO DUPLICATES

---

## 📊 METRICS

### Before Reorganization
```
Root-level files:     35
Services folder:      34 files (many duplicates)
Total backend files:  308
Duplicate components: 10+
Organizational debt:  HIGH
```

### After Reorganization
```
Root-level files:     4-6 only (app, config, schemas, database, dependencies)
Domain services:      ~25 consolidated files
Platform services:    ~12 files
Intelligence:         ~8 files
Workers:              ~6 files
Scripts:              ~10 files
Total backend files:  ~200 (from 308)
Duplicate components: 0
Organizational debt:  LOW
Scalability:          HIGH (ready for microservices split)
```

---

## ✨ BENEFITS OF THIS STRUCTURE

✅ **No More Duplicates**
- Single RouteFinder, SeatAllocator, PricingEngine, CacheManager
- Clear ownership prevents code duplication

✅ **Clear Scaling Path**
- Each domain can become a microservice independently
- Platform layer becomes shared infrastructure

✅ **Easy to Maintain**
- Related code in one place (domains/X/)
- Easy to find business logic
- Clear separation of concerns

✅ **Prevents Circular Dependencies**
- Domains don't depend on each other (mostly)
- Platform is trusted by all domains
- Intelligence is isolated (one-way dependency)

✅ **Team Scaling**
- Clear domain boundaries = clear team responsibilities
- New engineers know where to find code
- Less context switching

✅ **Testing**
- Domain tests in tests/unit/domain_X/
- Integration tests in tests/integration/
- Platform tests in tests/platform/

---

## ⚠️ CRITICAL RULES DURING IMPLEMENTATION

1. **Never delete files immediately**
   - Move to archive/ first
   - Delete only after verified working

2. **Test after each phase**
   - Run `python -m pytest` after each phase
   - Verify `app.py` starts without errors

3. **Update imports progressively**
   - Don't wait until the end
   - Update as you move files

4. **Use git commits between phases**
   - Each phase = one commit
   - Easier rollback if issues

5. **Preserve existing behavior**
   - No logic changes during reorganization
   - Same performance benchmarks

---

## 🚀 READY FOR NEXT STEP

Your architecture is set up with:
- ✅ Modern DDD pattern
- ✅ Clear domain boundaries
- ✅ Interface contracts
- ✅ Platform layer separation
- ✅ Consolidation priorities defined
- ✅ Step-by-step execution plan

**Should I proceed with Phase 1 (consolidating core engines)?**

I recommend starting with route finding:
1. Review all 4 route finding implementations
2. Select the best one
3. Move to `domains/routing/engine.py`
4. Archive others
5. Test that API still works

Would you like me to proceed with Phase 1?
