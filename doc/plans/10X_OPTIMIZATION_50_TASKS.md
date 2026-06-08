# 10X Optimization & Clean Architecture: 50 High-Priority Tasks

This plan outlines the steps to transform the RouteMaster backend into a highly efficient, "Tree DSA" style architecture, stripping away legacy monolith code, switching to binary-level optimizations, and integrating intelligent business pipelines.

## Phase 1: Structural Cleanup & Decoupling (Tasks 1-10)
**Goal:** Every file and folder must have a single, unambiguous responsibility.
1. **Remove Legacy Monoliths:** Delete `route_engine_MONOLITH.py.bak` and the `archive/` folder to prevent confusion and accidental imports.
2. **Consolidate Routers:** Merge `OptimizedRAPTOR`, `FastPathRouter`, `TurboRouter`, and `HybridRAPTOR` into a single `UnifiedRoutingOrchestrator` that delegates based on search complexity.
3. **Decouple Business Logic:** Move all remaining hardcoded rules (pantry bonuses, night penalties, GN compromises) completely out of the routing loop and into `RouteScorer`.
4. **Isolate Constraints:** Create a dedicated `constraints_engine.py` to pre-process user requests (like "Confirmed Only") before they hit the search algorithms.
5. **Clean Data Structures:** Ensure `backend/core/data_structures.py` is the absolute single source of truth; remove redundant duplicates in sub-folders.
6. **API Layer Separation:** Ensure the FastAPI endpoints (`api/`) strictly handle HTTP and authentication, delegating all logic to `services/`.
7. **Database Session Management:** Standardize the dual-database (`transit_graph.db` vs `user_store.db`) dependency injection in FastAPI.
8. **Dependency Audit:** Remove unused imports and libraries from `requirements.txt` to reduce memory footprint.
9. **Logger Standardization:** Implement a structured JSON logger for the routing engine to easily trace the exact path of a search query without flooding stdout.
10. **Test Coverage Verification:** Ensure core graph building and basic routing have unit tests before moving to binary optimizations.

## Phase 2: Binary & Data Structure Optimization (Tasks 11-20)
**Goal:** 10X performance by moving from JSON parsing to memory-mapped binary lookups.
11. **Convert JSON to Binary:** Refactor `station_transit_index` to use `struct.pack` for storing times and sequences as 4-byte integers instead of JSON strings.
12. **Implement Bitmask Filtering:** Use 64-bit integers for `train_running_days` to allow instant `(mask & day_bit) > 0` filtering during BFS.
13. **Memory Mapped SQLite:** Enable PRAGMA `mmap_size = 2147483648` (2GB) on `transit_graph.db` in production for near-RAM speed lookups.
14. **City Cluster Adjacency:** Pre-calculate and store connected components for multi-station cities (e.g., all Delhi stations) using integer arrays.
15. **Pre-compute Transfer Graph:** Convert the dynamic transfer logic into a static, pre-loaded adjacency list loaded into RAM on startup.
16. **Numpy Vectorization:** Use `numpy` arrays for distance calculations (Haversine) during the dominance filtering phase.
17. **Prune Invalid Trips:** Remove trips with `< 2` stops or missing geometries from the in-memory graph to save cycles.
18. **Index Hub Connectivity:** Build a dense `hub_transit_index` that acts as a Tier 0 lookup table for direct connections between major junctions.
19. **Cache Warming Script:** Create a background worker that pre-loads the top 100 most searched routes into Redis every morning.
20. **Zero-Copy Serialization:** Optimize the conversion from the internal `Route` object to the FastAPI JSON response to avoid unnecessary dict allocations.

## Phase 3: Live Data & RapidAPI Integration (Tasks 21-30)
**Goal:** Ensure 100% accuracy with live data while minimizing costly API calls.
21. **RapidAPI Seat Integration:** Finalize `verify_seat_availability_unified` to fetch real-time data for "Confirmed Only" requests.
22. **RapidAPI Fare Integration:** Connect the live fare endpoint to replace the 1500.0 fallback logic.
23. **Aggressive Redis Caching:** Implement a 15-minute TTL for all RapidAPI seat and fare responses to prevent rate-limit exhaustion.
24. **Batch API Requests:** If RapidAPI supports it, batch station schedule lookups rather than querying per train.
25. **Fallback Synchronization:** Ensure that if RapidAPI fails, the system smoothly falls back to the database without throwing a 500 error.
26. **Quota-Specific Searching:** Thread the `QuotaType` (GN, TATKAL) through the constraint engine so the API checks the correct availability.
27. **Predictive Availability:** Integrate the ML heuristic model to rank routes based on the *probability* of confirmation before spending API calls verifying them.
28. **Live Delay Adjustments:** Fetch live running status and inject a dynamic buffer into transfer calculations.
29. **API Health Monitoring:** Track RapidAPI latency and success rates; auto-disable the integration if it times out consistently.
30. **Mock Removal:** Scrub the codebase of any remaining `generate_mock_timetable` scripts in the production execution path.

## Phase 4: Route Categorization & Intelligent UI (Tasks 31-40)
**Goal:** Present routes cleanly based on user intent (Confirmed, Fastest, Cheapest).
31. **Categorization Engine:** Build a post-processing layer that groups the top 50 routes into buckets (e.g., "Confirmed Seats", "Shortest Layover").
32. **Top 3 Highlighting:** Implement logic to flag the absolute best 3 routes overall based on the user's Persona score.
33. **Dominance Filtering Tuning:** Tweak the Pareto optimality checks to ensure a fast but slightly more expensive route isn't hidden by a slower, cheaper one.
34. **Metadata Enrichment:** Ensure the `Route` object passes down exact reasons for its score (e.g., "Pantry Car Available", "High Survival Chance") for the UI to display.
35. **Alternative Suggestions:** If no confirmed seats exist, automatically suggest the same route +/- 1 day.
36. **Risk Zone Warnings:** Flag routes that pass through known delayed corridors in the response payload.
37. **Platform Number Tracking:** Extract and pass platform numbers from the database to improve transfer instructions.
38. **Waitlist Probability:** Display the ML-generated waitlist clearance probability on the UI for RAC/WL tickets.
39. **Accessibility Flags:** Ensure routes with short transfers are penalized heavily for Senior/Disabled passenger personas.
40. **Pagination:** Implement offset/limit parameters in the search endpoint to handle large result sets without freezing the client.

## Phase 5: 2-Tier Monetization & Booking Flow (Tasks 41-50)
**Goal:** Implement the "View Only" vs "Agent Booking" payment structure.
41. **Locking Mechanism:** Return route responses with sensitive details (Train Name, PNR, exact times) masked or `is_locked=True` by default.
42. **Tier 1 - Route Unlock (₹49):** Create an endpoint `/api/v2/payment/unlock` that processes a ₹49 fee and returns the unmasked `route_id`.
43. **Tier 2 - Agent Booking (Fare + ₹49 + ₹10):** Create an endpoint `/api/v2/payment/agent-booking` that calculates the total escrow amount.
44. **Dynamic Escrow Calculation:** Ensure the payment service correctly sums `Ticket Fare + 49 (Platform) + 10 (Agent)`.
45. **Escrow Status Tracking:** Update the `bookings` table to handle the transition from `CREATED` -> `UTR_SUBMITTED` -> `VERIFIED`.
46. **Route ID Persistence:** Save the exact searched route to `user_store.db` under a specific `route_id` so it can be retrieved post-payment without re-searching.
47. **Payment Session Expiry:** Implement a 10-minute timer on `PaymentSession` to release blocked inventory/routes if the user abandons checkout.
48. **Refund Pipeline Updates:** Ensure that if an Agent Booking fails, the ₹10 fee and Ticket Fare are refunded, but the ₹49 unlock fee is retained.
49. **Commission Tracking:** Log the ₹10 agent fee in the `commission_tracking` table for financial reporting.
50. **End-to-End Stress Test:** Simulate 100 concurrent users searching, unlocking, and booking to verify database transaction locks and caching logic.
