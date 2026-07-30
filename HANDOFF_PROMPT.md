# NeuralForge Team — Session Handoff Prompt
**Date:** June 4, 2026  
**Project:** Route Master — Indian Railway Multi-Segment Route Optimizer  
**Founder:** Gaurav Nagar (anthonynagar1122@gmail.com)  
**Workspace:** `C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\`

---

## MISSION BRIEFING FOR NEW SESSION

You are the NeuralForge AI engineering team. The founder (Gaurav) has approved full execution. Your job is to build a completely working fullstack website — backend + frontend — and not stop until it is functional. No planning conversations. Execute immediately.

**The product:** A user types Station A → Station B + date → sees ALL possible train routes (direct + 1-transfer + 2-transfer) with live delays, ranked by time/cost/reliability, with one-click IRCTC booking redirect. That is the entire core product.

---

## WHAT HAS ALREADY BEEN DONE (DO NOT REDO)

### Architecture decisions (locked)
- Single FastAPI monolith (no microservices)
- One API version: `/api/v1/`
- GTFS database schema in Supabase
- Redis (Upstash) for caching
- RapidAPI for live train status (7000 free calls/month)
- IRCTC redirect (no native booking)
- Vercel (frontend) + Render.com (backend)

### Files already written/fixed
| File | Status | What was done |
|---|---|---|
| `backend/app.py` | ✅ Rewritten | 100-line clean FastAPI. No Nexus. Simple lifespan. |
| `backend/requirements.txt` | ✅ Rewritten | 23 clean packages. No ML/Kafka. |
| `backend/core/route_engine/data_provider.py` | ✅ Rewritten | Full GTFS-compatible. Queries stops→trips→stop_times. |
| `backend/api/search/irctc.py` | ✅ Created | Builds pre-filled IRCTC booking URLs. |
| `backend/core/routing/__init__.py` | ✅ Fixed | Per-group try/except, critical routes always register. |
| `backend/.env` | ✅ Updated | Added USE_SIMPLE_LIFESPAN=true, ALLOW_DEGRADED_BOOT=true |
| `backend/core/middleware/cors.py` | ✅ Fixed | Vercel + custom domain support |
| `backend/test_system.py` | ✅ Created | Diagnostic script (DB, Redis, RapidAPI, route query) |
| `frontend/.env.production` | ✅ Created | Has VITE_API_URL placeholder for Render backend |
| `frontend/vercel.json` | ✅ Updated | SPA routing rules |
| `render.yaml` | ✅ Created | One-click Render.com deploy config |

### Archived (in `backend/_archived/`, intentional — do not touch)
`cat/`, `core/nexus/`, `services/agents/`, `services/finance/`, `services/intelligence/`, `services/orchestration/`, `core/sovereign/`, `guardian_ai/`, `services/realtime_ingestion/`, `services/synthetic_data/`

### Deleted (intentional — do not recreate)
`api/v2/`, `api/v3/`, `microservices/`, `infrastructure/terraform/`, `scratch/`, `api/deprecated/`, `services/deprecated/`

---

## WHERE WE STOPPED — EXECUTE FROM HERE

The previous session was cut off while creating `backend/api/v1/`. **This is the exact next step.** Build the following files in order.

---

## TASK 1 — SIGMA: Build `backend/api/v1/` (MOST CRITICAL)

The frontend currently calls `/api/v3/search/unified` (deleted). You must build clean replacement endpoints at `/api/v1/`.

### CRITICAL: Response format the frontend expects

The frontend `mapBackendRoutesToRoutes()` function in `frontend/src/services/railwayBackApi.ts` expects this exact JSON structure:

```json
{
  "source": "NDLS",
  "destination": "BCT",
  "stations": {
    "NDLS": { "code": "NDLS", "name": "New Delhi", "city": "Delhi" },
    "BCT": { "code": "BCT", "name": "Mumbai Central", "city": "Mumbai" }
  },
  "data": {
    "journeys": [
      {
        "journey_id": "uuid-here",
        "num_transfers": 0,
        "departure_time": "16:25",
        "arrival_time": "08:15",
        "total_duration": 955,
        "total_cost": 1395,
        "total_distance": 1384,
        "reliability_badge": "green",
        "is_locked": false,
        "legs": [
          {
            "train_number": "12951",
            "train_name": "Mumbai Rajdhani",
            "from_station_code": "NDLS",
            "to_station_code": "BCT",
            "departure_time": "16:25",
            "arrival_time": "08:15",
            "duration_minutes": 955,
            "fare": 1395,
            "distance": 1384
          }
        ],
        "metadata": {
          "irctc_url": "https://www.irctc.co.in/nget/train-search?fromStn=NDLS&toStn=BCT&..."
        }
      }
    ],
    "grouped_journeys": {
      "top_3_confirmed_fastest": [],
      "top_10_fastest_total": [],
      "top_5_optimal": [],
      "direct": [],
      "one_transfer": [],
      "two_transfer": [],
      "three_plus_transfer": [],
      "alternative_sorted": []
    },
    "pagination": {
      "total_results": 5,
      "current_page": 1,
      "limit": 20,
      "has_next": false,
      "total_pages": 1
    }
  }
}
```

### Files to create in `backend/api/v1/`:

**`backend/api/v1/__init__.py`** — empty

**`backend/api/v1/search.py`** — Route search  
- Method: `GET /api/v1/search/routes`
- Query params: `source`, `destination`, `date` (YYYY-MM-DD), `persona` (optional), `limit` (default 20)
- Logic:
  1. Resolve station codes using `DataProvider.find_stop()`
  2. Call `DataProvider.find_direct_trains(from_code, to_code)` → direct routes
  3. Call `DataProvider.find_hub_trains(from_code, to_code)` → 1-transfer routes
  4. Convert results to the `BackendRoutesResponse` JSON format above
  5. For each journey, generate IRCTC URL using `api.search.irctc.build_irctc_url_for_train()`
  6. Add live status from Redis cache if available (key: `live:{train_number}`)
  7. Cache full result in Redis for 5 minutes (key: `search:{from}:{to}:{date}`)
  8. Return response

Import only from:
- `from core.route_engine.data_provider import DataProvider, get_data_provider`
- `from api.search.irctc import build_irctc_url, build_irctc_url_for_train`
- `from database import get_transit_db` or `from database.infrastructure.session import SessionTransit`
- `from fastapi import APIRouter, Query, HTTPException`
- Standard library only — NO imports from `services.intelligence`, `core.sovereign`, `core.nexus`, `services.agents`

**`backend/api/v1/stations.py`** — Station autocomplete  
- Method: `GET /api/v1/stations/suggest`  
- Query params: `q` (min 2 chars), `limit` (default 10)
- Logic: try `station_search_engine.suggest(q, limit)` first, fallback to `DataProvider.search_stations(q, limit)`
- Response: `[{"code": "NDLS", "name": "New Delhi", "city": "Delhi", "state": "Delhi"}]`
- Cache in Redis 24h

**`backend/api/v1/auth.py`** — Clean email/password auth (NO Firebase, NO microservices)  
- `POST /api/v1/auth/register` — create user, hash password with bcrypt, store in `users` table
- `POST /api/v1/auth/login` — verify password, return JWT token
- `GET /api/v1/auth/me` — return current user from JWT
- JWT secret from `os.getenv("JWT_SECRET", "dev-secret-change-in-prod")`
- Use `passlib.context.CryptContext(schemes=["bcrypt"])`
- Use `jose.jwt.encode/decode` with HS256
- Import only: `fastapi`, `pydantic`, `passlib`, `jose`, `sqlalchemy`, `database`

**`backend/api/v1/live.py`** — Live train status  
- Method: `GET /api/v1/live/train/{train_number}`
- Logic:
  1. Check Redis cache first (key: `live:{train_number}`, TTL 60s)
  2. If miss → call RapidAPI: `GET https://indian-railway-irctc.p.rapidapi.com/api/trains-between-stations-v2` with header `x-rapidapi-key: {RAPIDAPI_KEY}`
  3. Parse response: extract delay_minutes, current_station, platform
  4. Cache 60s in Redis
  5. If RapidAPI fails → return `{"available": false, "delay_minutes": 0}`
- Track monthly call count in Redis (`rapidapi:calls:{YYYY-MM}`) — stop at 6800

**`backend/api/v1/pnr.py`** — PNR status  
- Method: `GET /api/v1/pnr/{pnr_number}`  
- Logic: call RapidAPI pnr-status endpoint, cache 5 min in Redis
- Returns: `{"pnr": "...", "status": "CONFIRMED", "train": "12951", "berth": "S4/45"}`

**`backend/api/v1/sos.py`** — Basic SOS (clean, no archived deps)
- `POST /api/v1/sos/trigger`
  - Body: `{ "lat": float, "lng": float, "train_no": str, "passenger_name": str }`
  - Store event in Supabase `sos_events` table (create if needed)
  - Send Twilio SMS to emergency contacts (if configured)
  - Return: `{ "event_id": "uuid", "status": "active", "tracking_url": "/track/{event_id}" }`
- `GET /api/v1/sos/{event_id}` — get event status
- `POST /api/v1/sos/{event_id}/resolve` — mark resolved
- Import: `twilio.rest.Client` (wrapped in try/except — Twilio is optional)

---

## TASK 2 — SIGMA: Update `backend/app.py`

Register the new v1 routers. Add this to the routers section:

```python
# V1 — Clean routes (always register these first, they are the product)
_include("api.v1.search",   "router", prefix="/api/v1")
_include("api.v1.stations", "router", prefix="/api/v1")
_include("api.v1.auth",     "router", prefix="/api/v1")
_include("api.v1.live",     "router", prefix="/api/v1")
_include("api.v1.pnr",      "router", prefix="/api/v1")
_include("api.v1.sos",      "router", prefix="/api/v1")
```

---

## TASK 3 — ORION: Update frontend API client

**File:** `frontend/src/services/railwayBackApi.ts`

Change the search URL from `/api/v3/search/unified` to `/api/v1/search/routes`:

```typescript
// OLD (broken — v3 was deleted):
const url = getRailwayApiUrl(`/api/v3/search/unified?${queryParams.toString()}`);

// NEW:
const url = getRailwayApiUrl(`/api/v1/search/routes?${queryParams.toString()}`);
```

Also change the method from `GET` to `GET` (same, just URL change).

The query params are already correct:
- `source`, `destination`, `date`, `persona`, `limit`

Also update station suggest URL from `/stations/suggest` to `/api/v1/stations/suggest` — check `suggestStationsApi()` function in the same file, it calls `getRailwayApiUrl('/stations/suggest?...')` — update to `/api/v1/stations/suggest?...`

---

## TASK 4 — ORION: Add "Book on IRCTC" button to RouteCard

**File:** `frontend/src/components/RouteCard.tsx`

The backend now returns `metadata.irctc_url` in each journey. Add a booking button that opens this URL:

```typescript
// In the RouteCard component, add:
const irctcUrl = route.metadata?.irctc_url;

// Button:
{irctcUrl && (
  <a 
    href={irctcUrl} 
    target="_blank" 
    rel="noopener noreferrer"
    className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
  >
    <ExternalLink size={14} />
    Book on IRCTC
  </a>
)}
```

---

## TASK 5 — NOVA: Verify route engine actually returns results

**File:** `backend/core/route_engine/data_provider.py` (already rewritten)

Test by running this in the backend:

```python
cd backend
python -c "
import asyncio, os
os.environ['DATABASE_URL'] = 'postgresql://postgres.bkzrxgtsfovctfviqkuh:kaliGaurav123@aws-1-ap-south-1.pooler.supabase.com:5432/postgres'
from core.route_engine.data_provider import DataProvider
dp = DataProvider()
stop = dp.find_stop('NDLS')
print('NDLS stop:', stop)
trains = dp.find_direct_trains('NDLS', 'BCT')
print('Direct trains found:', len(trains))
if trains:
    print('First train:', trains[0].route_id, trains[0].train_name, trains[0].departure_time)
"
```

If `find_stop('NDLS')` returns None, it means the `stops` table uses different codes. In that case, check what codes are actually in the DB:
```sql
SELECT code, name FROM stops ORDER BY is_major_junction DESC LIMIT 20;
```
And update `DataProvider.find_stop()` to use the correct column/format.

---

## TASK 6 — DAEDALUS: Deploy

After Tasks 1-5 are working locally:

**Backend → Render.com:**
1. Go to render.com → New → Web Service → Connect GitHub repo
2. Root directory: `backend`
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Set env vars: `DATABASE_URL`, `REDIS_URL`, `RAPIDAPI_KEY`, `JWT_SECRET`, `FRONTEND_URL`
6. Region: Singapore (closest to India)

**Frontend → Vercel:**
1. Go to vercel.com → New Project → Connect GitHub
2. Root directory: `frontend`
3. Set env var: `VITE_API_URL=https://your-backend.onrender.com`
4. Deploy

---

## DATABASE (GTFS schema — critical to understand)

```
stops table:
  id (int PK), code (varchar — e.g. "NDLS"), name, city, state,
  latitude, longitude, is_major_junction (bool), connectivity_score (float)

trips table:
  id (int PK), trip_id (varchar — train number), route_id (varchar — train number),
  service_id, is_cancelled (bool), delay_minutes (int)

stop_times table:
  id (int PK), trip_id (int FK→trips.id), stop_id (int FK→stops.id),
  arrival_time (TEXT "HH:MM:SS"), departure_time (TEXT),
  stop_sequence (int), arrival_timestamp (int), departure_timestamp (int)

trains_master table:
  train_number (varchar PK), train_name, source, destination,
  days_of_run (JSON), train_type

The route query:
  Find trips where stop X (from_code) appears BEFORE stop Y (to_code) in stop_times
```

---

## ENV VARS (already in `backend/.env`)

```
DATABASE_URL=postgresql://postgres.bkzrxgtsfovctfviqkuh:kaliGaurav123@aws-1-ap-south-1.pooler.supabase.com:5432/postgres
REDIS_URL=rediss://default:AZiZAAIncDIwNDdiZTY2NTNiY2Q0NTIyOTZiMTQ1MzlmNDRmZTVhOXAyMzkwNjU@amazed-rat-39065.upstash.io:6379
ENVIRONMENT=development
USE_SIMPLE_LIFESPAN=true
ALLOW_DEGRADED_BOOT=true
TELEGRAM_BOT_TOKEN=8263758262:AAEHCUddJ0LBBB6jvdNuuJ8DyN0gBGRSEsg
```

**Missing (Gaurav needs to add to .env):**
```
RAPIDAPI_KEY=<get from rapidapi.com — free 7000 calls/month>
JWT_SECRET=<generate a random 32-char string>
TWILIO_ACCOUNT_SID=<optional, for SOS SMS>
TWILIO_AUTH_TOKEN=<optional>
TWILIO_FROM_NUMBER=<optional>
```

---

## AGENT TEAM ASSIGNMENTS

| Agent | Role | Current Task |
|-------|------|--------------|
| SIGMA | Backend Python/FastAPI | Tasks 1 + 2 — build api/v1/ files |
| ORION | Frontend React/TypeScript | Tasks 3 + 4 — fix API URL + IRCTC button |
| NOVA | Route Engine | Task 5 — verify DB query works |
| VAULT | Database | Support NOVA — fix any schema issues |
| DAEDALUS | Infra/Deploy | Task 6 — deploy to Render + Vercel |
| CIPHER | Security | Review auth.py — ensure no security holes |
| MARCO | Product | Not blocking — observe |
| FELIX | CFO | Track RapidAPI quota in Redis |

---

## PHASE STATUS

```
Phase 0 (Fix backend) ──── ✅ DONE
Phase 1 (Core search live)─ 🔄 IN PROGRESS ← YOU ARE HERE
  ✅ data_provider.py rewritten
  ✅ IRCTC URL builder built
  ⏳ api/v1/ files — NEXT TASK
  ⏳ Frontend URL update
  ⏳ Local test
  ⏳ Deploy
Phase 2 (Auth + PNR) ────── Pending
Phase 3 (SOS live) ───────── Pending
Phase 4 (Chatbot/Telegram) ─ Future
```

---

## SUCCESS CRITERIA (launch criteria)

- [ ] `GET /health` returns 200 from Render URL
- [ ] `GET /api/v1/stations/suggest?q=del` returns Delhi stations
- [ ] `GET /api/v1/search/routes?source=NDLS&destination=BCT&date=2026-06-10` returns ≥1 route
- [ ] Each route has a valid `irctc_url` in metadata
- [ ] Frontend loads on Vercel, search form works, results display
- [ ] "Book on IRCTC" button opens pre-filled IRCTC search
- [ ] No console errors in browser

---

## HOW TO START

1. Read this entire document first
2. Run `cd backend && python test_system.py` to see current state
3. Start with SIGMA building `backend/api/v1/search.py`
4. Do not stop until all success criteria above are met
5. After each file is written, update agent logs in `.agent/logs/YYYY-MM-DD.json`

**[NEXUS]** Full approval granted by founder. Build everything. Ship it.
