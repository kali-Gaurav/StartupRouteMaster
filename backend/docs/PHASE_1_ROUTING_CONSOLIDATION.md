# PHASE 1: ROUTE ENGINE CONSOLIDATION (STRANGLER PATTERN)

**Status**: Implementation Plan Ready
**Pattern**: Strangler Pattern (safe, reversible migration)
**Risk Level**: 🔴 High (route engine is critical)
**Success Criteria**: API works, tests pass, feature flag works

---

## 📊 IMPLEMENTATION ANALYSIS

### Route Finding Implementations Compared

| File | Lines | Status | Quality | Best For |
|------|-------|--------|---------|----------|
| `core/route_engine/engine.py` | ~500 | ✅ PRODUCTION | ⭐⭐⭐⭐⭐ | Main implementation |
| `services/hybrid_search_service.py` | 87 | ✅ WRAPPER | ⭐⭐⭐ | Backwards compat |
| `services/advanced_route_engine.py` | 1006 | ⚠️ DUPLICATE | ⭐⭐⭐ | Archive |
| `services/multi_modal_route_engine.py` | 9 | ❌ STUB | ⭐⭐ | Archive |

### Decision: Use `core/route_engine/engine.py`

**Why**:
- ✅ Production-grade (HybridRAPTOR, snapshots, overlays, ML integration)
- ✅ Feature complete (live validators, data provider, metrics)
- ✅ Well-architectured (modular components)
- ✅ Already in use (app.py imports from core/route_engine/)

---

## 🚀 STRANGLER PATTERN EXECUTION

### Step 1: Create New Consolidated Routing Domain (With Adapters)

```
domains/routing/
  ├── __init__.py
  ├── interfaces.py           ✅ (already created)
  ├── engine.py               ← NEW (copy core/route_engine/engine.py)
  ├── adapters.py             ← NEW (compatibility layer)
  ├── raptor.py              ← (reference core if needed)
  ├── graph.py               ← (reference core if needed)
  ├── hub.py
  ├── snapshot_manager.py
  ├── data_structures.py
  ├── constraints.py
  ├── builder.py
  ├── transfer_logic.py
  ├── data_provider.py
  └── live_validators.py
```

### Step 2: Create Compatibility Adapter Layer

**File**: `domains/routing/adapters.py`

```python
from typing import List, Dict, Optional
from services.hybrid_search_service import HybridSearchService
from .engine import RailwayRouteEngine

class LegacyHybridSearchAdapter:
    """Adapter for old HybridSearchService API"""

    def __init__(self, new_engine: RailwayRouteEngine):
        self.new_engine = new_engine
        # Legacy fallback if needed
        self.legacy = None

    async def search_routes(
        self,
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None,
    ) -> List[Dict]:
        # Delegate to new engine
        return await self.new_engine.search_routes(
            source=source,
            destination=destination,
            travel_date=travel_date,
            budget_category=budget_category,
        )
```

### Step 3: Add Feature Flag to Config

**File**: `config.py` (append)

```python
# Route Engine Migration (Strangler Pattern)
USE_NEW_ROUTING_ENGINE = os.getenv(
    "USE_NEW_ROUTING_ENGINE",
    "true"
).lower() in ("1", "true", "yes")

ROUTE_ENGINE_LOG_BOTH = os.getenv(
    "ROUTE_ENGINE_LOG_BOTH",
    "false"
).lower() in ("1", "true", "yes")
```

### Step 4: Update Dependency Injection

**File**: `dependencies.py` (create if not exists) or update relevant DI files

```python
from config import Config
from domains.routing.engine import RailwayRouteEngine
from domains.routing.adapters import LegacyHybridSearchAdapter

def get_route_engine():
    """Dependency injection for route engine.

    Can switch between new and legacy based on feature flag.
    """
    engine = RailwayRouteEngine()

    if Config.USE_NEW_ROUTING_ENGINE:
        return engine
    else:
        # Fallback to legacy adapter for zero-downtime rollback
        return LegacyHybridSearchAdapter(engine)
```

### Step 5: Update API Layer to Use New Engine

**File**: `api/search.py` (update imports)

```python
from dependencies import get_route_engine

@router.get("/api/search")
async def search_routes(
    source: str,
    destination: str,
    travel_date: str,
    engine = Depends(get_route_engine)
):
    """Search routes using (new or legacy) engine."""
    routes = await engine.search_routes(
        source=source,
        destination=destination,
        travel_date=travel_date
    )
    return {"routes": routes}
```

### Step 6: Add Observability (Logging)

```python
import logging
from config import Config

logger = logging.getLogger(__name__)

def get_route_engine():
    engine = RailwayRouteEngine()

    if Config.USE_NEW_ROUTING_ENGINE:
        logger.info("🟢 Using NEW RouteEngine (domains/routing/engine.py)")
        return engine
    else:
        logger.warning("🟡 Using LEGACY HybridSearchAdapter (fallback)")
        return LegacyHybridSearchAdapter(engine)
```

---

## 📋 IMPLEMENTATION CHECKLIST

### Pre-Implementation (Already Done ✅)
- [x] Created `domains/routing/` folder structure
- [x] Created `domains/routing/interfaces.py` with RouteFinder protocol
- [x] Reviewed route engine implementations
- [x] Selected best implementation (core/route_engine/engine.py)

### Implementation Steps
- [ ] Create `domains/routing/engine.py` (copy from core/route_engine/)
- [ ] Create `domains/routing/adapters.py` (compatibility layer)
- [ ] Create `domains/routing/__init__.py` (exports)
- [ ] Add feature flags to `config.py`
- [ ] Create/update `dependencies.py` (DI layer)
- [ ] Update `api/search.py` (use DI)
- [ ] Add logging to show which engine is used
- [ ] Verify `app.py` starts without errors

### Testing
- [ ] Run `pytest tests/` (all tests pass)
- [ ] Test search API with USE_NEW_ROUTING_ENGINE=true
- [ ] Test search API with USE_NEW_ROUTING_ENGINE=false
- [ ] Verify feature flag switching works
- [ ] Check logs show correct engine in use
- [ ] Compare output of both engines (should be identical)

### Cleanup & Archive
- [ ] Create `archive/route_engines_v1/` folder
- [ ] Move `services/advanced_route_engine.py` to archive
- [ ] Move `services/multi_modal_route_engine.py` to archive
- [ ] Move `route_engine.py` (root) to archive if no longer needed
- [ ] DO NOT delete - just archive
- [ ] Create `archive/route_engines_v1/README.md` explaining deprecation

### Final State
```
domains/routing/
  ├── engine.py              ← NEW CONSOLIDATED (from core/)
  ├── adapters.py            ← Backwards compat layer
  ├── interfaces.py          ← Protocol definition
  └── [supporting files]

services/
  ├── hybrid_search_service.py  ← Can be deleted after verification

archive/route_engines_v1/
  ├── advanced_route_engine.py
  ├── multi_modal_route_engine.py
  └── README.md
```

---

## 🔄 ROLLBACK PLAN

If something breaks:

1. **Instant rollback via feature flag**:
   ```bash
   export USE_NEW_ROUTING_ENGINE=false
   ```

2. **Restart server**:
   ```bash
   python app.py
   ```

3. **Logs will show**:
   ```
   🟡 Using LEGACY HybridSearchAdapter (fallback)
   ```

4. **Zero user impact** - old adapter still works

---

## ⚠️ CRITICAL MONITORING

After deployment, watch for:

```python
# Log lines that indicate success:
"🟢 Using NEW RouteEngine"          # Good
"✅ Search completed in XXXms"      # Good

# Log lines that indicate problems:
"🟡 Using LEGACY HybridSearchAdapter"  # Fallback mode
"❌ Error in new engine"               # Bad
```

---

## 📊 SUCCESS METRICS

After Phase 1 completes, we should have:

- ✅ Single route engine in `domains/routing/engine.py`
- ✅ Feature flag for instant rollback
- ✅ All tests passing
- ✅ API responses identical to old engine
- ✅ `api/search.py` using new engine
- ✅ Old implementations archived (not deleted)
- ✅ Zero downtime migration

---

## 🚀 NEXT AFTER PHASE 1

Once Phase 1 is 100% verified:

1. Run in production for 2-3 weeks with feature flag
2. Monitor logs to confirm new engine is stable
3. Then delete: `services/advanced_route_engine.py`, etc.
4. Move to Phase 2 (Seat Allocation consolidation)

---

**Status**: Ready to Implement Phase 1
**Next**: Execute implementation steps above
