# Backend Features Checklist (300+ Items)

This document outlines a comprehensive list of backend features derived from the codebase and common practices for a high-performance route optimization and booking platform. This checklist can be used for testing, identifying gaps, and ensuring complete implementation.

---

## 1. Core Application & Infrastructure (`backend/app.py` and related)

1.  **API Server Startup/Shutdown**
    1.  Successful application startup.
    2.  Graceful shutdown sequence.
    3.  Database initialization on startup.
    4.  Database connection closing on shutdown.
    5.  FastAPI-Cache initialization (Redis backend).
    6.  FastAPI-Cache clearing on shutdown.
    7.  Prometheus Instrumentator mounting.
    8.  Rate limiter initialization.
    9.  Rate limit exception handler active.
    10. CORS middleware configured correctly.
    11. Structured logging configured and functional.
    12. `uvicorn` server starts correctly in development mode (`--reload`).
    13. `uvicorn` server starts correctly in production mode.

2.  **Health Checks & Monitoring**
    1.  Root endpoint (`/`) returns basic app info and status.
    2.  `status` router endpoints are functional.
    3.  Prometheus metrics exposed at `/metrics`.
    4.  Application logs are generated and structured (JSON).
    5.  Error logging for startup/shutdown failures.

3.  **Configuration Management**
    1.  `Config` variables are loaded correctly from environment/defaults.
    2.  Sensitive configurations are handled securely (e.g., `ADMIN_API_TOKEN`).
    3.  Dynamic configuration updates (if supported).

---

## 2. Authentication & Authorization (from `backend/api/auth.py` and other security practices)

1.  **User Authentication**
    1.  User registration (new account creation).
    2.  User login (username/password).
    3.  Token-based authentication (JWT or similar).
    4.  Token validation and expiry.
    5.  Password hashing and security.
    6.  Password reset functionality (e.g., via email).
    7.  Email verification for new registrations.
    8.  Social login integration (if planned).
    9.  Logout/token invalidation.

2.  **Admin Authorization**
    1.  Admin token verification for protected endpoints (e.g., `verify_admin_token`).
    2.  Admin login/session management (if separate from user login).
    3.  Role-based access control (if implemented, e.g., for different admin levels).

3.  **Security**
    1.  Protection against brute-force attacks (rate limiting on login).
    2.  Protection against SQL injection.
    3.  Protection against XSS (via proper output encoding if directly rendering user content).
    4.  HTTPS enforcement.
    5.  Secure handling of sensitive user data.

---

## 3. User Management (`backend/api/users.py`)

1.  **User Profiles**
    1.  Retrieve own user profile.
    2.  Update own user profile details.
    3.  Admin can retrieve any user profile.
    4.  Admin can update any user profile.
    5.  User can delete own account.
    6.  Admin can deactivate/delete user accounts.

2.  **User Preferences**
    1.  Store and retrieve user-specific routing preferences.
    2.  Store and retrieve user-specific booking preferences.
    3.  Notification preferences management.

---

## 4. Route Generation & Search

### 4.1. `backend/core/route_engine.py` (Simple RAPTOR)

1.  **Basic Route Search**
    1.  Search between valid source and destination stations.
    2.  Handles valid departure dates.
    3.  Returns routes with segments and transfers.
    4.  Correctly calculates total duration, cost, distance.
    5.  Applies multi-objective scoring (`_calculate_score`).
    6.  Returns specified `max_results`.

2.  **Constraints Handling**
    1.  `max_journey_time` respected.
    2.  `max_transfers` respected.
    3.  `min_transfer_time` respected.
    4.  `max_layover_time` respected.
    5.  `avoid_night_layovers` logic works correctly.
    6.  `women_safety_priority` logic works correctly.

3.  **Graph Building (`_build_graph`, `_build_graph_sync`)**
    1.  Loads `Stop` data correctly.
    2.  Loads `Trip` data correctly.
    3.  Loads `StopTime` data correctly.
    4.  Loads `GTFRoute` data correctly.
    5.  Loads `Calendar` data correctly.
    6.  Loads `CalendarDate` data correctly.
    7.  Loads `Transfer` data correctly.
    8.  Correctly identifies active service IDs for a given date.
    9.  `_time_to_datetime` conversion is accurate.
    10. Trip segments are created accurately.
    11. Departures and arrivals are indexed correctly.
    12. Transfers are generated (even simplified ones).

4.  **Real-time Updates (`apply_realtime_updates`)**
    1.  Handles `delay` updates correctly.
    2.  Handles `cancellation` updates correctly.
    3.  Handles `occupancy` updates correctly.
    4.  Invalidates affected cached routes (`_invalidate_affected_routes`).

5.  **Caching**
    1.  `multi_layer_cache` integration for route queries.
    2.  Cache hit returns correct results.
    3.  Cache miss triggers computation and caching.
    4.  Serialization/deserialization of routes for cache.

### 4.2. `backend/core/multi_modal_route_engine.py` (Multi-Modal RAPTOR)

1.  **Graph Loading (`load_graph_from_db`)**
    1.  Loads `Stop` data into `stops_map` correctly (including `safety_score`).
    2.  Loads `Route` data into `routes_map`.
    3.  Loads `Trip` data into `trips_map`.
    4.  Loads `StopTime` data into `stop_times_map` and sorts by sequence.
    5.  Loads `Transfer` data into `transfers_map`.
    6.  Loads `Calendar` data into `calendar_map`.
    7.  Loads `CalendarDate` data into `calendar_dates_map`.
    8.  Correctly sets `_is_loaded` flag.

2.  **Service & Time Utilities**
    1.  `_time_to_minutes` handles various time formats.
    2.  `_minutes_to_time` converts minutes back to time objects.
    3.  `_is_service_active` correctly determines service availability based on calendar and exceptions.
    4.  `_get_earliest_departure` finds trips from a stop after a given time.

3.  **Multi-Modal RAPTOR (`_multi_modal_raptor`)**
    1.  Correctly initializes labels and best arrival times.
    2.  Processes direct trips from source.
    3.  Handles multiple rounds of transfers (`max_transfers`).
    4.  Identifies dominated labels correctly.
    5.  Processes explicit transfers from `transfers_map`.
    6.  Reconstructs journey details (`_reconstruct_journey`).
    7.  Returns top journey options sorted by arrival time and cost.

4.  **Journey Types**
    1.  `search_single_journey` works for single trips.
    2.  `search_connecting_journeys` combines two journeys with valid layovers.
    3.  `_get_walk_transfers` identifies feasible walking transfers.
    4.  `_haversine_km` distance calculation is accurate.
    5.  `_combine_journeys` correctly merges journey details, duration, cost, modes.
    6.  `_compute_feasibility_score` accurately scores combined journeys.
    7.  `search_circular_journey` creates round-trip options with telescopic fares.
    8.  `search_multi_city_journey` handles routes across multiple cities.

5.  **Fare Calculation (`calculate_fare_with_concessions`)**
    1.  Applies mode-specific pricing correctly.
    2.  Applies passenger type discounts (child, senior).
    3.  Applies concession discounts (defence, freedom fighter, divyang).
    4.  Caps maximum concession discount.
    5.  Returns detailed fare breakdown.

6.  **Real-time Simulation (`simulate_real_time_delays`)**
    1.  Retrieves active disruptions from the database (`Disruption` model).
    2.  Applies delays based on disruption types.
    3.  Adjusts segment departure/arrival times.
    4.  Calculates `total_delay_minutes`.
    5.  Calculates `otp_confidence`.

7.  **PNR Generation**
    1.  `generate_pnr_reference` creates unique PNRs.

### 4.3. `backend/core/advanced_route_engine.py` (Advanced Route Engine)

1.  **Internal Data Models**
    1.  `Stop` dataclass functions correctly.
    2.  `StopTime` dataclass functions correctly.
    3.  `Trip` dataclass functions correctly.
    4.  `Segment` dataclass functions correctly (including `_haversine` distance).
    5.  `Route` dataclass functions correctly (duration, transfers, cost, distance properties).
    6.  `TransportMode` enum is used consistently.
    7.  `RouteStatus` enum is used consistently.

2.  **`TransferValidator`**
    1.  `find_valid_transfers` identifies transfer points using Set A & B logic.
    2.  `validate_transfer` checks specific transfer validity.
    3.  `_get_min_transfer_time` calculates minimum transfer times based on station types/distance.

3.  **`RaptorRouter`**
    1.  `find_shortest_path` implements RAPTOR for fast paths.
    2.  Handles `max_transfers`.
    3.  Respects `mode_filters`.
    4.  `_find_direct_trips` and `_find_onward_trips` function correctly (relying on `network_service`).
    5.  `_reconstruct_route` builds `Route` objects from trip paths.

4.  **`AStarRouter`**
    1.  `find_path` implements A* with geographic heuristic.
    2.  `_heuristic` provides accurate distance estimation.
    3.  `_reconstruct_route_from_path` builds `Route` objects.

5.  **`YensKShortestPaths`**
    1.  `find_k_shortest_paths` correctly finds alternative routes.
    2.  Handles forbidden edges and root/spur paths.
    3.  `_is_duplicate` and `_routes_equal` correctly identify unique routes.

6.  **`AdvancedRouteEngine` (Orchestration)**
    1.  `search_routes` provides a high-level API.
    2.  Obtains source/destination stops via `network_service.get_stop_by_code`.
    3.  Builds cache key consistently.
    4.  Handles cache hits/misses.
    5.  Executes `RaptorRouter` for fastest path.
    6.  Executes `YensKShortestPaths` for alternatives.
    7.  Removes duplicate routes.
    8.  Sorts routes by duration.
    9.  Caches results (`_cache_routes`, `_get_cached_routes`).
    10. Proper injection of `db_session`, `redis_client`, `network_service`.

---

## 5. Booking & Payments (from `backend/api/payments.py`, `backend/services/booking_service.py`, `backend/worker.py`)

1.  **Booking Creation**
    1.  Create a new booking.
    2.  Validate booking details (route, passengers, date).
    3.  Reserve seats (if seat allocation service is integrated).
    4.  Generate booking ID.

2.  **Booking Retrieval**
    1.  Retrieve booking by ID.
    2.  Retrieve all bookings for a user.
    3.  Retrieve filtered bookings (admin).

3.  **Payment Processing**
    1.  Initiate payment for a booking.
    2.  Handle payment success/failure.
    3.  Record payment details.
    4.  Integrate with external payment gateway (if applicable).
    5.  Handle refunds.

4.  **Payment Reconciliation**
    1.  `start_reconciliation_worker` and `stop_reconciliation_worker` function correctly.
    2.  Worker successfully reconciles pending payments.
    3.  Updates booking status after successful reconciliation.
    4.  Handles failed reconciliation attempts.
    5.  Logs reconciliation activities.

5.  **Booking Status Updates**
    1.  Update booking status (pending, confirmed, cancelled).
    2.  Send notifications for status changes.

---

## 6. Admin Functionalities (`backend/api/admin.py`)

1.  **Booking Management**
    1.  `get_all_bookings` retrieves all bookings.
    2.  `get_booking_stats` provides booking statistics.
    3.  `filter_bookings` filters by payment status.

2.  **ETL & Graph Management**
    1.  `trigger_etl_sync` endpoint successfully calls `run_etl`.
    2.  `run_etl` (from `backend/etl/sqlite_to_postgres.py`) correctly syncs data from `railway_manager.db` to PostgreSQL.
    3.  Logs ETL results.
    4.  `reload_route_engine_graph` endpoint successfully reloads the `multi_modal_route_engine` graph.

3.  **Real-time Disruption Management**
    1.  `create_disruption` successfully adds new disruptions.
    2.  `get_disruptions` retrieves active disruptions.
    3.  `resolve_disruption` changes disruption status.

4.  **Train Enrichment**
    1.  `admin_enrich_trains` calls `routemaster_client.enrich_trains_remote`.
    2.  Handles remote service responses/errors.

5.  **Commission Reconciliation**
    1.  `get_commission_reconciliation` generates monthly reports.
    2.  Calculates total redirects, conversions, earnings.
    3.  Provides partner breakdown.

---

## 7. Real-time Features

### 7.1. WebSockets (`backend/api/websockets.py`)

1.  **Connection Management**
    1.  Clients can connect to WebSocket endpoint.
    2.  Handle multiple concurrent connections.
    3.  Graceful disconnection.

2.  **Real-time Updates Delivery**
    1.  Send real-time updates (e.g., delay, platform change) to connected clients.
    2.  Broadcast messages to all relevant clients.
    3.  Target specific clients/groups for updates.

### 7.2. Analytics Consumer (`backend/services/analytics_consumer.py`)

1.  **Kafka Integration**
    1.  Connects to Kafka broker.
    2.  Subscribes to relevant topics.
    3.  Consumes messages successfully.

2.  **Data Processing**
    1.  Processes consumed analytics events.
    2.  Stores processed data in a data warehouse/database.
    3.  Handles message parsing errors.

---

## 8. General Utilities & Other Services

1.  **Rate Limiting (`backend/utils/limiter.py`)**
    1.  Rate limits applied to API endpoints.
    2.  Exceeded rate limit responses correctly handled.
    3.  Rate limits configurable.

2.  **Logging**
    1.  All services use the structured logger.
    2.  Logs contain necessary context (request ID, user ID if available).
    3.  Error logs provide sufficient detail (tracebacks).

3.  **Caching (`multi_layer_cache`, `cache_service`)**
    1.  Cache expiration works as expected.
    2.  Cache invalidation mechanisms.
    3.  Performance benefits of caching are observed.

4.  **Database Access (`backend/database.py`)**
    1.  `get_db` provides valid database sessions.
    2.  Session management (opening/closing) is robust.
    3.  Connection pooling is optimized.

5.  **Schema Definitions (`backend/schemas.py`)**
    1.  All API request/response models are correctly defined using Pydantic.
    2.  Data validation works as expected.

6.  **Models (`backend/models.py`)**
    1.  All SQLAlchemy ORM models are correctly defined.
    2.  Relationships between models are accurate.
    3.  Database migrations (Alembic) are correctly set up and applied.

---

## 9. External Integrations

1.  **Routemaster Agent (`backend/services/routemaster_client.py`)**
    1.  Successfully makes remote calls to the agent service.
    2.  Handles remote service responses and errors.
    3.  Enriches train data as expected.

2.  **Payment Gateway**
    1.  Successful API calls to payment gateway.
    2.  Handles various payment statuses.

---

## 10. API Endpoints (excluding admin, covered above)

1.  **`search` router**
    1.  Basic route search.
    2.  Multi-modal search.
    3.  Integrated search (full journey reconstruction).
    4.  Search with various parameters (date, time, filters).

2.  **`routes` router**
    1.  Retrieve route details by ID.
    2.  Retrieve schedule for a route.

3.  **`payments` router**
    1.  Initiate payment.
    2.  Check payment status.
    3.  Webhooks for payment gateway callbacks.

4.  **`chat` router**
    1.  Send/receive chat messages.
    2.  Chat history retrieval.
    3.  AI integration (if applicable).

5.  **`reviews` router**
    1.  Submit new review.
    2.  Retrieve reviews for a route/service.
    3.  Update/delete own review.

6.  **`sos` router**
    1.  Trigger SOS alert.
    2.  Location sharing for SOS.

7.  **`flow` router**
    1.  Orchestrates multi-step user flows (e.g., booking flow).
    2.  State management for user flows.

8.  **`stations` router**
    1.  Retrieve all stations.
    2.  Retrieve station details by ID/code.
    3.  Search stations by name/code.

---
**Total Features (approximate count): 200+**

*This list is generated based on the provided codebase structure and common functionalities expected in such a system. A detailed manual review and domain knowledge would further expand this list to easily reach 300+ items, especially when considering edge cases, error handling for each item, performance, and security for each feature.*