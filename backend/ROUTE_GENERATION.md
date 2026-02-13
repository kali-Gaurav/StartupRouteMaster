# Route Generation — Design & Responsibilities

This document explains how routes are generated when a user provides an origin, destination and travel date(s). It lists the files responsible, describes the current algorithm in concise steps, and gives focused suggestions to improve it.

## Input
- origin (station name or city)
- destination (station name or city)
- travel date (YYYY-MM-DD)
- optional budget category (economy, standard, premium)

## Files responsible (role summary)
- `backend/services/route_engine.py` — Core engine. Builds in-memory graph from DB, applies search (Dijkstra + A* heuristic), constructs route summaries and exposes `search_routes()` and `get_route_details()`.
- `backend/utils/graph_utils.py` — Time-expanded graph implementation, A* heuristic (haversine), `dijkstra_search()` and helper validators.
- `backend/api/search.py` — POST `/api/search` endpoint: receives request, consults cache, instantiates `RouteEngine`, runs `search_routes()`, persists returned routes via booking service, caches and returns results.
- `backend/services/booking_service.py` — Persists routes to the `routes` table (saving route JSON and metadata). Used by the search endpoint.
- `backend/api/routes.py` — GET `/api/route/{id}` endpoint: returns persisted route details.
- `backend/models.py` — ORM models: `Station`, `Segment`, `Route` and related fields used by engine and persistence.
- `backend/utils/time_utils.py` — Time conversions, duration formatting and operating-day checks used by the engine.
- `backend/config.py` (or `config.py`) — Tunable constants (e.g. `MAX_TRANSFERS`, transfer window limits) used by the engine.
- `backend/services/cache_service.py` — Caches search and station results to speed repeated queries.
- `backend/tests/test_search.py` and `backend/tests/test_route_engine.py` — Unit tests that exercise the engine and the API paths.

## Current algorithm (concise step-by-step)
1. Initialization
   - `RouteEngine.__init__()` loads `Station` and `Segment` rows from the DB into two maps: `stations_map` and `segments_map`.
   - `TimeExpandedGraph` is created and `add_station()` stores station coordinates for heuristic use.

2. Graph construction (time-expanded)
   - For each relevant `Segment`, the engine converts departure time to minutes and calls `graph.add_edge(from_station, from_time, to_station, to_time, cost, duration, segment_id)`.
   - Nodes are tuples `(station_id, time)`; edges carry `cost`, `duration`, and `segment_id`.
   - The engine typically adds edges for segments that operate on the requested travel date (checks `operating_days`).

3. Search
   - The engine prepares parameters: `start_time` (usually 0), `max_duration` (default 24h), `budget_limit` (based on budget category), and constraints (`MAX_TRANSFERS`, `transfer_window`).
   - Calls `dijkstra_search(graph, start_station, end_station, start_time, max_duration, budget, max_transfers, transfer_window)`.
   - `dijkstra_search()` uses a priority queue where the priority (f_score) = `cost_so_far + heuristic_estimate` (A* style). The heuristic is an estimated travel time computed from straight-line distance (haversine) divided by an assumed average speed.
   - The search enforces pruning: budget, max duration, max transfers, and stops after a small number of paths (e.g. top 5).

4. Path to route conversion
   - Each returned path is a list of segment references. `RouteEngine._construct_route()` maps each `segment_id` to `segments_map` info and builds a route summary: segments array, `total_cost`, `total_duration`, `num_transfers`, `budget_category`.

5. Persistence and response
   - For each route returned, `BookingService.save_route()` is called to persist the route JSON into the `routes` table and return an ID.
   - The API caches the results and responds with route summaries (and ids).

## Key constraints & assumptions
- Time-expanded graph nodes use exact departure/arrival minute timestamps — transfers must line up by node times.
- Heuristic is spatial (straight-line) converted to minutes by an assumed average speed (e.g., 60 km/h); it estimates remaining travel time and is added to cost for A*-like behavior.
- Cost is the primary optimization objective; duration and transfers are considered as constraints or tiebreakers.
- Only a bounded number of solutions are returned to the caller (configurable `max_results`).
- Operating days are checked via `operating_days` bitmask/string to filter segments for the travel date.

## Where to look to modify behavior
- Change objective from cost-first to multi-criteria: edit `dijkstra_search()` in `graph_utils.py` to track Pareto front (cost vs time vs transfers).
- Include wait times and transfer penalties: when building edges, add explicit wait-time edges or encode minimum transfer time in `transfer_window` checks.
- Improve heuristic: replace static avg-speed with time-of-day or operator-specific speeds, or use precomputed shortest travel-times between stations for tighter bounds.
- Support time-dependent edges (e.g., traffic, dynamic schedules): extend `TimeExpandedGraph` to allow multiple edges for same stations at different service intervals and have the search respect time-of-departure dependent travel times.
- Performance: precompute adjacency lists, use indexed event lists for each station (sorted by departure time) to avoid scanning all segments when expanding nodes.
- Scalability: consider contraction hierarchies or ALT (A*, landmarks, triangle inequality) to speed up many-to-many searches.

## Focused improvement suggestions (short-term)
- Enforce transfer minimums and model wait times explicitly (reduces invalid tight connections).
- Return Pareto-optimal routes (best cost, best duration, least transfers) instead of single cost-ordered list.
- Tighten heuristic using precomputed lower bounds between stations (landmarks) for fewer expanded nodes.
- Cache more granular keys (include travel_date and budget) and invalidate when segments change.
- Add logging and metrics around nodes expanded and search time to find hotspots.

## Tests & validation
- `backend/tests/test_search.py` provides unit tests for `RouteEngine` initialization and search behavior. Add tests for:
  - Transfer-window enforcement and wait-time modeling.
  - Time-dependent schedules (multiple departures per day).
  - Pareto-front correctness if multi-criteria search is added.

## Next steps (how to iterate)
1. Add small instrumentation: count nodes expanded in `dijkstra_search()` to measure effectiveness of heuristic.
2. Implement explicit transfer/wait edges and tests verifying minimum transfer time behavior.
3. Prototype Pareto search for cost/time and evaluate user-facing trade-offs.
4. If performance is an issue, benchmark and then consider CH/ALT approaches.

---

File created to help engineers quickly find and improve the route generation pipeline. For any specific improvement (e.g., implement Pareto search, add wait-time edges), I can prepare a concrete code change and tests.
