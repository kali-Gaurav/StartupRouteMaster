# Current Problems & Technical Debt - RouteMaster

## 🔴 Critical Issues

### 1. CORS Configuration Error
- **Symptom:** Browser console shows `Access-Control-Allow-Origin` header missing for the `/api/stats` endpoint.
- **Impact:** Frontend cannot fetch system statistics (CPU, RAM, Latency), leading to "blocked by CORS policy" errors.
- **Root Cause:** Likely the `CORSMiddleware` is not correctly applied or is bypassed for direct `app.get` routes in `app.py`.

### 2. Redis Authentication Failure
- **Symptom:** `AuthenticationError` when connecting to Upstash/RedisCloud.
- **Impact:** Caching, rate-limiting, and real-time features are degraded or non-functional.
- **Root Cause:** Incorrect `REDIS_URL` or issues in the `sanitize_redis_url` logic in `backend/core/infrastructure/redis.py`.

### 3. Initialization Performance (Bottleneck)
- **Symptom:** Backend takes time to start due to heavy background preprocessing.
- **User Request:** "upgrade our system so that it always runs instantly and every preprocessing must happen after 1st request not in the initialization."
- **Status:** Currently using `asyncio.create_task` in lifespan, but it still starts at boot time.

---

## 🟡 High Priority Issues

### 4. Backend Stability ("Stuck" Connections)
- **Symptom:** Reports of the backend getting "stuck" or losing connections.
- **Root Cause:** Possible deadlocks in async code, thread pool starvation, or unhandled exceptions in background tasks.

### 5. Dependency Version Mismatches
- **Symptom:** `RequestsDependencyWarning: urllib3 (2.6.3) or chardet (7.1.0)/charset_normalizer (3.4.6) doesn't match a supported version!`
- **Impact:** Potential instability in outgoing HTTP requests.

### 6. aiosqlite/SQLAlchemy Transaction Rollbacks
- **Symptom:** Logs show frequent `ROLLBACK` operations.
- **Root Cause:** Every request or health check might be starting a transaction and rolling it back if no write occurs, which is noisy and potentially inefficient.

---

## 🔵 Technical Debt & TODOs

### 7. Unimplemented Auth Features
- **File:** `backend/api/auth/auth.py`
- **Item:** `Implement verify_google_token`

### 8. System Integrations
- **File:** `backend/api/system/routemaster_integration.py`
- **Items:**
    - Initialize `GraphMutationEngine`.
    - Implement full trip insertion with stops/timing.
    - Implement notification service.

### 10. Massive Import & Module Breakage (Refactoring Debt)
- **Symptom:** Backend starts in "Degraded" mode with many `ModuleNotFoundError` and `ImportError`.
- **Root Cause:** Recent refactoring (2026-05-04) moved files but many internal imports were not updated.
- **Specific Missing/Broken Items:**
    - `services.ws_manager` missing (referenced in `gateway_agent.py`).
    - `core.resilience.redis_client` missing (referenced in `rate_limit.py`).
    - `services.search_service`, `services.station_service` missing.
    - `backend.telegram_bot` reference broken in `app.py`.
    - `Schedule` missing from `database.models`.
    - `api.dependencies` missing (referenced in many API files).
    - `services.search_service` missing (referenced in `api/v2/search.py`).

---

## ✅ Verified Working
- Supabase (Postgres & Auth) integration.
- Core Route Verification Service (RapidAPI integration).
- Payment order schema and logic.
