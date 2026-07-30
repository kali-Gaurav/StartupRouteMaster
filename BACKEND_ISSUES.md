# Backend Issues List

## 1. Missing Modules (ModuleNotFoundError)
The following modules are missing or cannot be found by the Python interpreter:
- `services.ws_manager`: Required by `services.agents.gateway_agent`.
- `core.resilience.redis_client`: Required by `core.resilience.rate_limit`.
- `services.station_service`: Required by search router.
- `api.dependencies`: Required by multiple routers (Users, Auth, Sathi, SOS).
- `services.search_service`: Required by `api.v2.search`.
- `backend.telegram_bot`: Referenced as a module in `app.py`.

## 2. Import Errors
- `cannot import name 'Schedule' from 'database.models'`: Affects Bookings, Chat, and Payments routers.

## 3. Infrastructure Issues
- **Redis Authentication:** Connection failing with authentication error (reported in global memory).
- **Lifespan/Middleware Failures:** Application falling back to no-op lifespan and degraded bootstrap mode due to module errors.

## 4. API & Frontend Integration
- **CORS Policy:** `Access-Control-Allow-Origin` missing for `/api/stats`.
- **404 Errors:** Frontend requesting `/api/status/health/live` and getting 404.

## 5. Architectural Improvements
- **Startup Optimization:** Preprocessing should happen after the first request (lazy initialization) instead of blocking the initial startup.

## 6. Environment & Dependencies
- `RequestsDependencyWarning`: Version mismatch for `urllib3` and `chardet`/`charset_normalizer`.
