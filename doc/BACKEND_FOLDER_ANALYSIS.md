# Backend Folder Analysis - Used vs Unused

**Date:** February 23, 2026  
**Purpose:** Identify connected vs disconnected folders/files for archiving

---

## ✅ ACTIVELY USED FOLDERS (Keep)

### 1. `backend/core/` ✅ **ACTIVE**
**Used by:** `app.py` (route_engine, monitoring)

**Files Used:**
- `core/route_engine/` - Main routing engine ✅
- `core/monitoring.py` - Prometheus metrics ✅
- `core/route_engine/engine.py` - RouteEngine class ✅
- `core/route_engine/data_provider.py` - Data provider ✅

**Status:** ✅ Keep - Core functionality

---

### 2. `backend/database/` ✅ **ACTIVE**
**Used by:** `app.py` (config, init_db, SessionLocal), all API endpoints

**Files Used:**
- `database/config.py` - Config class ✅
- `database/session.py` - SessionLocal ✅
- `database/models.py` - All ORM models ✅
- `database/__init__.py` - Exports ✅

**Status:** ✅ Keep - Essential database layer

---

### 3. `backend/api/` ✅ **ACTIVE**
**Used by:** `app.py` (all routers included)

**Routers Used:**
- `api/search.py` ✅
- `api/routes.py` ✅
- `api/payments.py` ✅
- `api/admin.py` ✅
- `api/chat.py` ✅
- `api/users.py` ✅
- `api/reviews.py` ✅
- `api/auth.py` ✅
- `api/status.py` ✅
- `api/sos.py` ✅
- `api/flow.py` ✅
- `api/websockets.py` ✅
- `api/bookings.py` ✅
- `api/realtime.py` ✅
- `api/stations.py` ✅
- `api/integrated_search.py` ✅

**Status:** ✅ Keep - All active API endpoints

---

### 4. `backend/services/` ✅ **ACTIVE** (Partially)
**Used by:** API endpoints, app.py

**Services Used:**
- `services/booking_service.py` ✅
- `services/analytics_consumer.py` ✅ (app.py startup)
- `services/realtime_ingestion/position_broadcaster.py` ✅ (app.py startup)
- `services/payment_service.py` ✅
- `services/user_service.py` ✅
- `services/unlock_service.py` ✅
- `services/verification_engine.py` ✅
- `services/booking/rapid_api_client.py` ✅ (newly added)

**Status:** ✅ Keep - Core services active

---

### 5. `backend/utils/` ✅ **ACTIVE**
**Used by:** `app.py` (limiter), various services

**Files Used:**
- `utils/limiter.py` ✅ (app.py)
- `utils/security.py` ✅
- `utils/station_utils.py` ✅

**Status:** ✅ Keep - Utility functions

---

### 6. `backend/worker.py` ✅ **ACTIVE**
**Used by:** `app.py` (start_reconciliation_worker)

**Status:** ✅ Keep - Payment reconciliation worker

---

### 7. `backend/pipelines/` ✅ **ACTIVE** (Partially)
**Used by:** `app.py` (initialize_pipelines)

**Files Used:**
- `pipelines/system.py` ✅ (app.py startup)

**Status:** ✅ Keep - Pipeline system

---

### 8. `backend/alembic/` ✅ **ACTIVE**
**Used by:** Database migrations

**Status:** ✅ Keep - Migration system

---

### 9. `backend/tests/` ✅ **ACTIVE**
**Used by:** Test suite

**Status:** ✅ Keep - Testing infrastructure

---

## ⚠️ PARTIALLY USED / NEEDS REVIEW

### 10. `backend/services/` ⚠️ **MIXED**
**Many files may be unused duplicates**

**Potentially Unused:**
- `services/route_engine.py` - Duplicate? Check if used
- `services/advanced_route_engine.py` - Duplicate?
- `services/multi_modal_route_engine.py` - Duplicate?
- `services/hybrid_search_service.py` - Check usage
- `services/search_service.py` - Check usage
- `services/advanced_seat_allocation_engine.py` - Duplicate?
- `services/smart_seat_allocation.py` - Duplicate?
- `services/seat_allocation.py` - Check which is primary
- `services/enhanced_pricing_service.py` - Check usage
- `services/price_calculation_service.py` - Check usage
- `services/yield_management_engine.py` - Check usage
- `services/cache_service.py` - Check usage
- `services/multi_layer_cache.py` - Check usage
- `services/cache_warming_service.py` - Check usage

**Action:** Review each file for actual usage

---

### 11. `backend/domains/` ⚠️ **UNCLEAR**
**Status:** May be alternative architecture not fully integrated

**Folders:**
- `domains/routing/` - Check if used instead of core/route_engine
- `domains/user/` - Check if used instead of services/user_service
- `domains/station/` - Check if used instead of services/station_service
- `domains/pricing/` - Check if used instead of services/pricing
- `domains/payment/` - Check if used instead of services/payment_service
- `domains/inventory/` - Check if used
- `domains/booking/` - Check if used instead of services/booking_service

**Action:** Check if these are used or if they're duplicate implementations

---

### 12. `backend/platform/` ⚠️ **UNCLEAR**
**Status:** May be alternative platform layer

**Folders:**
- `platform/monitoring/` - Check if used instead of core/monitoring
- `platform/integrations/` - Check usage
- `platform/graph/` - Check usage
- `platform/events/` - Check if used instead of services/event_producer
- `platform/cache/` - Check if used instead of services/cache

**Action:** Check if these are used or duplicates

---

## ❌ LIKELY UNUSED / ARCHIVE CANDIDATES

### 13. `backend/archive/` 📦 **ARCHIVED**
**Status:** Already archived, keep for reference

**Action:** ✅ Keep as-is (already archived)

---

### 14. `backend/microservices/` ❌ **NOT USED**
**Status:** gRPC microservices not integrated

**Evidence:**
- Not imported in app.py
- Contains NotImplementedError stubs
- Separate service architecture

**Folders:**
- `microservices/booking-service/` - gRPC service (not used)
- `microservices/inventory-service/` - gRPC service (not used)
- `microservices/route-service/` - gRPC service (not used)

**Action:** 📦 Archive - Not connected to main app

---

### 15. `backend/route_service/` ❌ **NOT USED**
**Status:** Separate service, not imported

**Files:**
- `route_service/app.py` - Separate FastAPI app?
- `route_service/raptor.py` - Duplicate?
- `route_service/raptor_data.py` - Duplicate?

**Action:** 📦 Archive - Not connected to main app

---

### 16. `backend/rl_service/` ❌ **NOT USED**
**Status:** Reinforcement learning service, not imported

**Action:** 📦 Archive - Not connected to main app

---

### 17. `backend/intelligence/` ⚠️ **UNCLEAR**
**Status:** ML/AI training, check usage

**Folders:**
- `intelligence/training/` - Check if used

**Action:** Review - May be used for ML training scripts

---

### 18. `backend/etl/` ✅ **ACTIVE** (Partially)
**Used by:** Admin ETL endpoint

**Status:** ✅ Keep - ETL functionality used

---

### 19. Root-level files ⚠️ **NEEDS CLEANUP**
**Many files should be moved**

**Files to Review:**
- `models.py` - Should be in database/ or merged
- `config.py` - ✅ Keep at root
- `schemas.py` - ✅ Keep at root
- `database.py` - ✅ Keep at root
- `app.py` - ✅ Keep at root
- `worker.py` - ✅ Keep at root
- `seat_inventory_models.py` - Should be in database/
- `graph_mutation_engine.py` - Check usage
- `ml_ranking_model.py` - Check usage
- `station_time_index.py` - Check usage
- Various test files - Should be in tests/
- Various script files - Should be in scripts/

**Action:** Review each file

---

## 📋 RECOMMENDED ACTIONS

### Immediate Archive (Not Connected)

1. **`backend/microservices/`** → `backend/archive/microservices/`
   - Reason: gRPC services not integrated
   - Impact: None (not used)

2. **`backend/route_service/`** → `backend/archive/route_service/`
   - Reason: Separate service not connected
   - Impact: None (not imported)

3. **`backend/rl_service/`** → `backend/archive/rl_service/`
   - Reason: Separate service not connected
   - Impact: None (not imported)

### Review & Consolidate

4. **`backend/domains/`** - Check if used
   - If not used → Archive
   - If used → Document which files use it

5. **`backend/platform/`** - Check if used
   - If not used → Archive
   - If used → Document which files use it

6. **`backend/services/`** - Review duplicates
   - Consolidate route engines
   - Consolidate seat allocators
   - Consolidate pricing engines
   - Consolidate cache services

### Clean Up Root

7. **Move root-level files:**
   - Test files → `tests/`
   - Script files → `scripts/`
   - Model files → `database/`
   - Utility files → `core/` or `utils/`

---

## 🔍 VERIFICATION STEPS

### Step 1: Check Domain Usage
```bash
grep -r "from backend.domains" backend/
grep -r "import backend.domains" backend/
```

### Step 2: Check Platform Usage
```bash
grep -r "from backend.platform" backend/
grep -r "import backend.platform" backend/
```

### Step 3: Check Microservices Usage
```bash
grep -r "from backend.microservices" backend/
grep -r "import backend.microservices" backend/
```

### Step 4: Check Route Service Usage
```bash
grep -r "from backend.route_service" backend/
grep -r "import backend.route_service" backend/
```

---

## 📊 SUMMARY

| Folder | Status | Action |
|--------|--------|--------|
| `core/` | ✅ Active | Keep |
| `database/` | ✅ Active | Keep |
| `api/` | ✅ Active | Keep |
| `services/` | ⚠️ Mixed | Review duplicates |
| `utils/` | ✅ Active | Keep |
| `pipelines/` | ✅ Active | Keep |
| `alembic/` | ✅ Active | Keep |
| `tests/` | ✅ Active | Keep |
| `etl/` | ✅ Active | Keep |
| `domains/` | ⚠️ Unclear | Review usage |
| `platform/` | ⚠️ Unclear | Review usage |
| `microservices/` | ❌ Unused | Archive |
| `route_service/` | ❌ Unused | Archive |
| `rl_service/` | ❌ Unused | Archive |
| `archive/` | 📦 Archived | Keep |
| `intelligence/` | ⚠️ Unclear | Review usage |

---

**Next:** Run verification commands to confirm usage before archiving.
