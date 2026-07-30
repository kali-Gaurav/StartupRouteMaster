# PHASE 1: Production Deployment (Week 2)
**Status:** Ready to Deploy  
**Timeline:** 3 days  
**Goal:** Route Master live at routemaster.in, serving real users

---

## ✅ Phase 0 Complete
All local verification done:
- Database: 350 stations + 200 trains seeded ✅
- Backend: All 10 endpoints tested, <2s latency ✅
- Frontend: All 5 pages tested, no console errors ✅
- Integration: Search → Book → PNR check works end-to-end ✅

---

## 🚀 PHASE 1: Deploy to Production

### Architecture (6 components)
```
┌─────────────────────────────────────────────────────────────┐
│                   Users (via Browser)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS
       ┌───────────────┴───────────────┐
       ▼                               ▼
┌─────────────────┐         ┌─────────────────────┐
│  Frontend       │         │ Backend API         │
│  Vercel         │         │ Render.com          │
│  routemaster.in │─────────│ api.routemaster.in  │
│  (React)        │         │ (FastAPI Python)    │
└─────────────────┘         └──────────┬──────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │  Supabase    │   │ Upstash      │   │ External     │
            │  Database    │   │ Redis Cache  │   │ APIs         │
            │  (GTFS)      │   │              │   │ (rappid.in,  │
            │              │   │              │   │  erail.in)   │
            └──────────────┘   └──────────────┘   └──────────────┘
```

### Prerequisites

**You'll need:**
1. GitHub account (for code hosting)
2. Render account (free tier: 0.5GB RAM, 1 worker process)
3. Vercel account (free tier: unlimited deployments)
4. Domain name (optional but recommended: ₹500-1000/year)

**Already configured:**
- Supabase database ✅
- Upstash Redis cache ✅
- External APIs (rappid.in, erail.in) ✅
- Environment variables in .env ✅

---

## Step-by-Step Deployment

### 1️⃣ Push Code to GitHub (5 minutes)

**Why:** Render + Vercel auto-deploy from Git commits

```bash
# Initialize git (if not already done)
cd /path/to/routemaster
git init
git add .
git commit -m "Route Master: Phase 1 production ready"

# Push to GitHub
git remote add origin https://github.com/YOUR_USERNAME/route-master.git
git branch -M main
git push -u origin main
```

**What to commit:**
- backend/ (FastAPI code)
- frontend/ (React code)
- .env (NO! Skip this — never commit secrets)
- .gitignore (must include .env)

**Create .gitignore** (if missing):
```
.env
.env.local
node_modules/
backend/__pycache__/
backend/.pytest_cache/
dist/
build/
*.pyc
```

---

### 2️⃣ Deploy Backend to Render.com (10 minutes)

**Steps:**

1. **Create Render account**
   - Go to https://render.com
   - Sign up with GitHub

2. **Create new Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repo
   - Select repository: your route-master repo

3. **Configure deployment**
   - Name: `route-master-api`
   - Environment: `Python 3.11`
   - Region: `Singapore` (closest to India)
   - Build Command:
     ```
     pip install -r backend/requirements.txt
     ```
   - Start Command:
     ```
     cd backend && uvicorn app:app --host 0.0.0.0 --port 8080
     ```

4. **Add environment variables**
   - In Render dashboard, go to Environment
   - Add all 8 variables from your .env:
     ```
     DATABASE_URL=postgresql://...
     REDIS_URL=rediss://...
     TELEGRAM_BOT_TOKEN=8263758262:AAE...
     Gemini_API_key=AIzaSy...
     JWT_SECRET=sk_prod_7x9mK2pL5qR8vN3wXyZ0aB4cD6eF9gH1jK2lM4nO7pQ
     RAZORPAY_KEY_ID=rzp_test_...
     RAZORPAY_KEY_SECRET=zrM8c2rv...
     TELEGRAM_CHAT_ID=8263758262
     ```

5. **Deploy**
   - Click "Create Web Service"
   - Wait for build: ~2-3 minutes
   - Expected URL: `https://route-master-api.onrender.com`

6. **Verify deployment**
   ```bash
   curl https://route-master-api.onrender.com/health
   # Expected: {"status": "ok"}
   ```

**Common issues:**
- Build fails: Check Python version, requirements.txt syntax
- Service dies after startup: Check if all env vars are set
- Slow startup: Free tier has limited CPU, first request takes ~30s

---

### 3️⃣ Deploy Frontend to Vercel (10 minutes)

**Steps:**

1. **Create Vercel account**
   - Go to https://vercel.com
   - Sign up with GitHub

2. **Import project**
   - Click "Add New..." → "Project"
   - Select your route-master repository
   - Click "Import"

3. **Configure build**
   - Framework: React
   - Build Command: `npm run build`
   - Output Directory: `frontend/dist`
   - Root Directory: `frontend`

4. **Add environment variables**
   - In Project Settings → Environment Variables
   - Add these:
     ```
     VITE_API_URL=https://route-master-api.onrender.com
     VITE_RAILWAY_API_URL=https://route-master-api.onrender.com
     VITE_RAZORPAY_KEY_ID=rzp_test_Si7Rzwylj21i3C
     VITE_SUPABASE_URL=https://bkzrxgtsfovctfviqkuh.supabase.co
     VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
     ```

5. **Deploy**
   - Click "Deploy"
   - Wait for build: ~1-2 minutes
   - Expected URL: `https://route-master.vercel.app`

6. **Verify deployment**
   - Open https://route-master.vercel.app in browser
   - Search: Delhi → Mumbai
   - Expected: Routes load in <3 seconds

---

### 4️⃣ Setup Custom Domain (Optional, 10 minutes)

**Goal:** routemaster.in instead of vercel.app subdomain

1. **Buy domain**
   - Namecheap, GoDaddy, or other registrar
   - Popular options:
     - routemaster.in (₹900/year)
     - routemaster.io (₹1800/year)
     - routemaster.co.in (₹600/year)

2. **Point DNS to Vercel**
   - In Vercel project: Settings → Domains
   - Add your domain
   - Vercel shows DNS records to add
   - Add to your domain registrar's DNS settings
   - Wait 5-30 minutes for propagation

3. **Point API subdomain to Render**
   - In Render: Environment → Domain
   - Add custom domain: `api.routemaster.in`
   - Get CNAME record from Render
   - Add to domain registrar's DNS
   - Wait for propagation

4. **Test**
   ```bash
   # Test frontend
   curl https://routemaster.in
   # Test backend
   curl https://api.routemaster.in/health
   ```

---

### 5️⃣ Comprehensive Production Testing (20 minutes)

**Test from production URLs (not localhost)**

**Backend Tests:**
```bash
# Test route search
curl "https://api.routemaster.in/api/v1/search/routes?from=NDLS&to=BCT&date=2026-06-25"

# Test 5 major city pairs
for pair in "NDLS-BCT" "NDLS-BRC" "BCT-MAS" "HWH-BCT" "NGP-NDLS"; do
  from=$(echo $pair | cut -d- -f1)
  to=$(echo $pair | cut -d- -f2)
  echo "Testing: $from → $to"
  curl -s "https://api.routemaster.in/api/v1/search/routes?from=$from&to=$to&date=2026-06-25" | jq '.routes | length'
done

# Test other endpoints
curl https://api.routemaster.in/health
curl "https://api.routemaster.in/api/v1/stations/suggest?q=delhi"
curl "https://api.routemaster.in/api/v1/live/train/12951"
```

**Frontend Tests (Browser):**
1. Open https://routemaster.in (or vercel.app)
2. Search Delhi → Mumbai, date = 5 days from now
3. Verify: ≥3 routes, fares shown, "Book on IRCTC" button visible
4. Click book button → opens IRCTC.co.in
5. Test PNR status: /pnr page
6. Test station board: /station/NDLS
7. Check DevTools Console: NO red errors

**Performance Checks:**
- Backend response time: <2 seconds (check Network tab)
- Frontend load time: <3 seconds (Vercel Analytics)
- Error rate: <0.1% (check Render logs)

---

### 6️⃣ Monitoring Setup (10 minutes)

**Goal:** Know if system is healthy

**Render Monitoring:**
- Dashboard automatically tracks:
  - Uptime %
  - Response time
  - CPU/memory usage
  - Error logs
- Alert thresholds already configured

**Vercel Monitoring:**
- Analytics auto-enabled
- Tracks Core Web Vitals (LCP, FID, CLS)
- Shows real user monitoring data

**Manual Health Checks:**
```bash
# Test every 5 minutes
while true; do
  echo "$(date): " $(curl -s https://api.routemaster.in/health)
  sleep 300
done
```

---

### 7️⃣ Run Production Validation Script (5 minutes)

```bash
cd backend
python scripts/validate_deployment.py --url https://api.routemaster.in
```

**Expected output:**
```
═══════════ Production Deployment Validator ═══════════

Testing 20 major city pairs...
✅ NDLS → BCT: 5 routes found, avg latency 1.2s
✅ NDLS → HWH: 8 routes found, avg latency 1.5s
✅ BCT → MAS: 3 routes found, avg latency 1.8s
... (17 more city pairs)

✅ API Response Time: 95th percentile = 1.8s
✅ Error Rate: 0.02%
✅ Uptime: 99.98%
✅ Database: 350 stations, 200 trains
✅ Cache: Redis connected, 50MB used

═══════════════════════════════════════════════════
✅ PRODUCTION READY!
```

---

## Rollback Plan (If Things Go Wrong)

### Backend issues:
```bash
# Render keeps last 10 deployments
# In Render dashboard: Deployments
# Click "Rollback" on previous working version
```

### Frontend issues:
```bash
# Vercel keeps every deployment
# In Vercel dashboard: Deployments
# Click date of working version
# Click "Promote to Production"
```

### Database issues:
```bash
# Supabase auto-backups every 24h
# If data corrupted:
#   1. Go to Supabase dashboard
#   2. Backups → Restore previous snapshot
#   3. Re-seed data: python scripts/seed_data.py
```

---

## Success Checklist

✅ Backend deployed to Render (api.routemaster.in)  
✅ Frontend deployed to Vercel (routemaster.in or vercel.app)  
✅ All 20 city pairs search successfully  
✅ Latencies <2 seconds (95th percentile)  
✅ Fares match IRCTC ±5%  
✅ No 500 errors in logs  
✅ Mobile UI responsive (tested on 2+ devices)  
✅ Monitoring dashboards accessible  
✅ Domain mapped (optional)  
✅ Health checks passing  

---

## What's Next

Once Phase 1 is complete and production is live:

### Week 3 (Phase 2): Safety & Support
- 24/7 support team setup (Twilio SOS)
- Safety scoring algorithm
- Fare alerts system
- Chatbot for 50+ common questions

### Week 4 (Phase 3): Real-Time Data
- Live GTFS feed integration (5-min updates)
- Real-time delay detection
- Crowding data
- Weather monitoring

### Week 5 (Phase 4): User Experience
- In-app navigation guidance
- Support escalation (<2 min response)
- Accessibility program (blind/deaf/mobility)
- Gamification & loyalty

### Week 6 (Phase 5): Production Readiness
- Full monitoring setup
- Capacity testing (10x load)
- Legal compliance audit
- Launch to all users

---

## Important Notes

1. **Never commit .env** — Use Render/Vercel environment variables
2. **HTTPS is automatic** — Render and Vercel provide SSL
3. **Database is live** — Same Supabase as local testing
4. **Monitor closely** — First 24h are critical
5. **Rollback easy** — Can revert in seconds if needed

---

## Estimated Time

- Push to GitHub: 5 min
- Deploy backend: 10 min (wait for build)
- Deploy frontend: 10 min (wait for build)
- Testing: 20 min
- Domain setup: 10 min (optional)
- Total: ~45 minutes for full deployment

---

## Emergency Contacts

If something breaks in production:

1. **Backend down:**
   - Check Render dashboard for errors
   - Look for error messages in logs
   - Rollback to previous version

2. **Frontend broken:**
   - Check Vercel deployment logs
   - Open browser DevTools Console for errors
   - Rollback to previous version

3. **Database issues:**
   - Check Supabase dashboard
   - Verify queries in query editor
   - Contact Supabase support if critical

4. **External APIs down:**
   - rappid.in fails → routes still work but no live delays
   - erail.in fails → use fare estimates
   - System gracefully degrades

---

**Ready to deploy? Start with Step 1: Push to GitHub, then follow the steps above.**

Questions? Check LOCAL_SETUP_STEPS.md or EXECUTION_PLAN_FULL.md for context.
