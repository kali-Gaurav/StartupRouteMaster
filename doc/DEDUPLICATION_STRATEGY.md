# COMPREHENSIVE DEDUPLICATION STRATEGY
**Date**: 2026-02-20
**Status**: Consolidated Duplicate Analysis
**Files to Process**: 44 duplicates across 10 categories

---

## CONSOLIDATION DECISIONS BY CATEGORY

### 1. ROUTE ENGINES (9 files → 1 canonical + archive)

**KEEP**: `core/route_engine/engine.py` (327 lines, Feb 20 05:14)
- Most modular and refactored implementation
- Uses shared infrastructure (metrics, ML integration)
- Part of new architecture
- Location: Primary domain routing

**ARCHIVE TO** `archive/route_engines_consolidated/v1/`:
- `services/route_engine.py` - 201 byte wrapper (REMOVE)
- `route_engine.py` - 686 byte wrapper at root (REMOVE from root, move to archive)
- `services/advanced_route_engine.py` (35K) - Move archive with notes
- `core/route_engine.py` (107K) - Legacy monolithic version
- `core/archive/route_engine_legacy.py` (96K) - Already archived
- Archive copies of above in `archive/route_engines_v1/`
- `services/multi_modal_route_engine.py` - Wrapper, keep logic in archive
- `core/archive/multi_modal_route_engine.py` (43K) - Full implementation in archive

**ACTION**: Keep only `core/route_engine/engine.py`, consolidate all wrappers, archive large legacy versions

---

### 2. SEAT ALLOCATION (6 files → 1 canonical + archive)

**KEEP**: `domains/inventory/seat_allocator.py` (17K, Feb 20 07:05)
- Most recent, already using shared infrastructure
- Uses OccupancyCalculator, OccupancyMetricsCollector from core/utils
- Canonical location in domains hierarchy

**ARCHIVE TO** `archive/seat_allocators_consolidated/v1/`:
- `services/seat_allocation.py` (17K) - Basic version (IDENTICAL)
- `archive/seat_allocators_v1/seat_allocation.py` (17K) - Duplicate of above
- `services/advanced_seat_allocation_engine.py` (18K) - Advanced but older version without shared imports
- `archive/seat_allocators_v1/advanced_seat_allocation_engine.py` (18K) - Duplicate without shared imports
- `services/smart_seat_allocation.py` (17K) - Fair distribution variant (ARCHIVE)
- `archive/seat_allocators_v1/smart_seat_allocation.py` (17K) - Duplicate

**ACTION**: Move all services/ versions to archive, keep only domains/inventory/ version with shared infrastructure

---

### 3. CACHING (6 files → 1 canonical + utilities)

**KEEP**: `platform/cache/manager.py` (newest, Feb 20 06:40)
- Modularized in platform hierarchy
- Uses shared CacheMetricsCollector and CacheKeyGenerator

**KEEP (utilities)**:
- `platform/cache/warming.py` - Cache warming strategies
- `platform/cache/cache_service.py` - Basic cache service (if exists)

**ARCHIVE TO** `archive/cache_managers_consolidated/v1/`:
- `services/multi_layer_cache.py` (18K) - Move entire file to archive
- `archive/cache_managers_v1/multi_layer_cache.py` (18K) - Duplicate in archive
- `services/cache_service.py` (7.2K) - Merge into platform version or archive
- `services/cache_warming_service.py` (13K) - Extract useful patterns to warming.py

**ACTION**: Consolidate all caching to platform/cache/, archive services/ versions

---

### 4. PRICING (4 files → 1 canonical + utilities)

**KEEP**: `domains/pricing/engine.py` (17K, Feb 20 07:06)
- Most recent, using shared infrastructure (PricingContext, DynamicPricingResult)
- Uses MetricsCollector, FeatureEngineer from core

**ARCHIVE TO** `archive/pricing_engines_consolidated/v1/`:
- `services/enhanced_pricing_service.py` (17K) - Move to archive (content moved to domains/)
- `archive/pricing_engines_v1/` - Already archived
- `services/price_calculation_service.py` (2.1K) - Extract basic math to utils, archive original

**ACTION**: Keep only domains/pricing/, move all services/ to archive

---

### 5. BOOKING (4 files → 2 canonical)

**KEEP**:
- `domains/booking/service.py` (19K, Feb 20 06:40) - Core service logic
- `domains/booking/orchestrator.py` (24K) - Transaction orchestration
- `api/booking.py` (API layer) - Keep separate

**ARCHIVE TO** `archive/booking_consolidated/v1/`:
- `services/booking_service.py` (19K) - Identical to domains version
- `booking_api.py` (12K, root) - Move to API archive or merge into api/booking.py
- `booking_orchestrator.py` (root) - Move to domains or archive

**ACTION**: Consolidate to domains/booking/, archive services/ and root-level versions

---

### 6. PAYMENT (4 files → 1 canonical + APIs)

**KEEP**:
- `domains/payment/service.py` (8.0K, Feb 20 06:40) - Core service
- `api/payments.py` (31K, Feb 19 02:07) - API endpoints
- `payment_service/` (microservice) - Keep if actively used, document dependency

**ARCHIVE TO** `archive/payment_consolidated/v1/`:
- `services/payment_service.py` (8.0K) - Move to archive (identical to domains/)
- `payment_service/app.py` - Move entire directory if not actively used

**ACTION**: Keep domains/payment/service.py as canonical, consolidate to domains/payment/

---

### 7. STATION SERVICES (4 files → 1 canonical)

**KEEP**:
- `domains/station/service.py` (3.3K) - Station search
- `domains/station/departure_service.py` (13K) - Departure lookup

**ARCHIVE TO** `archive/station_consolidated/v1/`:
- `services/station_service.py` (3.3K) - IDENTICAL, move to archive
- `services/station_departure_service.py` (13K) - IDENTICAL, move to archive

**ACTION**: Keep only domains/station/, archive all services/ versions

---

### 8. VERIFICATION (2 files → 1 canonical)

**KEEP**: `domains/verification/unlock_service.py` (3.3K)

**ARCHIVE TO** `archive/verification_consolidated/v1/`:
- `services/unlock_service.py` (3.3K) - IDENTICAL

**ACTION**: Keep only domains/verification/, remove services/ duplicate

---

### 9. JOURNEY RECONSTRUCTION (2 files → 1 canonical)

**KEEP**: `core/route_engine/engine.py` (already covers this functionality)

**ARCHIVE TO** `archive/journey_consolidated/v1/`:
- `services/journey_reconstruction.py` (394 bytes) - Wrapper, can remove
- `core/archive/journey_reconstruction.py` (17K) - Full implementation (archived)

**ACTION**: Functionality merged into routing engine, safe to archive wrappers

---

### 10. MODELS/SCHEMAS (3 files → aggregator pattern)

**KEEP**:
- `database/models.py` (39K) - Main SQLAlchemy models
- `seat_inventory_models.py` (13K) - Specialized seat models
- `models.py` (root) - Re-export aggregator (70 bytes) - USEFUL FOR COMPATIBILITY

**ACTION**: Keep all models, root models.py is useful for aggregation

---

## CONSOLIDATION EXECUTION PLAN

### Phase 1: Create Comprehensive Archive Structure (30 min)
```
archive/
├── route_engines_consolidated/v1/
│   ├── advanced_route_engine.py
│   ├── core_route_engine_legacy.py
│   └── multi_modal_route_engine.py
├── seat_allocators_consolidated/v1/
│   ├── basic_seat_allocation.py
│   ├── advanced_seat_allocation.py
│   └── smart_seat_allocation.py
├── cache_managers_consolidated/v1/
│   ├── multi_layer_cache.py
│   └── cache_warming.py
├── pricing_engines_consolidated/v1/
│   ├── enhanced_pricing_service.py
│   └── price_calculation_service.py
├── booking_consolidated/v1/
│   ├── booking_service.py
│   └── booking_api.py
├── payment_consolidated/v1/
│   └── payment_service.py
├── station_consolidated/v1/
│   ├── station_service.py
│   └── station_departure_service.py
└── verification_consolidated/v1/
    └── unlock_service.py
```

### Phase 2: Move Duplicate Files (1 hour)
1. Identify exact duplicates in archive/ - can safely delete
2. Move older services/ versions to archive/*/v1/
3. Move root-level duplicate files to appropriate archives
4. Remove wrapper files that duplicate functionality

### Phase 3: Update Imports (1 hour)
1. Scan all import statements
2. Replace imports from services/ with domains/ or core/
3. Create import alias mappings for breaking changes
4. Test critical import paths

### Phase 4: Validation (30 min)
1. py_compile all Python files
2. Test imports of consolidated modules
3. Verify no broken circular dependencies
4. Check database models integrity

### Phase 5: Documentation (30 min)
1. Create CONSOLIDATION_REPORT.md documenting what was removed
2. List archived versions with reasons
3. Document import changes needed
4. Create migration guide

---

## FILE COUNTS BY DECISION

| Decision | Count | Storage Saved |
|----------|-------|---------------|
| Keep (Canonical) | 15 | - |
| Move to Archive | 24 | ~850 KB |
| Delete (Exact Dupes) | 5 | ~50 KB |
| **TOTAL** | **44** | **~900 KB** |

---

## CRITICAL NOTES

⚠️ **IMPORT MIGRATION REQUIRED**:
- All `from services.X import Y` → `from domains.X import Y`
- All `from services.X import Y` → `from core.X import Y` (for core modules)
- All `from services.X import Y` → `from platform.X import Y` (for platform modules)

✅ **SAFE TO DELETE**:
- All wrapper files (journey_reconstruction.py, multi_modal_route_engine.py as wrappers)
- All exact duplicates in archive/routes_engines_v1/

⚠️ **REQUIRES TESTING**:
- Payment microservice (`payment_service/`) - document if used
- Multi-modal routing - verify if actually needed
- Cache warming strategies - extract to platform/cache/warming.py

---

## EXPECTED OUTCOMES

**Before**:
- 44 duplicate files scattered across services/, domains/, core/, archive/
- Confusing multiple locations for same functionality
- ~900 KB storage redundancy
- Import chaos with multiple possible paths

**After**:
- Single source of truth for each functionality
- Clear organization: domains/ (business), core/ (infrastructure), platform/ (shared)
- Consolidated archive for historical versions
- Straightforward imports from canonical locations
- ~900 KB freed up
- Clean, maintainable codebase

---

**Status**: Ready for execution
**Complexity**: Medium (need to systematically move files and update imports)
**Risk**: Low (with thorough testing and keeping archives)

