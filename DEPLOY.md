# Route Master — Production Deployment Guide
**Last updated:** June 5, 2026  
**Status:** Ready to deploy

---

## WHAT YOU'RE DEPLOYING

| Layer | Service | URL after deploy |
|-------|---------|-----------------|
| Frontend | Vercel (free) | `https://routemaster.vercel.app` |
| Backend API | Render.com (free) | `https://routemaster-api.onrender.com` |
| Database | Supabase (free) | Already connected |
| Cache | Upstash Redis (free) | Already connected |

---

## STEP 0 — Run validation script first (local)

```bash
cd backend
pip install asyncpg httpx  # if not installed
python scripts/schema_check.py     # Checks table schema, fixes column name issues
python scripts/seed_data.py --check  # Shows row counts
```

If tables are empty or don't exist:
```bash
python scripts/seed_data.py        # Seeds 350 stations + 50 trains with schedules
python scripts/seed_data.py --clear  # Start fresh (WARNING: deletes existing data)
```

Then validate everything works end-to-end:
```bash
uvicorn app:app --reload &          # Start server in background
python scripts/validate_deployment.py  # Tests 20 city pairs + all endpoints
```

---

## STEP 1 — Verify Supabase has data

Open Supabase dashboard → Table Editor. Check these tables exist and have rows:
- `stops` → should have 7,000+ rows
- `trips` → should have 10,000+ rows  
- `stop_times` → should have millions of rows
- `trains_master` → should have 10,000+ rows

If tables are empty, the search will return no results. Import GTFS data first.

**Create missing tables (run in Supabase SQL Editor):**
```sql
-- Users table (for auth)
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT DEFAULT '',
  role TEXT DEFAULT 'user',
  is_verified BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- SOS events table
CREATE TABLE IF NOT EXISTS sos_events (
  id UUID PRIMARY KEY,
  user_id UUID,
  train_no TEXT,
  location JSONB,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

-- Emergency contacts
CREATE TABLE IF NOT EXISTS emergency_contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  name TEXT NOT NULL,
  phone TEXT NOT NULL,
  relation TEXT
);
```

---

## STEP 2 — Deploy Backend to Render

1. Go to **render.com** → Sign up / Log in  
2. Click **New** → **Web Service**
3. Connect your GitHub repo
4. Settings:
   - **Name:** `routemaster-api`
   - **Region:** Singapore
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 30`
5. Click **Advanced** → Add environment variables:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | `postgresql://postgres.bkzrxgtsfovctfviqkuh:kaliGaurav123@aws-1-ap-south-1.pooler.supabase.com:5432/postgres` |
| `REDIS_URL` | `rediss://default:AZiZAAIncDIwNDdiZTY2NTNiY2Q0NTIyOTZiMTQ1MzlmNDRmZTVhOXAyMzkwNjU@amazed-rat-39065.upstash.io:6379` |
| `FRONTEND_URL` | `https://routemaster.vercel.app` |
| `ENVIRONMENT` | `production` |
| `ALLOW_DEGRADED_BOOT` | `true` |
| `LOG_LEVEL` | `info` |
| `JWT_SECRET` | *(generate any long random string)* |

6. Click **Create Web Service**
7. Wait 3-5 min for first build
8. Test: `https://routemaster-api.onrender.com/health` → should return `{"status":"ok"}`

---

## STEP 3 — Deploy Frontend to Vercel

1. Go to **vercel.com** → Sign up / Log in
2. Click **New Project** → Import from GitHub
3. Select the `startupV2` repo
4. Settings:
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
5. Add environment variables:

| Key | Value |
|-----|-------|
| `VITE_API_URL` | `https://routemaster-api.onrender.com` |
| `VITE_SUPABASE_URL` | `https://bkzrxgtsfovctfviqkuh.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | *(from Supabase dashboard → Settings → API)* |
| `VITE_APP_BASE_URL` | `https://routemaster.vercel.app` |

6. Click **Deploy**
7. Wait 2-3 min

---

## STEP 4 — Test End-to-End

Once both are deployed, test in this order:

### Backend health
```
GET https://routemaster-api.onrender.com/health
→ {"status":"ok","version":"1.0.0",...}
```

### Station autocomplete
```
GET https://routemaster-api.onrender.com/api/v1/stations/suggest?q=delhi&limit=5
→ [{"code":"NDLS","name":"New Delhi",...}, ...]
```

### Route search (the core product)
```
GET https://routemaster-api.onrender.com/api/v1/search/routes?source=NDLS&destination=BCT&date=2026-06-15
→ {"status":"success","data":{"journeys":[...],...}}
```

### Live train status
```
GET https://routemaster-api.onrender.com/api/v1/live/train/12951
→ {"available":true,"train_name":"...","delay_minutes":0,...}
```

### Frontend
Open `https://routemaster.vercel.app`:
- Type "Delhi" in FROM → should show station suggestions
- Type "Mumbai" in TO → should show station suggestions  
- Pick a date → click Search
- Should show route cards with train names, times, fares

---

## COMMON ISSUES

| Problem | Cause | Fix |
|---------|-------|-----|
| Search returns 0 results | `stops` table empty in Supabase | Import GTFS data |
| "Database degraded" in /health | DATABASE_URL wrong or SSL issue | Check DB URL in Render env vars |
| Station autocomplete empty | `stops.code` column format different | Check what codes exist: `SELECT code FROM stops LIMIT 5` |
| 502 Bad Gateway | Backend still starting up | Wait 30s, retry. Free tier sleeps. |
| CORS error in browser | FRONTEND_URL not set in Render | Add `FRONTEND_URL=https://routemaster.vercel.app` |

---

## ADDING RAPIDAPI KEY (for PNR status)

1. Go to rapidapi.com → search "IRCTC"
2. Subscribe to `irctc1.p.rapidapi.com` free plan (500 calls/month)
3. Copy API key
4. Add to Render env vars: `RAPIDAPI_KEY=your_key_here`

---

## ADDING TWILIO (for SOS SMS)

1. Go to twilio.com → free trial ($15 credit = ~1000 SMS)
2. Get: Account SID, Auth Token, a phone number
3. Add to Render env vars:
   - `TWILIO_ACCOUNT_SID=ACxxxxx`
   - `TWILIO_AUTH_TOKEN=xxxxx`
   - `TWILIO_FROM_NUMBER=+1xxxxxxxxxx`

---

## UPGRADE PATH (when users arrive)

| When | Action | Cost |
|------|--------|------|
| First 100 users | Stay on free tier | $0/mo |
| Free tier sleeping bothers users | Render Starter | $7/mo |
| >1000 daily searches | Render Standard | $25/mo |
| >10,000 daily searches | Add Redis caching (already built) | — |

---

## LOCAL DEVELOPMENT

```bash
# Backend
cd backend
python verify.py          # Check all connections
uvicorn app:app --reload  # Start on http://localhost:8000

# Frontend (new terminal)
cd frontend
npm run dev               # Start on http://localhost:5173
```

The root `.env` already has all credentials for local dev.
