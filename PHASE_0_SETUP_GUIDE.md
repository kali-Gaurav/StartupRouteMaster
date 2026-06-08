# Phase 0 Setup Guide: Pre-Deployment Verification

**Date:** June 6, 2026  
**Goal:** Verify all systems work locally before deploying to production  
**Duration:** ~3 days  
**Status:** ✅ In Progress

---

## ✅ Task 1: Environment Secrets (DONE)

### What was done:
- ✅ Generated `JWT_SECRET` = `sk_prod_7x9mK2pL5qR8vN3wXyZ0aB4cD6eF9gH1jK2lM4nO7pQ`
- ✅ Added placeholder for `RAPIDAPI_KEY` 
- ✅ Updated `.env` file with both

### Current .env Status (8 required variables):

| Variable | Status | Value |
|----------|--------|-------|
| DATABASE_URL | ✅ | postgresql://postgres.bkzrxgtsfovctfviqkuh:... |
| REDIS_URL | ✅ | rediss://default:AZiZAAIncDIwNDdiZTY2NTMiY2Q0NTIyOTZiMTQ1MzlmNDRmZTVhOXAyMzkwNjU@... |
| TELEGRAM_BOT_TOKEN | ✅ | 8263758262:AAEHCUddJ0LBBB6jvdNuuJ8DyN0gBGRSEsg |
| Gemini_API_key | ✅ | AIzaSyA9OOupynXhH77Mw2CMaqh7W2GniXOXZwo |
| JWT_SECRET | ✅ | sk_prod_7x9mK2pL5qR8vN3wXyZ0aB4cD6eF9gH1jK2lM4nO7pQ |
| RAPIDAPI_KEY | ⏳ PENDING | Need to signup at RapidAPI |
| RAZORPAY_KEY_ID | ✅ | rzp_test_Si7Rzwylj21i3C |
| RAZORPAY_KEY_SECRET | ✅ | zrM8c2rvPzoBCut2ah7z7TcC |

### ⚠️ ACTION REQUIRED: Get RAPIDAPI_KEY

**Why:** Used for PNR status lookups (10-digit PNR → booking status)

**Steps:**
1. Go to https://rapidapi.com/apidojo/api/irctc1
2. Click "Subscribe to Test" (free tier: 7,000 calls/month)
3. Confirm you're logged in
4. Copy your API Key from dashboard
5. Replace `YOUR_RAPIDAPI_KEY_HERE` in `.env` with your actual key

**Example:**
```
RAPIDAPI_KEY=abc123def456ghi789jkl012mno345pqr678stu
```

**Note:** If you don't do this now, PNR lookups will gracefully fail (fallback to "Check IRCTC directly")

---

## Next Steps (Tasks 2-6)

### Task 2: Database Seeding (Blocked until Task 1 complete)
**What:** Run schema validation + load 350 Indian railway stations + 50 trains into Supabase
```bash
cd backend
python scripts/schema_check.py
python scripts/seed_data.py
```

### Task 3: Backend Verification (Blocked until Task 2 complete)
**What:** Verify all connections working
```bash
cd backend
python verify.py
```

### Task 4: Backend API Testing (Blocked until Task 3 complete)
**What:** Test 10 endpoints locally
```bash
cd backend
uvicorn app:app --reload
# In another terminal, test endpoints
```

### Task 5: Frontend Testing (Blocked until Task 3 complete)
**What:** Test 5 pages in browser
```bash
cd frontend
npm run dev
# Open http://localhost:3000
```

### Task 6: Integration Test (Blocked until Tasks 4 & 5 complete)
**What:** Full end-to-end flow: search → book → PNR check

---

## Timeline

- **Today (June 6):** Task 1 (this doc)
- **Tomorrow (June 7):** Tasks 2-3 (database + backend verification)
- **June 8:** Tasks 4-6 (testing locally)
- **June 9:** Begin Phase 1 (production deployment)

---

## Troubleshooting

### If verify.py fails:
- Check all 8 env vars are present: `cat .env | grep -E "DATABASE_URL|REDIS_URL|..."`
- Test database directly: `psql $DATABASE_URL -c "SELECT COUNT(*) FROM stops;"`
- Test Redis: `redis-cli -u $REDIS_URL PING`

### If seed_data.py fails:
- Ensure database exists: `CREATE DATABASE postgres;` in Supabase
- Ensure schema exists: run `schema_check.py` first
- Check disk space: Supabase free tier has 500MB limit

### If backend tests fail:
- Check VITE_API_URL in frontend = http://localhost:8000
- Check backend server is running: `curl http://localhost:8000/health`
- Check no port 8000 already in use: `lsof -i :8000`

### If frontend won't load:
- Check npm cache: `npm cache clean --force`
- Delete node_modules: `rm -rf node_modules && npm install`
- Check Node version: should be 18+

---

## Verification Checklist

Before moving to Task 2, confirm:

- [ ] `.env` file has all 8 variables
- [ ] JWT_SECRET is random 32+ chars
- [ ] RAPIDAPI_KEY is obtained (or at least attempted)
- [ ] No sensitive keys committed to Git
- [ ] `.gitignore` includes `.env` (never commit secrets)

---

## Ready for Phase 1?

After Task 6 is complete:
1. All searches work locally (<2s latency)
2. No 500 errors in logs
3. Fares match IRCTC within 5%
4. Mobile UI works
5. Accessibility: no console errors

Then proceed to Phase 1: Production Deployment (Render + Vercel)

---

**Questions?** Check the full EXECUTION_PLAN_FULL.md for detailed steps.
