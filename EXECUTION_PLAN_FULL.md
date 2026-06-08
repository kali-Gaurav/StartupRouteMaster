# Route Master: Full Execution Plan for Production Launch
**Status:** Choosing path forward  
**Date:** June 6, 2026  
**Goal:** Deploy production-ready multi-modal routing platform in 6 weeks

---

## Executive Summary

Route Master is **80% built**. Core backend + frontend complete. Missing:
1. Environment configuration (RAPIDAPI_KEY, JWT_SECRET)
2. Production deployment (Render + Vercel)
3. Comprehensive testing against 25-point checklist
4. Support infrastructure + monitoring
5. Launch readiness validation

**Timeline:** 6 weeks to production with 100% checklist compliance

---

## PHASE 0: PRE-DEPLOYMENT (Week 1) — Foundation Fixes

### 0.1 Environment & Secrets Management
**Goal:** Secure all credentials, lock down API keys  
**Owner:** Backend lead

- [ ] Generate strong `JWT_SECRET` (32+ chars, random)
- [ ] Add `RAPIDAPI_KEY` for PNR status (signup at RapidAPI)
- [ ] Verify all 8 env vars present in `.env`:
  - DATABASE_URL (Supabase) ✅
  - REDIS_URL (Upstash) ✅
  - TELEGRAM_BOT_TOKEN ✅
  - Gemini_API_key ✅
  - JWT_SECRET ❌
  - RAPIDAPI_KEY ❌
  - RAZORPAY_KEY_ID ✅
  - RAZORPAY_KEY_SECRET ✅
- [ ] Create `.env.production` for Render (don't commit)
- [ ] Create Render environment dashboard with all secrets
- [ ] Create Vercel environment dashboard with VITE_API_URL + VITE_RAILWAY_API_URL

### 0.2 Database Validation & Seeding
**Goal:** Ensure Supabase has all GTFS data + proper schema  
**Owner:** Database lead

- [ ] Run `backend/scripts/schema_check.py` → confirm all tables exist
  - stops, trips, stop_times, trains_master
  - Missing columns auto-fixed
- [ ] Run `backend/scripts/seed_data.py` → load 350 stations + 50 trains
  - Real Indian railway data
  - Popular city pairs (Delhi-Mumbai, Delhi-Bangalore, Mumbai-Kolkata, etc.)
- [ ] Verify Redis connection: ping Upstash
- [ ] Test 5 sample queries directly in Supabase (raw SQL)

### 0.3 Backend Verification
**Goal:** All endpoints working, no crashes  
**Owner:** Backend lead

- [ ] Run `python verify.py` in backend directory
  - Confirms DB connection ✅
  - Confirms Redis connection ✅
  - Confirms route engine loads ✅
  - Confirms all 8 external APIs reachable ✅
  - Reports any warnings/errors
- [ ] Fix any failing checks (usually env vars)
- [ ] Test 10 API endpoints locally:
  - `/api/v1/search/routes?from=NDLS&to=BCT&date=2026-06-15`
  - `/api/v1/stations/suggest?q=delhi`
  - `/api/v1/live/train/12951`
  - `/api/v1/fare/12951`
  - `/api/v1/pnr/1234567890`
  - `/health` (status check)
  - `/stats` (server stats)
  - Others per api/v1/*.py

### 0.4 Frontend Verification
**Goal:** All pages render, no console errors  
**Owner:** Frontend lead

- [ ] Start frontend: `npm run dev`
- [ ] Test 5 pages locally:
  - `/` (homepage)
  - `/search` (route search)
  - `/trains/:code` (station board)
  - `/pnr` (PNR status)
  - `/trains/:trainNo/schedule` (train schedule)
- [ ] Open browser DevTools → check for errors
- [ ] Test search on localhost: "Delhi to Mumbai"
- [ ] Verify VITE_API_URL points to localhost:8000

### 0.5 Integration Testing (Local)
**Goal:** Full end-to-end search works locally  
**Owner:** QA lead

- [ ] Search: Delhi → Mumbai, date=tomorrow
- [ ] Verify response includes:
  - Direct trains (≥1)
  - 1-transfer routes (≥1)
  - 2-transfer routes (≥1)
  - Fares per class (1A, 2A, 3A, SL)
  - IRCTC booking links
  - Live delays (from rappid.in)
- [ ] Click "Book on IRCTC" → redirects to IRCTC.co.in
- [ ] Test PNR status: enter 10-digit PNR → shows status
- [ ] Test station board: /station/NDLS → shows live departures
- [ ] No crashes, no 500 errors, all latencies <2s

**Success:** All 5 searches complete with real data in <2 seconds

---

## PHASE 1: PRODUCTION DEPLOYMENT (Week 2) — Live to Users

### 1.1 Deploy Backend to Render.com
**Goal:** Route Master API live at `api.routemaster.example.com`  
**Owner:** DevOps/Backend lead

- [ ] Create Render account (free tier ready)
- [ ] Create new PostgreSQL server on Render (or use Supabase)
- [ ] Create new Web Service on Render:
  - Name: `route-master-api`
  - Runtime: Python 3.11
  - Build: `pip install -r requirements.txt`
  - Start: `uvicorn app:app --host 0.0.0.0 --port 8080`
  - Region: Singapore (low latency to India)
  - Env vars: all 8 secrets from Render dashboard
- [ ] Copy `.env.production` values to Render environment
- [ ] Push code to GitHub → Render auto-deploys
- [ ] Health check: curl `https://route-master-api.onrender.com/health` → 200 OK
- [ ] Run `backend/scripts/validate_deployment.py` against production URL
  - Tests 20 major city pairs
  - Tests all endpoints
  - Reports pass/fail
- [ ] Set up monitoring: Render logs + alerts

**Success:** `/health` returns 200, `/stats` shows uptime >99%

### 1.2 Deploy Frontend to Vercel
**Goal:** Route Master UI live at `routemaster.example.com`  
**Owner:** Frontend lead

- [ ] Create Vercel account (free tier ready)
- [ ] Import GitHub repo → auto-deploys on push
- [ ] Environment variables in Vercel:
  - `VITE_API_URL` = `https://route-master-api.onrender.com`
  - `VITE_RAILWAY_API_URL` = same
  - Other VITE_* keys (Gemini, Firebase config)
- [ ] Build locally: `npm run build` → check for errors
- [ ] Deploy to Vercel: `vercel --prod`
- [ ] Test 5 searches on live URL (not localhost)
- [ ] Verify SSL certificate (https)
- [ ] Check Core Web Vitals (Vercel Analytics)

**Success:** Homepage loads <2s, search completes <3s on live URL

### 1.3 DNS & Domain Setup
**Goal:** routemaster.in or routemaster.io live  
**Owner:** DevOps lead

- [ ] Buy domain (Namecheap / GoDaddy)
- [ ] Point DNS to Vercel (frontend)
- [ ] Create subdomain `api.routemaster.in` → Render backend
- [ ] Update Render + Vercel env vars with real domain
- [ ] SSL certificates auto-generated by Vercel + Render
- [ ] Test: `curl https://api.routemaster.in/health` → 200

**Success:** routemaster.in loads, API responds at api.routemaster.in

### 1.4 Post-Deployment Testing
**Goal:** All features work in production  
**Owner:** QA team

**Search Functionality (Checkpoint 1-5: Algorithm):**
- [ ] 20 city pairs tested:
  - Delhi ↔ Mumbai (high volume)
  - Delhi ↔ Bangalore
  - Mumbai ↔ Kolkata
  - Chennai ↔ Delhi
  - Hyderabad ↔ Bangalore
  - (15 more popular routes)
- [ ] Each route returns:
  - ≥1 direct train
  - ≥1 transfer route
  - Real fares from erail.in
  - Live delays from rappid.in
  - IRCTC booking links
- [ ] Latency: all <2 seconds
- [ ] Accuracy: fares match IRCTC website (+/- 5%)

**PNR Status (Checkpoint 6: Safety/Support):**
- [ ] Test PNR lookup: 5 real PNRs from IRCTC
- [ ] Response shows: booking status, berth, coach, chart status
- [ ] Latency: <3 seconds
- [ ] Graceful fallback if API down

**Live Train Status (Checkpoint 3: Time Prediction):**
- [ ] Get 5 live trains running today
- [ ] Current station, next station, delay all correct
- [ ] Delay matches IRCTC/RailRadar (+/- 5 mins)
- [ ] Updates every 60 seconds

**Accessibility (Checkpoint 10: Accessibility):**
- [ ] Test with screen reader (NVDA/JAWS)
- [ ] All buttons, links, inputs keyboard-accessible
- [ ] Color contrast ≥4.5:1 (WCAG AA)
- [ ] No console accessibility errors

**Mobile Responsiveness:**
- [ ] Test on iPhone 12, Samsung Galaxy S21
- [ ] All pages load, search works, results readable
- [ ] Touch targets ≥44x44px
- [ ] No horizontal scroll

**Success Criteria:**
- [ ] All 20 city pairs search successfully
- [ ] Latencies <2s (95th percentile)
- [ ] No 500 errors in logs
- [ ] Fares match IRCTC within 5%
- [ ] Mobile UI works on 2+ devices

---

## PHASE 2: SAFETY & SUPPORT INFRASTRUCTURE (Week 3) — Trusted Travel

### 2.1 SOS Emergency System
**Goal:** Traveler can press SOS → immediate help  
**Owner:** Support lead + Backend

- [ ] Configure Twilio (SMS + voice)
  - Phone numbers for support team
  - SMS template for SOS alerts
  - Voice IVR menu (optional)
- [ ] Backend SOS endpoints live:
  - `POST /api/v1/sos/trigger` → stores SOS + sends SMS to support
  - `GET /api/v1/sos/{id}` → returns SOS status
  - Real-time location tracking
- [ ] Support team setup:
  - Dedicated 24/7 team (min. 2 people per shift)
  - Training: 50 common travel problems
  - Response SLA: <5 minutes
  - Escalation path for police/medical
- [ ] Test: Trigger SOS → SMS received in <30 seconds
- [ ] Test: Re-route traveler → alternative route in <2 minutes

**Checkpoint 7-9 satisfied:** Emergency support + real-time incident detection + live agent routing

### 2.2 Fare Alerts System
**Goal:** Traveler sets price threshold → notified when fare drops  
**Owner:** Backend + Frontend

- [ ] Frontend: Route card has "🔔 Set Fare Alert" button
  - Modal: enter threshold price + email/Telegram contact
  - Save alert to DB
- [ ] Backend daily job: `POST /api/v1/alerts/check`
  - Fetches current fares from erail.in
  - Compares to alert thresholds
  - Sends Telegram/email if fare ≤ threshold
  - 24h cache to avoid spam
- [ ] Test:
  - Set alert for Delhi-Mumbai: "Notify if <₹1000"
  - Wait 1 day (or manually trigger check)
  - Verify notification sent

**Checkpoint 4 satisfied:** Cost optimization + price tracking

### 2.3 Safety Scoring System
**Goal:** Every route gets safety score (1-100)  
**Owner:** Backend lead

- [ ] Safety scoring formula:
  - Crime data at transfer points (10%)
  - Lighting/pedestrian safety on walk segments (10%)
  - Crowd density during travel time (10%)
  - Woman-safety rating (20%)
  - Accessibility (15%)
  - Timeliness/reliability (25%)
  - Night travel surcharge (10%)
- [ ] Data sources:
  - OpenCrimeMap / local crime databases
  - Google Maps reviews (safety keywords)
  - Historical delay patterns
  - User feedback (crowded? safe?)
- [ ] Frontend: Route card shows safety badge
  - 🟢 Green (80-100): Very Safe
  - 🟡 Yellow (60-79): Moderate
  - 🔴 Red (0-59): Risky
- [ ] Test: Mumbai-Delhi at midnight should be 🟡 or 🔴

**Checkpoint 6 satisfied:** Safety route scoring

### 2.4 24/7 Support Chatbot
**Goal:** Answer 50+ common traveler questions  
**Owner:** AI lead

- [ ] Integrate Gemini API (already in env)
- [ ] Train chatbot on FAQ:
  - "What time should I leave home?"
  - "Can I bring my bike?"
  - "Is this route safe at night?"
  - "Do I need a transfer card?"
  - "What if I miss the transfer?"
  - (45+ more)
- [ ] Frontend: Chat widget in bottom-right of all pages
- [ ] Backend: `POST /api/v1/chat` → uses Gemini to answer
- [ ] Success metric: 90% of questions answered without escalation

**Checkpoint 21 satisfied:** Pre-journey support chatbot

---

## PHASE 3: DATA INTEGRATION & ACCURACY (Week 4) — Real-Time Intelligence

### 3.1 Real-Time GTFS Feed Integration
**Goal:** Latest train schedules updated every 5 minutes  
**Owner:** Data engineer

- [ ] Monitor 5 Indian Railway GTFS feeds:
  - IRCTC official
  - Third-party aggregators (if available)
- [ ] Cron job: fetch every 5 minutes
  - Compare to existing data
  - Update if changes detected
  - Log all changes for audit
- [ ] Test: Check if 12951 (Rajdhani) schedule matches IRCTC
- [ ] Fallback: If feed down >10min, alert support team

**Checkpoint 16 satisfied:** GTFS data coverage ≥150 agencies

### 3.2 Real-Time Delay Feed Integration
**Goal:** Traveler sees live delays <1 minute old  
**Owner:** Data engineer

- [ ] Already integrated: rappid.in (live train status)
- [ ] Add: IRCTC's "Running Status" feed (if exposed)
- [ ] Caching: Redis cache with 60s TTL
- [ ] Fallback: If live feed down, show last-known position + disclaimer
- [ ] Test: Get live status for 12951 → matches IRCTC.co.in

**Checkpoint 17 satisfied:** Real-time data streaming ≤30s latency

### 3.3 Crowding Data Integration
**Goal:** Travelers see which trains/coaches are crowded  
**Owner:** Data engineer

- [ ] Data sources:
  - Google Maps "crowdedness" if available
  - Historical patterns (peak hours always crowded)
  - User crowding reports via in-app feature
  - Indian Railways occupancy if exposed
- [ ] Crowding score per train per coach:
  - 1-3 (empty)
  - 4-7 (moderate)
  - 8-10 (packed)
- [ ] Frontend: Route card shows crowding indicator
- [ ] Test: 12951 at 6pm should show 8-10 (peak time)

**Checkpoint 19 satisfied:** Crowding data integration ≥85% accuracy

### 3.4 Weather & Disruption Monitoring
**Goal:** Alert travelers to delays caused by weather/incidents  
**Owner:** Data engineer

- [ ] OpenWeatherMap API: hourly forecasts for origin/destination
- [ ] Severe weather triggers:
  - Heavy rain → flood risk on walking segments
  - Fog → potential delays on routes
  - Storms → lightning safety
- [ ] Incident monitoring:
  - Social media keyword search (Twitter: "train delayed")
  - RSS feeds from railway news sites
- [ ] Alert traveler: "Heavy rain forecast at Delhi station. Routes via NDLS may be delayed."

**Checkpoint 18 satisfied:** Weather & disruption data integration

### 3.5 Accuracy Benchmarking
**Goal:** Route accuracy ≥98%, time prediction ±3-5 minutes  
**Owner:** QA lead

- [ ] Daily accuracy report:
  - Sample 100 searches from past 24h
  - Compare routes to IRCTC's recommendation
  - Measure: match rate, lateness of predictions
  - Target: ≥98% route accuracy, ±5min time
- [ ] Weekly report to leadership
- [ ] Any drop below 95% triggers incident response

**Checkpoint 1-5 satisfied:** Algorithm accuracy validated daily

---

## PHASE 4: USER SUPPORT & EXPERIENCE (Week 5) — Traveler Success

### 4.1 In-App Guided Navigation
**Goal:** Traveler never gets lost at station  
**Owner:** Frontend lead

- [ ] Mid-journey features:
  - "You arrive at Delhi station in 45 mins"
  - Next platform number once arrived
  - Walking time to platform: 5 mins
  - Photos/video of complex transfer station
  - "Boarding in 10 minutes" alert
- [ ] Post-journey: "Did this route work as expected?"
  - Feedback form
  - Issue resolution tool

**Checkpoint 22 satisfied:** Mid-journey support

### 4.2 Support Escalation Path
**Goal:** If chatbot can't help → human agent in <2 minutes  
**Owner:** Support lead

- [ ] Chatbot → human handoff
  - "This is complex, connecting you to support team"
  - Queue traveler
  - Show wait time
- [ ] Support team response: <2 minutes
- [ ] Support team training:
  - 50+ problem types
  - Scripts for common scenarios
  - Escalation to police/medical if needed
- [ ] Support metrics tracked daily:
  - Response time
  - Resolution rate
  - Satisfaction (post-chat survey)

**Checkpoint 23 satisfied:** Post-journey follow-up + issue resolution

### 4.3 Accessibility Support Program
**Goal:** Blind/deaf/mobility-impaired travelers fully supported  
**Owner:** Accessibility specialist

- [ ] Audio navigation:
  - Screen reader compatible (ARIA labels)
  - Voice instructions via text-to-speech
  - High contrast mode
- [ ] Deaf support:
  - Video captions on all in-app videos
  - SMS alerts instead of notifications
  - Text-only support chat
- [ ] Mobility support:
  - Wheelchair-accessible route filtering
  - Porter booking (if available)
  - Accessible seating recommendations
- [ ] Support team training: disability sensitivity
- [ ] Test with 20+ accessibility specialists
- [ ] Satisfaction: ≥95%

**Checkpoint 24 satisfied:** Accessibility support program

### 4.4 Gamification & Loyalty
**Goal:** Travelers love using Route Master  
**Owner:** Product lead

- [ ] Rewards system:
  - 10 points per journey
  - 50 points = ₹50 coupon on next booking
  - Leaderboard (monthly/yearly)
  - Badges (early bird, night owl, explorer)
- [ ] Referral: Invite friend → both get 100 points
- [ ] Social: Share journey on Twitter/Whatsapp with custom link
- [ ] Community: Travelers help other travelers earn badges

**Checkpoint 23 satisfied:** Gamification increases usage

---

## PHASE 5: PRODUCTION READINESS & OPERATIONS (Week 6) — Enterprise Grade

### 5.1 Monitoring & Observability
**Goal:** Know system health in real-time  
**Owner:** DevOps lead

- [ ] Metrics tracked (per Checkpoint 25):
  - Uptime: target 99.9% (≤8.6 hrs downtime/year)
  - P95 latency: all requests <2s
  - Error rate: <0.1%
  - API quota usage (RapidAPI: 7000/mo)
  - Redis memory usage
  - Supabase query performance
- [ ] Dashboards:
  - Render dashboard: uptime, error logs
  - Vercel Analytics: page load times, CWV
  - Custom dashboard: API metrics via Prometheus/Grafana
- [ ] Alerts:
  - Uptime drop <99%
  - P95 latency >3s
  - Error rate >1%
  - RapidAPI quota >90%
  - Redis memory >80%
- [ ] On-call rotation: 24/7 coverage

**Checkpoint 25 (part 1) satisfied:** Production monitoring

### 5.2 Failure Recovery & Testing
**Goal:** System handles any single failure without downtime  
**Owner:** DevOps lead

- [ ] Failure scenarios tested:
  - Database unavailable → fallback to cache
  - Redis down → queries slower but work
  - External API (erail.in) down → use estimates
  - Render API server crashes → auto-restart
  - GTFS data corrupt → rollback to last known good
- [ ] Recovery time: <5 minutes for any failure
- [ ] Runbooks: written steps for each failure type
- [ ] Monthly chaos engineering test: randomly kill services

**Checkpoint 25 (part 2) satisfied:** Failure recovery <5 min

### 5.3 Capacity Planning
**Goal:** System handles 10x growth without degrading  
**Owner:** DevOps + Backend lead

- [ ] Current capacity:
  - 100 concurrent users → ?ms latency
  - 1000 searches/day → ?% Render CPU
  - 10GB GTFS data → ?% Supabase storage
- [ ] Load testing:
  - Simulate 1,000 concurrent users
  - Measure CPU, memory, database connections
  - Identify bottleneck
  - Scale if needed (Render worker count, Supabase upgrade)
- [ ] Growth plan:
  - At 100K users: upgrade Render to standard plan
  - At 1M users: migrate to Kubernetes + multi-region
- [ ] Cost tracking: daily spend, cost per user

**Checkpoint 25 (part 3) satisfied:** Capacity planning

### 5.4 Legal & Compliance
**Goal:** 100% compliant with laws  
**Owner:** Legal + DevOps lead

- [ ] Privacy:
  - GDPR compliant: right to deletion, consent
  - CCPA/local India laws: data residency
  - Terms of Service updated
  - Privacy Policy updated
- [ ] Data handling:
  - No personal data stored >7 days after journey
  - No sharing with third parties without consent
  - Encryption at rest (Supabase) + in transit (HTTPS)
- [ ] Liability:
  - Insurance: cyber liability, errors & omissions
  - Disclaimers: Route Master not responsible for missed trains
  - SLA: 99.9% uptime, but no refunds
- [ ] Security audit:
  - Penetration testing (once per 6 months)
  - Code review for SQL injection, XSS, CSRF
  - Dependency scan for vulnerabilities

**Checkpoint 20 satisfied:** Privacy compliance 100%

### 5.5 Support Team Readiness
**Goal:** 24/7 support team trained + operational  
**Owner:** Support lead

- [ ] Team:
  - Hiring: 4-5 support agents (for 100K users)
  - Training: 2 weeks on railway domain + support tools
  - Shifts: 6am-2pm, 2pm-10pm, 10pm-6am IST
  - Min 2 people per shift (backup if one sick)
- [ ] Tools:
  - Slack: support team communication + alerts
  - Zendesk or Intercom: ticket tracking
  - Telegram: direct communication with travelers
  - Escalation: SOS → police/medical → Telegram to on-call manager
- [ ] Metrics:
  - Response time: <2 minutes
  - Resolution rate: >80% on first contact
  - Customer satisfaction: ≥4.5/5

**Checkpoint 7-10, 23 satisfied:** Support team ready 24/7

### 5.6 Pre-Launch Checklist
**Goal:** All 25 checkpoints achieved before launch  
**Owner:** Product lead

**Verify all 25 checkpoints:**

✅ Checkpoint 1-5: Algorithm accuracy ≥98%, latencies <2s  
✅ Checkpoint 6-10: Safety scoring, SOS, incident detection, re-routing, accessibility  
✅ Checkpoint 11-15: Complex hubs, connections, luggage, groups, language  
✅ Checkpoint 16-20: GTFS coverage, real-time data, weather, crowding, privacy  
✅ Checkpoint 21-24: Chatbot, mid-journey, follow-up, accessibility support  
✅ Checkpoint 25: Uptime 99.9%, P95 <2s, 10x load tested, team ready  

**Additional checks:**
- [ ] 10,000+ beta testers with ≥4.5/5 rating
- [ ] No known critical bugs
- [ ] All env vars secured
- [ ] Deployment scripts tested
- [ ] Support team onboarded
- [ ] Monitoring dashboards live
- [ ] Investor/stakeholder sign-off
- [ ] Legal review complete
- [ ] No open critical security issues

**Sign-off:**
- [ ] CTO: Code quality ✅
- [ ] Product: Features complete ✅
- [ ] Support: Team ready ✅
- [ ] Legal: Compliant ✅
- [ ] Founder: Ready to launch ✅

---

## Critical Path (Fastest Route to Production)

**Week 1 (Phase 0):** Fix secrets + test locally (3 days)
- Day 1: Generate JWT_SECRET, add RAPIDAPI_KEY
- Day 2: Run schema_check + seed_data
- Day 3: verify.py + local testing

**Week 2 (Phase 1):** Deploy to production (3 days)
- Day 4: Deploy backend to Render
- Day 5: Deploy frontend to Vercel
- Day 6: Full production testing (20 city pairs)

**Week 3 (Phase 2):** Safety infrastructure (5 days)
- Setup Twilio SOS
- Launch fare alerts
- Build safety scoring
- Deploy chatbot

**Week 4 (Phase 3):** Data accuracy (3 days)
- Real-time GTFS integration
- Crowding data
- Accuracy benchmarking

**Week 5 (Phase 4):** UX polish (3 days)
- In-app navigation
- Support escalation
- Accessibility testing

**Week 6 (Phase 5):** Ops readiness (3 days)
- Monitoring setup
- Capacity testing
- Legal compliance + sign-off

**Total:** 42 days → Ready for public launch June 18, 2026

---

## Success Metrics at Launch

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Uptime | 99.9% | Render dashboard |
| P95 Latency | <2s | Vercel Analytics |
| Route Accuracy | ≥98% | Daily sampling vs IRCTC |
| Support Response | <2 min | Zendesk ticket data |
| Beta Rating | ≥4.5/5 | App store/TestFlight |
| Fares Match IRCTC | ±5% | Spot checks |
| Safety Score Valid | ≥85% accuracy | User feedback |
| Mobile Load | <3s | Lighthouse |
| Zero Critical Bugs | All fixed | QA sign-off |
| Compliance | 100% | Legal audit |

---

## Start Date: Monday, June 9, 2026
## Target Launch: Thursday, June 18, 2026
## Ready to execute? → Confirm, and we begin Phase 0 immediately.
