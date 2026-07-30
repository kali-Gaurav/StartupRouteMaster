# Route Master: Local Setup & Testing (Tasks 2-6)
**Run these commands on YOUR MACHINE (not in cloud)**

---

## Prerequisites
- Node.js 18+ installed
- Python 3.9+ installed
- .env file in project root (already configured)
- Supabase DATABASE_URL accessible from your machine

---

## TASK 2: Database Seeding (5-10 minutes)

### Step 1: Install backend dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 2: Validate database schema
```bash
python scripts/schema_check.py
```

**Expected output:**
```
═══════════ Route Master Schema Validator ═══════════

✅ Connected to Supabase
-- stops --
✅ id ✓
✅ code ✓
✅ name ✓
✅ Row count: 350+
-- trips --
✅ id ✓
✅ trip_id ✓
✅ route_id ✓
✅ Row count: 200+
-- stop_times --
✅ id ✓
✅ trip_id ✓
...
✅ Schema is VALID — ready to search!
```

If you see "Row count: 0" for any table, continue to Step 3.

### Step 3: Seed database with Indian railway data
```bash
python scripts/seed_data.py
```

**Expected output:**
```
✅ Connected to Supabase
✅ Created table: stops (if new)
✅ Inserted 350 stations
✅ Created table: trips
✅ Inserted 200 trains
✅ Created table: stop_times
✅ Inserted 15,000+ stop_time entries
✅ All data seeded successfully!
```

This loads:
- 350+ Indian railway stations (all major junctions)
- 200+ popular trains (Rajdhani, Shatabdi, Express, etc.)
- 15,000+ stop-time entries (full schedules)

**If you see errors:**
- Check DATABASE_URL in .env is correct
- Ensure Supabase project exists and is accessible
- Run `python scripts/schema_check.py --clear` to reset schema (WARNING: deletes all data)

---

## TASK 3: Verify All Connections (2-3 minutes)

### Run verification script
```bash
python verify.py
```

**Expected output:**
```
═══════════ Route Master Connection Verifier ═══════════

✅ Database (Supabase) — Connected
   - stops: 350 rows
   - trips: 200 rows
   - stop_times: 15,000 rows
   - trains_master: 200 rows

✅ Redis Cache (Upstash) — Connected
   - Ping: 45ms
   - Memory: 512MB available

✅ Route Engine — Loaded
   - DataProvider ready
   - GTFS indices built

✅ External APIs
   - rappid.in (live train status) — OK
   - erail.in (fares) — OK
   - RapidAPI (PNR) — OK (optional)
   - Telegram — OK

═══════════════════════════════════════════════════════
✅ All systems GREEN — ready to start server!
```

**If you see ❌:**
- Most likely: missing .env variables. Check: cat .env
- Database down: check Supabase dashboard
- Redis down: check Upstash dashboard

---

## TASK 4: Test Backend Endpoints (5 minutes)

### Terminal 1: Start the backend server
```bash
cd backend
uvicorn app:app --reload
```

Wait for:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### Terminal 2: Test 10 endpoints

**Test 1: Route Search**
```bash
curl "http://localhost:8000/api/v1/search/routes?from=NDLS&to=BCT&date=2026-06-20"
```

Expected: JSON with direct trains, 1-transfer, 2-transfer routes, fares, IRCTC links

**Test 2: Station Autocomplete**
```bash
curl "http://localhost:8000/api/v1/stations/suggest?q=delhi"
```

Expected: List of Delhi stations (NDLS, DLI, NZM, etc.)

**Test 3: Live Train Status**
```bash
curl "http://localhost:8000/api/v1/live/train/12951"
```

Expected: Current station, delay, next station, running status

**Test 4: Fare Lookup**
```bash
curl "http://localhost:8000/api/v1/fare/12951"
```

Expected: Available classes (1A, 2A, 3A, SL) with prices

**Test 5: PNR Status**
```bash
curl "http://localhost:8000/api/v1/pnr/1234567890"
```

Expected: Booking status, berth, coach, chart status (or graceful fallback)

**Test 6: Health Check**
```bash
curl "http://localhost:8000/health"
```

Expected: `{"status": "ok"}`

**Test 7: Server Stats**
```bash
curl "http://localhost:8000/stats"
```

Expected: Uptime, requests, CPU, memory

**Test 8: Station Board (Departures)**
```bash
curl "http://localhost:8000/api/v1/stations/NDLS/departures?date=2026-06-20"
```

Expected: Next 20 trains departing from NDLS

**Test 9: Train Schedule**
```bash
curl "http://localhost:8000/api/v1/stations/schedule/12951"
```

Expected: Full timetable for train 12951 with all stops

**Test 10: Auth Register**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com", "password":"SecurePass123"}'
```

Expected: JWT token + user object

---

## TASK 5: Test Frontend Pages (10 minutes)

### Terminal 3: Start the frontend
```bash
cd frontend
npm install  # if not already done
npm run dev
```

Wait for:
```
  Local:        http://localhost:5173/
```

### Open browser and test 5 pages

**Page 1: Homepage** → http://localhost:5173/
- Check: Logo, search form visible
- Check: DevTools Console → NO red errors
- Check: Page loads in <2 seconds

**Page 2: Route Search** → http://localhost:5173/search
- Input: From = "Delhi", To = "Mumbai", Date = tomorrow
- Click "Search"
- Expected: List of routes (direct + transfers) with fares, "Book on IRCTC" button
- Latency: <2 seconds
- Check DevTools Console → NO errors

**Page 3: PNR Status** → http://localhost:5173/pnr
- Input: 10-digit PNR (e.g., 1234567890)
- Click "Check Status"
- Expected: Booking status, berth number, coach, chart status
- Check: Console → NO errors

**Page 4: Station Board** → http://localhost:5173/station/NDLS
- Expected: Next 20 trains departing from NDLS (New Delhi station)
- Check: FIDS-style display (platform, departure time, train name)
- Auto-refresh every 2 minutes should work

**Page 5: Train Schedule** → http://localhost:5173/trains/12951/schedule
- Expected: Full timetable for train 12951 (Rajdhani Express)
- Check: All stops with arrival/departure times

### DevTools Checks (F12)
- Open DevTools → Console tab
- Look for red ❌ errors (should be none)
- Yellow ⚠️ warnings are OK
- Network tab: Check all API calls return 200 status
- Performance: Page load should be <2 seconds

---

## TASK 6: Full End-to-End Integration Test (10 minutes)

### Scenario: Book Delhi→Mumbai train, check status

**Step 1: Search for routes**
- Browser: http://localhost:5173/search
- Input: Delhi → Mumbai, date = 2 days from now
- Expected: ≥3 direct trains visible (12951, 12953, 12954, etc.)
- Check: Each route shows fare (₹1000-₹3000), classes (1A, 2A, 3A, SL), travel time

**Step 2: Click "Book on IRCTC"**
- Click "Book on IRCTC" button on any route
- Expected: Opens https://www.irctc.co.in with route pre-filled
- Verify: Train number, date, from/to match

**Step 3: Check PNR Status**
- Go to http://localhost:5173/pnr
- Enter a real IRCTC PNR from your account (or test PNR 1234567890)
- Expected: Shows booking status, berth, coach, chart status

**Step 4: Check Live Delays**
- Go back to search results
- Each train should show: "Delay: +5 min" or "On Time"
- This comes from rappid.in live feed

**Step 5: Check Station Board**
- Click "Station Board" → /station/NDLS
- Expected: Shows next 20 trains departing New Delhi
- Check: Times match search results

### Success Criteria
✅ All 5 searches return results <2 seconds  
✅ Fares match IRCTC website (±5%)  
✅ No 500 errors in backend logs  
✅ No red errors in frontend console  
✅ "Book on IRCTC" redirects work  
✅ Mobile UI responsive (test on phone or DevTools device mode)  

---

## Troubleshooting

### Backend won't start
```bash
# Check if port 8000 is in use
lsof -i :8000
# Kill it: kill -9 <PID>
```

### Frontend won't start
```bash
# Clear npm cache
npm cache clean --force
# Delete node_modules and reinstall
rm -rf node_modules
npm install
npm run dev
```

### Searches return empty results
```bash
# Check database has data
cd backend
python scripts/schema_check.py
# If row count = 0, run:
python scripts/seed_data.py
```

### API returns 500 errors
```bash
# Check logs in terminal 1 (backend)
# Look for error message
# Common fixes:
#  - Missing env variable → add to .env
#  - Database unreachable → check DATABASE_URL
#  - Redis unreachable → check REDIS_URL
```

### Frontend can't reach backend
```bash
# Check VITE_API_URL in .env
VITE_API_URL=http://localhost:8000
# If wrong, update and restart: npm run dev
```

---

## Once All Tasks Complete

When all tests pass:
- ✅ Task 2: Database seeded (350 stations, 200 trains)
- ✅ Task 3: verify.py returns all GREEN
- ✅ Task 4: All 10 backend endpoints work (<2s latency)
- ✅ Task 5: All 5 frontend pages load, no console errors
- ✅ Task 6: Full end-to-end search → book → check status works

**Celebrate!** You're ready for Phase 1: Production Deployment (Render + Vercel)

---

## Quick Reference: Command Summary

```bash
# Setup (one time)
cd backend && pip install -r requirements.txt
python scripts/schema_check.py
python scripts/seed_data.py
python verify.py

# Development loop
# Terminal 1:
cd backend && uvicorn app:app --reload

# Terminal 2:
cd frontend && npm run dev

# Terminal 3:
# Run curl commands from above

# Browser:
# http://localhost:5173 (frontend)
# http://localhost:8000/docs (backend Swagger docs)
```

---

**Next Steps:** Once you complete Tasks 2-6, we proceed to Phase 1 (Production Deployment).

**Estimated time:** 30-45 minutes total
