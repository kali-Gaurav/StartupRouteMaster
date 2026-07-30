# Current System Issues to Fix

## 1. Frontend Issues
- **React Router Future Flags:** Warnings in the console regarding `v7_startTransition` and `v7_relativeSplatPath`. These need to be opted into in the router configuration.
- **SOSWidget Geolocation:** `GeolocationPositionError` when the user denies location. Needs a graceful error handling/fallback mechanism instead of an unhandled rejection.
- **Server Warmup 404:** `useServerWarmup.ts` is trying to hit `http://localhost:5173/api/status/health/live` which returns 404. This is likely hitting the frontend dev server instead of the backend (`http://localhost:8000`), or the endpoint doesn't exist.

## 2. Backend API & CORS Issues
- **/api/stats 500 Error:** The endpoint `/api/stats` is crashing (Internal Server Error).
- **CORS Blocked:** Because the `/api/stats` endpoint is crashing (or due to missing CORS config), it's missing the `Access-Control-Allow-Origin` header, causing the browser to block the response.

## 3. Backend Initialization & Performance
- **Heavy Initialization:** The user requested that preprocessing must happen *after* the first request, not during initialization, to ensure the app starts instantly.
- **Verbose SQL Logging:** The console is flooded with `aiosqlite` and `sqlalchemy` debug logs. The logging level needs to be reduced to `INFO` or `WARNING`.
- **Connection Stability:** Ensure the backend doesn't get "stuck" and doesn't lose connections (e.g., proper SQLAlchemy pooling/connection handling).
