# RouteMaster V2 — MVP Build Roadmap & Quick Start

**Status:** 🚀 Ready to Build  
**Target Completion:** 10 features → 40-50 hours of focused build  
**Launch Target:** 2-3 weeks

---

## QUICK REFERENCE: WHAT'S HAPPENING

### The Situation
- 50+ features exist as code, components, sketches, ideas
- **Problem:** They're not integrated, not wired, not production-ready
- **Goal:** Pick them one by one, complete them fully (audit → design → build → test → optimize), make them work together
- **Outcome:** Professional startup MVP with all core features working

### The Process (8 Phases per Feature)
1. **Audit** — What exists? What's missing?
2. **Design** — Workflows, screens, databases, APIs
3. **Plan** — Step-by-step implementation roadmap
4. **Build** — Code, APIs, integrations
5. **Test** — Unit, integration, manual, security
6. **Optimize** — Performance, UX, reliability
7. **Document** — Updates to memory files
8. **Ship** — Deploy and monitor

---

## FEATURE BUILD QUEUE

### ✅ COMPLETED
- Feature #1: Booking Flow & Payment — **DESIGN PHASE COMPLETE** (see `FEATURE_01_BOOKING_FLOW_COMPLETE_DESIGN.md`)

### 🎯 NEXT TO BUILD (Recommended Order)

#### Feature #2: User Dashboard (4-6h)
- Why: User retention. Shows bookings, history, profile.
- Current state: Skeleton only
- Files: `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Bookings.tsx`
- Key components: Bookings list, past journeys, saved routes, profile settings
- Dependencies: Booking DB data
- Status: After Feature #1

#### Feature #3: Email & SMS Notifications (3-4h)
- Why: Engagement. Transaction notifications + marketing.
- Current state: SendGrid API key exists, not integrated
- Key services: Email confirmation, SMS alerts, booking updates
- Dependencies: Email service integration
- Status: After Feature #1

#### Feature #4: Telegram Bot Wiring (2-3h)
- Why: Low-friction user acquisition. User search intent without login.
- Current state: Parser exists, need to wire to search + booking
- Key commands: `/search Delhi Mumbai`, `/live 12951`, `/pnr 1234567890`
- Dependencies: Search, PNR, track APIs
- Status: Can start in parallel with #1

#### Feature #5: Admin Operations Dashboard (6-8h)
- Why: Operational visibility. Monitor bookings, delays, issues.
- Current state: Skeleton only
- Key metrics: Daily searches, daily bookings, revenue, failed payments, delayed trains
- Real-time data: Live train tracking, incident alerts
- Status: After #1, #2

#### Feature #6: Recommendations Engine (6-8h)
- Why: Engagement & upsell. "Users also searched...", "Best time to travel..."
- Current state: Zero
- Algorithm: Collaborative filtering (user search patterns) + content-based (route similarity)
- Status: After Feature #2 (need booking/search history)

#### Feature #7: Ratings & Reviews System (4-5h)
- Why: Trust & UX. User-generated content for SEO.
- Current state: Zero
- Key: Post-journey review form, aggregate ratings, display on train pages
- Status: After #1 (need completed bookings)

#### Feature #8: Push Notifications (3-4h)
- Why: Re-engagement. Departure reminders, delay alerts, special offers.
- Current state: Zero
- Tech: Firebase Cloud Messaging + service worker
- Status: After #1 (have user bookings to target)

#### Feature #9: Admin Finance Dashboard (4-6h)
- Why: Revenue tracking. Commission, payouts, disputes.
- Current state: Skeleton only
- Metrics: Revenue by route, by class, by booking source, payout schedule
- Status: After #1, #5

#### Feature #10: Refund & Cancellation Flow (3-4h)
- Why: User experience. Reduce support load.
- Current state: Backend skeleton, frontend zero
- Key: User-initiated cancellation, automatic refunds, policy clarity
- Status: After #1 (built into booking feature)

---

## DETAILED BUILD PLAN

### WEEK 1: Core Payment & User Features

**Day 1-2: Feature #1 - Booking & Payment (Primary)**
- [ ] Create booking tables in Supabase
- [ ] Build BookingService (create, confirm, list)
- [ ] Build PaymentService (Razorpay order, verification)
- [ ] Wire frontend to backend
- [ ] Test end-to-end payment flow
- Estimated: 12-15 hours
- Owner: You (follow `FEATURE_01_BOOKING_FLOW_COMPLETE_DESIGN.md`)

**Day 2-3: Feature #4 - Telegram Bot Wiring (Parallel)**
- [ ] Connect /search endpoint to bot parser
- [ ] Wire bot to return routes
- [ ] Add /book command (link to web booking)
- [ ] Test all commands
- Estimated: 2-3 hours
- Owner: You
- File: `backend/api/v1/telegram.py` (modify)

**Day 3-4: Feature #3 - Email/SMS Notifications (After #1)**
- [ ] Set up SendGrid client
- [ ] Create email templates (booking confirmation, alerts)
- [ ] Create SMS templates (Twilio)
- [ ] Wire to booking confirmation
- [ ] Test delivery
- Estimated: 3-4 hours
- Owner: You

---

### WEEK 2: Dashboard & Admin

**Day 5-6: Feature #2 - User Dashboard (After #1)**
- [ ] Build Dashboard.tsx with booking tabs (Upcoming, Past, Cancelled)
- [ ] Fetch user bookings from /api/v1/bookings/my
- [ ] Build Bookings.tsx with detailed view
- [ ] Add filters (date, status, train)
- [ ] Add action buttons (track, cancel, review)
- Estimated: 4-6 hours
- Owner: You

**Day 7-8: Feature #5 - Admin Operations Dashboard (Parallel)**
- [ ] Build AdminOperations.tsx with live metrics
- [ ] Wire to backend /api/v1/admin/metrics
- [ ] Create backend metrics aggregation
- [ ] Display: searches/day, bookings/day, revenue/day, delayed trains
- [ ] Real-time updates (WebSocket or polling)
- Estimated: 6-8 hours
- Owner: You

---

### WEEK 3: Engagement & Trust

**Day 9-10: Feature #7 - Ratings & Reviews (After #1)**
- [ ] Create reviews table
- [ ] Build post-journey review form
- [ ] Build train review aggregation
- [ ] Display on TrainSchedule and CityPairRoutes pages
- [ ] Test end-to-end
- Estimated: 4-5 hours
- Owner: You

**Day 10-11: Feature #8 - Push Notifications (After #1)**
- [ ] Set up Firebase Cloud Messaging
- [ ] Create service worker
- [ ] Build notification subscription flow
- [ ] Send test notifications
- [ ] Build admin notification sender
- Estimated: 3-4 hours
- Owner: You

**Day 11-12: Feature #6 - Recommendations (After #2)**
- [ ] Build recommendation algorithm
- [ ] Create reco tables in DB
- [ ] Wire to search results
- [ ] Display "Users also searched"
- [ ] Display "Best time to travel"
- Estimated: 6-8 hours
- Owner: You

---

### WEEK 4: Finalization

**Day 13-14: Testing & Optimization**
- [ ] Run full regression testing
- [ ] Performance optimization (Lighthouse)
- [ ] Security audit
- [ ] Load testing (10 concurrent bookings)
- Estimated: 4-6 hours

**Day 15: Deployment & Launch**
- [ ] Deploy all changes to production
- [ ] Verify all features work on live
- [ ] Monitor errors, metrics
- [ ] Quick rollback plan ready

---

## DEPENDENCY MAP

```
Feature #1: Booking & Payment ✅ (DESIGN DONE)
  ├─ Feature #2: Dashboard (depends on #1 bookings)
  ├─ Feature #3: Notifications (depends on #1 booking data)
  ├─ Feature #7: Reviews (depends on #1 completed bookings)
  ├─ Feature #8: Push (depends on #1 user bookings)
  └─ Feature #6: Recommendations (depends on #2 booking history)

Feature #4: Telegram Bot Wiring (independent)

Feature #5: Admin Dashboard (depends on #1 bookings)
  └─ Feature #9: Finance Dashboard (depends on #5 + payment data)

Feature #10: Refund Flow (part of Feature #1)
```

---

## HOW TO USE THESE DOCUMENTS

### For Feature #1 (Booking Flow)
1. Read `FEATURE_01_BOOKING_FLOW_COMPLETE_DESIGN.md` (entire document)
2. Start with database migrations (Part 3)
3. Build backend services (Part 6)
4. Wire frontend (Part 5)
5. Test end-to-end (Part 7)
6. Mark complete, move to Feature #2

### For Future Features
1. Create `FEATURE_XX_NAME_COMPLETE_DESIGN.md`
2. Follow same 8-phase structure
3. Update this roadmap

---

## CURRENT PROJECT STATE (Snapshot)

### ✅ What Works
- Route search (GTFS data, fare APIs)
- Station autocomplete
- Live train tracking
- PNR status lookup
- Authentication (Firebase + JWT)
- SOS/Safety features
- Fare alerts (Telegram)
- Telegram bot (partially)
- Database (Supabase GTFS)
- Caching (Redis)
- Frontend UI components (comprehensive)
- Admin dashboard skeletons (30+ pages)

### ❌ What's Missing / Broken
- Booking system (no order creation, no payment flow)
- User dashboard (no data, no wiring)
- Payment integration (keys exist, not wired)
- Email service (not wired)
- Admin dashboards (empty)
- Notifications (not built)
- Recommendations (not built)
- Reviews (not built)
- Refunds (partial)

### 📊 Architecture Score
| Aspect | Status | Gap |
|--------|--------|-----|
| Backend APIs | 60% | Missing booking/payment endpoints |
| Database | 70% | Missing booking/payment tables |
| Frontend | 50% | Many empty components, missing integration |
| Testing | 10% | Minimal test coverage |
| Deployment | 70% | Ready, not tested with features |
| Documentation | 40% | Good memory, missing feature docs |

---

## METRICS TO TRACK

As you build each feature, measure:

```
Feature #1 (Booking)
  - Booking completion rate (✓ by day 1)
  - Payment success rate (goal: >95%)
  - Email delivery rate (goal: >98%)
  - Average booking time (goal: <3 min)
  - Refund processing time (goal: <24h)

Feature #2 (Dashboard)
  - Dashboard load time (goal: <2s)
  - User engagement (bookings viewed)
  - Repeat booking rate

Feature #3+ (follow similar pattern)
```

---

## CRITICAL SUCCESS FACTORS

1. **Execute sequentially** — Don't try all 10 at once. One per 1-2 days.
2. **Complete each feature fully** — No "80% done". Audit → Design → Build → Test → Ship.
3. **Update memory after each feature** — Keep project state fresh for next session.
4. **Test on live before launch** — Use Razorpay test keys, then switch to live.
5. **Monitor post-launch** — Watch error rates, payment failures, email delivery.

---

## REFERENCE: FILE LOCATIONS

### Key Directories
- Backend: `C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\backend`
- Frontend: `C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\frontend`
- Database: Supabase (PostgreSQL)
- Deployment: Render (backend), Vercel (frontend)

### Key Files Created This Session
- `FEATURE_AUDIT_MASTER.md` — All 50 features listed & ranked
- `FEATURE_01_BOOKING_FLOW_COMPLETE_DESIGN.md` — Complete design for Feature #1
- `MVP_BUILD_ROADMAP.md` — This document

---

## NEXT IMMEDIATE STEPS (Do This Now)

1. **Read** `FEATURE_01_BOOKING_FLOW_COMPLETE_DESIGN.md` (30 min)
2. **Create** database migrations file (already planned)
3. **Create** SQLAlchemy models for Booking, Payment, Ticket (1h)
4. **Create** BookingService class skeleton (1h)
5. **Test** database connections
6. **Report** back when database is ready

---

**Status:** 📋 Audit & Design Complete. Ready to Start Building.

**Owner:** Gaurav (execute sequentially)  
**Support:** Use memory files + this roadmap  
**Target:** Launch with 10 features fully integrated in 2-3 weeks

Good luck! 🚀
