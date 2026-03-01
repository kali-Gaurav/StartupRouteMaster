# Backend Archive Execution Plan

**Date:** February 23, 2026  
**Status:** Ready for Execution  
**Approach:** Phase-by-phase, test after each phase

---

## 🔍 KEY FINDINGS

### Critical Dependencies Found:

1. **`graph_mutation_engine.py`** - Compatibility shim that imports from `platform/`
   - Used in: `api/routemaster_integration.py`, `tests/test_graph_mutation.py`
   - **Action:** Keep shim, but need to update it if archiving platform/

2. **`services/route_engine.py`** - Used in multiple places
   - Used in: `api/status.py`, `workers/search_worker.py`, `tests/`, `scripts/`
   - **Action:** Keep - This is actively used

3. **`services/hybrid_search_service.py`** - Used in domains adapter
   - Used in: `domains/routing/adapters.py`
   - **Action:** Keep - Used by domains (but domains may be archived)

---

## 📦 PHASE 1: SAFE ARCHIVES (No Breaking Dependencies)

### Archive 1: `backend/microservices/` → `backend/archive/microservices/`

**Status:** ✅ Safe - Only used in archived files and own tests

**Command:**
```bash
cd backend
mkdir -p archive/microservices
mv microservices/* archive/microservices/
```

**Verification:**
- Check app.py still starts
- Run basic tests

---

### Archive 2: `backend/route_service/` → `backend/archive/route_service/`

**Status:** ✅ Safe - Not imported anywhere

**Command:**
```bash
cd backend
mkdir -p archive/route_service
mv route_service/* archive/route_service/
```

**Verification:**
- Check app.py still starts

---

### Archive 3: `backend/rl_service/` → `backend/archive/rl_service/`

**Status:** ✅ Safe - Not imported anywhere

**Command:**
```bash
cd backend
mkdir -p archive/rl_service
mv rl_service/* archive/rl_service/
```

**Verification:**
- Check app.py still starts

---

## ⚠️ PHASE 2: REVIEW BEFORE ARCHIVING

### Archive 4: `backend/domains/` → `backend/archive/domains/`

**Status:** ⚠️ Needs Review

**Dependencies:**
- `domains/routing/adapters.py` imports `services/hybrid_search_service.py`
- `graph_mutation_engine.py` imports from `domains.routing`

**Files Using Domains:**
- `graph_mutation_engine.py` (compatibility shim)
- `domains/` files themselves (self-references)

**Action Plan:**
1. Check if `domains/` is actually used in main app (app.py)
2. If not used → Archive
3. Update `graph_mutation_engine.py` if needed (it's a shim anyway)

**Command (After Review):**
```bash
cd backend
mkdir -p archive/domains
mv domains/* archive/domains/
```

**Note:** `graph_mutation_engine.py` is a shim that imports from `platform/`, so archiving domains should be safe if platform is also archived.

---

### Archive 5: `backend/platform/` → `backend/archive/platform/`

**Status:** ⚠️ Needs Review

**Dependencies:**
- `graph_mutation_engine.py` imports from `platform.graph.train_state`
- `platform/` may have other dependencies

**Action Plan:**
1. Check if `platform/` is used directly in app.py (it's not)
2. Check if `graph_mutation_engine.py` is actually used
3. If `graph_mutation_engine.py` is used → Keep platform/ OR update shim
4. If `graph_mutation_engine.py` is not used → Archive both

**Files Using Platform:**
- `graph_mutation_engine.py` (shim)
- `api/routemaster_integration.py` (check if this is used)
- `tests/test_graph_mutation.py` (test file)

**Decision:**
- If `routemaster_integration.py` is not used → Archive platform/
- If `routemaster_integration.py` is used → Keep platform/ OR refactor

**Command (After Review):**
```bash
cd backend
mkdir -p archive/platform
mv platform/* archive/platform/
```

**If graph_mutation_engine.py needs to stay:**
- Update shim to point to new location OR
- Keep platform/ but document it's only for compatibility

---

## 🔧 PHASE 3: UPDATE COMPATIBILITY SHIMS

### Update `graph_mutation_engine.py`

**Current:** Imports from `backend.platform.graph.train_state`

**If Platform Archived:**
- Option 1: Update shim to import from new location
- Option 2: Move platform code to core/ or services/
- Option 3: Remove shim if not needed

**Check Usage First:**
```bash
grep -r "from backend.graph_mutation_engine\|import backend.graph_mutation_engine" backend/
```

---

## 📋 EXECUTION CHECKLIST

### Phase 1: Safe Archives
- [ ] Archive `microservices/`
- [ ] Test app.py starts
- [ ] Archive `route_service/`
- [ ] Test app.py starts
- [ ] Archive `rl_service/`
- [ ] Test app.py starts

### Phase 2: Review & Archive
- [ ] Check `routemaster_integration.py` usage
- [ ] Check `graph_mutation_engine.py` usage
- [ ] Decide on `domains/` archive
- [ ] Decide on `platform/` archive
- [ ] Archive `domains/` (if safe)
- [ ] Archive `platform/` (if safe)
- [ ] Update compatibility shims (if needed)

### Phase 3: Verification
- [ ] Run full test suite
- [ ] Verify app.py starts
- [ ] Check for broken imports
- [ ] Update documentation

---

## 🎯 ACTIVE FOLDERS AFTER ARCHIVING

```
backend/
├── core/              ✅ Active - Route engine, monitoring
├── database/         ✅ Active - Models, config, session
├── api/              ✅ Active - All API endpoints
├── services/         ✅ Active - Business logic (review duplicates)
├── utils/            ✅ Active - Utilities
├── pipelines/        ✅ Active - Pipeline system
├── alembic/          ✅ Active - Migrations
├── tests/            ✅ Active - Test suite
├── etl/              ✅ Active - ETL
├── scripts/          ✅ Active - Scripts
├── worker.py         ✅ Active - Payment worker
├── app.py            ✅ Active - Main app
├── config.py         ✅ Active - Config
├── schemas.py        ✅ Active - Schemas
├── database.py       ✅ Active - DB session
└── archive/          📦 Archived code
    ├── microservices/
    ├── route_service/
    ├── rl_service/
    ├── domains/      (if archived)
    └── platform/     (if archived)
```

---

## ⚠️ IMPORTANT NOTES

1. **Backup First:** Create git commit before archiving
2. **Test After Each Phase:** Don't archive everything at once
3. **Keep Archive Accessible:** Don't delete, just move to archive/
4. **Update Imports:** If any files break, update imports
5. **Document Changes:** Update README with archive locations

---

## 🚀 QUICK START

### Execute Phase 1 (Safe Archives):
```bash
cd backend

# Archive microservices
mkdir -p archive/microservices
mv microservices/* archive/microservices/

# Archive route_service
mkdir -p archive/route_service
mv route_service/* archive/route_service/

# Archive rl_service
mkdir -p archive/rl_service
mv rl_service/* archive/rl_service/

# Test
python -c "from backend.app import app; print('✅ App imports successfully')"
```

### Review Phase 2:
```bash
# Check routemaster_integration usage
grep -r "routemaster_integration" backend/api/

# Check graph_mutation_engine usage
grep -r "graph_mutation_engine" backend/ --exclude-dir=archive
```

---

**Status:** Ready to execute Phase 1. Review Phase 2 dependencies before archiving domains/platform.
