# Route Master — Master Build Plan
**Last updated:** June 4, 2026  
**Status:** Execution-ready  
**Goal:** Get a real, working, live product in front of real users as fast as possible.

---

## THE MISSION (One Sentence)

> A traveller types Station A → Station B + date, and Route Master shows them every possible train route — direct and multi-transfer — with live delays, ranked by time/cost/reliability, in under 2 seconds. That's it. That's the product.

---

## WHAT WE HAVE TODAY

### ✅ Already Built (Assets we keep)
| Component | What it is | Status |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite | ✅ Built, mostly working |
| Search UI | StationSearch, RouteCard, Index page | ✅ Built |
| Backend | FastAPI + Python | ❌ BROKEN (circular imports) |
| Route Engine | RAPTOR + TurboRouter algorithms | ✅ Code exists, untested live |
| Database | Supabase (PostgreSQL) + train data | ✅ Connected |
| Redis Cache | Upstash Redis | ✅ Connected |
| RapidAPI live status | Train live status integration | ✅ Code exists |
| Booking redirect | IRCTC redirect logic | ✅ IrctcRedirect page exists |
| SOS service | Emergency safety system | ✅ Built but untested |
| Auth | Supabase Auth + JWT | ✅ Built |
| Payment | Razorpay integration | ✅ Built (Phase 2) |

### ❌ Critical Broken Issues
1. **Backend won't start** — circular import: `booking_service → inventory_service` (missing singleton)
2. **Search API untested end-to-end** — route engine exists but never run against real DB
3. **No live deployment** — frontend and backend are not deployed anywhere
4. **Over-engineered startup** — 30+ services loading at boot; most aren't needed for core search

---

## GOAL: WHAT A REAL USER MUST BE ABLE TO DO

```
1. Open the website (any device, any browser)
2. Type "Mumbai" in the FROM box → see station suggestions instantly
3. Type "Delhi" in the TO box → see station suggestions
4. Pick a date
5. Click Search
6. See 3–8 route options in under 3 seconds:
   - Each shows: train name(s), departure → arrival, total duration, estimated fare, class availability
   - Live delay status pulled from RapidAPI (if available)
   - Route type: Direct / 1 Transfer / 2 Transfers
   - Sort by: Fastest | Cheapest | Most Reliable
7. Click any route → "Book on IRCTC" button opens IRCTC pre-filled for that train
```

That is the ENTIRE core product. Everything else is secondary.

---

## PHASE STRUCTURE

```
PHASE 0 ── Fix backend startup            [1–2 days]   ← DO THIS FIRST
PHASE 1 ── Core search works live         [3–5 days]   ← PRODUCT VALUE
PHASE 2 ── Users + saved searches         [3–5 days]   ← RETENTION
PHASE 3 ── SOS safety live                [2–3 days]   ← DIFFERENTIATION
PHASE 4 ── Chatbot / Telegram / ML        [future]     ← GROWTH
```

---

## PHASE 0 — FIX BACKEND STARTUP
**Goal:** `python app.py` starts without errors. Health check returns 200.

### Task 0.1 — Fix circular import chain
**File:** `backend/services/booking_service.py`  
**Problem:** Line 23 imports `inventory_service` as a singleton — but that singleton was removed.  
**Fix:**
```python
# REMOVE this:
from services.inventory_service import inventory_service

# REPLACE with factory pattern (consistent with how inventory_service was refactored):
from services.inventory_service import get_inventory_service
```
Also fix `pricing_service` and `notification_service` imports in `booking_service.py` to use factory pattern, not singleton.

### Task 0.2 — Slim the startup
**Problem:** `app.py` loads 30+ services at boot including Kafka, fraud detection, ML models. Most aren't needed for search.  
**Fix:** Move everything non-critical to lazy loading. Boot order:
1. Database connection (Supabase) ✅
2. Redis connection (Upstash) ✅
3. Route engine init ✅
4. Station search index ✅
5. API routes ✅
6. Everything else → lazy on first call

### Task 0.3 — Verify health endpoint
`GET /health` must return:
```json
{ "status": "ok", "db": "connected", "redis": "connected", "version": "1.0.0" }
```

### Task 0.4 — Run search API manually
Test end-to-end via curl or Postman:
```bash
POST /api/v1/search
{ "from": "NDLS", "to": "MMCT", "date": "2026-06-10", "class": "SL" }
```
Must return at least one route. Fix any errors.

---

## PHASE 1 — CORE SEARCH WORKING LIVE
**Goal:** Real user on real browser gets real train routes.

### Task 1.1 — Station autocomplete API
- `GET /api/v1/stations/search?q=mum` → returns top 10 matching stations
- Data: Use existing station DB (we have 7000+ stations)
- Cache in Redis with 24hr TTL (stations don't change)
- Frontend `StationSearch` component already calls this — just make the API work

### Task 1.2 — Route search API (core)
`POST /api/v1/search/routes`  
Input:
```json
{
  "from_station": "NDLS",
  "to_station": "MMCT",
  "date": "2026-06-10",
  "quota": "GN",
  "class_preference": "SL"
}
```
Output (per route):
```json
{
  "route_id": "...",
  "route_type": "DIRECT | 1_TRANSFER | 2_TRANSFER",
  "segments": [
    {
      "train_no": "12951",
      "train_name": "Mumbai Rajdhani",
      "from_station": "NDLS",
      "to_station": "MMCT",
      "departure": "16:25",
      "arrival": "08:15+1",
      "duration_mins": 955,
      "classes": ["1A", "2A", "3A"],
      "estimated_fare": 1200,
      "live_status": { "delay_mins": 5, "current_station": "Kota" }
    }
  ],
  "total_duration_mins": 955,
  "total_fare": 1200,
  "reliability_score": 0.87,
  "irctc_booking_url": "https://www.irctc.co.in/nget/train-search?..."
}
```

**Route discovery logic (use existing code):**
1. TurboRouter → Direct routes (fastest to compute)
2. Hub Intersection → 1-transfer routes (top 5 hubs: NDLS, MMCT, MAS, HWH, PUNE)
3. RAPTOR → 2-transfer routes (limit to 3 results)
4. Deduplicate + rank by (time × 0.4) + (cost × 0.3) + (reliability × 0.3)

**IRCTC booking URL generation:**
```
https://www.irctc.co.in/nget/train-search?
  fromStn={from_code}&toStn={to_code}&jrnyDate={date}&jrnyClass={class}&
  jrnySrc=P&returnDate=&ticketType=E
```

### Task 1.3 — Live train status (RapidAPI)
- `GET /api/v1/trains/{train_no}/live?date={date}`
- Pulls from RapidAPI (existing `RapidApiProvider` code)
- Cache in Redis for 60 seconds (protect the 7000/month free quota)
- If RapidAPI returns error/limit → return `{ "status": "unavailable" }` gracefully
- Show on route card: green "On Time" / yellow "5 min late" / red "30+ min late"

**RapidAPI quota strategy:**
- Only call live status when user explicitly views a route (not during search)
- Batch: If user searches NDLS→MMCT, fetch live status for top 3 direct trains only
- Never auto-refresh — only on user click/reload

### Task 1.4 — Frontend: Wire search to backend
The Index.tsx already calls `searchRoutesApi` from `railwayBackApi.ts`. Verify:
1. API base URL is set correctly (env var `VITE_RAILWAY_API_URL`)
2. `mapBackendRoutesToRoutes` correctly maps new response format
3. RouteCard shows: train names, departure/arrival, duration, fare, live status badge
4. "Book on IRCTC" button opens `irctc_booking_url` in new tab

### Task 1.5 — Deploy: Frontend + Backend live
**Frontend → Vercel (free)**
- Connect GitHub repo
- Set env var: `VITE_RAILWAY_API_URL=https://your-backend.onrender.com`
- Auto-deploys on every push

**Backend → Render.com (free tier)**
- Create Web Service, connect repo, root dir = `backend/`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Set env vars: DATABASE_URL, REDIS_URL, RAPIDAPI_KEY
- Free tier: 512MB RAM, sleeps after 15min inactivity (upgrade if needed)

**OR Backend → Railway.app ($5/mo)**
- Better cold start, stays alive 24/7
- Recommended once we have real users

---

## PHASE 2 — USER ACCOUNTS & SAVED SEARCHES
**Goal:** Users can log in, save their routes, and check PNR status.

### What to build:
1. **Login/Signup** — Supabase Auth (email+password + Google OAuth). Auth pages already exist in frontend (`/auth/login`, `/auth/signup`). Just wire to Supabase client.
2. **Saved searches** — After search, logged-in user sees "Save this route" button. Stored in Supabase `user_saved_routes` table.
3. **Search history** — Last 10 searches stored locally + synced to DB for logged-in users.
4. **PNR status checker** — `GET /api/v1/pnr/{pnr}` → calls RapidAPI `pnr-status` endpoint → shows booking status, berth number, coach.
5. **Train schedule page** — `GET /api/v1/trains/{train_no}/schedule` → full timetable from DB.

### What NOT to build yet:
- Native booking (requires IRCTC partnership/API license — not worth now)
- Payment processing (not needed if redirecting to IRCTC)
- Seat inventory management (IRCTC handles this)

---

## PHASE 3 — SOS SAFETY FEATURE
**Goal:** A live user on a train can trigger SOS, share location, and alert emergency contacts.

### What to build:
1. **SOS button** — Already exists in frontend (`SOSWidget` component). Wire to backend.
2. **Emergency contacts** — User stores up to 3 contacts (name + phone). Stored in Supabase.
3. **SOS trigger** — `POST /api/v1/sos/trigger` → sends SMS to all emergency contacts via Twilio (or WhatsApp)
4. **Location sharing** — Browser GPS → WebSocket → backend → share link with contacts
5. **Responder dashboard** — `/responder` page already exists. Contact opens link, sees live location on map.

### SOS flow:
```
User presses SOS button
  → Frontend gets GPS coordinates
  → POST /api/v1/sos/trigger { location, train_no, passenger_name }
  → Backend sends SMS: "ALERT: [Name] needs help. Train [no]. Live location: routemaster.in/track/[id]"
  → Responder page shows live moving dot on map
  → User can dismiss when safe
```

**SMS provider:** Twilio (you already have Twilio skill). Free trial gives 15$ credit = ~1000 SMS.

---

## PHASE 4 — FUTURE FEATURES (build after core is proven)
These are NOT blocked — but don't start until Phase 1 is live and real users are using it.

| Feature | Why to wait |
|---|---|
| AI Chatbot (RailAssistant) | Adds cost (LLM API calls). Core search must work first. |
| Telegram Bot | Good for power users. Build after web is stable. |
| ML delay prediction (CAT model) | Need real usage data first. |
| Demand-based pricing insights | Need booking data first. |
| Mobile app (React Native) | Web first. Validate on web, then go mobile. |
| Kafka event streaming | Overkill until 10k+ concurrent users. |
| Microservices split | Single FastAPI app is fine until 50k users/month. |

---

## TECH STACK (Confirmed, No Changes)

| Layer | Technology | Why |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind | Already built |
| Backend | FastAPI (Python 3.11) | Already built |
| Database | Supabase (PostgreSQL) | Already connected, has data |
| Cache | Upstash Redis | Already connected |
| Live Train Status | RapidAPI (Indian Railways API) | Free 7000 calls/month |
| Auth | Supabase Auth | Simplest, already integrated |
| SMS (SOS) | Twilio | Free trial, easy |
| Frontend Hosting | Vercel | Free, instant deploy |
| Backend Hosting | Render.com / Railway.app | Free / $5/mo |
| Payments (future) | Razorpay | Already integrated (Phase 2+) |

**What we DO NOT add:**
- Kafka (overkill — use PostgreSQL LISTEN/NOTIFY or simple job queue for now)
- Kubernetes (overkill — single Docker container is fine)
- ML serving infrastructure (use simple Python functions in-process)
- Multiple databases (Supabase handles everything)

---

## DATABASE: WHAT WE NEED IN SUPABASE

### Existing tables (verify these exist):
- `stations` — station_code, name, state, zone
- `trains` — train_no, train_name, type
- `train_routes` — train_no, station_code, arrival, departure, day, distance_km
- `schedules` — actual timetable with halt times

### New tables needed (Phase 2):
```sql
-- Saved routes (Phase 2)
CREATE TABLE user_saved_routes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  from_station TEXT NOT NULL,
  to_station TEXT NOT NULL,
  route_data JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- SOS events (Phase 3)
CREATE TABLE sos_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  train_no TEXT,
  location JSONB,  -- { lat, lng, accuracy }
  status TEXT DEFAULT 'active',  -- active | resolved
  created_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

-- Emergency contacts (Phase 3)
CREATE TABLE emergency_contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  name TEXT NOT NULL,
  phone TEXT NOT NULL,
  relation TEXT
);
```

---

## API ENDPOINTS: PRIORITY LIST

### MUST BUILD (Phase 0-1, no launch without these)
```
GET  /health                           Backend health check
GET  /api/v1/stations/search?q=        Station autocomplete
POST /api/v1/search/routes             Core route search
GET  /api/v1/trains/{no}/live          Live train status (RapidAPI)
```

### BUILD NEXT (Phase 2)
```
POST /api/v1/auth/login                User login
POST /api/v1/auth/signup               User signup
GET  /api/v1/pnr/{pnr}                PNR status check
GET  /api/v1/trains/{no}/schedule      Full timetable
POST /api/v1/users/saved-routes        Save a route
GET  /api/v1/users/saved-routes        Get saved routes
```

### BUILD LATER (Phase 3)
```
POST /api/v1/sos/trigger               SOS alert
POST /api/v1/sos/contacts              Save emergency contacts
WS   /ws/sos/{event_id}               Live location streaming
```

### DO NOT BUILD YET (Phase 4+)
```
POST /api/v1/bookings                  Native booking
POST /api/v1/payments/initiate         Razorpay payment
POST /api/v1/chatbot                   AI assistant
```

---

## RAPIDAPI — SMART USAGE (Stay in Free Tier)

**Free tier:** 7,000 calls/month = ~230 calls/day  
**Paid tier:** starts at $10/month for 50,000 calls

### Strategy to stay free as long as possible:
1. **Cache aggressively:** Redis TTL 60s for live status, 5min for PNR, 24hr for schedules
2. **Only fetch on demand:** Don't prefetch live status — only fetch when user views a route
3. **Top-3 only:** For a search result showing 6 routes, only fetch live status for the top 3
4. **Skip weekday nights:** Trains run on time more often at night — skip live calls 10pm–5am
5. **Track quota:** Redis counter `rapidapi:calls:2026-06` — warn at 6000, stop at 6800

### RapidAPI endpoints to use:
- `GET /liveTrainStatus/{trainNo}/{date}` → delay, current station
- `GET /pnrStatus/{pnr}` → booking confirmation, berth
- `GET /trainSchedule/{trainNo}` → full timetable (cache 7 days)
- `GET /trainsBetweenStations/{from}/{to}/{date}` → direct trains (supplement our DB)

---

## WHAT SUCCESS LOOKS LIKE (LAUNCH CRITERIA)

Phase 1 is "done" and ready for real users when ALL of these pass:

- [ ] `GET /health` returns 200 from production URL
- [ ] Station search returns results in < 500ms
- [ ] Route search for NDLS→MMCT returns ≥ 3 routes in < 3 seconds
- [ ] At least one route has live status data from RapidAPI
- [ ] IRCTC booking URL opens correct pre-filled search on IRCTC website
- [ ] Frontend deployed on Vercel, loads on mobile browser
- [ ] No console errors on search flow
- [ ] 5 test searches from different cities all return results

---

## WHAT WE ARE NOT BUILDING (Clear Scope Boundary)

These ideas sound good but are WASTE for now:

| ❌ Not building now | Why |
|---|---|
| Our own ticketing/PNR system | IRCTC monopoly, needs govt license |
| Real-time seat inventory | IRCTC doesn't expose this via free API |
| Train cancellation predictions | Need months of data collection first |
| Multi-modal (bus + train) | Completely different data sources, different problem |
| International trains | Indian railways only for now |
| Voice search | Nice to have, not core |
| PWA / offline mode | Complex, core must work online first |
| Kafka message streaming | Zero users, zero need for event queue |
| Kubernetes / microservices | Single FastAPI app handles 10k users fine |

---

## EXECUTION ORDER (What to do next, exactly)

### TODAY / TOMORROW:
1. Fix `backend/services/booking_service.py` circular import (30 min)
2. Run backend locally, confirm `/health` works (30 min)
3. Test route search with `curl` or Postman for NDLS→MMCT (1 hour)
4. Fix any route engine DB query errors (1–2 hours)
5. Verify station autocomplete returns results (30 min)

### THIS WEEK:
6. Wire frontend to local backend, confirm search shows results (2 hours)
7. Add live status badge to RouteCard using RapidAPI (2 hours)
8. Generate IRCTC URL from route result, add "Book on IRCTC" button (1 hour)
9. Deploy backend to Render.com (1 hour)
10. Deploy frontend to Vercel (30 min)

### NEXT WEEK:
11. Supabase Auth — login/signup flow working (2 hours)
12. PNR status checker page (2 hours)
13. Save favourite routes (1 hour)
14. Mobile responsiveness check + fixes (2 hours)

### AFTER THAT:
15. SOS feature — emergency contacts + Twilio SMS (2–3 days)
16. Train tracking page — live location on map (2 days)

---

## OPEN QUESTIONS (Decide before building)

1. **Domain name?** routemaster.in is the company name — is the domain bought?
2. **Analytics?** Add Plausible or Posthog (free) from day 1 to track searches
3. **Error tracking?** Add Sentry (free) to catch backend crashes in production
4. **Rate limiting?** Add `slowapi` to FastAPI — 20 requests/min per IP on search
5. **IRCTC affiliation?** Can we add UTM parameters to IRCTC URLs to track referrals?

---

*This plan is the single source of truth for what we're building. Any new feature idea must be measured against: "Does this help a real user search for train routes?" If not, it goes to Phase 4.*
