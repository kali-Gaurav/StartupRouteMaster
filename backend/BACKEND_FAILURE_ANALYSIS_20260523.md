# Backend Startup Failure Analysis

**Date:** May 23, 2026  
**Session:** Backend startup and failure investigation  
**Status:** ❌ FAILED - ImportError during bootstrap

---

## Executive Summary

The backend failed to start properly due to a circular import chain that culminates in an `ImportError` when trying to import `inventory_service` from `services.inventory_service`. The application falls back to degraded mode but critical services are not initialized.

---

## Critical Error

```
ImportError: cannot import name 'inventory_service' from 'services.inventory_service'
```

**Location:** `services/booking_service.py` (line 23)

---

## Import Chain Analysis

The failure occurs through a 6-level deep import chain:

```
app.py
  ↓
core.infrastructure.lifespan
  ↓
services.finance.ingestion_worker
  ↓
services.orchestration.recovery
  ↓
services.orchestration.booking_orchestrator
  ↓
services.booking_service [LINE 23 - FAILURE]
  ↓
services.inventory_service [MISSING EXPORT]
```

---

## Root Cause

### Problem 1: Missing Singleton Instance

In `services/inventory_service.py`, the global singleton instance was removed:

```python
# Removed global singleton instance
# inventory_service = None

def get_inventory_service(db: AsyncSession) -> InventoryService:
    """Get or create inventory service instance."""
    return InventoryService(db)
```

However, `services/booking_service.py` still tries to import it as a singleton:

```python
from services.inventory_service import inventory_service
from services.pricing_service import pricing_service
from services.fraud_detection import fraud_detection_service
from services.notification_service import notification_service
```

### Problem 2: Inconsistent Service Patterns

Other services like `pricing_service` still use the singleton pattern:

```python
# In services/pricing_service.py
pricing_service = None

def get_pricing_service(db: Session) -> PricingService:
    global pricing_service
    if pricing_service is None:
        pricing_service = PricingService(db)
    return pricing_service
```

But `inventory_service` was refactored to use a factory function only.

### Problem 3: Circular Dependencies

The import chain creates a circular dependency:
- `booking_service` imports from multiple services
- These services depend on each other through orchestration layer
- The lifespan tries to initialize everything at startup

---

## Successfully Initialized Components

Before the failure, these components were successfully initialized:

| Component | Status | Details |
|-----------|--------|---------|
| Telegram Bot Handlers | ✅ | 8 actions registered (open_dashboard, request_refund, rate_journey, etc.) |
| Circuit Breakers | ✅ | 5 circuit breakers initialized (telegram_api, redis_l2, cache_redis, scraper_browser, scraper_context) |
| Redis Cache | ✅ | Successfully connected to Redis |
| S3/boto3 | ✅ | Client initialized |

---

## Degraded Boot Behavior

The application falls back to "no-op lifespan" when the production lifespan fails:

```
2026-05-23 10:55:03,692 [ERROR] api-gateway [RID:N/A]: Production lifespan unavailable; falling back to no-op lifespan.
```

This means:
- Database connections may not be established
- Background workers won't start
- Some API routes may not function properly
- Application runs in degraded mode

---

## Recommendations

### Priority 1: Fix Import Error (Immediate)

**Option A:** Restore the singleton instance in `inventory_service.py`

```python
# Add back at the end of services/inventory_service.py
inventory_service = None

def get_inventory_service(db: AsyncSession) -> InventoryService:
    """Get or create inventory service instance."""
    global inventory_service
    if inventory_service is None:
        inventory_service = InventoryService(db)
    return inventory_service
```

**Option B:** Update `booking_service.py` to use factory function

```python
# Change from:
from services.inventory_service import inventory_service

# To:
from services.inventory_service import get_inventory_service
# And use get_inventory_service(db) where needed
```

### Priority 2: Break Circular Dependencies

Consider these architectural improvements:

1. **Lazy Imports:** Import services inside functions instead of at module level
2. **Dependency Injection:** Use a DI container (already exists: `routemaster.container`)
3. **Service Locator Pattern:** Create services on-demand through a service locator
4. **Simplify Import Chain:** Reduce depth of service dependencies

### Priority 3: Improve Startup Resilience

1. **Graceful Degradation:** Ensure core API still works even if optional services fail
2. **Health Checks:** Add more granular health checks for each service
3. **Startup Validation:** Validate all imports before starting the lifespan

---

## Files to Modify

1. `services/inventory_service.py` - Add back singleton export OR
2. `services/booking_service.py` - Change import to use factory function
3. `core/infrastructure/lifespan.py` - Consider lazy loading of services

---

## Next Steps

1. ✅ Logs captured: `backend_startup_logs_20260523_1055.txt`
2. ⏳ Fix the import error
3. ⏳ Test backend startup again
4. ⏳ Verify all features work in degraded mode
5. ⏳ Refactor to prevent future circular dependencies

---

## Log Files

- **Startup Logs:** `backend/backend_startup_logs_20260523_1055.txt`
- **This Analysis:** `backend/BACKEND_FAILURE_ANALYSIS_20260523.md`