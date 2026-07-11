# RouteMaster Feature #1 — Deployment Checklist

**Feature**: Booking System (Teams 1-5)  
**DevOps Lead**: Team 6  
**Deployment Date**: [TBD]  
**Status**: Ready for deployment

---

## Pre-Deployment (1-2 days before)

### Code Review
- [ ] All Teams 1-5 code reviewed and approved
- [ ] No merge conflicts
- [ ] All tests passing locally
- [ ] No console errors or warnings

### Environment Preparation
- [ ] `.env.local` filled with Razorpay test credentials
- [ ] `.env.staging` ready (stored in Render dashboard)
- [ ] `.env.production` ready (stored in Render secrets)
- [ ] All required API keys obtained:
  - [ ] RAZORPAY_KEY_ID (test: rzp_test_...)
  - [ ] RAZORPAY_KEY_SECRET
  - [ ] RAZORPAY_WEBHOOK_SECRET

### Database
- [ ] Database backup created (Supabase)
- [ ] All migrations tested locally
- [ ] Tables verified:
  - [ ] `bookings` table exists
  - [ ] `booking_idempotency` table exists
  - [ ] `booking_monitors` table exists
  - [ ] All indexes present

### Monitoring Setup
- [ ] Grafana dashboard created
- [ ] Alert rules configured:
  - [ ] Payment success rate alert
  - [ ] Webhook latency alert
  - [ ] Database down alert
- [ ] Slack #devops-team-6-payments channel ready
- [ ] PagerDuty on-call rotation set

### Team Coordination
- [ ] All team leads know their roles
- [ ] Rollback procedure reviewed
- [ ] Escalation contacts listed
- [ ] Standup scheduled for deployment day

---

## Day Before (24 hours)

### Final Validation
- [ ] Run `bash scripts/pre_deploy.sh` → All checks pass ✓
- [ ] Run `python scripts/test_webhook.py --test all` → All tests pass ✓
- [ ] Database connectivity confirmed
- [ ] Redis connectivity confirmed
- [ ] Razorpay client initialization works

### Staging Deployment Rehearsal
- [ ] Merge code to `staging` branch
- [ ] Render auto-deploys (watch for 3-5 min)
- [ ] Hit endpoint: `curl https://staging-api.../health` → 200 OK
- [ ] Send test webhook → processes successfully
- [ ] Check logs for errors

### Team Readiness
- [ ] All teams available on deployment day
- [ ] Communication channels tested (Slack, Zoom)
- [ ] Team leads have runbook access
- [ ] Rollback contacts confirmed

---

## Deployment Day

### Pre-Deployment (1 hour before)

**Terminal 1: Deployment Engineer**
```bash
cd backend

# 1. Final checks
bash scripts/pre_deploy.sh
# Expected: ✓ ALL CHECKS PASSED

# 2. Code review one more time
git log --oneline staging..production | head -20

# 3. Backup database
# In Supabase: Settings → Backups → Create Manual Backup

# 4. Notify teams
# Post in #devops-team-6-payments: "Deployment starting in 1 hour"
```

**Terminal 2: Monitoring**
```bash
# Start watching metrics
# Open: https://grafana.routemaster.app/d/feature1-payments
# Watch: Success rate, latency, error rate (should be stable)
```

**Terminal 3: Logs**
```bash
# SSH to staging/production
# Tail logs: tail -f logs/app.log
# Watch for errors
```

### Staging Deployment (30 minutes)

**Step 1: Code merge**
```bash
git checkout staging
git pull origin staging
git merge --no-ff feature/booking-feature-1
git push origin staging
# Expected: Render auto-deploys in 3-5 min
```

**Step 2: Verify build**
```bash
# Monitor: https://dashboard.render.com
# Service: routemaster-api-staging
# Wait for: "Deploy successful"

curl https://staging-api.routemaster.railway.app/health
# Expected: {"status": "ok"}
```

**Step 3: Smoke test**
```bash
# Team 1: Create booking
curl -X POST https://staging-api.../api/v1/bookings -d '...'
# Expected: {booking_id, status: pending}

# Team 2: Create payment order
curl -X POST https://staging-api.../api/v1/payments/create -d '...'
# Expected: {order_id, key}

# Team 3: Send webhook (use script)
python scripts/test_webhook.py --environment staging
# Expected: All events processed successfully
```

**Step 4: Monitor for 30 minutes**
```
Watch metrics:
- Payment success rate (should be 100%)
- Webhook latency p99 (should be < 5s)
- Error rate (should be 0%)
- Database latency (should be < 100ms)

If any issues: STOP. Investigate before proceeding.
```

### Production Deployment (Canary)

**Phase 1: 10% Traffic (30 minutes)**

```bash
# 1. Merge to production
git checkout production
git pull origin production
git merge --no-ff staging
git push origin production

# 2. Deploy (Render auto-deploys)
# Wait for: "Deploy successful"

# 3. Set traffic split to 10%
# Render Dashboard → Service: routemaster-api-prod
# → Deployments → Route 10% to new version, 90% to current

# 4. Monitor for 30 min
curl https://api.routemaster.app/health  # Should work

# Watch Grafana metrics:
# - Success rate (target: > 99%)
# - Error rate (target: < 0.5%)
# - Latency p99 (target: < 500ms)

# If all green: Continue to Phase 2
# If issues: ROLLBACK (set traffic to 0%, revert to previous)
```

**Phase 2: 50% Traffic (30 minutes)**

```bash
# 1. Increase traffic
# Render Dashboard → Service: routemaster-api-prod
# → Route 50% to new version, 50% to current

# 2. Monitor for 30 min
# Watch same metrics as Phase 1

# If all green: Continue to Phase 3
# If issues: ROLLBACK
```

**Phase 3: 100% Traffic (go live)**

```bash
# 1. Remove old version
# Render Dashboard → Service: routemaster-api-prod
# → Route 100% to new version
# → Deactivate old version

# 2. Confirm deployment
curl https://api.routemaster.app/health

# 3. Post success message
# Slack: "Feature #1 Booking System deployed to production ✓"

# 4. Monitor continuously
# Next 24 hours: Watch all metrics closely
```

---

## Post-Deployment

### First Hour
- [ ] All endpoints respond (< 200ms)
- [ ] No error spikes in logs
- [ ] Payment success rate > 99%
- [ ] Webhook latency p99 < 10s
- [ ] Database latency < 100ms
- [ ] Team 1-5 report no issues

### First 24 Hours
- [ ] Continuous monitoring
- [ ] No rollbacks needed
- [ ] Success rate stays > 99.5%
- [ ] Alert rules trigger correctly (test one)
- [ ] Runbook validated with real scenario

### After 24 Hours
- [ ] Success criteria met
- [ ] All teams sign off ✓
- [ ] Monitoring dashboard operational
- [ ] Documentation updated
- [ ] Post-mortem scheduled (if any issues)

---

## Rollback Procedure

**If anything goes wrong**:

### Immediate Rollback (< 2 minutes)

```bash
# 1. Pause payments (stop accepting new charges)
curl -X POST https://api.routemaster.app/admin/payments/pause \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 2. Revert deployment
# Render Dashboard → Service: routemaster-api-prod
# → Deployments → Select previous version → "Activate"

# 3. Verify rollback
curl https://api.routemaster.app/health

# 4. Resume payments
curl -X POST https://api.routemaster.app/admin/payments/resume \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 5. Post incident notification
# Slack: "@channel Rolled back Feature #1 due to [reason]"
```

### Database Rollback (if schema migration failed)

```bash
# 1. Stop app
# Render → Service → routemaster-api-prod → Restart (already done)

# 2. Restore from backup
# Supabase → Settings → Backups → Restore [previous backup]

# 3. Verify data
# Test query: SELECT COUNT(*) FROM bookings;

# 4. Restart app
# Render → Service → routemaster-api-prod → Deploy [previous version]
```

---

## Success Criteria

✅ **Must have all of these**:

- [ ] All endpoints responding (HTTP 200)
- [ ] Payment success rate > 99.5%
- [ ] Webhook latency p99 < 10s
- [ ] Database latency p99 < 100ms
- [ ] Error rate < 0.5%
- [ ] No red alerts in monitoring
- [ ] All Teams 1-5 sign off
- [ ] Zero critical issues reported

❌ **If any of these happen, ROLLBACK immediately**:

- [ ] Payment success rate drops below 98%
- [ ] Webhook latency p99 > 15s
- [ ] Database connection errors
- [ ] Unexplained error spikes
- [ ] PagerDuty alert fires
- [ ] Rollback from any team

---

## Contact & Escalation

| Role | Name | Slack | Phone |
|------|------|-------|-------|
| DevOps Lead | [Name] | @devops-lead | +91... |
| Team 1 Lead | [Name] | @team1-lead | +91... |
| Team 2 Lead | [Name] | @team2-lead | +91... |
| Team 3 Lead | [Name] | @team3-lead | +91... |
| Team 4 Lead | [Name] | @team4-lead | +91... |
| Team 5 Lead | [Name] | @team5-lead | +91... |
| On-Call Engineer | [Name] | @oncall | +91... |

**Escalation path**:
1. Post in #devops-team-6-payments (immediate)
2. Page on-call engineer (if critical)
3. Activate incident response (if severe)

---

## Notification Timeline

| Time | Message | Channel |
|------|---------|---------|
| T-24h | "Deployment scheduled for [time]" | Slack |
| T-1h | "Deployment starting in 1 hour" | Slack |
| T+0 | "Staging deployment in progress" | Slack |
| T+30m | "Production canary: 10% traffic" | Slack |
| T+1h | "Production canary: 50% traffic" | Slack |
| T+1.5h | "Production canary: 100% traffic" | Slack |
| T+2h | "Feature #1 deployed successfully ✓" | Slack |
| T+24h | "Deployment verified, monitoring green ✓" | Slack |

---

## Sign-Off

**Before deployment**:
- [ ] Gaurav (Founder): Approved deployment
- [ ] DevOps Lead: All infrastructure ready
- [ ] Team 1-5 Leads: Code ready for deployment
- [ ] QA: Staging verified
- [ ] On-Call Engineer: Available

**After deployment**:
- [ ] DevOps Lead: Deployment successful ✓
- [ ] Team 1-5 Leads: Functionality verified ✓
- [ ] On-Call Engineer: Monitoring set up ✓
- [ ] Gaurav: Feature #1 live ✓

---

## Links

- **Render Dashboard**: https://dashboard.render.com
- **Supabase**: https://app.supabase.com
- **Grafana**: https://grafana.routemaster.app
- **Razorpay Dashboard**: https://dashboard.razorpay.com
- **GitHub**: [repo link]
- **Slack**: #devops-team-6-payments
- **Runbook**: [shared drive link]

---

**Created**: June 8, 2026  
**Version**: 1.0  
**Last Updated**: [TBD]

**Status**: READY FOR DEPLOYMENT
