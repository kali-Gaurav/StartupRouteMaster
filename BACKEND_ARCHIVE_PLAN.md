# Backend Archive Plan - Unused/Disconnected Files

**Date:** February 23, 2026  
**Status:** Ready for Execution

---

## ✅ VERIFICATION RESULTS

### Domains Folder
- **Usage:** Only self-references and `graph_mutation_engine.py`
- **Status:** ❌ NOT USED in main app
- **Action:** Archive

### Platform Folder
- **Usage:** Not imported in `app.py` or main code
- **Status:** ❌ NOT USED in main app
- **Action:** Archive

### Microservices Folder
- **Usage:** Only in archived files and own tests
- **Status:** ❌ NOT USED in main app
- **Action:** Archive

### Route Service Folder
- **Usage:** Not imported anywhere
- **Status:** ❌ NOT USED in main app
- **Action:** Archive

---

## 📦 ARCHIVE ACTIONS

### 1. Archive `backend/microservices/` → `backend/archive/microservices/`

**Reason:** gRPC microservices architecture not integrated into main FastAPI app

**Files to Archive:**
```
backend/microservices/
├── booking-service/
├── inventory-service/
├── route-service/
├── common/
├── tests/
└── README.md
```

**Impact:** None - Not imported in app.py

**Command:**
```bash
mkdir -p backend/archive/microservices
mv backend/microservices/* backend/archive/microservices/
```

---

### 2. Archive `backend/route_service/` → `backend/archive/route_service/`

**Reason:** Separate service not connected to main app

**Files to Archive:**
```
backend/route_service/
├── app.py
├── raptor.py
├── raptor_data.py
└── db_utils.py
```

**Impact:** None - Not imported anywhere

**Command:**
```bash
mkdir -p backend/archive/route_service
mv backend/route_service/* backend/archive/route_service/
```

---

### 3. Archive `backend/rl_service/` → `backend/archive/rl_service/`

**Reason:** Reinforcement learning service not integrated

**Files to Archive:**
```
backend/rl_service/
└── app.py
```

**Impact:** None - Not imported anywhere

**Command:**
```bash
mkdir -p backend/archive/rl_service
mv backend/rl_service/* backend/archive/rl_service/
```

---

### 4. Archive `backend/domains/` → `backend/archive/domains/`

**Reason:** Domain-driven design architecture not used in main app

**Files to Archive:**
```
backend/domains/
├── routing/
├── user/
├── station/
├── pricing/
├── payment/
├── inventory/
└── booking/
```

**Impact:** None - Only self-references

**Note:** `graph_mutation_engine.py` references domains, but check if graph_mutation_engine is used first

**Command:**
```bash
mkdir -p backend/archive/domains
mv backend/domains/* backend/archive/domains/
```

---

### 5. Archive `backend/platform/` → `backend/archive/platform/`

**Reason:** Platform layer not used in main app

**Files to Archive:**
```
backend/platform/
├── monitoring/
├── integrations/
├── graph/
├── events/
└── cache/
```

**Impact:** None - Not imported in app.py

**Command:**
```bash
mkdir -p backend/archive/platform
mv backend/platform/* backend/archive/platform/
```

---

### 6. Review `backend/graph_mutation_engine.py`

**Status:** ⚠️ Needs review

**References:** `backend.domains.routing`

**Action:** 
- Check if `graph_mutation_engine.py` is imported anywhere
- If not used → Archive
- If used → Update imports to remove domains dependency

**Check:**
```bash
grep -r "graph_mutation_engine\|GraphMutationEngine" backend/
```

---

## 🔍 ADDITIONAL CLEANUP (Optional)

### Root-Level Files to Organize

**Move to `backend/archive/root_files/`:**
- `models.py.bak` - Backup file
- `seat_inventory_models.py` - Should be in database/ (or merge)
- `ml_ranking_model.py` - Check usage
- `station_time_index.py` - Check usage

**Move to `backend/tests/`:**
- `conftest.py` - If duplicate
- Test files at root level

**Move to `backend/scripts/`:**
- Script files at root level

---

## 📋 EXECUTION CHECKLIST

### Phase 1: Safe Archives (No Dependencies)
- [ ] Archive `microservices/`
- [ ] Archive `route_service/`
- [ ] Archive `rl_service/`
- [ ] Archive `platform/`

### Phase 2: Review Before Archive
- [ ] Check `graph_mutation_engine.py` usage
- [ ] Archive `domains/` (after checking graph_mutation_engine)

### Phase 3: Root Cleanup
- [ ] Review root-level files
- [ ] Move unused files to archive
- [ ] Organize test files
- [ ] Organize script files

---

## ⚠️ SAFETY NOTES

1. **Backup First:** Create a backup before archiving
2. **Test After:** Run tests after archiving to ensure nothing breaks
3. **Git Commit:** Commit each archive phase separately
4. **Document:** Update README with archive locations

---

## 📊 EXPECTED RESULTS

**Before:**
- ~404 Python files
- Multiple disconnected architectures
- Duplicate implementations

**After:**
- Cleaner structure
- Only active code in main folders
- Archived code preserved for reference
- Easier to navigate and maintain

---

## 🎯 ACTIVE FOLDERS (Keep)

After archiving, these will be the main active folders:

```
backend/
├── core/              ✅ Active routing engine
├── database/         ✅ Active database layer
├── api/              ✅ Active API endpoints
├── services/         ✅ Active business logic (review duplicates)
├── utils/            ✅ Active utilities
├── pipelines/        ✅ Active pipeline system
├── alembic/          ✅ Active migrations
├── tests/            ✅ Active test suite
├── etl/              ✅ Active ETL
├── scripts/          ✅ Active scripts
├── archive/          📦 Archived code
│   ├── microservices/
│   ├── route_service/
│   ├── rl_service/
│   ├── domains/
│   └── platform/
└── [root files]      ✅ app.py, config.py, schemas.py, database.py, worker.py
```

---

**Status:** Ready to execute archive plan. Review and execute phase by phase.
