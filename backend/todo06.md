  🏆 The Next 50: Production Hardening & Efficiency Master Plan

  Phase 1: The Unified API Gateway (app.py Integration)
  We need `app.py` to be the command center exposing all our powerful backend features.
   1. [API] Implement /api/v2/search endpoint connecting to SearchService (with pagination/offset).
   2. [API] Implement /api/v2/stations/suggest for lightning-fast station autocomplete.
   3. [API] Implement /api/v2/live/train/{train_no} for real-time train location tracking.
   4. [API] Implement /api/v2/live/station/{station_code} for live station departure boards.
   5. [API] Implement /api/v2/auth/sync to handle Supabase JWT validation and local user_store.db syncing.
   6. [API] Implement /api/v2/user/profile for reading/updating user preferences.
   7. [API] Implement /api/v2/user/history to fetch past bookings and searches.
   8. [API] Implement /api/v2/booking/initiate to push items into the BookingQueue.
   9. [API] Setup FastAPI Exception Handlers to return standardized JSON error payloads.
   10. [API] Add API Route versioning and standard OpenAPI/Swagger documentation tags.

  Phase 2: Developer Dashboard & Observability (monitoring/)
  You cannot optimize what you cannot see. We need a visual dashboard.
   11. [Monitor] Create monitoring/dashboard.html (Vanilla JS/HTML/CSS) served directly by FastAPI.
   12. [Monitor API] Endpoint /admin/system/health to aggregate CPU, RAM, and DB disk usage.
   13. [Monitor API] Endpoint /admin/cache/stats to visualize Redis hit/miss ratios across all 5 layers.
   14. [Monitor API] Endpoint /admin/engine/metrics to show Turbo vs. FastRouter vs. RAPTOR usage charts.
   15. [Monitor API] Endpoint /admin/diagnostics/zero-routes to list top failing src-dest pairs.
   16. [Monitor API] Endpoint /admin/etl/status to show the latest ETLMetadata runs and sync progress.
   17. [Monitor UI] Build "Clear Cache" and "Warmup Cache" trigger buttons in the dashboard.
   18. [Monitor UI] Build "Trigger Graph Rebuild" button in the dashboard.
   19. [Monitor] Implement FastAPI middleware to track Request Latency (p50, p90, p99) and expose to dashboard.
   20. [Security] Add Basic Auth / RBAC (Role-Based Access Control) to lock down the /admin routes.

  Phase 3: Database Efficiency, Retrieval & Caching (.db layer)
  SQLite is fast, but we need to push it to its absolute limits for read/write efficiency.
   21. [DB Efficiency] Implement SQLite FTS5 (Full-Text Search) virtual tables for ultra-fast station and train name lookups.
   22. [DB Efficiency] Create composite indexes on station_schedule (station_id, day_of_week, departure).
   23. [DB Efficiency] Create a scheduled background task (using APScheduler) to run VACUUM and ANALYZE on databases nightly.
   24. [DB Migration] Set up Alembic specifically for the multi-database (User vs. Transit) architecture.
   25. [Cache] Implement Redis Pub/Sub to invalidate local LRU caches across multiple Uvicorn workers.
   26. [Cache] Add memory-eviction policies (Maxmemory-policy allkeys-lru) to Redis config via code.
   27. [Cache] Implement pre-fetching: When a user searches a route, asynchronously pre-fetch seat availability for the top 3 results.
   28. [Data Handling] Migrate station_transit_index JSON generation to a background task that updates incrementally.
   29. [Data Handling] Add data compression (Zstandard) for large JSON blobs stored in SQLite (booking_details).
   30. [Data Handling] Implement soft-deletes (is_deleted flag) instead of hard deletes in `user_store.db`.

  Phase 4: Real-Time Data Handling & Analytics
  Handling live delays, dynamic pricing, and user telemetry.
   31. [Real-Time] Implement WebSocket endpoint (/ws/live-status) for pushing train delays to clients instantly.
   32. [Real-Time] Create LiveStatusPoller background worker that iteratively checks active trains against the external API.
   33. [Real-Time] Implement Redis Streams to bridge the Poller worker and the FastAPI WebSockets.
   34. [Real-Time] Add "Stale Data Eviction": Auto-remove delays from train_states if not updated in 2 hours.
   35. [Analytics] Build UserDropoffLogger middleware to track at which API step a user abandoned a search.
   36. [Analytics] Track conversion rates (Searches -> Availability Clicks -> Bookings) in the dashboard.
   37. [Analytics] Calculate dynamic "Popularity Scores" for stations based on real search volume and inject into StationRank.
   38. [Analytics] Log API response times per partner/provider to detect external degradation automatically.
   39. [Simulation] Enhance simulate_connection_survival to factor in real-time weather alerts mapped via coordinates.
   40. [Queue] Implement a robust dead-letter queue (DLQ) for failed real-time ingestions.

  Phase 5: Reliability, Security, and Production Scaling
  Protecting the system from abuse and ensuring high uptime.
   41. [Security] Implement Redis-based Rate Limiting (e.g., max 20 searches / minute / IP).
   42. [Security] Add bot-protection middleware to block suspicious scraping behavior.
   43. [Resilience] Add Circuit Breakers to all external API calls (NTES, RapidAPI, Payment Gateways).
   44. [Resilience] Implement fallback logic: If Redis dies, automatically gracefully degrade to SQLite + Local LRU without crashing.
   45. [Booking] Implement Idempotency Keys for booking and payment endpoints to prevent double-charging.
   46. [Scaling] Configure Uvicorn/Gunicorn for multi-worker deployment based on CPU cores.
   47. [Scaling] Abstract the database connection strings to easily swap SQLite for PostgreSQL later without code changes.
   48. [Testing] Add integration tests specifically for the new API endpoints using TestClient.
   49. [Testing] Add load-testing scripts (using Locust or k6) to verify the multi-db architecture under 1000+ concurrent requests.
   50. [Launch] Finalize Dockerfile to correctly mount volumes for user_store.db and transit_graph.db to prevent data loss on container restart.