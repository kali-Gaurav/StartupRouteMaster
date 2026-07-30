# Route Master — How to Run Everything

## Quick Start (3 commands)

```bash
# Terminal 1 — Backend
cd C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\backend
pip install -r requirements.txt
python verify.py          ← check everything is connected
uvicorn app:app --reload --port 8000

# Terminal 2 — Frontend
cd C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\frontend
npm install
npm run dev
```

Then open: **http://localhost:5173**

---

## Before First Run — Add These to `.env`

Open `C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\.env` and add:

```
RAPIDAPI_KEY=your_key_here   ← get free at rapidapi.com/search/indian-railway
JWT_SECRET=any-random-32-char-string-here
```

Optional (for SOS SMS):
```
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=+1234567890
```

---

## What Each Endpoint Does

| Method | URL | What it does |
|--------|-----|-------------|
| GET | /health | Backend health check |
| GET | /docs | Full API documentation (Swagger) |
| GET | /api/v1/stations/suggest?q=delhi | Station autocomplete |
| GET | /api/v1/search/routes?source=NDLS&destination=BCT&date=2026-06-10 | Route search |
| GET | /api/v1/live/train/12951 | Live train delay status |
| GET | /api/v1/pnr/1234567890 | PNR booking status |
| POST | /api/v1/auth/register | Create account |
| POST | /api/v1/auth/login | Login, get JWT token |
| GET | /api/v1/auth/me | Get current user |
| POST | /api/v1/sos/trigger | Trigger SOS alert |

---

## Test the Core Search

```bash
curl "http://localhost:8000/api/v1/search/routes?source=NDLS&destination=BCT&date=2026-06-10"
```

Expected: JSON with `data.journeys` containing trains with departure/arrival times and `metadata.irctc_url`.

---

## Deploy to Production

**Backend → Render.com**
1. render.com → New Web Service → connect GitHub
2. Root directory: `backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Add env vars: DATABASE_URL, REDIS_URL, RAPIDAPI_KEY, JWT_SECRET, FRONTEND_URL

**Frontend → Vercel**
1. vercel.com → New Project → connect GitHub
2. Root directory: `frontend`
3. Add env var: `VITE_API_URL=https://your-render-backend.onrender.com`
4. Deploy

---

## If Something Breaks

Run `python verify.py` — it shows exactly what's working and what isn't.

Common issues:
- **"Station NDLS not found"** → DB might use different codes. Run verify.py to see sample codes.
- **"Database unavailable"** → Check DATABASE_URL in .env
- **"Redis degraded"** → Check REDIS_URL in .env (search still works without Redis)
- **"RAPIDAPI_KEY not set"** → Live status won't work, but route search still works

---

## File Structure (post-cleanup)

```
startupV2/
├── backend/
│   ├── app.py              ← FastAPI entry point (100 lines, clean)
│   ├── requirements.txt    ← 23 packages only
│   ├── verify.py           ← Run this to check everything
│   ├── api/v1/             ← ALL WORKING ENDPOINTS ARE HERE
│   │   ├── search.py       ← Route search
│   │   ├── stations.py     ← Station autocomplete
│   │   ├── auth.py         ← Login/signup/JWT
│   │   ├── live.py         ← Live train status
│   │   ├── pnr.py          ← PNR status
│   │   └── sos.py          ← SOS alerts
│   ├── core/route_engine/
│   │   └── data_provider.py ← GTFS DB queries (rewritten)
│   └── _archived/          ← Archived modules (recoverable)
└── frontend/
    ├── src/pages/Index.tsx         ← Main search page
    ├── src/components/RouteCard.tsx ← Route card + IRCTC button
    └── src/services/railwayBackApi.ts ← API client
```
