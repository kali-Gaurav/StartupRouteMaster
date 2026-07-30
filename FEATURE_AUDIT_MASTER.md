# RouteMaster V2 — Feature Audit & MVP Completion Roadmap
**Created:** June 8, 2026  
**Status:** Phase 0 — Feature Audit & Ranking  
**Objective:** Transform 50+ partially implemented features into a professional startup MVP

---

## PART 1: TOP 50 FEATURES — RANKED BY BUSINESS IMPACT

### Tier 1: Core MVP Features (Must-Have)

#### 1. **Route Search & Discovery** [PARTIALLY BUILT]
- **Current State:** Backend fully working (api/v1/search/routes). Direct + 1-transfer routes live. Real fares from erail.in. Redis cache working.
- **Frontend:** Index.tsx implemented with UI. RouteCard components built.
- **Gap:** Missing 2-transfer routes optimization. Missing result ranking/sorting. Missing saved searches. Missing advanced filters.
- **Business Value:** Core revenue driver. Every user action starts here.
- **Dependency:** Database (✅), Redis (✅), External APIs (✅)

#### 2. **Station Autocomplete & Suggestions** [PARTIALLY BUILT]
- **Current State:** GET /api/v1/stations/suggest implemented. Trie index + DB fallback working. Fast response (<100ms).
- **Gap:** Missing recent searches. Missing smart location detection. Missing route suggestions based on user patterns.
- **Business Value:** Reduces friction. Increases conversion. Improves UX.
- **Dependency:** Database (✅)

#### 3. **Live Train Status & Tracking** [PARTIALLY BUILT]
- **Current State:** GET /api/v1/live/train/{no} via rappid.in (FREE, UNLIMITED). Returns current station, delay, full route. 60s Redis cache.
- **Frontend:** TrainTracking.tsx built. Real-time updates.
- **Gap:** Missing WebSocket for live updates. Missing delay predictions. Missing incident alerts.
- **Business Value:** High user engagement. Retention driver.
- **Dependency:** External API (rappid.in) ✅

#### 4. **PNR Status Lookup** [PARTIALLY BUILT]
- **Current State:** GET /api/v1/pnr/{pnr} implemented. RapidAPI integration (7000/mo quota).
- **Frontend:** PNRStatus.tsx with passenger details, berth, coach, chart status.
- **Gap:** Missing real-time refresh. Missing booking history integration. Missing ticket PDF download.
- **Business Value:** Reduces support load. High user search intent.
- **Dependency:** RapidAPI (needs key)

#### 5. **Authentication & User Management** [PARTIALLY BUILT]
- **Current State:** Firebase Auth integrated. JWT backend (auth.py). POST /auth/register, /login working. /auth/firebase-sync bridge built.
- **Frontend:** LoginPage.tsx, SignupPage.tsx, VerifyOTPPage.tsx.
- **Gap:** Missing password reset flow. Missing email verification. Missing social login fallback. Missing profile completion wizard.
- **Business Value:** Gating for all user-specific features.
- **Dependency:** Firebase (✅), Backend JWT (✅)

#### 6. **Booking Flow & IRCTC Integration** [PARTIALLY BUILT]
- **Current State:** RouteCard has "Book on IRCTC" button. Generates deep-link with train+date+class pre-filled. Redirect to IRCTC.
- **Frontend:** Bookings.tsx skeleton. BookingFlowModal.tsx, BookingReviewStep.tsx components.
- **Gap:** Missing actual booking on our platform. Missing payment integration (Razorpay keys exist but not wired). Missing booking history. Missing ticket storage.
- **Business Value:** Commission revenue. High-friction conversion point.
- **Dependency:** Payment gateway (Razorpay) ✅, IRCTC API (deep-link only)

#### 7. **SOS / Emergency Safety** [PARTIALLY BUILT]
- **Current State:** POST /api/v1/sos/trigger implemented. Twilio SMS integration ready. Backend stores SOS records.
- **Frontend:** SOS.tsx, SOSWidget.tsx. Safety page. Real-time location via geolocation API.
- **Gap:** Missing trusted contact management. Missing automatic police/support escalation. Missing incident photo storage. Missing SOS history.
- **Business Value:** Differentiator for safety-conscious users. High trust signal.
- **Dependency:** Twilio (needs env vars), Geolocation API ✅

#### 8. **Fare Alerts System** [PARTIALLY BUILT]
- **Current State:** POST /api/v1/alerts/fare, GET /api/v1/alerts/mine, DELETE /api/v1/alerts/{id}. Telegram integration. Daily cron job (render.yaml).
- **Frontend:** RouteCard has "🔔 Set Fare Alert" button.
- **Gap:** Missing email alerts. Missing SMS alerts (Twilio fallback). Missing alert history. Missing threshold recommendations. Missing AI price prediction.
- **Business Value:** User retention. Email/SMS marketing channel.
- **Dependency:** Telegram (✅), Email service, Twilio

#### 9. **Train Schedule & Timetables** [PARTIALLY BUILT]
- **Current State:** GET /api/v1/stations/schedule/{train_no} built. Returns full route with arrival/departure times. 1h Redis cache.
- **Frontend:** TrainSchedule.tsx page with detailed timetable.
- **Gap:** Missing platform info. Missing train class availability calendar. Missing historical on-time performance.
- **Business Value:** SEO goldmine. High search intent.
- **Dependency:** Database (✅)

#### 10. **Station Departures Board** [PARTIALLY BUILT]
- **Current State:** GET /api/v1/stations/{code}/departures implemented. FIDS-style display. Auto-refresh every 2min.
- **Frontend:** StationBoard.tsx with upcoming/past departures. Popular station chips. Date picker.
- **Gap:** Missing platform assignments. Missing occupancy info. Missing seat availability preview.
- **Business Value:** Engagement. SEO. Station-specific pages.
- **Dependency:** Database (✅)

---

### Tier 2: Engagement & Monetization Features (High-Priority)

#### 11. **User Dashboard & Booking History** [SKELETON ONLY]
- **Current State:** Dashboard.tsx exists but empty. No data wiring.
- **Gap:** Missing upcoming journeys. Missing past bookings. Missing saved routes. Missing wishlist. Missing trip analytics.
- **Business Value:** User retention. Repeat booking driver.
- **Dependency:** Database (user_bookings table), Auth

#### 12. **City-Pair SEO Pages** [PARTIALLY BUILT]
- **Current State:** GET /api/v1/routes/{from_slug}/{to_slug} implemented. CityPairRoutes.tsx with FAQ, rich snippets.
- **Gap:** Missing city guides. Missing popular times. Missing route reviews/ratings. Missing traveler tips.
- **Business Value:** Organic traffic. Search intent capture.
- **Dependency:** Database, Content

#### 13. **Recommendation Engine** [NOT BUILT]
- **Current State:** Zero implementation.
- **Gap:** Missing "Users who searched X also searched Y". Missing "Best time to travel route X". Missing personalized route suggestions.
- **Business Value:** Engagement. Cross-selling. Upsell.
- **Dependency:** Analytics data, User behavior tracking

#### 14. **Traveler Ratings & Reviews** [NOT BUILT]
- **Current State:** Zero implementation.
- **Gap:** Rate train quality. Rate food. Rate cleanliness. Rate staff. Aggregate reviews.
- **Business Value:** Trust. User-generated content. SEO.
- **Dependency:** Database (reviews table), Auth

#### 15. **Seat Map Visualization** [NOT BUILT]
- **Current State:** Zero implementation.
- **Gap:** Interactive seat selection. Live occupancy heatmap. Class availability preview.
- **Business Value:** UX differentiator. Booking confidence.
- **Dependency:** IRCTC seat API (not available), Alternative: coach-level availability

#### 16. **Telegram Bot** [PARTIALLY BUILT]
- **Current State:** api/v1/telegram.py with message parser. Webhook auto-register on startup. Parses: "Delhi Mumbai", "NDLS BCT 15 June", "live 12951", "pnr 1234567890".
- **Gap:** Missing command menu (/start, /help, /alert, /track, /pnr). Missing subscription management. Missing user linking to main app.
- **Business Value:** Freemium distribution. Low-friction user acquisition.
- **Dependency:** Telegram Bot API ✅

#### 17. **Voice Search** [COMPONENT BUILT, NOT INTEGRATED]
- **Current State:** VoiceSearch.tsx component exists. No backend wiring.
- **Gap:** Missing speech-to-text API integration. Missing voice-to-route intent parsing.
- **Business Value:** Accessibility. Mobile-first UX.
- **Dependency:** Speech API (Google Cloud, Web Speech API)

#### 18. **Push Notifications** [NOT BUILT]
- **Current State:** Zero implementation.
- **Gap:** Missing service worker. Missing notification center. Missing preference management. Missing scheduled alerts (departure soon, train delayed, booking confirmed).
- **Business Value:** High engagement. Re-engagement driver.
- **Dependency:** Firebase Cloud Messaging, Service Worker

#### 19. **Payment & Razorpay Integration** [PARTIALLY BUILT]
- **Current State:** RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET in .env. PaymentModal.tsx, BookingPaymentStep.tsx components exist. RazorpayCheckout.tsx page.
- **Gap:** Missing payment processing logic. Missing order creation. Missing webhook for payment confirmation. Missing receipt generation.
- **Business Value:** Revenue. Commission from bookings.
- **Dependency:** Razorpay (✅), Order/Payment DB tables

#### 20. **Wallet & Incentive System** [COMPONENT BUILT, NOT INTEGRATED]
- **Current State:** IncentiveWallet.tsx component built. No backend logic.
- **Gap:** Missing wallet balance tracking. Missing referral credits. Missing cashback. Missing loyalty points.
- **Business Value:** Retention. Repeat booking incentive.
- **Dependency:** Database (wallet, transactions tables)

---

### Tier 3: Admin & Operations Features (Medium-Priority)

#### 21. **Admin Dashboard - Overview** [SKELETON ONLY]
- **Current State:** AdminDashboard.tsx exists but empty. No data wiring.
- **Gap:** Missing KPIs (searches, bookings, revenue). Missing live metrics. Missing user heatmaps.
- **Business Value:** Operations visibility. Decision making.
- **Dependency:** Analytics DB, Real-time metrics

#### 22. **Admin Finance Dashboard** [SKELETON ONLY]
- **Current State:** AdminFinance.tsx exists but empty. FinancialDashboard.tsx also empty.
- **Gap:** Missing revenue tracking. Missing commission breakdown. Missing payout management. Missing financial reports.
- **Business Value:** Billing. Growth tracking.
- **Dependency:** Payment DB, Transaction tracking

#### 23. **Admin Operations Dashboard** [SKELETON ONLY]
- **Current State:** AdminOperations.tsx exists but empty.
- **Gap:** Missing real-time train status monitoring. Missing delay tracking. Missing incident management.
- **Business Value:** Support operations. Incident response.
- **Dependency:** Real-time data feeds

#### 24. **Admin Growth & Marketing** [SKELETON ONLY]
- **Current State:** AdminGrowth.tsx exists but empty.
- **Gap:** Missing campaign management. Missing user acquisition metrics. Missing retention analytics.
- **Business Value:** Growth strategy execution.
- **Dependency:** Analytics, Campaign DB

#### 25. **Admin AI & Intelligence** [SKELETON ONLY]
- **Current State:** AdminAI.tsx, AdminIntelligence.tsx exist but empty. RAG chatbot partially built (RailAssistantChatbot.tsx).
- **Gap:** Missing chatbot conversation history. Missing AI model management. Missing NLP training.
- **Business Value:** Support automation. Customer engagement.
- **Dependency:** LLM API (Gemini key exists), RAG backend

#### 26. **Admin System & Monitoring** [SKELETON ONLY]
- **Current State:** AdminSystem.tsx exists but empty. Health endpoints (/health/live, /stats) built.
- **Gap:** Missing server status. Missing API monitoring. Missing error tracking. Missing performance metrics.
- **Business Value:** System reliability. Incident prevention.
- **Dependency:** Monitoring service, Logs aggregation

#### 27. **Admin Inventory Management** [SKELETON ONLY]
- **Current State:** AdminInventory.tsx exists but empty.
- **Gap:** Missing DB of managed inventory. Assuming this is for partner integrations.
- **Business Value:** Partner ecosystem.
- **Dependency:** Inventory DB schema

#### 28. **Admin Audit & Compliance** [SKELETON ONLY]
- **Current State:** AdminAudit.tsx exists but empty.
- **Gap:** Missing audit logs. Missing compliance tracking. Missing user data access logs.
- **Business Value:** Legal/regulatory compliance.
- **Dependency:** Audit DB, Logging

#### 29. **Admin Settings & Configuration** [SKELETON ONLY]
- **Current State:** AdminSettings.tsx exists but empty.
- **Gap:** Missing feature toggles. Missing API rate limits. Missing alert thresholds.
- **Business Value:** Operations control.
- **Dependency:** Config DB

#### 30. **Agent Portal / Employee Dashboard** [SKELETON ONLY]
- **Current State:** AgentPortal.tsx exists but empty.
- **Gap:** Missing employee task management. Missing performance metrics. Missing shift scheduling.
- **Business Value:** Team coordination.
- **Dependency:** Employee DB, Task management

---

### Tier 4: Advanced Features (Medium-Long Term)

#### 31. **Email Marketing & Campaigns** [NOT BUILT]
- **Current State:** Zero implementation.
- **Gap:** Missing campaign builder. Missing email templates. Missing A/B testing. Missing subscriber management.
- **Business Value:** User engagement. Retention.
- **Dependency:** Email service (SendGrid?)

#### 32. **SMS Marketing & Notifications** [PARTIALLY BUILT]
- **Current State:** Twilio SDK ready. SOS SMS implementation exists.
- **Gap:** Missing marketing SMS. Missing SMS templates. Missing SMS campaign scheduling.
- **Business Value:** Direct user engagement. High open rate.
- **Dependency:** Twilio ✅

#### 33. **Referral & Affiliate System** [NOT BUILT]
- **Current State:** Zero implementation.
- **Gap:** Missing referral code generation. Missing affiliate dashboard. Missing commission tracking.
- **Business Value:** Viral growth. User acquisition.
- **Dependency:** Referral DB schema

#### 34. **Trip Analytics & Insights** [NOT BUILT]
- **Current State:** Zero implementation.
- **Gap:** Missing user trip patterns. Missing spending trends. Missing favorite routes.
- **Business Value:** User engagement. Personalization.
- **Dependency:** Analytics DB, Event tracking

#### 35. **Swarm Intelligence & Multi-Agent System** [ARCHIVED]
- **Current State:** Archived in `_archived/services_agents/` (54 agents built). AdminSwarm.tsx page exists but empty.
- **Gap:** Agents were built but not integrated into operations. Needs orchestration backend.
- **Business Value:** Automation at scale. Decision support.
- **Dependency:** Event bus, Agent orchestration framework

#### 36. **Nexus System** [ARCHIVED]
- **Current State:** Archived in `_archived/core_nexus/`. Bootstrap system built.
- **Gap:** System designed but not integrated. Core purpose: Multi-system orchestration.
- **Business Value:** Internal system coordination.
- **Dependency:** Inter-service communication

#### 37. **TBR Engine (Time-Based Routing)** [PARTIALLY IMPLEMENTED]
- **Current State:** Referenced in memory. Part of route engine.
- **Gap:** Not clear current state. Needs audit.
- **Business Value:** Route optimization based on time windows.
- **Dependency:** GTFS data, Algorithm

#### 38. **RAPTOR Engine (Multi-Transfer)** [PARTIALLY BUILT]
- **Current State:** core/route_engine/raptor.py exists. Algorithm implemented.
- **Gap:** May not be fully integrated into search flow. Needs testing.
- **Business Value:** Better route options. Higher booking conversion.
- **Dependency:** Database ✅

#### 39. **CAT (Contextual Attention Transformer) ML Model** [ARCHIVED]
- **Current State:** Archived in `_archived/cat/`. ML transformer built.
- **Gap:** Model trained but not deployed. Not integrated into search.
- **Business Value:** ML-powered route ranking. Personalization.
- **Dependency:** Model serving infrastructure

#### 40. **Real-Time Data Pipeline** [PARTIALLY BUILT]
- **Current State:** Redis caching layer. Daily cron jobs. Telegram alerts.
- **Gap:** Missing Kafka/event bus for high-volume updates. Missing streaming analytics.
- **Business Value:** Real-time operations. Live dashboards.
- **Dependency:** Kafka or similar, Streaming DB

---

### Tier 5: Polish & Infrastructure (Lower-Priority for MVP)

#### 41. **Mobile App (iOS/Android)** [NOT BUILT]
- **Current State:** Mini-app architecture in place (mini-app/ pages). Progressive Web App ready.
- **Gap:** No native app. React Native not used.
- **Business Value:** App store distribution. User retention.
- **Dependency:** React Native or Flutter, App store deployment

#### 42. **Progressive Web App (PWA)** [PARTIALLY BUILT]
- **Current State:** Service worker structure partially in place. Manifest file likely missing.
- **Gap:** Missing offline support. Missing app shortcuts. Missing splash screens.
- **Business Value:** App-like experience. Installable.
- **Dependency:** Service Worker, Manifest

#### 43. **Dark Mode** [NOT BUILT]
- **Current State:** Zero implementation. UI component library ready (shadcn/ui).
- **Gap:** Missing dark theme. Missing theme toggle.
- **Business Value:** User preference. Reduced eye strain.
- **Dependency:** CSS variables, Theme provider

#### 44. **Internationalization (i18n)** [NOT BUILT]
- **Current State:** Zero implementation.
- **Gap:** Missing translations. Missing RTL support.
- **Business Value:** Market expansion beyond India (Hindi, regional languages).
- **Dependency:** i18n library (next-i18n-router?)

#### 45. **Accessibility (a11y)** [PARTIALLY BUILT]
- **Current State:** shadcn/ui components have baseline a11y. No comprehensive audit done.
- **Gap:** Missing ARIA labels, keyboard navigation testing, screen reader testing.
- **Business Value:** Legal compliance. Inclusive design.
- **Dependency:** a11y testing tools

#### 46. **SEO Optimization** [PARTIALLY BUILT]
- **Current State:** Schema.org JSON-LD added. Sitemap built. Meta tags added.
- **Gap:** Missing h1/h2 optimization. Missing alt text. Missing internal linking strategy.
- **Business Value:** Organic traffic.
- **Dependency:** Content strategy

#### 47. **Analytics & Logging** [PARTIALLY BUILT]
- **Current State:** Backend has some logging. No comprehensive analytics.
- **Gap:** Missing user event tracking. Missing funnel analytics. Missing error tracking (Sentry?).
- **Business Value:** Understanding user behavior. Debugging.
- **Dependency:** Analytics DB, Event tracking

#### 48. **Performance Optimization** [PARTIALLY DONE]
- **Current State:** Redis caching. Frontend minification. Image optimization needed.
- **Gap:** Missing image optimization. Missing code splitting. Missing lazy loading review.
- **Business Value:** Page speed. Conversion.
- **Dependency:** Lighthouse audit, Optimization tools

#### 49. **Security Hardening** [PARTIALLY DONE]
- **Current State:** CORS configured. JWT auth implemented. HTTPS enforced.
- **Gap:** Missing rate limiting. Missing XSS protection review. Missing CSRF tokens. Missing security headers.
- **Business Value:** Data protection. User trust.
- **Dependency:** Security library additions

#### 50. **DevOps & Deployment Pipeline** [PARTIALLY BUILT]
- **Current State:** Render.yaml for backend. Vercel for frontend. GitHub Actions cron job.
- **Gap:** Missing CI/CD testing. Missing staging environment. Missing canary deploys. Missing rollback strategy.
- **Business Value:** Deployment safety. Quick iterations.
- **Dependency:** GitHub Actions, Testing setup

---

## PART 2: FEATURE RANKING MATRIX

| Rank | Feature | Impact | MVP Critical | Build Time | Status | Next Action |
|------|---------|--------|--------------|------------|--------|-------------|
| 1 | Route Search | 🔴 CRITICAL | Yes | 5h | 80% | Wire 2-transfer + sorting |
| 2 | Station Autocomplete | 🔴 CRITICAL | Yes | 2h | 90% | Add recent searches |
| 3 | Live Train Status | 🔴 CRITICAL | Yes | 3h | 85% | WebSocket integration |
| 4 | PNR Status | 🟠 HIGH | Yes | 2h | 75% | Add booking history link |
| 5 | Authentication | 🟠 HIGH | Yes | 4h | 80% | Add reset flow |
| 6 | Booking Flow | 🟠 HIGH | Yes | 8h | 30% | **FEATURE #1** |
| 7 | SOS / Safety | 🟠 HIGH | Maybe | 4h | 70% | Add trusted contacts |
| 8 | Fare Alerts | 🟠 HIGH | Maybe | 3h | 75% | Add email/SMS |
| 9 | Train Schedule | 🟠 HIGH | No | 2h | 80% | Add platforms |
| 10 | Station Board | 🟠 HIGH | No | 2h | 85% | Add occupancy |
| 11 | User Dashboard | 🟡 MED | Maybe | 6h | 5% | Build bookings view |
| 12 | City-Pair SEO | 🟡 MED | Maybe | 4h | 70% | Add guides |
| 13 | Recommendations | 🟡 MED | No | 6h | 0% | Build engine |
| 14 | Ratings & Reviews | 🟡 MED | No | 6h | 0% | Design schema |
| 15 | Telegram Bot | 🟡 MED | Maybe | 3h | 60% | Wire to search |
| 16 | Voice Search | 🟡 MED | No | 3h | 30% | Integrate speech API |
| 17 | Push Notifications | 🟡 MED | No | 4h | 0% | Setup FCM |
| 18 | Payment Integration | 🔴 CRITICAL | Yes | 6h | 40% | **FEATURE #2** |
| 19 | Wallet System | 🟡 MED | No | 5h | 20% | Build backend |
| 20 | Admin Dashboard | 🟡 MED | Maybe | 8h | 10% | Design KPIs |
| ... | ... | ... | ... | ... | ... | ... |

---

## PART 3: FEATURE #1 — BOOKING FLOW & PAYMENT INTEGRATION

### Phase 1: Current State Audit

#### What Exists
- ✅ Route search returns journey data with train number, date, class, fare
- ✅ User authentication (Firebase + JWT)
- ✅ Razorpay credentials configured
- ✅ UI components: BookingFlowModal.tsx, BookingPaymentStep.tsx, BookingReviewStep.tsx, BookingStepProgress.tsx
- ✅ RazorpayCheckout.tsx page
- ✅ Database has user auth

#### What's Missing
- ❌ Booking order creation (POST /api/v1/bookings)
- ❌ Booking status tracking (GET /api/v1/bookings/{id}, /api/v1/bookings/my)
- ❌ Payment processing (Razorpay payment order, webhook handling)
- ❌ Booking confirmation & ticket storage
- ❌ Booking history in dashboard
- ❌ Email/SMS confirmation
- ❌ PDF ticket generation
- ❌ Refund/cancellation flow

#### Architecture Gaps
- ❌ `bookings` table (order info, payment status, user_id, train_info, seat, fare, status)
- ❌ `payments` table (razorpay_order_id, razorpay_payment_id, amount, status)
- ❌ `tickets` table (booking_id, pnr, ticket_no, seat_no, coach)
- ❌ Backend order service
- ❌ Payment webhook handler
- ❌ Email service integration

### Phase 2: Design & Architecture

*To be completed in next step*

### Phase 3: Implementation Plan

*To be completed in next step*

---

## Quick Reference: What Needs to Happen Next

**Immediate (This Session):**
1. Complete Feature #1 (Booking Flow) audit
2. Design Feature #1 database schema
3. Design Feature #1 API endpoints
4. Plan Feature #1 implementation

**Next Session:**
1. Build Feature #1 backend (order service, payment webhook)
2. Wire Feature #1 frontend to backend
3. Test Feature #1 end-to-end
4. Mark Feature #1 as "Production Ready"
5. Move to Feature #2

**Delivery Goal:** Complete 5-10 features fully before launch to achieve "professional MVP" status.

---

**Status:** 📋 Audit complete. Ready for design phase on Feature #1.
