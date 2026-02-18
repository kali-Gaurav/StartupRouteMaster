Based on an analysis of the RouteMaster repository and your current architectural plans, here are the 30 most critical bottlenecks categorized by their impact on production, along with their high-performance solutions.

🚄 Routing Engine & Data Bottlenecks
Dijkstra Complexity on Time-Expanded Graphs: As the network grows, Dijkstra's search space becomes massive, slowing down multi-modal queries.
Status: COMPLETED. Replaced with RAPTOR algorithm and removed Dijkstra implementation.
Solution: Transition to the RAPTOR algorithm for transit segments; it is specifically optimized for "rounds" of transfers rather than node-by-node exploration.

Synchronous External API Calls: Waiting for real-time railway or flight APIs during a primary search will block the user experience.
Status: COMPLETED. `search_routes` now returns initial results without real-time unlock data. Real-time unlock data is fetched asynchronously when a specific route is selected via `/api/routes/{route_id}` endpoint.
Solution: Use your internal graph for the initial search and fetch real-time "unlock" details asynchronously only when a specific route is selected.

Static Data in segments Table: Your current database uses estimated durations which do not reflect real-world delays.
Status: COMPLETED. ETL pipeline modified to pull authoritative `stop_times` from `train_schedule` and `train_running_days` tables in `railway_manager.db`.
Solution: Complete the ETL pipeline to pull authoritative stop_times from railway_manager.db to ensure schedule-level accuracy.

Lack of Geo-Spatial Indexing: Standard SQL queries for "stations near me" will slow down as the station count increases.
Status: COMPLETED. PostGIS enabled in `docker-compose.yml` and `PostgresLoader`. `Station` model updated with `geom` column, populated during ETL. New `/api/search/stations/near` endpoint added using `ST_DWithin`.
Solution: Implement PostGIS on your PostgreSQL database to use ST_DWithin for lightning-fast coordinate lookups.

Graph Reload Latency: Rebuilding the entire in-memory graph on every backend restart causes significant downtime.
Status: COMPLETED. Implemented serialized graph caching using `pickle` to save/load `RouteEngine` state during startup.
Solution: Implement serialized graph caching using Pickle or Protobuf to restore the graph state in milliseconds during startup.

💰 Payment & Booking Workflow
Race Conditions in Seat Availability: Multiple users might pay for the last seat simultaneously.

Solution: Implement a Distributed Lock in Redis with a 10-minute TTL when a user enters the "Payment" phase to hold the seat.

Atomic Webhook Failures: If the Razorpay webhook fails after a successful payment, the booking remains "pending" even though the user paid.

Solution: Create a Reconciliation Worker that polls the Razorpay API every 15 minutes to sync "pending" bookings with their actual payment status.

Lack of Idempotency in Payments: Retrying a failed payment request might result in double charges.

Solution: Use the booking_id as an Idempotency Key in all payment gateway communications.

Static Pricing Logic: Your current engine sums segment costs but doesn't handle dynamic pricing or platform fees.

Solution: Implement a centralized PriceCalculationService that applies taxes, convenience fees, and real-time surges before the payment trigger.

Single Point of Failure in DB Migrations: Manual SQL updates can corrupt production data.

Solution: Use an automated migration tool like Alembic to manage schema changes across your Supabase environments.

🤖 AI Agent & Chatbot Scaling
Chatbot Prompt Injection: Malicious users could trick the AI agent into triggering SOS or free bookings.

Solution: Implement a Gateway Validator that inspects AI-generated tool calls against user permissions before execution.

High Latency in OpenRouter Responses: LLM response times can exceed 3-5 seconds.

Solution: Use Streamed Responses on the frontend to show the user the "AI is thinking" and provide text chunk-by-chunk.

Stateless AI Conversations: The chatbot often forgets the "Source" station mentioned in the previous turn.

Solution: Store conversation context in Redis Hash sets mapped to the user’s session ID to maintain short-term memory.

Unstructured AI Outputs: The chatbot might return route info in a format the frontend cannot parse.

Solution: Use Pydantic Output Parsers with the OpenRouter API to force the AI to return strictly formatted JSON.

Context Window Overflow: Long conversations can exceed the LLM's token limit, causing errors.

Solution: Implement a sliding window buffer that only sends the last 5-10 messages to the AI.

📊 Infrastructure & Monitoring
N+1 Query Problems: Fetching 10 routes and then performing 10 separate queries for station details kills performance.

Solution: Use SQL Joins or eager loading in SQLAlchemy to fetch all required route data in a single database hit.

Lack of Horizontal Scaling: A single FastAPI instance will choke at 1000 concurrent users.

Solution: Deploy using Gunicorn with Uvicorn workers behind an Nginx load balancer.

Unprotected SOS Triggers: Fake SOS alerts could overwhelm your support dashboard.

Solution: Implement Rate Limiting (via slowapi) specifically for the /api/sos endpoint.

Log Volatility: Standard print statements are lost on server crashes.

Solution: Use Structured JSON Logging (structlog) and pipe them to a centralized service like ELK or Grafana Loki.

Redis Cache Poisoning: If the database schema changes, old cached routes might crash the app.

Solution: Include a Version Prefix (e.g., v1:route:hash) in all Redis keys to allow easy cache clearing during updates.

💻 Frontend & UX Bottlenecks
Large Bundle Size: Loading all pages at once slows down the initial mobile experience.

Solution: Utilize React.lazy() and Suspense for route-based code splitting.

Unoptimized Map Rendering: Rendering 1000+ coordinates in Leaflet causes browser lag.

Solution: Use Marker Clustering and only render coordinates within the current map viewport.

Lack of Offline Support: Users lose their ticket view when entering tunnels or areas with poor signal.

Solution: Implement a Service Worker (PWA) to cache the /ticket/:id details in the browser's IndexedDB.

Prop Drilling in Booking Flow: Managing booking state across 5 modals is becoming unmaintainable.

Solution: Use a Zustand store or the existing BookingFlowContext to centralize the state machine.

Slow Image Loading: Raw PNGs (like image_e6b76b.png) slow down the landing page.

Solution: Convert assets to WebP format and use a CDN for asset delivery.

🛡️ Security & Compliance
Exposed .env Secrets: Hardcoding API keys in code or committing them to Git.

Solution: Use GitHub Secrets and a Vault provider for production environment variables.

Lack of JWT Invalidation: Users cannot "log out" of all devices if a token is stolen.

Solution: Maintain a Redis Blacklist of revoked tokens checked during the auth_required middleware.

Insecure Admin Dashboard: If the dashboard URL is guessed, revenue data is exposed.

Solution: Implement Role-Based Access Control (RBAC) and require a separate 2FA for admin routes.

CORS Misconfiguration: Allowing * (all origins) in production exposes users to CSRF attacks.

Solution: Explicitly whitelist only your production domain in the CORSMiddleware.

Unencrypted Sensitive Data: Storing phone numbers in plain text in the Users table.

Solution: Use AES-256 encryption for PII (Personally Identifiable Information) at the database level.