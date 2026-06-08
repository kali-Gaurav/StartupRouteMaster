# Consolidated Backend Issues & Fix Plan

## 1. Identified Issues

### Infrastructure & Startup
- **Slow Startup:** The backend takes too long to initialize because heavy preprocessing happens during startup.
- **Lazy Preprocessing:** Preprocessing should be triggered *after* the first request, not during app creation.
- **Connection Stability:** Reports of backend getting "stuck" or losing connections.

### API Endpoints
- **404 Errors on Health Checks:** Frontend is requesting `http://localhost:5173/api/status/health/live` (port 5173 is frontend, should be 8000) or the backend is missing the exact path.
- **500 Error on `/api/stats`:** The stats endpoint is failing with an Internal Server Error.

### Security & CORS
- **CORS Blocked for `/api/stats`:** The browser blocks requests to `/api/stats` due to a missing `Access-Control-Allow-Origin` header. This often happens when the endpoint crashes (500 error) before CORS headers are applied, or if CORS is misconfigured for certain failure modes.
- **Invalid CORS Headers:** Reports of invalid or missing response headers for CORS requests.

## 2. Proposed Fixes

### A. Instant Startup & Lazy Preprocessing
- [ ] Verify `LazyBootMiddleware` is correctly triggering `_nexus_background_boot` in `lifespan.py`.
- [ ] Ensure `_nexus_background_boot` handles all heavy initializations (DB pools, ML models, engine warming).
- [ ] Move any blocking logic from `create_app` or module-level imports into the background boot sequence.

### B. Fix `/api/stats` & CORS
- [ ] Debug the 500 error in `/api/stats`. It likely fails during module import or stats collection.
- [ ] Ensure `CORSMiddleware` is the absolute outermost middleware.
- [ ] Explicitly handle CORS in the exception handlers to ensure headers are present even on 500 errors.

### C. Health Check Alignment
- [ ] Ensure `/api/status/health/live` is correctly registered and reachable.
- [ ] (Optional) Update frontend config to point to the correct backend port (8000).

## 3. Verification Plan
- [ ] Run backend in the background.
- [ ] Capture logs to `backend/startup_output.txt` and `backend/startup.err`.
- [ ] Verify instant startup (ping `/health` within milliseconds).
- [ ] Trigger first request and monitor background preprocessing logs.
- [ ] Test `/api/stats` with a cross-origin request (e.g., via `curl` or a test script).
