# DOW — Detailed Operational Workflow & Algorithms (RouteMaster)

> Purpose: a single, readable reference so any developer or engineer can understand how the system works end‑to‑end — frontend, backend, database, algorithms, caching, and the chatbot.

---

## Table of contents
1. Overview (system components)
2. End-to-end request flows
   - Route search (UI → API → engine → DB)
   - Station autocomplete
   - Chatbot-driven search
3. Data models and in‑memory structures
4. Route generation algorithm (detailed)
   - Graph model
   - Date-aware Dijkstra + A* (pseudocode & complexity)
   - Transfer handling, pruning, budget filtering, and route construction
5. Filtering — server vs client responsibilities
6. Caching and performance tuning
7. Chatbot: NLU, entity extraction & session flow
8. Examples (request / response & chat flow)
9. How to run & test locally
10. Known limitations & next improvements
11. Where to read code (file map)

---

## 1 — Overview (components)
- Frontend: React + TypeScript UI that calls backend APIs and applies client-side filters/sorting.
  - Key: `src/pages/Index.tsx`, `src/components/RailAssistantChatbot.tsx`
- Backend: FastAPI application exposing endpoints for search, routes, chat, bookings, payments.
  - Key: `backend/api/search.py`, `backend/services/route_engine.py`, `backend/utils/graph_utils.py`, `backend/api/chat.py`
- Database: PostgreSQL (models in `backend/models.py`) storing stations, segments, vehicles, saved routes, bookings.
- Cache: Redis (via `backend/services/cache_service.py`) for session and result caching.

Goal: sub-100ms typical route searches using an in‑memory, time‑aware graph + caching.

---

## 2 — End-to-end flows

### 2.1 Route search (user → routes)
1. User triggers search in UI (manual form or via chatbot). Frontend calls `searchRoutesApi()` → POST `/api/search`.
2. Backend `search_routes_endpoint` uses the singleton `route_engine` to search:
   - If graph not loaded → server logs error (graph is loaded on startup by `app.on_event("startup")`).
   - Query is hashed (MD5) and cache_service is checked.
3. If cache miss, `RouteEngine.search_routes()` runs the in-memory search (`dijkstra_search`) over `TimeExpandedGraph`.
4. Matching paths are converted into route objects and filtered (budget, transfers).
5. Results are cached (key = md5(query)) and returned to frontend.
6. Frontend maps backend schema → UI `Route` model (`mapBackendRoutesToRoutes`) and applies client filters / sorts.

Files: `backend/api/search.py`, `backend/services/route_engine.py`, `src/services/railwayBackApi.ts`, `src/pages/Index.tsx`.

### 2.2 Station autocomplete
- Frontend calls GET `/api/search/stations?q=...`.
- Backend queries `stations_master` using ILIKE; candidate set limited and scored by `calculate_station_score()`.
- Scoring rules: exact code/name match, prefix matches, substring matches, junction bonus (+100).
- Results cached in Redis for 1 hour.

Files: `backend/api/search.py`, DB table: `stations_master` (`StationMaster` model).

### 2.3 Chatbot-driven flow
1. Frontend sends chat message → POST `/chat` (session_id optional).
2. Backend chat endpoint stores session (Redis or local fallback) and runs rule-based NLU:
   - `get_intent_from_message()` — keyword intents (search, sort, navigate, etc.)
   - `extract_stations_from_message()` and `extract_date_from_message()` parse entities using regex and heuristics
3. If intent == search and both source+destination found, backend returns a response with `trigger_search=true` and `collected` payload (stations + optional date + correlation_id).
4. Frontend resolves station names → station codes using `searchStationsApi()` and then triggers a normal route search in the UI (keeps UX unified).

Files: `backend/api/chat.py`, `src/components/RailAssistantChatbot.tsx`, `src/lib/chatEventBus.ts`.

### 2.4 Sequence diagram (overview)
Below is a compact sequence diagram (Mermaid) showing the common search + chatbot path:

```mermaid
sequenceDiagram
  actor User
  participant Frontend
  participant ChatUI as "Chat UI"
  participant Backend
  participant RouteEngine
  participant Cache as "Redis Cache"
  participant DB
  User->>Frontend: Enter origin/destination/date (or tap chatbot quick action)
  Frontend->>Backend: POST /api/search {source,destination,date,...}
  Backend->>Cache: GET route:{md5(query)}
  alt cache hit
    Cache-->>Backend: routes JSON
    Backend-->>Frontend: 200 OK {routes}
  else cache miss
    Backend->>RouteEngine: search_routes(...)
    RouteEngine->>DB: (segments/stations loaded at startup)
    RouteEngine-->>Backend: matching paths
    Backend->>Cache: SET route:{md5} = routes (TTL)
    Backend-->>Frontend: 200 OK {routes}
  end
  note over Frontend,Backend: Frontend maps response → UI models and applies client filters
  User->>ChatUI: "Find trains Delhi to Mumbai on 14-02-2026"
  ChatUI->>Backend: POST /chat {message, session_id?}
  Backend->>Backend: parse intent & entities (source, destination, date)
  alt entities resolved
    Backend-->>ChatUI: reply (trigger_search=true + collected + correlation_id)
    ChatUI->>Frontend: emit event (rail-assistant-search)
    Frontend->>Backend: POST /api/search (resolved station codes + correlation_id)
  end
```

---

## 3 — Data models & in‑memory structures
- Persistent DB models (high level):
  - `Station` / `StationMaster` — coordinates, codes, names
  - `Segment` — source, dest, departure/arrival, duration_minutes, cost, operating_days
  - `Route` (saved), `Booking`, `Payment`, `UnlockedRoute`
  - See `backend/models.py`

- In-memory structures (RouteEngine):
  - `stations_map: Dict[station_id -> metadata]` (name, coords)
  - `segments_map: Dict[segment_id -> {...}]` (departure, arrival, duration, cost, operating_days)
  - `TimeExpandedGraph.edges[from_station] = List[{ segment_id }]` — adjacency list

Graph loaded once at startup by `route_engine.load_graph_from_db(db)` (see `backend/app.py`).

---

## 4 — Route generation algorithm (detailed)
This is the heart of the system: a date-aware search over a time-expanded graph using a Dijkstra variant with an A*‑style heuristic.

### 4.1 Graph model
- Nodes: stations (station_id)
- Edges: segments leaving a station; an edge points to a `segment_id` which contains:
  - departure_time (string), arrival_time, duration (minutes), cost, operating_days, vehicle_id
- Time-expanded behavior: search tracks absolute datetimes (start_datetime + offsets) when evaluating feasible departures.

### 4.2 Algorithm summary — `dijkstra_search(...)`
- Priority queue keyed by f_score = (elapsed_time_since_search_start + heuristic_minutes)
- State stored: (f_score, cost, transfers, current_station, path_so_far, current_arrival_datetime)
- For each outgoing segment from current station:
  - Consider departures on the search date (and limited look‑ahead for transfers)
  - Skip if segment is not operating on that date (operating_days check)
  - Enforce transfer window (min / max wait) when transfers > -1
  - Compute arrival_datetime = departure_datetime + duration
  - Push new state into the PQ with updated cost, transfers, path
- Terminate when destination reached or top candidate limit reached

Pseudocode (simplified):
- PQ ← {(0, 0, -1, start_station, [], start_datetime)}
- while PQ:
  - pop state
  - if current == end: add completed path
  - if transfers >= max_transfers: prune
  - for segment in outgoing(current):
    - for day_offset in 0..day_range:
      - if not operating_on_day(segment, date + day_offset): continue
      - departure_dt = date + departure_time
      - if departure_dt < min_allowed_departure: continue
      - if wait_time > transfer_window_max: continue
      - compute arrival_dt and cost
      - compute heuristic (haversine -> minutes)
      - push (elapsed_minutes + heuristic, new_cost, new_transfers, dest_station, path + [segment], arrival_dt)

### 4.3 Heuristic (A* component)
- `TimeExpandedGraph.get_heuristic()` uses haversine distance / assumed average speed (60 km/h) to estimate remaining travel time (in minutes).
- Heuristic is admissible for time-minimization objective (simple optimistic time estimate) and reduces search branching.

### 4.4 Transfer & pruning logic
- Transfers count is tracked and compared to `Config.MAX_TRANSFERS`.
- Transfer windows: `TRANSFER_WINDOW_MIN` (minimum connection time) and `TRANSFER_WINDOW_MAX` (maximum allowed wait). Long waits are pruned for transfer legs.
- First leg is treated differently (search start time constraint).
- Paths are limited (stop after N final_paths) to bound work and response latency.

### 4.5 Route construction & budget filtering
- After paths are found, `RouteEngine._construct_route_from_path()` builds the final route object:
  - segments list with mode, from/to, departure/arrival, duration, cost
  - totals (total_cost, total_duration), safetyScore (simple heuristic), num_transfers
  - id derived from md5 of segments payload (stable-ish identifier)
- Budget categories implemented (example thresholds):
  - economy: 1000, standard: 2000, premium: 5000 (applied as max cost filter)
- Final sort typically by `total_cost` (configurable)

### 4.6 Complexity
- Worst-case: similar to multi-criteria shortest-path searches; practical runtime dominated by branching at busy nodes and `max_transfers` constraint.
- Typical complexity is O(E log V) for single-source Dijkstra; with time-expansion and day windows the effective branching increases but is controlled by pruning and transfer limits.

Files: `backend/utils/graph_utils.py`, `backend/services/route_engine.py`.

---

## 5 — Filtering: server vs client
- Server-side (during generation):
  - Max transfers, transfer windows, operating days, budget category (hard filters)
  - Server can also return pre-sorted results (sort_by param)
- Client-side (after receiving results):
  - Category, transfers filter, departure window (morning/afternoon/evening), max duration, max cost
  - Client sorts for fastest/cheapest/reliable without re-querying the backend
  - UI filtering implemented in `Index.tsx` (useMemo → `filteredRoutes` / `sortedRoutes`)

Rationale: server does heavy pruning; client gives instant interactive filtering.

---

## 6 — Caching & performance
- Cache service: Redis via `CacheService` (global `cache_service`).
- What is cached:
  - Station autocomplete results (TTL 3600s)
  - Route search results (MD5 of query as key)
  - Chat sessions (Redis with TTL from `Config.REDIS_SESSION_EXPIRY_SECONDS`)
- Cache keys & behavior:
  - Route key: `route:{md5_hash_of_query}` (engine uses `RouteEngine._get_cache_key()`)
  - Station autocomplete key: `stations_autocomplete:{q}`
- Fallbacks: if Redis unavailable, in-memory fallbacks are used for sessions and frontend local caches are used for offline UI capability.

Performance notes:
- Cached searches: < 20ms (typical)
- Uncached searches: 40–150ms depending on complexity
- Tests and CI include search unit tests (`backend/tests/test_search.py`).

---

## 7 — Chatbot internals (NLU + integration)
- Backend chat is rule-based (not ML): keyword intent detection + regex-based entity extraction.
  - `get_intent_from_message()` returns intents like `search`, `sort_cost`, `sort_duration`, `navigate_*`.
  - `extract_stations_from_message()` uses regex patterns and `CITY_STATION_MAP` for city → major station resolution; fallback to fuzzy matching.
  - `extract_date_from_message()` supports `dd-mm-yyyy`, `yyyy-mm-dd`, `tomorrow`, `today`, `next monday`, and weekday parsing.
- Session management: Redis-backed sessions (`SESSION_KEY_PREFIX = chat:session:`) or local in-memory `_local_sessions` fallback.
- When a chat response contains `trigger_search: true` with `collected` payload, frontend will resolve station names → codes and call the standard route search API (unified path).

Files: `backend/api/chat.py`, `src/components/RailAssistantChatbot.tsx`.

---

## 8 — Example flows & payloads

### 8.1 UI search example (frontend → backend)
Request (POST /api/search):
```json
{ "source": "New Delhi", "destination": "Mumbai Central", "date": "2026-02-14", "budget": "economy" }
```
Response (trimmed):
```json
{ "routes": [ { "id": "route_...", "source":"New Delhi","destination":"Mumbai Central","segments":[...], "total_cost":750, "total_duration":"12h30" } ], "message":"Search completed successfully." }
```

### 8.2 Chatbot → triggers search
- User: "Find trains from Delhi to Mumbai on 14-02-2026"
- Backend `/chat` returns: `trigger_search: true`, `collected: { source: "New Delhi", destination: "Mumbai Central", date: "2026-02-14" }`, `correlation_id`.
- Frontend resolves station codes and calls `searchRoutesApi(fromCode, toCode, {..., correlationId})`.

---

## 9 — How to run & test locally

### QuickStart — run locally (PowerShell)
1. Prepare DB and Redis
   - Create a PostgreSQL DB (example):
     ```powershell
     createdb routemaster
     ```
   - Start Redis locally or via Docker:
     ```bash
     docker run -p 6379:6379 redis:7
     ```

2. Backend (PowerShell)
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   $env:DATABASE_URL = "postgresql://user:pass@localhost/routemaster"
   $env:REDIS_URL = "redis://localhost:6379/0"
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```
   (Unix/macOS: source .venv/bin/activate && pip install -r requirements.txt && uvicorn app:app --reload)

3. Frontend (project root)
   ```bash
   pnpm install
   pnpm dev
   # or: npm install && npm run dev
   ```

4. Run tests
   ```bash
   # Backend unit tests
   cd backend
   pytest -q tests
   ```

### Quick curl examples (works from Bash / Git Bash / WSL)
- Health:
  ```bash
  curl http://localhost:8000/health
  ```

- Station autocomplete:
  ```bash
  curl "http://localhost:8000/api/search/stations?q=delhi"
  ```

- Route search:
  ```bash
  curl -X POST "http://localhost:8000/api/search" \
    -H "Content-Type: application/json" \
    -d '{"source":"New Delhi","destination":"Mumbai Central","date":"2026-02-14","budget":"economy"}'
  ```
  Expected: 200 OK, JSON with `routes` array.

- Chat (rule-based NLU):
  ```bash
  curl -X POST "http://localhost:8000/chat" \
    -H "Content-Type: application/json" \
    -d '{"message":"Find trains from Delhi to Mumbai on 14-02-2026"}'
  ```
  Expected: JSON reply; if entities were extracted the response contains `trigger_search: true` and `collected`.

Notes:
- For PowerShell use single quotes for JSON body or use Invoke-RestMethod:
  ```powershell
  Invoke-RestMethod -Uri "http://localhost:8000/api/search" -Method POST -ContentType "application/json" -Body '{"source":"NDLS","destination":"BCT","date":"2026-02-14"}'
  ```
- If backend is unavailable, frontend falls back to cached/local routes for some seeded origin/destination pairs.

Health checks:
- Backend health: GET `/health`
- Chat health: GET `/chat/health`

---

## 10 — Known limitations & suggested improvements
- Chatbot NLU is rule‑based — consider integrating an LLM or dialog manager for richer parsing.
- Time handling assumes departure times as HH:MM strings and uses day offsets; complex multi-day itineraries may need richer time-expanded nodes.
- Cost model is simplistic (segment.cost aggregation). For fare accuracy, integrate a dedicated fare engine.
- Heuristic uses a constant avg speed (60 km/h); accuracy could improve by transport-mode specific heuristics.
- Consider multi-thread-safe graph reload for live schedule updates (currently graph is loaded on startup only).

---

## 11 — Quick code map (where to look)
- Route search & engine: `backend/api/search.py`, `backend/services/route_engine.py`, `backend/utils/graph_utils.py`
- Chatbot: `backend/api/chat.py`, `src/components/RailAssistantChatbot.tsx`
- Frontend mapping & filtering: `src/services/railwayBackApi.ts`, `src/pages/Index.tsx`
- Cache: `backend/services/cache_service.py`
- Models: `backend/models.py`
- Startup & graph load: `backend/app.py`

---

## Appendix — Troubleshooting & tips
- If search returns empty but DB has routes: ensure `route_engine.load_graph_from_db()` ran (check startup logs). See `app.on_event("startup")`.
- If autocomplete slow: check Redis availability and `stations_autocomplete:*` cache keys.
- To debug transfers: enable DEBUG logs for `graph_utils.py` (search traces show considered segments and pruning reasons).

---

If you want, I can:
- add a mermaid sequence diagram to this file, or
- add a short QuickStart section showing exact commands and `curl` examples, or
- generate onboarding slides from this DOW.

Pick one and I'll add it to the file. 

---

*Generated: DOW.md — authoritative developer guide for RouteMaster.*
