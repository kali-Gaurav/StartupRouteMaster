# DevOps Team 6 — Feature #1 Booking System Infrastructure

**Status**: COMPLETE & READY FOR PRODUCTION  
**Created**: June 8, 2026  
**For**: Teams 1-5 (Booking, Payment, Webhook, Idempotency, Monitoring)

---

## Start Here

### For Gaurav (Founder)
1. Read `DEVOPS_TEAM_6_SUMMARY.md` (2 min) — Overview of what's done
2. Check `DEVOPS_SETUP_TEAM_6.md` section 1-3 for credentials setup
3. All Teams 1-5 ready to build in parallel — no blockers

### For Teams 1-5
1. Read `TEAMS_1_5_QUICK_START.md` — Your specific instructions
2. Database tables ready (verified) — start building
3. Use environment variables from `.env.local.template`
4. Run `bash scripts/pre_deploy.sh` before deployment

### For DevOps/Deployment
1. `DEVOPS_SETUP_TEAM_6.md` — Complete deployment guide
2. Pre-deployment: `bash scripts/pre_deploy.sh`
3. Test webhooks: `python scripts/test_webhook.py`
4. Monitor: See section 6 (KPIs, alerts, dashboard)

---

## Files Created

### Documentation (4 files)

| File | Purpose | Audience | Length |
|------|---------|----------|--------|
| `DEVOPS_SETUP_TEAM_6.md` | Complete infrastructure guide | DevOps, Architect | 10 sections |
| `DEVOPS_TEAM_6_SUMMARY.md` | Quick overview & checklist | Gaurav, Leads | 2 pages |
| `TEAMS_1_5_QUICK_START.md` | Each team's build instructions | Teams 1-5 | 5 sections |
| `README_DEVOPS_TEAM_6.md` | This file (navigation) | Everyone | Quick ref |

### Configuration Templates (3 files)

| File | Environment | Razorpay Keys | Use |
|------|-------------|---------------|-----|
| `.env.local.template` | Development | Test (rzp_test_) | Copy → .env.local |
| `.env.staging.template` | Staging | Test (rzp_test_) | Copy → Render env |
| `.env.production.template` | Production | LIVE (rzp_live_) | Copy → Render secrets |

### Automation Scripts (2 files)

| File | Purpose | When to use |
|------|---------|------------|
| `scripts/pre_deploy.sh` | Pre-deployment validation | Before every deploy |
| `scripts/test_webhook.py` | Webhook event testing | During development/staging |

---

## Quick Start (30 minutes)

### Step 1: Local Development Setup (5 min)
```bash
cd backend

# Copy dev template
cp .env.local.template .env.local

# Get Razorpay test credentials
# Visit: https://dashboard.razorpay.com → Settings → API Keys
# Copy Key ID (rzp_test_...) and Key Secret

# Edit .env.local with your credentials
nano .env.local
```

### Step 2: Verify Everything Works (5 min)
```bash
# Run pre-deployment checks
bash scripts/pre_deploy.sh

# Expected: ✓ ALL CHECKS PASSED
```

### Step 3: Start Building (20 min)
```bash
# Terminal 1: Start server
python app.py

# Terminal 2: Read your team's instructions
cat TEAMS_1_5_QUICK_START.md  # Find your team

# Terminal 3: Test webhooks (if Team 3)
python scripts/test_webhook.py --test all
```

---

## What's Ready For Each Team

### Team 1: Booking API
- ✅ `Booking` table with all fields
- ✅ Database session management
- ✅ Sample code in TEAMS_1_5_QUICK_START.md
- Build: POST `/api/v1/bookings`, GET `/api/v1/bookings/{id}`

### Team 2: Payment Flow
- ✅ `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` env vars
- ✅ Razorpay Python client (in requirements.txt)
- ✅ Idempotency framework
- Build: POST `/api/v1/payments/create`

### Team 3: Webhook Handler
- ✅ `RAZORPAY_WEBHOOK_SECRET` env var
- ✅ Signature verification framework
- ✅ Test script: `scripts/test_webhook.py`
- Build: POST `/api/v1/payments/webhook`

### Team 4: Idempotency Engine
- ✅ `BookingIdempotency` table with TTL logic
- ✅ Sample IdempotencyEngine class in guide
- ✅ Database session ready
- Build: Deduplication logic + cleanup job

### Team 5: Error Handling & Monitoring
- ✅ Prometheus metrics framework
- ✅ Structured logging format
- ✅ Alert thresholds defined
- Build: Metrics emission + error handling

---

## Database Verification

**All required tables exist**:

```python
from database.models.core import (
    Booking,                 # bookings table
    BookingIdempotency,      # booking_idempotency table
    BookingMonitor,          # booking_monitors table
    User,                    # users table
    BankTransaction          # bank_transactions table
)
```

**To verify locally**:
```bash
bash scripts/pre_deploy.sh  # Checks all tables exist
```

**Tables in database** (verified in core.py):
- Line 209: `Booking` table
- Line 261: `BookingIdempotency` table
- Line 291: `BookingMonitor` table
- Line 44: `BankTransaction` table
- Line 73: `User` table

---

## Deployment Timeline

### Day 1: Local Development
- Teams 1-5 build in parallel
- Run `scripts/pre_deploy.sh` frequently
- Test `scripts/test_webhook.py` (Team 3)

### Day 2: Staging
- Merge to `staging` branch
- Render auto-deploys (3-5 min)
- Monitor metrics for 1-2 hours
- All teams QA: payment flow end-to-end

### Day 3: Production (Canary)
- 10% traffic (30 min)
- 50% traffic (30 min)
- 100% traffic → monitor 24h
- If issues: Rollback to previous version

---

## Key Commands

**Pre-deployment validation**:
```bash
bash backend/scripts/pre_deploy.sh
```

**Test webhook locally**:
```bash
python backend/scripts/test_webhook.py \
  --environment development \
  --booking-id test-123 \
  --amount 5000 \
  --test all
```

**Start local server**:
```bash
cd backend
python app.py
```

**Check database tables**:
```bash
python -c "
from database.infrastructure.session import get_sync_db
from sqlalchemy import inspect
db = get_sync_db()
inspector = inspect(db)
for table in inspector.get_table_names():
    if 'booking' in table:
        print(f'✓ {table}')
"
```

---

## Troubleshooting

### "Missing RAZORPAY_KEY_ID"
→ Copy `.env.local.template` to `.env.local` and fill in credentials

### "Database connection failed"
→ Check `DATABASE_URL` in `.env.local`
→ Verify Supabase is running
→ Run: `bash scripts/pre_deploy.sh`

### "Webhook test fails"
→ Make sure server is running: `python app.py`
→ Check logs: `tail -f logs/app.log`
→ Run: `python scripts/test_webhook.py --environment development`

### "Pre-deployment validation fails"
→ Run: `bash scripts/pre_deploy.sh`
→ Fix any ✗ items (follow error messages)
→ Re-run validation

---

## Monitoring & Alerts

**Production KPIs**:
- Payment success rate > 99.5%
- Webhook latency p99 < 10s
- Payment authorization time < 2s

**Alert thresholds**:
- Success rate < 98% → Page on-call
- Webhook latency > 10s p99 → Page on-call
- Database down → Page on-call

**See**: `DEVOPS_SETUP_TEAM_6.md` section 6 for full monitoring spec

---

## Team Assignments

| Team | Lead | Component | Status |
|------|------|-----------|--------|
| 1 | [Name] | Booking API | Ready to build |
| 2 | [Name] | Payment Flow | Ready to build |
| 3 | [Name] | Webhook Handler | Ready to build |
| 4 | [Name] | Idempotency | Ready to build |
| 5 | [Name] | Monitoring | Ready to build |
| 6 | [You] | DevOps Infrastructure | ✅ COMPLETE |

---

## Documentation Map

```
Decision tree for finding what you need:

Are you...

├─ Gaurav (founder)?
│  └─ Read: DEVOPS_TEAM_6_SUMMARY.md (2 min overview)
│
├─ Team 1 (Booking API)?
│  └─ Read: TEAMS_1_5_QUICK_START.md → Team 1 section
│
├─ Team 2 (Payment Flow)?
│  └─ Read: TEAMS_1_5_QUICK_START.md → Team 2 section
│
├─ Team 3 (Webhook Handler)?
│  └─ Read: TEAMS_1_5_QUICK_START.md → Team 3 section
│  └─ Use: scripts/test_webhook.py for testing
│
├─ Team 4 (Idempotency)?
│  └─ Read: TEAMS_1_5_QUICK_START.md → Team 4 section
│
├─ Team 5 (Monitoring)?
│  └─ Read: TEAMS_1_5_QUICK_START.md → Team 5 section
│
├─ DevOps/Deployment?
│  └─ Read: DEVOPS_SETUP_TEAM_6.md (complete guide)
│  └─ Use: scripts/pre_deploy.sh for validation
│
└─ Need configuration?
   └─ See: .env.local.template (dev)
   └─ See: .env.staging.template (staging)
   └─ See: .env.production.template (prod)
```

---

## Success Criteria

### Local (Day 1)
- [ ] All environment variables set
- [ ] `pre_deploy.sh` passes all checks
- [ ] Each team can run their endpoints
- [ ] Database tables accessible

### Staging (Day 2)
- [ ] Code deployed to staging
- [ ] Payment flow works end-to-end
- [ ] Webhook processes events
- [ ] Idempotency prevents duplicates
- [ ] Metrics show > 99% success rate

### Production (Day 3)
- [ ] Canary deployment successful
- [ ] 10% → 50% → 100% traffic increase
- [ ] No error rate spike
- [ ] Webhooks process in < 5s
- [ ] 24h monitoring green

---

## Support

**Questions?** Check these in order:
1. Section 8 of `DEVOPS_SETUP_TEAM_6.md` (Verification Steps)
2. Your team's section in `TEAMS_1_5_QUICK_START.md`
3. Run `bash scripts/pre_deploy.sh` (identifies issues)
4. Slack: `#devops-team-6-payments`

**Contact DevOps**: [Slack DM / Email]

---

## Files at a Glance

```
backend/
├── README_DEVOPS_TEAM_6.md                    ← You are here
├── DEVOPS_SETUP_TEAM_6.md                     ← Full guide (10 sections)
├── DEVOPS_TEAM_6_SUMMARY.md                   ← 2-page overview
├── TEAMS_1_5_QUICK_START.md                   ← Team instructions
├── .env.local.template                        ← Dev config template
├── .env.staging.template                      ← Staging config template
├── .env.production.template                   ← Production config template
├── database/
│   └── models/core.py                         ← All tables defined
├── scripts/
│   ├── pre_deploy.sh                          ← Validation script
│   └── test_webhook.py                        ← Webhook testing
└── app.py                                     ← Main app entry point
```

---

## Last Words

✅ All DevOps infrastructure is done.
✅ No blockers for Teams 1-5.
✅ Database is ready.
✅ Deployment procedures are documented.
✅ You can build with confidence.

**Next step**: Teams 1-5 start building (parallel execution).

---

**Created by**: DevOps Team 6  
**Date**: June 8, 2026  
**Status**: READY FOR EXECUTION

Good luck! 🚀
