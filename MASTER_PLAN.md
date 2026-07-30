# Route Master — Master Plan & Product Roadmap
**Company:** NeuralForge  
**Product:** Route Master — India's smartest train route optimizer  
**Last updated:** June 5, 2026

---

## THE MISSION

> A traveller types Station A → Station B + date.  
> Route Master shows every possible train route — direct and multi-transfer —  
> with live delays, real fares, ranked by time/cost/reliability, in under 2 seconds.  
> One tap books on IRCTC.

**That's it. Everything else is secondary.**

---

## WHAT'S LIVE TODAY (June 5, 2026)

### ✅ Built & working
| Feature | Endpoint | Status |
|---------|----------|--------|
| Station autocomplete | `GET /api/v1/stations/suggest` | ✅ Trie index + DB fallback |
| Route search | `GET /api/v1/search/routes` | ✅ Direct + 1-transfer |
| Real IRCTC fares | `GET /api/v1/fare/{train}` | ✅ erail.in scrape |
| Live train status | `GET /api/v1/live/train/{no}` | ✅ rappid.in (free, unlimited) |
| PNR status | `GET /api/v1/pnr/{pnr}` | ✅ RapidAPI (needs key) |
| SOS alert | `POST /api/v1/sos/trigger` | ✅ Twilio SMS + tracking URL |
| Auth (register/login) | `POST /api/v1/auth/*` | ✅ JWT + bcrypt |
| Health/stats | `GET /health`, `/stats` | ✅ |

### ✅ Frontend built
- Search form (IRCTC-style, dark header)
- Station autocomplete dropdown
- Route cards with "Book on IRCTC" button
- Train tracking page (`/track/:trainNumber`)
- SOS page with live location
- Auth pages (login, signup)
- Admin dashboard
- Mobile-first responsive

---

## PHASE GOALS

### PHASE 1 — LAUNCH (This week)
**Goal:** First real user gets train route results  
**Success criteria:**
- [ ] `GET /health` returns 200 from Render URL
- [ ] Station search returns results in < 500ms
- [ ] Route search for NDLS→BCT returns ≥ 3 routes in < 3s
- [ ] IRCTC booking link opens correct page
- [ ] Frontend loads on mobile browser without errors
- [ ] 5 different city pairs all return results

**Remaining work:**
1. Deploy backend to Render (see DEPLOY.md — 30 min)
2. Deploy frontend to Vercel (see DEPLOY.md — 15 min)
3. Set VITE_API_URL in Vercel to Render URL
4. Test 5 searches manually

### PHASE 2 — RETENTION (Week 2-3)
**Goal:** Users come back. Saved routes. PNR check.  
- Add RAPIDAPI_KEY for PNR status
- Test login/signup flow end-to-end
- Add saved routes feature
- Add PNR status page

### PHASE 3 — SAFETY (Week 4)
**Goal:** SOS differentiator live  
- Add TWILIO keys
- Test SOS trigger → SMS to contacts
- Build emergency contacts UI
- Live location tracking on responder page

### PHASE 4 — GROWTH (Month 2+)
**Goal:** 1000+ daily users  
- SEO: station-pair landing pages (e.g. `/trains/ndls-to-bct`)
- Share route feature
- Telegram bot for quick searches
- Analytics (Plausible or Posthog — free tier)

---

## ALGORITHM: HOW ROUTE SEARCH WORKS

```
User: NDLS → BCT, 2026-06-15

1. TurboRouter (direct trains)
   → SQL: trips where from_stop=NDLS and to_stop=BCT in sequence
   → Returns: [Rajdhani 12951, Aug Kranti 12953, ...]

2. Hub Intersection (1-transfer)
   → IF direct_trains < 3:
   → Check 15 major hub stations (NDLS, BCT, PUNE, MAS, HWH...)
   → For each hub: find leg1 (NDLS→hub) + leg2 (hub→BCT)
   → Match by layover time (45min to 4hr window)
   → Returns: [NDLS→PUNE→BCT via Deccan Queen + Konkan Kanya, ...]

3. Real fare injection
   → For first train: fetch erail.in (actual IRCTC fares)
   → Apply to all journeys on same route

4. Ranking
   → Sort by: duration × 0.4 + cost × 0.3 + reliability × 0.3

5. Response
   → BackendRoutesResponse format
   → Frontend: mapBackendRoutesToRoutes()
   → Display: RouteCard with "Book on IRCTC" → irctc_url
```

---

## DATA SOURCES

| Data | Source | Freshness | Cost |
|------|--------|-----------|------|
| Train schedules | Supabase GTFS | Static (update monthly) | Free |
| Live running status | rappid.in | 60s cache | Free, unlimited |
| Real fares | erail.in | 24h cache | Free, unlimited |
| PNR status | RapidAPI IRCTC | 5min cache | 500 calls/mo free |
| SOS SMS | Twilio | Real-time | $15 trial |

---

## EFFICIENCY GUIDELINES (Limited tokens / API calls)

These rules protect our free tiers:

1. **Redis cache everything** — live status (60s), fares (24h), stations (24h)
2. **rappid.in for all live train status** — unlimited, never RapidAPI
3. **RapidAPI only for PNR** — never for live status
4. **erail.in for fares** — unlimited, 24h cache
5. **IRCTC redirect for booking** — never try to build native booking
6. **erail.in for seat class info** — don't scrape IRCTC directly

---

## ARCHITECTURE (Stay simple until 10k users)

```
[Vercel] React App
    ↓ HTTPS
[Render.com] FastAPI (1 worker, 512MB)
    ↓           ↓           ↓
[Supabase]  [Upstash]   [rappid.in]
 PostgreSQL   Redis       Live status
 GTFS data    Cache       (free, unlimited)
```

**What we DO NOT add until 50k users:**
- Kafka / message queues
- Multiple microservices  
- Kubernetes / Docker Swarm
- ML serving infrastructure
- Multiple database shards

---

## TEAM ROLES (AI Agents)

| Agent | Role | Focus |
|-------|------|-------|
| SIGMA | Backend | FastAPI, data_provider, search algorithm |
| ORION | Frontend | React, UI components, API wiring |
| DAEDALUS | DevOps | Deploy configs, CI/CD, monitoring |
| NOVA | Data | GTFS import, DB schema, data quality |

---

## SUCCESS METRICS (Track from day 1)

| Metric | Target Week 1 | Target Month 1 |
|--------|--------------|----------------|
| Daily searches | 10 | 500 |
| Search success rate (≥1 result) | 80% | 90% |
| Search latency (p95) | < 3s | < 1.5s |
| IRCTC click-through rate | 20% | 35% |
| Daily active users | 5 | 100 |

**Add analytics:** Install Plausible (€9/mo) or Posthog (free) on day 1.

---

## OPEN ACTIONS (In priority order)

1. **[TODAY]** Run `python verify.py` locally — confirm Supabase + Redis
2. **[TODAY]** Deploy to Render + Vercel (follow DEPLOY.md)
3. **[TODAY]** Test NDLS→BCT search end-to-end in browser
4. **[THIS WEEK]** Buy domain `routemaster.in` (~₹1000/yr)
5. **[THIS WEEK]** Add Google Analytics or Plausible
6. **[THIS WEEK]** Get RAPIDAPI_KEY for PNR status
7. **[NEXT WEEK]** Invite 5 beta users, collect feedback
