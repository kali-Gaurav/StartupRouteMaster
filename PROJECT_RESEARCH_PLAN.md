# RouteMaster V2 — Comprehensive Research Plan
**Created:** July 29, 2026  
**Purpose:** Identify key research areas, unknowns, and risks before MVP launch  
**Target Completion:** 2-3 weeks  
**Status:** Initial Planning Phase

---

## EXECUTIVE SUMMARY

RouteMaster V2 is a train booking & discovery platform with 50+ partially implemented features. This research plan identifies:
- **25+ research areas** requiring investigation before production launch
- **Technical unknowns** that impact architecture & timeline
- **Business/market gaps** that affect product-market fit
- **Risk factors** that could derail the MVP
- **Prioritized research roadmap** for the next 2-3 weeks

---

## SECTION 1: PROJECT OVERVIEW & CURRENT STATE

### Project Goal
Build a professional MVP for a train booking & discovery platform with payment integration, real-time tracking, and user engagement features.

### Current Implementation Status
- **Code Written:** ~80% (50+ features exist as code/components)
- **Features Wired:** ~20% (most not integrated/tested)
- **Database:** Supabase PostgreSQL (✅ ready)
- **Auth:** Firebase (✅ implemented)
- **Payment:** Razorpay (✅ credentials, not wired)
- **APIs:** Multiple external (IRCTC, RapidAPI, Twilio, Telegram)
- **Frontend:** React/TypeScript (✅ components exist)
- **Backend:** Python/FastAPI (✅ partial APIs)

### Launch Target
**2-3 weeks:** 10 core features fully built, tested, and deployed

---

## SECTION 2: CRITICAL RESEARCH AREAS

### TIER 1: MUST RESEARCH (Blocks MVP Launch)

#### 2.1 External API Reliability & Quotas
**Current State:** Multiple external APIs, unclear quotas and SLA guarantees  
**Unknowns:**
- [ ] IRCTC API rate limits & uptime SLA
- [ ] RapidAPI PNR quota (7000/month?) — is this enough?
- [ ] Rappid.in train tracking — stability & fallback plan
- [ ] erail.in scraping — legal status & detection risk
- [ ] Twilio SMS cost per SMS & quota limits

**Research Tasks:**
1. **Audit each API:**
   - Query actual rate limits (not documentation)
   - Check uptime monitoring (last 30 days)
   - Identify quota resets & overage costs
   - Document fallback strategies

2. **Cost Analysis:**
   - Calculate monthly API costs at 10K MAU
   - Identify expensive APIs (candidate for in-house solution)
   - Benchmark against competitors

3. **Legal & Compliance:**
   - Verify IRCTC terms (deep-link vs. API resale)
   - Check erail.in ToS (scraping vs. integration)
   - Document partner dependencies for compliance

**Success Metrics:**
- [ ] All external APIs documented with uptime % & quota
- [ ] Cost model for 10K/100K/1M MAU defined
- [ ] Fallback strategy for each critical API
- [ ] Legal review completed

**Timeline:** 3-4 days  
**Owner:** Backend/DevOps lead

---

#### 2.2 Database Performance & Scalability
**Current State:** PostgreSQL via Supabase, no load testing  
**Unknowns:**
- [ ] Can search queries handle 1000 RPS?
- [ ] Index strategy for route search (from/to + date)
- [ ] Booking concurrency — can handle simultaneous payments?
- [ ] Data retention — how much data is too much?
- [ ] Backup/recovery plan

**Research Tasks:**
1. **Load Testing:**
   - Run k6 or locust against search endpoint
   - Test 1K → 10K → 100K concurrent users
   - Identify bottleneck (N+1 queries? Indexes?)
   - Document max sustainable load

2. **Query Analysis:**
   - Profile slow queries (> 100ms)
   - Review indexes on bookings, searches, alerts
   - Test multi-join operations (bookings + payments + users)
   - Measure cache hit rates (Redis)

3. **Capacity Planning:**
   - Storage growth model (GB/month)
   - Backup strategy & retention
   - Archive strategy for old bookings
   - Cost model for data growth

**Success Metrics:**
- [ ] Load test results documented (throughput, latency, errors)
- [ ] Query performance baseline established
- [ ] Scaling strategy defined (vertical vs. horizontal)
- [ ] Backup/recovery tested

**Timeline:** 3-4 days  
**Owner:** Database/Backend lead

---

#### 2.3 Payment Flow Security & Compliance
**Current State:** Razorpay integrated in code, not production-tested  
**Unknowns:**
- [ ] PCI-DSS compliance — what's in-scope?
- [ ] Webhook security — how to prevent replay attacks?
- [ ] Refund flow — Razorpay automatic vs. manual?
- [ ] Chargeback handling — policy & process?
- [ ] Fraud detection — prevention for fake bookings?

**Research Tasks:**
1. **Security Audit:**
   - Review payment code for injection/XSS
   - Verify Razorpay webhook signature validation
   - Check token storage (no hardcoded secrets)
   - Audit payment error handling (no data leaks)

2. **Compliance Review:**
   - Document PCI-DSS applicability
   - Review Razorpay ToS (allowed use cases)
   - Check for hidden fees (Razorpay charges)
   - Identify audit logging requirements

3. **Operational Testing:**
   - Test payment with real Razorpay sandbox
   - Test refund flow (full + partial)
   - Test failure scenarios (declined card, timeout)
   - Test webhook reliability (resend mechanism)

4. **Fraud Prevention:**
   - Design rate limiting (prevent booking spam)
   - Implement duplicate check (same user, same route)
   - Add booking verification (email/SMS)
   - Monitor for suspicious patterns

**Success Metrics:**
- [ ] Security review completed, no critical issues
- [ ] PCI-DSS scope & requirements documented
- [ ] Payment flow tested end-to-end
- [ ] Fraud prevention rules implemented

**Timeline:** 4-5 days  
**Owner:** Security/Backend lead + Finance

---

#### 2.4 User Authentication & Account Security
**Current State:** Firebase + JWT backend, partial signup flow  
**Unknowns:**
- [ ] OTP delivery reliability (SMS vs. Email vs. Telegram)
- [ ] Session management — JWT expiry strategy?
- [ ] Password reset flow — secure?
- [ ] Social login fallback — implemented?
- [ ] Account recovery — lost email/phone?

**Research Tasks:**
1. **Authentication Flow Review:**
   - Audit Firebase integration (token handling)
   - Review JWT backend (expiry, refresh logic)
   - Check password reset flow (secure token, expiry)
   - Verify OTP delivery (Twilio integration)

2. **Account Security:**
   - Implement email verification (post-signup)
   - Add 2FA option (TOTP, SMS)
   - Create account recovery flow (email + phone)
   - Document session timeout strategy

3. **User Communication:**
   - Verify email delivery (sendgrid?)
   - Test SMS OTP (Twilio)
   - Design password reset email
   - Plan account security notifications

**Success Metrics:**
- [ ] Complete signup/login flow tested
- [ ] Email/SMS delivery verified
- [ ] Password reset & account recovery tested
- [ ] Security audit passed

**Timeline:** 2-3 days  
**Owner:** Backend/Security lead

---

#### 2.5 Real-Time Data Infrastructure
**Current State:** Redis cache exists, no WebSocket infrastructure  
**Unknowns:**
- [ ] WebSocket scaling — can support concurrent updates?
- [ ] Live train tracking — update frequency & data freshness?
- [ ] Delayed event handling — how to notify users of delays?
- [ ] Push notification reliability — delivery rate?

**Research Tasks:**
1. **Real-Time Architecture:**
   - Design WebSocket server (Socket.io vs. native)
   - Plan Redis pub/sub for cross-server messaging
   - Document update frequency for different data types
   - Model storage/retention of real-time events

2. **Live Train Data:**
   - Analyze Rappid.in data freshness (update interval)
   - Plan caching strategy (cache miss fallback)
   - Design notification rules (when to alert user)
   - Test with high-frequency updates

3. **Push Notifications:**
   - Audit Firebase Cloud Messaging integration
   - Plan notification queue (Redis/Celery)
   - Design retry logic (failed delivery)
   - Document delivery rate expectations

**Success Metrics:**
- [ ] WebSocket scalability tested (concurrent connections)
- [ ] Live data refresh rates documented
- [ ] Notification delivery tested (delivery rate %)
- [ ] Architecture design completed

**Timeline:** 3-4 days  
**Owner:** Backend/DevOps lead

---

### TIER 2: IMPORTANT RESEARCH (Affects Product Quality)

#### 2.6 Email & SMS Delivery Reliability
**Current State:** SendGrid API keys exist, SMS not integrated  
**Unknowns:**
- [ ] SendGrid delivery rates & spam handling
- [ ] Email bounce rates — how to clean list?
- [ ] SMS delivery reliability — 100%?
- [ ] Cost model — scalability at 100K messages/day?

**Research Tasks:**
1. **Email Service Audit:**
   - Set up SendGrid (verify domain, SPF/DKIM)
   - Test delivery (whitelist, spam folder)
   - Design email templates (responsive)
   - Plan unsubscribe/preference management

2. **SMS Service:**
   - Evaluate Twilio (cost, delivery, support)
   - Check DLT registration (India compliance)
   - Test delivery reliability
   - Plan SMS template library

3. **Notification Strategy:**
   - Document when to send email vs. SMS vs. push
   - Design notification preferences (user opt-in)
   - Plan notification cadence (frequency caps)

**Success Metrics:**
- [ ] Email templates created & tested
- [ ] SMS service configured
- [ ] Delivery rates documented
- [ ] Opt-in/preference system designed

**Timeline:** 2-3 days  
**Owner:** Frontend/Backend lead

---

#### 2.7 Search & Discovery Optimization
**Current State:** Search API exists, no ranking/filtering  
**Unknowns:**
- [ ] Search relevance — how to rank results?
- [ ] Filter effectiveness — user preferences vs. defaults?
- [ ] Performance — can filter complex queries?
- [ ] Caching strategy — when to cache vs. compute?

**Research Tasks:**
1. **Search Relevance:**
   - Analyze user behavior (what do users click?)
   - Design ranking algorithm (price, time, rating)
   - A/B test different rankings
   - Monitor search CTR

2. **Filter System:**
   - Identify high-value filters (price, departure time, class)
   - Test faceted search performance
   - Design filter UI (mobile-friendly)
   - Plan saved filters (user preferences)

3. **Caching Strategy:**
   - Profile cache hit rates (by city-pair)
   - Identify hot queries (popular routes)
   - Plan cache invalidation (when to refresh)
   - Document cache size vs. performance tradeoff

**Success Metrics:**
- [ ] Search ranking algorithm designed
- [ ] Filter performance tested
- [ ] Cache strategy documented
- [ ] User engagement metrics baseline

**Timeline:** 3-4 days  
**Owner:** Frontend/Backend lead

---

#### 2.8 Recommendation Engine Viability
**Current State:** Not built. Skeleton only.  
**Unknowns:**
- [ ] Is there enough data for personalization?
- [ ] Collaborative filtering vs. content-based?
- [ ] Complexity vs. value tradeoff?
- [ ] How to avoid filter bubbles?

**Research Tasks:**
1. **Data Availability:**
   - Audit search history data
   - Check booking patterns (repeat users?)
   - Analyze journey frequency
   - Identify data gaps

2. **Algorithm Selection:**
   - Research collaborative filtering (user-user, item-item)
   - Evaluate content-based filtering (route similarity)
   - Consider hybrid approach
   - Model complexity vs. recommendation quality

3. **Personalization Strategy:**
   - Plan A/B testing framework
   - Design recommendation UI placement
   - Document success metrics (CTR, bookings)
   - Identify cold-start problem (new users)

**Success Metrics:**
- [ ] Data availability assessed
- [ ] Algorithm selected & prototyped
- [ ] Recommendation metrics defined
- [ ] MVP version designed (simple vs. complex)

**Timeline:** 3-4 days  
**Owner:** ML/Data lead + Product

---

### TIER 3: HELPFUL RESEARCH (Improves Launch Quality)

#### 2.9 Admin Dashboard Metrics & Monitoring
**Current State:** Skeleton only  
**Unknowns:**
- [ ] What metrics matter most to operations?
- [ ] Alert thresholds — when to escalate?
- [ ] Real-time vs. batch reporting?
- [ ] Access control — who sees what data?

**Research Tasks:**
1. **KPI Selection:**
   - Interview ops/finance on critical metrics
   - Design dashboard layout (priority > nice-to-have)
   - Identify alert conditions (e.g., failed payment > 5%)
   - Plan data refresh frequency

2. **Monitoring Integration:**
   - Set up logging (centralized vs. distributed)
   - Design alerting (Slack/email alerts)
   - Plan anomaly detection (automated alerts)
   - Document runbooks (how to respond)

**Success Metrics:**
- [ ] KPI dashboard designed
- [ ] Critical alerts configured
- [ ] Monitoring setup tested
- [ ] Runbook documentation created

**Timeline:** 2-3 days  
**Owner:** DevOps/Backend lead

---

#### 2.10 Mobile Experience & Performance
**Current State:** React frontend, not tested on mobile  
**Unknowns:**
- [ ] Is mobile UX responsive/fast?
- [ ] Touch interactions — working correctly?
- [ ] Network resilience — handles slow/offline?
- [ ] Performance — FCP/LCP < 3s?

**Research Tasks:**
1. **Mobile Testing:**
   - Test on iOS (Safari, Chrome)
   - Test on Android (Chrome, Samsung Internet)
   - Verify touch targets (48px minimum)
   - Check responsive design (all screen sizes)

2. **Performance Audit:**
   - Run Lighthouse (mobile audit)
   - Measure Core Web Vitals (FCP, LCP, CLS)
   - Identify slow components
   - Profile bundle size (JS, CSS, images)

3. **Network Resilience:**
   - Test with slow 3G
   - Test with dropped connection (retry logic)
   - Design offline fallback (if applicable)
   - Test service worker caching

**Success Metrics:**
- [ ] Mobile UI tested & fixed
- [ ] Lighthouse score > 80
- [ ] Core Web Vitals within Google standards
- [ ] Performance baseline documented

**Timeline:** 2-3 days  
**Owner:** Frontend lead

---

#### 2.11 SEO & Content Strategy
**Current State:** City-pair pages exist, SEO not optimized  
**Unknowns:**
- [ ] Are pages indexable by Google?
- [ ] Keyword strategy — what to target?
- [ ] Content quality — competitive vs. thin?
- [ ] Internal linking — crawlability?

**Research Tasks:**
1. **Technical SEO:**
   - Audit robots.txt, sitemap.xml
   - Check meta tags (title, description)
   - Verify JSON-LD schema (organization, breadcrumb)
   - Test Core Web Vitals impact on ranking

2. **Keyword Research:**
   - Identify search intent (navigation, transactional, informational)
   - Research keyword volume (city-pairs)
   - Analyze competitor content
   - Plan content roadmap (cities, routes, guides)

3. **Content Strategy:**
   - Design city guide template
   - Plan route-specific content (tips, best times)
   - Strategy for user-generated content (reviews)
   - Link building plan (backlinks)

**Success Metrics:**
- [ ] Technical SEO audit passed
- [ ] Keyword research documented
- [ ] Content calendar created
- [ ] Baseline search impressions tracked

**Timeline:** 2-3 days  
**Owner:** Product/Marketing lead

---

#### 2.12 Analytics & Instrumentation
**Current State:** No analytics configured  
**Unknowns:**
- [ ] What events to track?
- [ ] Analytics tool (Google Analytics, Mixpanel, custom)?
- [ ] Data retention & privacy?
- [ ] Dashboard design for product/business teams?

**Research Tasks:**
1. **Event Strategy:**
   - Define user journey (signup → search → book)
   - Identify key events (search, click, book, payment)
   - Plan event properties (metadata)
   - Document event taxonomy

2. **Tool Selection:**
   - Evaluate Google Analytics 4 (free, powerful)
   - Mixpanel vs. Amplitude (advanced cohort analysis)
   - Privacy consideration (GDPR compliance)
   - Plan data warehousing (BigQuery, Snowflake)

3. **Dashboard Design:**
   - Acquisition (how users find app)
   - Engagement (user actions)
   - Retention (repeat users)
   - Monetization (revenue, ARPU)

**Success Metrics:**
- [ ] Event taxonomy documented
- [ ] Analytics tool deployed
- [ ] Key dashboards created
- [ ] Privacy policy updated

**Timeline:** 2-3 days  
**Owner:** Product/Data lead

---

## SECTION 3: TECHNICAL RESEARCH CHECKLIST

### Backend Infrastructure
- [ ] Python/FastAPI version compatibility
- [ ] Docker build & deployment process
- [ ] Environment variable strategy (dev/staging/prod)
- [ ] Error handling & logging standardization
- [ ] API versioning strategy
- [ ] Rate limiting configuration
- [ ] CORS/security headers

### Frontend Architecture
- [ ] React/TypeScript best practices (folder structure)
- [ ] State management (Redux/Context vs. Query)
- [ ] Component library documentation
- [ ] Build optimization (code splitting, lazy loading)
- [ ] Testing strategy (unit, integration, E2E)
- [ ] Error boundary implementation
- [ ] Loading states & skeleton screens

### Database Schema
- [ ] Foreign key constraints review
- [ ] Data integrity rules
- [ ] Audit logging (who changed what)
- [ ] Soft deletes vs. hard deletes strategy
- [ ] Historical data tracking (for refunds, disputes)

### DevOps & Deployment
- [ ] CI/CD pipeline configuration (GitHub Actions?)
- [ ] Database migration strategy
- [ ] Rollback procedures
- [ ] Monitoring & alerting setup
- [ ] Log aggregation strategy
- [ ] Disaster recovery plan

---

## SECTION 4: BUSINESS & MARKET RESEARCH

#### 4.1 Competitive Landscape
**Unknowns:**
- [ ] Top 3 competitors (feature comparison)
- [ ] Market size & growth rate
- [ ] Pricing strategy (commission %, markup)
- [ ] Differentiation opportunities

**Research Tasks:**
1. User research interviews (5-10 users)
2. Competitor feature audit
3. Pricing analysis (Indian market)
4. Market sizing study

**Timeline:** 4-5 days

---

#### 4.2 User Acquisition & Retention
**Unknowns:**
- [ ] Where do early users come from?
- [ ] What's the optimal notification frequency?
- [ ] How to maximize repeat bookings?
- [ ] Referral incentive structure?

**Research Tasks:**
1. Design acquisition channels (organic, paid, partnerships)
2. User retention analysis (booking frequency)
3. Referral program design
4. Email marketing strategy

**Timeline:** 3-4 days

---

#### 4.3 Monetization & Unit Economics
**Unknowns:**
- [ ] Booking rate (% of users who book)
- [ ] Average order value (AOV)
- [ ] Commission rate (IRCTC partnership terms)
- [ ] CAC payback period

**Research Tasks:**
1. Model revenue scenarios (100 → 10K → 100K users)
2. Calculate customer acquisition cost (CAC)
3. Lifetime value (LTV) estimation
4. Profitability timeline

**Timeline:** 2-3 days

---

## SECTION 5: RISK ASSESSMENT

### High-Risk Items
1. **IRCTC API Dependency** — Single point of failure, no alternative
   - Mitigation: Contact IRCTC for SLA, develop fallback (show erail.in data)

2. **Payment Gateway Downtime** — No revenue during outage
   - Mitigation: Razorpay has 99.99% uptime, add fallback (bank transfer)

3. **Database Performance** — Search query latency blocks UX
   - Mitigation: Load test before launch, optimize indexes

4. **Regulatory Changes** — India has strict travel/financial regulations
   - Mitigation: Legal review, maintain compliance calendar

### Medium-Risk Items
1. **External API Rate Limits** — Quota exhaustion
   - Mitigation: Cache aggressively, plan upgrade path

2. **Email/SMS Deliverability** — Low adoption if notifications fail
   - Mitigation: Test before launch, monitor delivery rates

3. **Auth/Security Vulnerabilities** — User data breach
   - Mitigation: Security audit, penetration testing

### Low-Risk Items
1. **Frontend Performance** — Bad user experience
   - Mitigation: Lighthouse audit, performance monitoring

2. **Content SEO** — Low organic traffic
   - Mitigation: Content strategy, backlink building

---

## SECTION 6: RESEARCH ROADMAP & TIMELINE

### Week 1: Critical Infrastructure Research
- External API audit (2.1)
- Database performance testing (2.2)
- Payment security review (2.3)
- Authentication audit (2.4)

**Deliverables:** API specification, database performance report, security checklist

### Week 2: Product & Feature Research
- Real-time infrastructure design (2.5)
- Email/SMS delivery setup (2.6)
- Search & discovery optimization (2.7)
- Recommendation engine evaluation (2.8)

**Deliverables:** Real-time architecture doc, email/SMS setup guide, search ranking spec

### Week 3: Quality & Launch Research
- Admin dashboard design (2.9)
- Mobile performance audit (2.10)
- SEO & content strategy (2.11)
- Analytics instrumentation (2.12)

**Deliverables:** Admin dashboard spec, mobile checklist, content calendar, analytics plan

---

## SECTION 7: SUCCESS METRICS & SIGN-OFF

### Research Quality Metrics
- [ ] All Tier 1 research areas completed (2.1-2.5)
- [ ] At least 90% of unknown risks documented
- [ ] Mitigation strategies defined for high-risk items
- [ ] All deliverables documented in memory files

### MVP Launch Readiness
- [ ] External APIs stress-tested & quota confirmed
- [ ] Database can handle 10x current load
- [ ] Payment flow tested end-to-end with Razorpay
- [ ] Auth system secured & verified
- [ ] Real-time infrastructure designed (implementation pending)

### Sign-off Checklist
- [ ] CTO/Technical Lead reviews all research
- [ ] Product Manager approves feature prioritization
- [ ] Finance approves cost model & unit economics
- [ ] Legal reviews compliance & partnerships

---

## SECTION 8: RESEARCH OUTPUT TEMPLATES

### For Each Research Area:
```
## Topic: [Name]
**Status:** [In Progress/Completed]
**Owner:** [Team member]
**Deadline:** [Date]

### Findings:
- Finding 1
- Finding 2

### Unknowns Resolved:
- [ ] Question 1: Answer
- [ ] Question 2: Answer

### Action Items:
1. Action 1 (deadline)
2. Action 2 (deadline)

### Risk Mitigation:
- Risk 1 → Mitigation approach

### Sign-off:
- [x] Reviewed by [stakeholder]
- [x] Approved by [stakeholder]
```

---

## SECTION 9: APPENDIX

### Key Contacts & Resources
- **IRCTC Integration:** Reach out to partnerships@irctc.co.in
- **Razorpay Support:** https://razorpay.com/support
- **Firebase Console:** https://console.firebase.google.com
- **Supabase Dashboard:** https://supabase.com/dashboard
- **API Documentation:** See `.kiro/specs/` folder

### Documentation Files to Update After Research
- `PROJECT_TECHNICAL_SPEC.md` (new)
- `PROJECT_RISK_LOG.md` (new)
- `DEPLOYMENT_CHECKLIST.md` (new)
- Memory files (learnings)

### Tools & Services for Research
- **Load Testing:** k6, locust
- **Monitoring:** Datadog, New Relic, Sentry
- **Analytics:** Google Analytics 4, Mixpanel
- **SEO Tools:** Semrush, Ahrefs, Google Search Console

---

## NEXT STEPS

1. **Assign owners** for each research area (Tier 1 first)
2. **Schedule kickoff meetings** with relevant teams
3. **Create tracking spreadsheet** for research status
4. **Set daily standups** (15 min) to discuss blockers
5. **Publish findings** as they complete (don't wait for all)
6. **Update memory file** with learnings for next session

---

**Research Lead:** Claude  
**Last Updated:** July 29, 2026  
**Status:** Ready for Team Assignment & Execution
