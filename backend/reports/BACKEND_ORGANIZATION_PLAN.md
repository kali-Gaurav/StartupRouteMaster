# BACKEND ORGANIZATION & CLEANUP AUDIT

**Date**: 2026-02-20
**Status**: Initial Audit Complete
**Total Python Files**: 308
**Root-Level Files to Organize**: 35
**Files in Services Folder**: 34 (with duplicates)

---

## EXECUTIVE SUMMARY

Current state is **messy with significant duplication**:
- 35 files at root level (should be 4: app.py, config.py, schemas.py, database.py)
- 34 files in services/ with many serving overlapping purposes
- Multiple route engines, seat allocators, pricing engines doing similar work
- Test files scattered at root and in tests/ folder
- Scripts at root instead of scripts/ folder

**Goal**: Clean, organized structure with:
- **Root**: Only 4 core files (app.py, config.py, schemas.py, database.py)
- **Logic organized into standard folders**: api/, services/, core/, database/, utils/, scripts/, tests/
- **No duplicate functionality** - consolidate similar files
- **Clear responsibility** - each file has single purpose

---

## PART 1: ROOT-LEVEL FILES AUDIT

### Files to MOVE (not delete):

#### API/BOOKING/PAYMENT (Move to api/)
```
booking_api.py           -> api/booking.py
booking_orchestrator.py  -> services/booking_orchestrator.py
mock_api_server.py       -> tests/fixtures/mock_api_server.py
```

#### ML/AI/MODELS (Move to ml/ subfolder in services/)
```
baseline_heuristic_models.py      -> services/ml/baseline_models.py
ml_data_collection.py             -> scripts/ml_data_collection.py
ml_reliability_model.py           -> services/ml/reliability_model.py
ml_training_pipeline.py           -> scripts/ml_training_pipeline.py
models.py                         -> MERGE into database/models.py
run_ml_data_collection.py         -> scripts/run_ml_data_collection.py
seat_inventory_models.py          -> MERGE into database/seat_inventory_models.py
setup_ml_database.py              -> scripts/setup_ml_database.py
shadow_inference_service.py       -> services/ml/shadow_inference.py
staging_rollout.py                -> scripts/ml_staging_rollout.py
```

#### TESTS (Move to tests/)
```
check_db.py                       -> scripts/check_db.py
concurrency_load_tester.py        -> tests/load/concurrency_test.py
simple_load_test.py               -> tests/load/simple_load_test.py
test_chat_enhanced.py             -> tests/
test_db_connectivity.py           -> tests/
test_event_pipeline.py            -> tests/
test_graph_mutation.py            -> tests/
```

#### SCRIPTS/WORKERS (Move to scripts/)
```
audit_kafka_config.py             -> scripts/audit_kafka_config.py
search_worker.py                  -> scripts/search_worker.py
seed_stations.py                  -> scripts/seed_stations.py
start_analytics_consumer.py        -> scripts/start_analytics_consumer.py
worker.py                         -> scripts/payment_worker.py
```

#### DATABASE/UTILITIES (Move to appropriate locations)
```
frequency_aware_range.py          -> core/routing/frequency_aware_range.py
station_time_index.py             -> core/routing/station_time_index.py
inspect_railway_db.py             -> scripts/inspect_railway_db.py
bulk_update_imports.py            -> scripts/bulk_update_imports.py
```

#### KEEP at Root (4 files only)
```
✓ app.py                  - Main FastAPI application
✓ config.py               - Configuration management
✓ schemas.py              - Pydantic models
✓ database.py             - DB session factory
```

---

## PART 2: SERVICES FOLDER DUPLICATES

### Group 1: Route Finding (CONSOLIDATE)
**Current files** (4 different implementations):
```
- route_engine.py                 [DUPLICATE - legacy]
- hybrid_search_service.py         [PRIMARY - use this]
- advanced_route_engine.py         [DUPLICATE - merge into hybrid]
- multi_modal_route_engine.py      [DUPLICATE - archive or merge]
```

**Action**:
- Keep: `hybrid_search_service.py` (rename to `route_search_service.py`)
- Archive: `route_engine.py`, `advanced_route_engine.py`, `multi_modal_route_engine.py`
- Review `core/route_engine/` for overlaps with `core/route_engine.py` at root

### Group 2: Seat Allocation (CONSOLIDATE)
**Current files** (3 different implementations):
```
- seat_allocation.py               [LEGACY]
- advanced_seat_allocation_engine.py [PRIMARY - review this]
- smart_seat_allocation.py         [NEWER - review this]
```

**Action**:
- Analyze which is most recent/complete
- Keep the best one, rename to `seat_allocation_service.py`
- Archive the others

### Group 3: Pricing/Yield (CONSOLIDATE)
**Current files** (3 different implementations):
```
- price_calculation_service.py
- enhanced_pricing_service.py
- yield_management_engine.py
```

**Action**:
- Keep: `enhanced_pricing_service.py` (most complete)
- Archive: `price_calculation_service.py`, `yield_management_engine.py`

### Group 4: Caching (CONSOLIDATE)
**Current files** (3 different implementations):
```
- cache_service.py
- cache_warming_service.py
- multi_layer_cache.py
```

**Action**:
- Keep: `cache_service.py` (main)
- Keep: `cache_warming_service.py` (separate concern)
- Archive: `multi_layer_cache.py` (review if features needed)

### Group 5: Delay/Cancellation Prediction (CONSOLIDATE)
**Current files** (3 different implementations):
```
- delay_predictor.py
- cancellation_predictor.py
- delay_service.py
```

**Action**:
- Consolidate into: `delay_prediction_service.py`
- Review actual implementations for feature differences

### Group 6: ML Models (CONSOLIDATE)
**Current files** (4 different):
```
- route_ranking_predictor.py
- tatkal_demand_predictor.py
- [baseline_heuristic_models.py - at root]
- [ml_reliability_model.py - at root]
```

**Action**:
- Move all to: `services/ml/`
- Create: `services/ml/model_registry.py` to manage all models

### Core Services (Keep as-is)
```
✓ booking_service.py             - Booking operations
✓ analytics_consumer.py          - Analytics processing
✓ event_producer.py              - Event streaming
✓ payment_service.py             - Payment operations
✓ verification_engine.py         - Verification logic
✓ unlock_service.py              - Unlock details
✓ user_service.py                - User operations
✓ station_service.py             - Station operations
✓ review_service.py              - Review management
✓ redirect_service.py            - Redirects
✓ routemaster_client.py          - External API client
```

---

## PART 3: TARGET DIRECTORY STRUCTURE

```
backend/
│
├── ========== ROOT (4 files only) ==========
├── app.py                          ✓ Main application
├── config.py                       ✓ Configuration
├── schemas.py                      ✓ Pydantic models
├── database.py                     ✓ DB session
│
├── ========== API ROUTES ==========
├── api/
│   ├── __init__.py
│   ├── search.py
│   ├── booking.py                  <- moved from booking_api.py
│   ├── payments.py
│   ├── auth.py
│   ├── users.py
│   ├── stations.py
│   ├── status.py
│   ├── reviews.py
│   ├── chat.py
│   ├── flow.py
│   ├── admin.py
│   ├── sos.py
│   ├── dependencies.py
│   ├── websockets.py
│   ├── integrated_search.py
│   ├── revenue_management.py
│   └── routemaster_integration.py
│
├── ========== SERVICES (BUSINESS LOGIC) ==========
├── services/
│   ├── __init__.py
│   │
│   ├── routing/                          [NEW SUBSECTION]
│   │   ├── route_search_service.py       <- renamed from hybrid_search_service.py
│   │   └── __init__.py
│   │
│   ├── booking/                          [NEW SUBSECTION]
│   │   ├── booking_service.py
│   │   ├── booking_orchestrator.py       <- moved from root
│   │   └── __init__.py
│   │
│   ├── inventory/                        [NEW SUBSECTION]
│   │   ├── seat_allocation_service.py    <- consolidated from 3 files
│   │   ├── analytics_consumer.py
│   │   └── __init__.py
│   │
│   ├── pricing/                          [NEW SUBSECTION]
│   │   ├── pricing_service.py            <- consolidated from 3 files
│   │   └── __init__.py
│   │
│   ├── cache/                            [NEW SUBSECTION]
│   │   ├── cache_service.py
│   │   ├── cache_warming_service.py
│   │   └── __init__.py
│   │
│   ├── ml/                               [NEW SUBSECTION]
│   │   ├── __init__.py
│   │   ├── model_registry.py
│   │   ├── delay_prediction_service.py   <- consolidated from 3 files
│   │   ├── demand_predictor.py           <- moved from root
│   │   ├── ranking_predictor.py
│   │   ├── reliability_model.py          <- moved from root
│   │   ├── baseline_models.py            <- moved from root
│   │   └── shadow_inference.py           <- moved from root
│   │
│   ├── payment/                          [NEW SUBSECTION]
│   │   ├── payment_service.py
│   │   └── __init__.py
│   │
│   ├── verification/                     [NEW SUBSECTION]
│   │   ├── verification_engine.py
│   │   ├── unlock_service.py
│   │   └── __init__.py
│   │
│   ├── graph/                            [NEW SUBSECTION]
│   │   ├── graph_mutation_engine.py      <- moved from root
│   │   ├── graph_mutation_service.py     <- moved from root
│   │   ├── train_state_service.py        <- moved from root
│   │   └── __init__.py
│   │
│   ├── user/                             [NEW SUBSECTION]
│   │   ├── user_service.py
│   │   └── __init__.py
│   │
│   ├── station/                          [NEW SUBSECTION]
│   │   ├── station_service.py
│   │   ├── station_departure_service.py
│   │   └── __init__.py
│   │
│   ├── event/                            [NEW SUBSECTION]
│   │   ├── event_producer.py
│   │   └── __init__.py
│   │
│   ├── integration/                      [NEW SUBSECTION]
│   │   ├── routemaster_client.py
│   │   ├── review_service.py
│   │   ├── redirect_service.py
│   │   └── __init__.py
│   │
│   ├── monitoring/                       [NEW SUBSECTION]
│   │   ├── performance_monitor.py
│   │   ├── perf_check.py
│   │   └── __init__.py
│   │
│   └── legacy/                           [DEPRECATED]
│       └── [all archived files if still needed]
│
├── ========== CORE ALGORITHMS ==========
├── core/
│   ├── __init__.py
│   ├── route_engine/                    [EXISTING - KEEP]
│   │   ├── engine.py
│   │   ├── graph.py
│   │   ├── raptor.py
│   │   ├── builder.py
│   │   ├── hub.py
│   │   ├── snapshot_manager.py
│   │   ├── data_provider.py
│   │   ├── live_validators.py
│   │   ├── transfer_intelligence.py
│   │   ├── regions.py
│   │   ├── constraints.py
│   │   ├── data_structures.py
│   │   ├── frequency_aware_range.py     <- moved from root
│   │   ├── station_time_index.py        <- moved from root
│   │   └── __init__.py
│   │
│   ├── validators/                      [EXISTING - KEEP]
│   │   ├── __init__.py
│   │   └── [all validation files]
│   │
│   └── archive/                         [EXISTING - KEEP]
│       └── [deprecated route engines]
│
├── ========== DATABASE ==========
├── database/
│   ├── __init__.py
│   ├── models.py                   <- consolidated from models.py at root
│   ├── seat_inventory_models.py     <- moved from root (or merge into models.py)
│   ├── session.py
│   └── config.py
│
├── ========== UTILITIES ==========
├── utils/
│   ├── __init__.py
│   ├── validators.py
│   ├── validation.py
│   ├── time_utils.py
│   ├── graph_utils.py
│   ├── station_utils.py
│   ├── security.py
│   ├── limiter.py
│   ├── metrics.py
│   ├── generators.py
│   └── logger.py
│
├── ========== SCRIPTS (Standalone executables) ==========
├── scripts/                             [NEW]
│   ├── __init__.py
│   ├── README.md
│   ├── check_db.py                      <- moved from root
│   ├── seed_stations.py                 <- moved from root
│   ├── inspect_railway_db.py            <- moved from root
│   ├── audit_kafka_config.py            <- moved from root
│   ├── bulk_update_imports.py           <- moved from root
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── search_worker.py             <- moved from root
│   │   ├── payment_worker.py            <- moved from root (worker.py)
│   │   └── start_analytics_consumer.py  <- moved from root
│   │
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── ml_data_collection.py        <- moved from root
│   │   ├── run_ml_data_collection.py    <- moved from root
│   │   ├── ml_training_pipeline.py      <- moved from root
│   │   ├── setup_ml_database.py         <- moved from root
│   │   └── ml_staging_rollout.py        <- moved from root
│   │
│   └── migrations/
│       └── [manual migration scripts if needed]
│
├── ========== TESTS ==========
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   │
│   ├── unit/                            [Organize existing tests]
│   │   └── [single-unit tests]
│   │
│   ├── integration/                     [Organize existing tests]
│   │   └── [multi-unit integration tests]
│   │
│   ├── load/                            [NEW SUBSECTION]
│   │   ├── concurrency_test.py          <- moved from root
│   │   ├── simple_load_test.py          <- moved from root
│   │   └── locust_load_test.py
│   │
│   ├── fixtures/
│   │   ├── mock_api_server.py           <- moved from root
│   │   └── [other test fixtures]
│   │
│   └── [existing test files organized here]
│
├── ========== DATABASE MIGRATIONS ==========
├── alembic/                             [EXISTING - KEEP]
│   ├── env.py
│   ├── versions/
│   └── alembic.ini
│
├── ========== ARCHIVED/DEPRECATED ==========
├── archive/
│   ├── offline_phase2_deprecated/        [EXISTING - KEEP]
│   ├── route_engines_v1/                 [NEW - move here]
│   │   ├── route_engine.py               <- from root
│   │   ├── advanced_route_engine.py      <- from services/
│   │   └── multi_modal_route_engine.py   <- from services/
│   ├── seat_allocators/                  [NEW - move here]
│   │   └── [old seat allocation files]
│   ├── pricing_engines/                  [NEW - move here]
│   │   └── [old pricing files]
│   ├── cache_managers/                   [NEW - move here]
│   │   └── [old cache files]
│   └── README.md
│
├── ========== SUPPORTING SYSTEMS ==========
├── pipelines/                           [EXISTING - KEEP]
├── etl/                                 [EXISTING - KEEP]
├── microservices/                       [EXISTING - KEEP]
├── api_gateway/                         [EXISTING - KEEP]
│
├── ========== DOCUMENTATION ==========
├── docs/                                [EXISTING - KEEP]
├── examples/                            [EXISTING - KEEP]
│
└── ========== CONFIGURATION ==========
    ├── .env
    ├── .env.example
    ├── requirements.txt
    ├── Dockerfile
    ├── pytest.ini
    └── README.md
```

---

## PART 4: FILE MOVEMENT CHECKLIST

### Phase 1: Root-Level Files (41 moves/consolidations)

- [ ] **Move booking files**: `booking_api.py` → `api/booking.py`, `booking_orchestrator.py` → `services/booking/`
- [ ] **Move ML files**: All 10 ML files from root to `services/ml/` or `scripts/ml/`
- [ ] **Move test files**: All 7 test files from root to `tests/`
- [ ] **Move script files**: All 5 worker/script files to `scripts/` and `scripts/workers/`
- [ ] **Move utility files**: `frequency_aware_range.py`, `station_time_index.py` → `core/routing/`
- [ ] **Merge database files**: `models.py`, `seat_inventory_models.py` → `database/`

### Phase 2: Services Folder Consolidation (34 → ~20 files)

- [ ] **Route finding**: Keep `hybrid_search_service.py` → rename to `services/routing/route_search_service.py`, archive 3 others
- [ ] **Seat allocation**: Consolidate 3 files into `services/inventory/seat_allocation_service.py`
- [ ] **Pricing**: Keep `enhanced_pricing_service.py` → `services/pricing/pricing_service.py`, archive 2 others
- [ ] **Caching**: Keep both main and warming, consolidate with `multi_layer_cache.py`
- [ ] **Delay prediction**: Consolidate 3 files into `services/ml/delay_prediction_service.py`
- [ ] **Reorganize by subsection**: Create booking/, routing/, inventory/, pricing/, cache/, ml/, payment/, verification/, graph/, user/, station/, event/, integration/, monitoring/ subsections

### Phase 3: Archive Old Files

- [ ] Create `archive/route_engines_v1/`, `archive/seat_allocators/`, `archive/pricing_engines/`, `archive/cache_managers/`
- [ ] Move duplicates to archive with README explaining deprecation

### Phase 4: Update Imports

- [ ] Update `app.py` imports (route includes, startup events)
- [ ] Update all `api/` files imports (routes use services from new locations)
- [ ] Update test imports to use new paths

### Phase 5: Verification

- [ ] Verify `app.py` starts without import errors
- [ ] Run full test suite
- [ ] Check for any remaining relative imports that need updating

---

## PART 5: FILES TO KEEP AT ROOT (4 ONLY)

1. **app.py** - Main FastAPI application with all routers included
2. **config.py** - Configuration management (env vars, settings)
3. **schemas.py** - Shared Pydantic models for request/response
4. **database.py** - Database session factory

All other files MUST be moved to appropriate directories.

---

## DUPLICATES TO CONSOLIDATE

| Purpose | Current Files | Action | Target |
|---------|---------------|--------|--------|
| Route Finding | route_engine.py, hybrid_search_service.py, advanced_route_engine.py, multi_modal_route_engine.py | Keep best, archive 3 | services/routing/route_search_service.py |
| Seat Allocation | seat_allocation.py, advanced_seat_allocation_engine.py, smart_seat_allocation.py | Review & keep best | services/inventory/seat_allocation_service.py |
| Pricing | price_calculation_service.py, enhanced_pricing_service.py, yield_management_engine.py | Keep enhanced, archive 2 | services/pricing/pricing_service.py |
| Caching | cache_service.py, cache_warming_service.py, multi_layer_cache.py | Review & consolidate | services/cache/ |
| Delay Prediction | delay_predictor.py, cancellation_predictor.py, delay_service.py | Consolidate features | services/ml/delay_prediction_service.py |
| ML Models | route_ranking_predictor.py, tatkal_demand_predictor.py, baseline_heuristic_models.py, ml_reliability_model.py | Organize under registry | services/ml/ with model_registry.py |

---

## NEXT STEPS

1. **Review & Approve**: Confirm this structure matches your vision
2. **Phase 1 Execution**: Move root-level files
3. **Phase 2 Execution**: Consolidate services duplicates
4. **Phase 3 Execution**: Create consolidated files
5. **Phase 4 Execution**: Update all imports
6. **Phase 5 Verification**: Test full backend

---

**Status**: Audit Complete, Ready for User Review
