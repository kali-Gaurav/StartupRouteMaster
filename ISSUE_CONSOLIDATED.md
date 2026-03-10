# Consolidated Backend Issues - March 10, 2026

## 1. CORS Policy Blocking
- **Problem:** Frontend requests to `/api/stats` (and potentially others) are blocked by CORS.
- **Error:** `Access-Control-Allow-Origin` header is missing.
- **Status:** Partially addressed by reordering middleware and updating exception handler, but still appearing in logs.

## 2. RuntimeError: No Response Returned
- **Problem:** `lazy_load_api_routes` middleware is causing a crash on the first API request.
- **Error:** `RuntimeError: No response returned.`
- **Root Cause:** `BaseHTTPMiddleware` (used via `@app.middleware`) has issues when modifying the app (registering routers) during a request.
- **Fix:** Remove lazy-loading of routers; they are fast enough to register at startup. Keep heavy data loading (Graph/Redis) in background tasks.

## 3. Slow/Blocking Startup
- **Status:** Already improved by moving Graph/Redis to background tasks in `lifespan`. Startup is now "instant" from Uvicorn's perspective.

## 4. Database Connection Stability & Noisy Logs
- **Problem:** Logs are flooded with `aiosqlite` and `sqlalchemy` debug messages. Frequent `ROLLBACK` messages.
- **Fix:** Set log level to `INFO` for these libraries.

## 5. Route Mismatches (404s)
- **Problem:** Frontend is hitting `/api/status/health/live`, `/api/health/live`, `/api/stats`, etc.
- **Fix:** Consolidate these routes and ensure they are always mapped.

## 6. Redis Connection Timeout
- **Problem:** `amazed-rat-39065.upstash.io:6379` is timing out.
- **Status:** App falls back to RAM-ONLY mode, which is fine, but we should ensure the timeout doesn't block the background init task indefinitely.
