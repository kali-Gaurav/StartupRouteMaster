# Backend Startup Issues and Recommended Fixes

This document captures every warning, error, and gap observed during backend startup. Each issue is described along with recommended actions to resolve or mitigate the problem.

## 1. Pydantic Configuration Warning
**Message:**
```
UserWarning: Valid config keys have changed in V2:
* 'allow_population_by_field_name' has been renamed to 'populate_by_name'
```
**Cause:**
The application uses Pydantic V2 but one or more models (including some in third-party libraries) still declare the old key.

**Fix:**
- Our own schemas already use `populate_by_name = True` but the warning can still be emitted by external packages. Keep dependencies up-to-date.
- Search for `allow_population_by_field_name` and replace with `populate_by_name` if any custom models remain.

This warning is harmless but should be resolved before upgrading to Pydantic 3.

## 2. RapidAPIClient Not Available
**Message:**
```
RapidAPIClient not available - verification will use database only
```
**Cause:**
The RapidAPI client library is missing or not imported correctly.

**Fix:**
- Ensure `RapidAPIClient` dependency is installed and included in `requirements.txt` or `pyproject.toml`.
- Check import paths and initialization logic.

## 3. SQLAlchemy Relationship Warning
**Message:**
```
Could not determine join condition between parent/child tables on relationship Profile.user - there are no foreign keys linking these tables...
```
**Cause:**
The `Profile` and `User` models lacked a `ForeignKey` relationship, so SQLAlchemy could not auto‑resolve the join condition.

**Fix:**
- Added a `ForeignKey('profiles.id')` constraint to `User.supabase_id`.
- Updated `User` and `Profile` relationships with `back_populates` and explicit `foreign_keys` annotations.
- Tests now show `User.supabase_id` has the expected foreign key and ORM queries resolve correctly.

This eliminates the warning and allows eager/lazy loading of profiles seamlessly.

## 4. Missing Model File
**Message:**
```
Failed to load model: [Errno 2] No such file or directory: 'route_ranking_model.pkl'
```
**Cause:**
The machine learning model file is expected but not present in working directory.

**Fix:**
- Added `ROUTE_RANKING_MODEL_PATH` env variable to configure path (update `.env.example`).
- Model loader already logs an error; no crash occurs. Consider adding a default behaviour or training scaffolding if missing.

Note: This warning is informational and does not stop the app from running with offline ranking.



## 5. Config Import Failures & Offline Mode
**Messages:**
```
Config not available, assuming offline mode
Config not available, live validators disabled
```
**Causes:**
- Modules such as the route engine and live validators attempted to import `Config` using a path that sometimes failed depending on how the application was launched (`PYTHONPATH`/`app-dir`).
- In absence of a valid `DATABASE_URL` or network access, startup would crash.

**Fixes:**
- Added fallback import logic (`from database.config` then `from backend.database.config`) in `route_engine`, `live_validators`, and other locations.
- Added a lightweight `__init__.py` to `services/booking` so relative imports no longer break.
- Updated `Config.validate()` to allow missing `DATABASE_URL` when `OFFLINE_MODE` is true and to log a warning.
- Introduced `OFFLINE_MODE` environment variable (documented in `.env.example`) and automatic SQLite in‑memory fallback when DNS/connection errors occur.
- Updated `database/session.py` to catch `OperationalError` (including DNS resolution failures) and switch to SQLite automatically; this prevents application startup failure when the configured host is unreachable.

These changes eliminate crashes when running locally without external services and reduce spurious warnings.

---
**New environment variables added:**
- `READ_DATABASE_URL` for optional read‑replica
- `OFFLINE_MODE` to explicitly force offline behaviour
- `ROUTE_RANKING_MODEL_PATH` to override model file location

The example `.env` file has been updated accordingly.

## 6. Booking Manager Initialization Error
**Message:**
```
Booking manager failed to initialize: attempted relative import beyond top-level package
```
**Cause:**
A module uses a relative import that escapes the package root.

**Fix:**
- Convert relative imports to absolute imports using the project package name.
- Ensure `backend` is included in `PYTHONPATH` or use proper package structure.

## 7. FastAPI Deprecation Warnings
**Messages:**
```
on_event is deprecated, use lifespan event handlers instead.
```
**Cause:**
The application uses the `@app.on_event` decorator which is deprecated in favour of lifespan context managers.

**Fix:**
- Refactor startup/shutdown handlers to use `lifespan` event handlers as per FastAPI docs.

## 8. Supabase Connectivity Issues
**Message:**
```
Unable to verify Supabase connectivity: ... SSL handshake failed ...
```
**Cause:**
- SSL handshake failed; target host unreachable or misconfigured.

**Fix:**
- Validate Supabase URL and network connectivity.
- Ensure proper SSL certificates and firewall rules.
- Consider mocking or disable Supabase client for offline/test runs.

## 9. DNS / IP Resolution and Supabase Networking
**Messages:**
```
could not translate host name "db.orfikmmpbboesbxdiwzb.supabase.co" to address: No such host is known.
``` 

and occasionally connection failures when attempting to resolve an IPv6
address.

**Cause:**
- Client machine may not support IPv6 or the DNS record returned only an IPv6
address.  Supabase free tier projects do not provide a dedicated IPv4 host; the
pooler resolves to IPv4 automatically.

**Fix:**
- Prefer the **shared connection pooler URL** in your `DATABASE_URL`.  It always
resolves to IPv4 and avoids the need for the IPv4 add‑on.
- If you require a direct connection, enable the paid **Dedicated IPv4 address**
(add-on costs $4/mo per database) or configure your client to use IPv6.
- Our `init_db` logic now falls back to SQLite so startup no longer crashes when
the host is unreachable.

This guidance is also reflected in `.env.example` comments.

## 10. pg_trgm Extension Creation Failure
**Message:**
```
Could not create pg_trgm extension: (psycopg2.OperationalError) could not translate host name...
```
**Cause:**
Extension creation failed due to underlying connectivity issue.

**Fix:**
- Resolve network/DNS issues as above before attempting database migrations.
- Handle extension creation errors gracefully during initialization.

## 11. Application Startup Failure
**Message:**
```
Application startup failed. Exiting.
```
**Cause:**
Cascading failure from inability to connect to the database during `init_db()`.

**Fix:**
- Address database connectivity problems; provide fallback or retry logic.
- Add clearer logs and exit codes for database initialization failure.

## Recommendations Summary
1. **Fix configuration and dependency issues** (RapidAPI, model file, config file).
2. **Correct database model definitions** to include proper foreign keys.
3. **Refactor code for environment handling**, using offline fallbacks and absolute imports.
4. **Resolve network/DNS problems** or provide local dev database settings.
5. **Update deprecated patterns** (Pydantic config keys, FastAPI `on_event`).
6. **Enhance startup error handling** and logging for maintainability.

> ⚠️ Many issues stem from missing or misconfigured external services (Supabase, RapidAPI). For local development, ensure `DATABASE_URL` is pointed to a reachable database or mock services.

---

This file should be reviewed and updated as fixes are implemented.