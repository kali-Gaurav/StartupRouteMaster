# Backend Cleanup Summary - Used vs Unused Folders

**Date:** February 23, 2026  
**Analysis Complete:** ✅  
**Ready for Archive:** Phase 1 (Safe)

---

## ✅ ACTIVELY USED FOLDERS (Keep)

### Core Active Folders:
1. **`backend/core/`** ✅
   - Route engine, monitoring, validators
   - Used by: app.py, API endpoints

2. **`backend/database/`** ✅
   - Models, config, session
   - Used by: app.py, all services

3. **`backend/api/`** ✅
   - All API routers
   - Used by: app.py (all routers included)

4. **`backend/services/`** ✅ (Partially)
   - Core business logic
   - Used by: API endpoints, app.py
   - **Note:** Some duplicates need review

5. **`backend/utils/`** ✅
   - Utilities (limiter, security, etc.)
   - Used by: app.py, services

6. **`backend/pipelines/`** ✅
   - Pipeline system
   - Used by: app.py startup

7. **`backend/alembic/`** ✅
   - Database migrations
   - Used by: Migration system

8. **`backend/tests/`** ✅
   - Test suite
   - Used by: Testing

9. **`backend/etl/`** ✅
   - ETL functionality
   - Used by: Admin endpoints

10. **`backend/scripts/`** ✅
    - Standalone scripts
    - Used by: Manual execution

---

## ❌ UNUSED FOLDERS (Archive)

### Safe to Archive (Phase 1):

1. **`backend/microservices/`** ❌
   - **Status:** Not imported in app.py
   - **Usage:** Only in archived files and own tests
   - **Action:** ✅ Archive to `backend/archive/microservices/`

2. **`backend/route_service/`** ❌
   - **Status:** Not imported anywhere
   - **Usage:** Separate service not connected
   - **Action:** ✅ Archive to `backend/archive/route_service/`

3. **`backend/rl_service/`** ❌
   - **Status:** Not imported anywhere
   - **Usage:** Separate service not connected
   - **Action:** ✅ Archive to `backend/archive/rl_service/`

### Review Before Archive (Phase 2):

4. **`backend/domains/`** ⚠️
   - **Status:** Not imported in app.py
   - **Usage:** Only self-references
   - **Dependency:** `graph_mutation_engine.py` references it
   - **Action:** ⚠️ Review - Archive if graph_mutation_engine not used

5. **`backend/platform/`** ⚠️
   - **Status:** Not imported in app.py
   - **Usage:** Only by `graph_mutation_engine.py` shim
   - **Dependency:** `graph_mutation_engine.py` imports from it
   - **Action:** ⚠️ Review - Archive if graph_mutation_engine not used

6. **`backend/graph_mutation_engine.py`** ⚠️
   - **Status:** Compatibility shim
   - **Usage:** Used in `api/routemaster_integration.py` (not in app.py)
   - **Dependency:** Imports from `platform/`
   - **Action:** ⚠️ Review - Archive if routemaster_integration not used

---

## 📊 SUMMARY TABLE

| Folder | Status | Used In App.py | Action |
|--------|--------|----------------|--------|
| `core/` | ✅ Active | Yes | Keep |
| `database/` | ✅ Active | Yes | Keep |
| `api/` | ✅ Active | Yes | Keep |
| `services/` | ✅ Active | Yes | Keep (review duplicates) |
| `utils/` | ✅ Active | Yes | Keep |
| `pipelines/` | ✅ Active | Yes | Keep |
| `alembic/` | ✅ Active | N/A | Keep |
| `tests/` | ✅ Active | N/A | Keep |
| `etl/` | ✅ Active | Indirect | Keep |
| `scripts/` | ✅ Active | N/A | Keep |
| `microservices/` | ❌ Unused | No | ✅ Archive |
| `route_service/` | ❌ Unused | No | ✅ Archive |
| `rl_service/` | ❌ Unused | No | ✅ Archive |
| `domains/` | ⚠️ Unclear | No | ⚠️ Review |
| `platform/` | ⚠️ Unclear | No | ⚠️ Review |
| `archive/` | 📦 Archived | N/A | Keep |

---

## 🚀 RECOMMENDED ACTIONS

### Immediate (Phase 1 - Safe):
```bash
cd backend

# Archive unused services
mkdir -p archive/microservices archive/route_service archive/rl_service
mv microservices/* archive/microservices/
mv route_service/* archive/route_service/
mv rl_service/* archive/rl_service/

# Test
python -c "from backend.app import app; print('✅ App works')"
```

### After Review (Phase 2):
```bash
# Check if routemaster_integration is used
grep -r "routemaster_integration" backend/api/app.py

# If not used, archive domains/platform
mkdir -p archive/domains archive/platform
mv domains/* archive/domains/
mv platform/* archive/platform/

# Update or remove graph_mutation_engine.py shim if needed
```

---

## 📝 NOTES

1. **`services/` folder has duplicates** - Review and consolidate:
   - Multiple route engines
   - Multiple seat allocators
   - Multiple pricing engines
   - Multiple cache services

2. **Root-level files** - Some should be organized:
   - Test files → `tests/`
   - Script files → `scripts/`
   - Model files → `database/`

3. **Archive preserves code** - Nothing deleted, just moved

---

## ✅ VERIFICATION

After archiving, verify:
- [ ] `app.py` starts without errors
- [ ] All API endpoints work
- [ ] Tests pass
- [ ] No broken imports

---

**Status:** Ready to execute Phase 1 archives. Review Phase 2 dependencies before archiving domains/platform.
