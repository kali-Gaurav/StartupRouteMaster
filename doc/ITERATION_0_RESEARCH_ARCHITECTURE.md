# ITERATION 0: Comprehensive Research & Architecture Analysis

**Date:** July 11, 2026  
**Status:** Research Complete - Ready for Implementation  
**Scope:** Full codebase analysis, architecture mapping, dependency graph

---

## 1. PROJECT OVERVIEW

### Mission
RouteMaster is a **railway route optimization and booking platform** that:
- Finds optimal multi-segment railway routes between any two Indian cities
- Verifies seat availability and fares via IRCTC API (RapidAPI)
- Manages automated/manual booking queue system
- Handles payments via Razorpay (₹39 unlock fee + booking amounts)
- Provides real-time tracking and notifications

### Current Status
- **Deployment Readiness:** ~40% 
- **Backend:** FastAPI framework mostly complete with gaps in booking queue execution
- **Frontend:** React/TypeScript UI partially built, admin dashboard missing
- **Database:** PostgreSQL (Supabase) schema defined, migrations in Alembic
- **ML/AI:** Pre-trained models available (delay prediction, route ranking, tatkal demand)
- **Integrations:** Supabase, RapidAPI (partially), Razorpay, Redis, Kafka ready

---

## 2. ARCHITECTURE OVERVIEW

### High-Level System Design
```
┌─────────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│ Frontend: React 18.3 + TypeScript + Tailwind CSS + Vite         │
│ - Route Search Interface                                         │
│ - Booking Checkout Flow                                         │
│ - Admin Dashboard (TODO)                                        │
│ - Booking History & Management                                  │
│ - Real-time Notifications                                       │
└────────────────────┬────────────────────────────────────────────┘
                     │ REST API + WebSockets
┌────────────────────▼────────────────────────────────────────────┐
│               API & APPLICATION LAYER                            │
├─────────────────────────────────────────────────────────────────┤
│ Backend: FastAPI 0.109 + Uvicorn + SQLAlchemy 2.0               │
│                                                                  │
│ API Routes:                                                      │
│ ├─ /api/search → Route search (RAPTOR engine)                   │
│ ├─ /api/bookings → Booking queue management                     │
│ ├─ /api/payments → Razorpay integration                         │
│ ├─ /api/stations → Station master data                          │
│ ├─ /api/realtime → Live seat availability (WebSocket)           │
│ ├─ /api/admin → Admin dashboard endpoints                       │
│ ├─ /api/users → User profiles & history                         │
│ └─ /api/chat → AI assistant for route help                      │
│                                                                  │
│ Core Services:                                                   │
│ ├─ Route Engine (RAPTOR + hubbing)                              │
│ ├─ Booking Service (queue-based execution)                      │
│ ├─ Search Service (hybrid query + ML ranking)                   │
│ ├─ Payment Service (Razorpay integration)                       │
│ ├─ Verification Service (RapidAPI/IRCTC)                        │
│ └─ ML Integration (delay prediction, ranking)                   │
│                                                                  │
│ Background Workers:                                              │
│ ├─ Celery tasks (booking execution, notifications)              │
│ ├─ APScheduler jobs (cache warming, data sync)                  │
│ └─ Kafka consumers (real-time event streaming)                  │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼──┐  ┌──────▼──┐  ┌─────▼────┐
│ Database │  │  Cache  │  │  Message │
│ Layer    │  │  Layer  │  │  Queue   │
└──────────┘  └─────────┘  └──────────┘
```

### Technology Stack

#### Backend
- **Framework:** FastAPI 0.109, Uvicorn 0.24, Pydantic 2.6
- **Database:** SQLAlchemy 2.0, Alembic migrations, PostgreSQL (Supabase)
- **Caching:** Redis 5.0, FastAPI-Cache2
- **Task Queue:** Celery 5.3, Redis, Kafka (confluent-kafka 2.4)
- **Scheduling:** APScheduler 3.10
- **ML/Analytics:** scikit-learn 1.3, LightGBM 4.3, numpy, matplotlib
- **Geospatial:** GeoAlchemy2 (PostGIS)
- **Authentication:** Supabase Auth, JWT, python-jose, passlib+bcrypt
- **Integrations:** 
  - RapidAPI (IRCTC verification)
  - Razorpay (payments)
  - Twilio (SMS)
  - SendGrid (email)
  - Slack (alerts)
- **Observability:** Prometheus, Grafana, Jaeger, structured logging

#### Frontend
- **Framework:** React 18.3, React Router 6.21, Vite 7.3
- **UI:** Radix UI (20+ components), shadcn/ui patterns, Lucide icons
- **Styling:** Tailwind CSS 3.4, PostCSS
- **State Management:** React Query 5.28 (TanStack), React Hook Form 7.51
- **Validation:** Zod 3.22
- **Offline Database:** Dexie (IndexedDB)
- **Analytics:** PostHog, Sentry
- **Charts:** Chart.js
- **Utilities:** date-fns, Fuse.js (search), compromise (NLP)
- **PWA:** vite-plugin-pwa

#### Infrastructure
- **Containerization:** Docker, Docker Compose
- **Orchestration:** Kubernetes (manifests in /k8s)
- **Cloud Deployment:** Railway (backend), Vercel (frontend)
- **CI/CD:** GitHub Actions (configured in .github/)
- **Database:** PostgreSQL (Supabase managed), SQLite (offline fallback)
- **Message Broker:** Kafka + Zookeeper
- **Monitoring Stack:** Prometheus, Grafana, AlertManager, Loki, Jaeger

---

## 3. DATABASE SCHEMA

### Core Tables

#### User Management
- **users** - User accounts with email/phone authentication
- **profiles** - Supabase profile companion table (auth sync)
- **subscriptions** - Premium features and limits

#### Booking System (Queue-Based)
- **booking_requests** - User booking intent (from search results)
- **booking_queue** - Pending requests awaiting execution
- **booking_results** - Completed bookings with PNR and ticket details
- **bookings** - Direct bookings (legacy, for internal use)
- **passenger_details** - Passenger info for each booking
- **booking_transactions** - Payment transaction records
- **refunds** - Refund tracking and audit
- **execution_logs** - Booking execution audit trail

#### Route & Station Data
- **stations** - Railway station master data (~3000 stations)
- **trains** - Train schedules and metadata
- **segments** - Route segments between stops
- **stop_times** - Departure/arrival times for each segment
- **transfers** - Inter-train connections and transfer points
- **live_locations** - Real-time train tracking (GPS)

#### Seat Management
- **seat_inventory** - Seat availability snapshot
- **seat_allocations** - Allocated seats per booking

#### ML & Analytics
- **route_search_logs** - Search query logging (for ML training)
- **disruption_logs** - Train delays and cancellations
- **user_behavior** - Clickthrough, search patterns (analytics)

#### Admin & Monitoring
- **admin_actions** - Admin activity audit
- **system_health** - System metrics and alerts
- **risk_zones** - Geo-tagged risk areas
- **rate_limit_counters** - API rate limiting

### Offline Databases
- **railway_data.db** (SQLite, ~123MB) - Cached schedule data
- **transit_graph.db** (SQLite, ~88MB) - Pre-computed routing graphs for RAPTOR

---

## 4. API ENDPOINTS ARCHITECTURE

### Search & Discovery
```
GET  /api/search/routes?from=DEL&to=BLR&date=2026-07-15
     → Returns: ranked list of possible routes
     → Uses: RAPTOR engine + ML ranking + cache

GET  /api/search/route/{id}?access_token=xxx
     → Returns: detailed route info (stations, times, prices)
     → Uses: RapidAPI for live verification
     → Payment: ₹39 unlock fee required

GET  /api/stations
     → Station master data (search autocomplete)

POST /api/search/history
     → Get user's past searches
```

### Booking Management
```
POST /api/bookings/request
     Body: { route_id, passengers, preferences }
     → Creates booking_request in database
     → Returns: request_id for tracking

GET  /api/bookings/queue
     → Admin only: View pending booking queue

POST /api/bookings/execute/{request_id}
     → Admin: Execute booking from queue to IRCTC
     → Calls: RapidAPI IRCTC booking endpoint
     → Result: PNR generated or failure with refund

GET  /api/bookings/status/{request_id}
     → User: Check booking status (PENDING/CONFIRMED/CANCELLED)

GET  /api/bookings/my-bookings
     → User: View all their bookings
     → Returns: Booking history with PNRs, tickets

DELETE /api/bookings/{booking_id}
     → User: Cancel booking
     → Triggers: Refund processing
```

### Payment & Transactions
```
POST /api/payments/unlock
     Body: { unlock_amount: 39 }
     → Razorpay payment for route access
     → Returns: payment_id, order_id, verification_token

POST /api/payments/verify
     Body: { razorpay_payment_id, razorpay_signature }
     → Verify unlock payment
     → On success: Mark route as accessible for user

POST /api/payments/booking
     Body: { booking_request_id, amount }
     → Payment for booking itself
     → Only after admin confirms availability

GET  /api/payments/transactions
     → User: View payment history
     → Admin: View all transactions (with filters)
```

### Real-Time Updates
```
WebSocket /ws/bookings/{booking_id}
     → Client: Receives live status updates
     → Events: status_changed, payment_confirmed, ticket_issued

WebSocket /ws/seat-availability/{train_id}
     → Real-time seat inventory changes
     → Kafka-backed event stream

WebSocket /ws/admin/queue
     → Admin: Live booking queue updates
     → Shows: pending requests, execution status
```

### Admin Operations
```
GET  /api/admin/dashboard
     → Overview: queue depth, success rate, revenue

GET  /api/admin/queue/stats
     → Analytics: processing speed, failure reasons

POST /api/admin/queue/execute-batch
     Body: { request_ids: [...] }
     → Bulk execute bookings

POST /api/admin/refund/{booking_id}
     → Manual refund processing

GET  /api/admin/logs/{booking_id}
     → Full execution audit trail
```

---

## 5. CORE BUSINESS LOGIC

### Route Finding Engine (RAPTOR)
**Location:** `/backend/core/engines/raptor_engine.py`

**Algorithm:**
1. **Input:** Origin station, destination, date, time, preferences
2. **Phase 1 - Graph Building:** Load train segments for date, build transit graph
3. **Phase 2 - RAPTOR Iterations:**
   - Round 1: Direct trains + nearest-interchange connections
   - Round 2+: Multi-segment routes with hub optimization
   - Stop criterion: No improvement in last 3 rounds or max 5 rounds
4. **Output:** Ranked list of pareto-optimal routes

**Caching Strategy:**
- Daily snapshots of route_engine_graph.pkl (~19MB)
- Redis cache for popular searches (TTL: 4 hours)
- Copy-on-Write overlay for real-time delays
- Dexie.js (IndexedDB) on frontend for recent searches

**Performance Targets:**
- Single segment: <100ms
- Multi-segment (3+ trains): <500ms
- Cache hit: <10ms

### ML-Based Ranking
**Location:** `/backend/core/ml_integration.py`

**Models:**
1. **Route Ranking Model** (`route_ranking_model.pkl`) - LightGBM
   - Features: distance, duration, price, transfers, delays
   - Output: relevance score [0-1]
   - Used for: Re-ranking RAPTOR results

2. **Delay Prediction** (`delay_model.pkl`) - LightGBM
   - Features: train ID, segment, historical delay patterns
   - Output: expected delay (minutes)
   - Used for: Adjust arrival time display

3. **Reliability Model** (`reliability_model.pkl`) - Binary classifier
   - Features: route characteristics, user preferences
   - Output: Success probability [0-1]
   - Used for: Display confidence score

4. **Tatkal Demand Forecast** (`tatkal_demand_model.pkl`)
   - Features: date, train, competition
   - Output: Demand level (low/medium/high)
   - Used for: Tatkal booking recommendations

### Booking Queue System
**Location:** `/backend/services/booking/`

**Workflow:**
```
1. User submits booking_request via /api/bookings/request
   ├─ Validated for: passengers, route validity, user quota
   └─ Stored with status: PENDING

2. Admin/System picks requests from booking_queue table
   ├─ Sorted by: user priority, route popularity, time received
   └─ Status: QUEUED

3. Booking executor calls RapidAPI IRCTC endpoint
   ├─ Inputs: train ID, route, passengers, quotas
   └─ Response: PNR or seat unavailable

4. On Success:
   ├─ Create booking_result with PNR, ticket details
   ├─ Update booking_queue status: EXECUTED
   ├─ Send confirmation via email/SMS
   └─ Update user booking history

5. On Failure:
   ├─ Log error to execution_logs
   ├─ Try next request from queue
   └─ After 3 failures or 24h elapsed:
       ├─ Process refund via Razorpay
       ├─ Notify user
       └─ Mark refund as COMPLETED
```

### Payment Processing
**Location:** `/backend/services/payment/` + Razorpay integration

**Payment Flows:**
1. **Unlock Fee (₹39):**
   - User pays to see detailed route info + live availability
   - One-time per route per day
   - Refundable if booking fails

2. **Booking Payment:**
   - Full ticket amount charged
   - Only charged after admin confirms availability
   - Non-refundable within 24h (per IRCTC policy)

3. **Refunds:**
   - Automatic: Booking fails after 3 attempts
   - Manual: User cancellation request
   - Processing: Razorpay refund API + audit logging

---

## 6. EXTERNAL INTEGRATIONS

### Supabase (Authentication + Database)
- **Auth:** User signup/login via email/phone OTP
- **Database:** PostgreSQL with realtime subscriptions
- **Storage:** Profile images, ticket PDFs
- **Configuration:** Environment variables required
  - `SUPABASE_URL`
  - `SUPABASE_KEY` (anon key for frontend)
  - `SUPABASE_SERVICE_KEY` (backend-only privileged ops)

### RapidAPI / IRCTC Integration
- **Endpoint:** IRCTC API proxy via RapidAPI
- **Features:** Route search, seat availability, booking
- **Error Handling:** Fallback to cached data or queue retry
- **Cost:** Per-request billing model
- **Status:** Partially integrated, needs verification testing

### Razorpay (Payment Processing)
- **Features:** Payment collection, refunds, webhooks
- **Implementation:** `/backend/services/payment/razorpay.py`
- **Configuration:**
  - `RAZORPAY_KEY_ID`
  - `RAZORPAY_KEY_SECRET`
  - Webhook URL for async refund notifications

### Kafka / Message Streaming
- **Use:** Real-time event streaming for seat updates
- **Topics:**
  - `seat-inventory-changes`
  - `booking-status-updates`
  - `admin-queue-updates`
- **Configuration:** Broker URL, topic names in environment

### Twilio (SMS Notifications)
- **Use:** Booking confirmations, alerts, OTP delivery
- **Configuration:**
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_PHONE_NUMBER`

### SendGrid (Email Notifications)
- **Use:** Booking receipts, password resets, announcements
- **Configuration:**
  - `SENDGRID_API_KEY`
  - Email templates stored in Sendgrid

### RouteMaster Agent (Data Service)
- **Purpose:** Separate microservice for IRCTC scraping & verification
- **Location:** Deployed separately (not in main backend)
- **Integration:** API calls for route validation, seat verification
- **Status:** Exists, integration partially complete

---

## 7. KNOWN ISSUES & GAPS (P0/P1)

### P0 - CRITICAL (Blocking Core Features)

#### Gap 1: Booking Queue Execution Incomplete
- **Issue:** Database models created but execution flow not fully implemented
- **Impact:** Cannot complete end-to-end bookings
- **Fix Needed:** 
  - Implement booking executor (calls RapidAPI, processes results)
  - Complete admin queue endpoints
  - Add retry logic and failure handling
- **Estimated Effort:** 16 hours

#### Gap 2: RapidAPI Integration Partially Working
- **Issue:** Client exists but end-to-end testing incomplete
- **Impact:** Cannot verify live seat availability
- **Fix Needed:**
  - Verify API credentials and endpoint
  - Test with real train IDs
  - Add error handling for API downtime
  - Implement fallback to cached data
- **Estimated Effort:** 12 hours

#### Gap 3: Admin Dashboard UI Missing
- **Issue:** No frontend interface for admins to execute bookings
- **Impact:** Manual booking execution not user-friendly
- **Fix Needed:**
  - Build admin panel (React component)
  - Add queue visualization
  - Implement execution controls
  - Add analytics dashboard
- **Estimated Effort:** 24 hours

#### Gap 4: Supabase IPv6 Connection Issues
- **Issue:** DNS resolution fails on some client machines
- **Impact:** Production connectivity unreliable
- **Fix Needed:**
  - Migrate to IPv4-only pooler connection
  - Update DATABASE_URL in configs
  - Document connection best practices
- **Estimated Effort:** 4 hours

### P1 - HIGH PRIORITY

#### Gap 5: Refund System Partial
- **Issue:** API endpoint missing, Razorpay refund incomplete
- **Impact:** Failed bookings cannot be refunded automatically
- **Fix Needed:**
  - Add refund API endpoint
  - Implement async refund processing
  - Add webhook handlers for Razorpay refund status
- **Estimated Effort:** 12 hours

#### Gap 6: Pydantic V2 Migration Warnings
- **Issue:** Config key deprecation (`allow_population_by_field_name`)
- **Impact:** Deprecation warnings in logs
- **Fix Needed:**
  - Update all Pydantic models to V2 syntax
  - Remove deprecated config keys
- **Estimated Effort:** 6 hours

#### Gap 7: WebSocket Real-Time Updates
- **Issue:** Infrastructure exists but integration incomplete
- **Impact:** No live seat availability updates
- **Fix Needed:**
  - Implement WebSocket handlers for seat changes
  - Integrate with Kafka consumer
  - Test with concurrent connections
- **Estimated Effort:** 16 hours

#### Gap 8: Testing Coverage Low
- **Issue:** 60+ test files exist but integration tests incomplete
- **Impact:** Risk of regressions in production
- **Fix Needed:**
  - Add integration tests for booking flow
  - Add E2E tests for payment processing
  - Add load tests for concurrent bookings
  - Add security tests (OWASP top 10)
- **Estimated Effort:** 32 hours

---

## 8. DEPLOYMENT ARCHITECTURE

### Development Environment
- **Setup:** `docker-compose.dev.yml`
- **Services:** Backend API, Frontend dev server, PostgreSQL, Redis, Kafka, Mailhog
- **Database:** Supabase-managed PostgreSQL (shared dev instance)
- **Start:** `docker-compose -f docker-compose.dev.yml up`

### Production Environment
- **Backend:** Railway.app (Procfile-based deployment)
- **Frontend:** Vercel (static hosting, auto-deploy from main)
- **Database:** Supabase PostgreSQL (production cluster)
- **Cache:** Redis on Railway or managed provider
- **Message Queue:** Kafka cluster (managed service)
- **Monitoring:** Prometheus + Grafana (on Railway or K8s)
- **Alerts:** AlertManager → Slack integration

### Kubernetes Setup
- **Manifests:** `/k8s/*.yaml`
- **Deployments:** route-service (8002), RL-service (8003), scraper (8001)
- **StatefulSets:** Redis, Kafka, Zookeeper
- **ConfigMaps/Secrets:** Environment variables, credentials
- **Ingress:** NGINX-based routing to services
- **Auto-scaling:** HorizontalPodAutoscaler (based on CPU/memory)

### Database Migrations
- **Tool:** Alembic
- **Location:** `/backend/alembic/versions/`
- **Process:**
  1. Create schema change (SQL)
  2. Generate revision: `alembic revision --autogenerate -m "description"`
  3. Apply: `alembic upgrade head`
  4. Test on dev, then production
- **CI/CD:** Migrations run automatically on deployment

---

## 9. MONITORING & OBSERVABILITY

### Metrics (Prometheus)
- **Exposed at:** `/metrics`
- **Key Metrics:**
  - HTTP request latency (p50, p95, p99)
  - API error rates (by endpoint)
  - Database query duration
  - Cache hit rate
  - Booking success rate
  - Payment processing time
  - Queue depth and processing speed

### Logging
- **Strategy:** Structured logging (JSON format)
- **Tools:** Python logging + FastAPI logging middleware
- **Retention:** 30 days (cloud provider default)
- **Filtering:** By level, service, user ID

### Tracing (Jaeger)
- **Spans:** Per API request, database query, external API call
- **Service Map:** Visualize inter-service dependencies
- **Latency Analysis:** Identify slow components

### Dashboards (Grafana)
- **SOS Dashboard:** System overview, uptime, error rates
- **Financial Dashboard:** Revenue, refunds, payment success rate
- **Queue Dashboard:** Queue depth, throughput, failures
- **ML Dashboard:** Model performance, prediction accuracy

### Alerting
- **Rules:** AlertManager configuration
- **Channels:** Slack, email, PagerDuty (optional)
- **Key Alerts:**
  - API error rate > 5%
  - Database connection failures
  - Queue depth growing
  - Payment processing delay > 30s
  - ML model prediction latency > 1s

---

## 10. TESTING STRATEGY

### Unit Tests
- **Framework:** pytest
- **Coverage:** All core logic (route engine, booking service, payment)
- **Location:** `/backend/tests/`
- **Run:** `pytest tests/`

### Integration Tests
- **Scope:** API endpoints with mocked external services
- **Database:** Test database (SQLite or separate Supabase project)
- **Fixtures:** conftest.py with reusable test clients
- **Run:** `pytest tests/integration/`

### End-to-End Tests
- **Scope:** Complete user flows (search → book → pay → confirm)
- **Tools:** Selenium or Playwright (frontend)
- **Environment:** Staging environment
- **Run:** Post-deployment validation

### Performance Tests
- **Load Testing:** Locust (simulate concurrent users)
- **Scenarios:**
  - 100 concurrent searches (target: <1s latency)
  - 50 concurrent bookings (target: queue throughput >10/min)
  - Cache effectiveness (target: >80% hit rate)

### Security Tests
- **OWASP Top 10:**
  - SQL injection (parameterized queries)
  - XSS (input sanitization, React escaping)
  - CSRF (CSRF tokens in forms)
  - Auth bypass (JWT validation, rate limiting)
  - Sensitive data exposure (HTTPS, encryption)
- **Tools:** OWASP ZAP, manual penetration testing
- **Frequency:** Before production release

### Smoke Tests
- **Automated Checks:**
  - Health endpoint responds
  - Database connects
  - Cache initializes
  - External APIs reachable
- **Run:** On every deployment

---

## 11. DEVELOPMENT WORKFLOW

### Branch Strategy
- **Main Branch:** `main-production` (production-ready)
- **Development Branch:** `develop` or feature branches
- **Feature Branches:** `feature/booking-queue`, `fix/rapidapi-integration`
- **Deploy:** Merge to `main-production` triggers production deployment

### Code Quality
- **Linting:** ESLint (frontend), Flake8 (backend)
- **Type Checking:** TypeScript (frontend), mypy (backend, optional)
- **Formatting:** Prettier (frontend), black (backend)
- **Pre-commit:** Hooks configured in `.pre-commit-config.yaml`

### Git Workflow
1. Create feature branch: `git checkout -b feature/name`
2. Commit changes: `git commit -m "descriptive message"`
3. Push to remote: `git push origin feature/name`
4. Open pull request with description
5. Code review + CI tests pass
6. Merge to development
7. Final testing on staging
8. Merge to `main-production` for production deployment

### Deployment Checklist
- [ ] All tests pass (unit + integration)
- [ ] No security vulnerabilities (OWASP scan)
- [ ] Database migrations reviewed and tested
- [ ] Performance benchmarks met (latency, throughput)
- [ ] Documentation updated (API, deployment guide)
- [ ] Monitoring dashboards configured
- [ ] Rollback plan documented

---

## 12. KEY PERFORMANCE INDICATORS (KPIs)

### System Performance
- **API Latency:** P95 < 500ms for search, < 1s for bookings
- **Cache Hit Rate:** >80% for frequently searched routes
- **Database Query Time:** P95 < 100ms for normal queries
- **System Uptime:** >99.5% monthly availability

### Business Metrics
- **Booking Success Rate:** >95% (for verified seats)
- **Payment Success Rate:** >99% (Razorpay reliability)
- **Customer Satisfaction:** NPS > 50 (via surveys)
- **Queue Processing Time:** <5 minutes average

### ML Model Performance
- **Route Ranking:** NDCG@5 > 0.85 (relevance)
- **Delay Prediction:** MAE < 15 minutes
- **Reliability Score:** AUC > 0.90 (classification)
- **Tatkal Forecast:** Accuracy > 80%

---

## 13. NEXT STEPS (ITERATION ROADMAP)

### Iteration 0 ✅ DONE
- Research complete, architecture documented, dependencies mapped

### Iteration 1: Backend Stabilization (40 hours)
- Fix Pydantic V2 issues
- Stabilize route engine
- Complete search API
- Fix Supabase connectivity

### Iteration 2: Booking Queue (48 hours)
- Implement booking executor
- Complete RapidAPI integration
- Add refund system
- Build queue monitoring

### Iteration 3: Frontend UI (56 hours)
- Build search interface
- Implement checkout flow
- Build admin dashboard
- Add real-time notifications

### Iteration 4: ML & Analytics (40 hours)
- Optimize ML models
- Build annotation pipeline
- Add feature engineering
- Integrate into production

### Iteration 5: Integrations & Real-Time (36 hours)
- Complete RouteMaster Agent integration
- Implement Kafka event streaming
- Build WebSocket support
- Add notifications (SMS, email)

### Iteration 6: Testing & QA (44 hours)
- Expand test coverage to 90%+
- Add integration tests
- Load testing
- Security audit

### Iteration 7: Deployment & Infra (32 hours)
- Production Railway setup
- Kubernetes manifests
- Disaster recovery
- Monitoring dashboards

### Iteration 8: Security & Compliance (28 hours)
- Security audit
- Rate limiting
- Data encryption
- Compliance verification

### Iteration 9: Documentation & Launch (24 hours)
- API documentation
- Deployment guides
- Runbooks
- Production launch

---

## SUMMARY

**Total Estimated Effort:** ~348 hours (~9 weeks at 40 hours/week)

**Current Blockers:**
1. Booking queue executor incomplete
2. RapidAPI integration needs verification
3. Admin dashboard UI missing

**Next Action:** Start Iteration 1 - Backend stabilization and route engine hardening.

---

*Document prepared by: Claude AI Assistant*  
*Branch: claude/project-research-architecture-xdeo8l*
