# RouteMaster V2: Production Deployment Checklist ✅

**Last Updated:** February 22, 2026  
**Status:** 🚀 READY FOR PRODUCTION DEPLOYMENT

---

## PRE-DEPLOYMENT VERIFICATION (Do This First)

### Code & Configuration ✓
- [x] All 5 Critical Fixes implemented:
  - [x] Frontend API URL configured for Docker (VITE_API_URL=http://api_gateway:8000)
  - [x] CORS origins set to environment variables
  - [x] Health check endpoints enhanced with Redis checks
  - [x] Database connection pool tuned (pool_size=20)
  - [x] Production docker-compose override created
- [x] Environment file template created (.env.prod.example)
- [x] Frontend Dockerfile created with 2-stage build
- [x] All services have health checks configured
- [x] JWT Secret Key generation documented

### Testing Completed
- [ ] **Local Development**: `docker-compose up -d` works
  - [ ] All services pass health checks
  - [ ] Frontend loads at http://localhost:5173
  - [ ] API responds at http://localhost:8000/api/health
  - [ ] Prometheus metrics accessible at http://localhost:9090
  - [ ] Grafana accessible at http://localhost:3000
- [ ] **Smoke Tests**: Run test_smoke.sh and verify all tests pass
- [ ] **Integration Test**: Full booking flow works end-to-end
  - [ ] Route search → Booking → Payment → Ticket
- [ ] **Load Testing**: k6 or Locust tested with 100+ concurrent users
- [ ] **Chaos Testing**: Services recover from single failures

---

## PRODUCTION SERVER SETUP

### Infrastructure Prerequisites
- [ ] Server specs: 16+ GB RAM, 100+ GB storage, Ubuntu 22.04 LTS
- [ ] Docker 24.0+ installed and verified
- [ ] Docker Compose 2.0+ installed and verified
- [ ] SSH configured (key-based auth only)
- [ ] Firewall configured (allow only ports 80, 443, 22)
- [ ] DNS A record points to server IP
- [ ] SSL certificate obtained (Let's Encrypt)

### System Configuration
- [ ] System time synchronized (ntpdate)
- [ ] Swap configured (if <16GB RAM)
- [ ] Disk partitions optimized (`df -h`)
- [ ] Log rotation configured
- [ ] Automatic updates enabled

### Security Hardening
- [ ] SSH key-based auth only (no passwords)
- [ ] Fail2ban configured for SSH
- [ ] Sudo access limited to specific users
- [ ] Regular backups tested and working
- [ ] Database backups encrypted and off-site
- [ ] No hardcoded secrets in code

---

## DEPLOYMENT EXECUTION

### Pre-Flight Checks
```bash
# Run these commands before deployment
[ ] docker --version          # Should be 24.0+
[ ] docker-compose --version  # Should be 2.0+
[ ] df -h /                   # Should have 100+ GB free
[ ] free -h                   # Should have 16+ GB available
[ ] systemctl status docker   # Should be active
```

### Environment Preparation
- [ ] Clone repository to production server
- [ ] Copy .env.prod.example → .env.prod
- [ ] Fill in all values in .env.prod:
  - [ ] DATABASE_URL (with production credentials)
  - [ ] REDIS_PASSWORD (strong random value)
  - [ ] JWT_SECRET_KEY (openssl rand -hex 32)
  - [ ] RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET
  - [ ] TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
  - [ ] SENDGRID_API_KEY
  - [ ] OPENROUTER_API_KEY
  - [ ] ALLOWED_ORIGINS (your domain)
  - [ ] FRONTEND_API_URL (your domain)
  - [ ] GRAFANA_ADMIN_PASSWORD
- [ ] SSL certificates placed in ./monitoring/nginx/ssl/
- [ ] .env.prod permissions: `chmod 600 .env.prod`

### Deploy Stack
```bash
# Step 1: Create volumes
[ ] docker volume create postgres_data
[ ] docker volume create redis_data
[ ] docker volume create grafana_data

# Step 2: Deploy
[ ] docker-compose -f docker-compose.yml \
               -f docker-compose.prod.yml \
               --env-file .env.prod \
               up -d

# Step 3: Monitor startup (should take 2-3 minutes)
[ ] docker-compose ps  # All services should show "Up"
[ ] sleep 60 && docker-compose ps  # Wait and check again

# Step 4: Verify health
[ ] curl http://localhost:8000/api/health
[ ] curl http://localhost:3000  # Frontend
[ ] curl http://localhost:5173  # Frontend alternate
```

### Post-Deployment Verification
- [ ] All containers are running: `docker-compose ps`
- [ ] No error logs: `docker-compose logs --tail=20 | grep -i error`
- [ ] Database responsive: `docker-compose exec db pg_isready -U postgres`
- [ ] Redis responsive: `docker-compose exec redis redis-cli ping`
- [ ] API Gateway healthy: `curl http://localhost:8000/api/health`
- [ ] Frontend loads: `curl http://localhost:3000 | head -20`

### Smoke Test Suite
```bash
# Run smoke tests
[ ] ./smoke-tests.sh

# Expected output:
# ✅ Health check passed
# ✅ Auth endpoint responding
# ✅ Search endpoint working
# ✅ Frontend serving
# ✅ Prometheus working
# 🎉 All smoke tests passed!
```

---

## USER ACCEPTANCE TESTING (UAT)

### Authentication Flow
- [ ] User can send OTP via phone
- [ ] OTP verification works
- [ ] JWT token is issued
- [ ] Token is stored in browser
- [ ] Subsequent requests include token
- [ ] Expired token triggers re-login

### Route Search
- [ ] Search works without authentication
- [ ] Date picker limits to valid dates
- [ ] Results display with proper formatting
- [ ] Sorting by price and duration works
- [ ] Filtering by class and quota works
- [ ] Performance is fast (<2 seconds)

### Booking Flow
- [ ] User can select a route
- [ ] Passenger details form works
- [ ] Availability check passes/fails correctly
- [ ] Booking can be confirmed
- [ ] PNR is generated and displayed

### Payment Processing
- [ ] Payment modal opens
- [ ] Razorpay payment gateway initializes
- [ ] Payment can be completed with test card
- [ ] Payment verification succeeds
- [ ] Booking is created after payment
- [ ] User can download ticket PDF

### SOS Functionality
- [ ] SOS page loads
- [ ] Location permission works
- [ ] SOS alert can be triggered
- [ ] Alert appears in responder dashboard
- [ ] SMS/Email notification sent

### Real-time Features
- [ ] WebSocket connection established
- [ ] Live train position updates received
- [ ] Train status changes propagate in real-time
- [ ] Multiple connections don't cause issues

### Admin/Monitoring
- [ ] Prometheus metrics accessible at :9090
- [ ] Grafana dashboards show data at :3000
- [ ] Logs visible in Loki at :3100
- [ ] Alerts configure correctly

---

## MONITORING & ALERTING SETUP

### Prometheus Configuration
- [ ] Prometheus scrape targets configured
- [ ] Alert rules loaded (rules.yml)
- [ ] Webhooks configured for Slack/Email
- [ ] Memory/CPU alerts firing correctly

### Grafana Dashboards
- [ ] Default admin password changed
- [ ] Data sources added (Prometheus, Loki)
- [ ] Dashboards imported or created:
  - [ ] API Latency
  - [ ] Database Performance
  - [ ] Error Rates
  - [ ] WebSocket Connections
  - [ ] System Resources
- [ ] Notification channels configured (Slack, Email, PagerDuty)

### Log Aggregation
- [ ] Loki storing logs from all containers
- [ ] Promtail shipping logs correctly
- [ ] Log viewers can search by container, error level
- [ ] Log retention policy set (30 days)

### Backup & Recovery
- [ ] Database backup script created and tested
- [ ] Backups run on schedule (2 AM daily)
- [ ] Off-site backup storage configured (S3)
- [ ] Restore procedure documented and tested
- [ ] Recovery Time Objective (RTO) <1 hour

---

## PERFORMANCE BASELINE

### Record These Metrics Before Launch
```
API Latency (p95):         _____ ms
API Latency (p99):         _____ ms
Database Queries/sec:      _____ qps
Redis Hit Ratio:           _____%
Active WebSocket Connections: _____
Memory Usage:              _____GB
CPU Usage:                 _____%
Disk I/O:                  _____ MB/s
Network I/O:               _____ Mbps
```

### Load Test Results
- [ ] 100 concurrent users: API latency <500ms
- [ ] 500 concurrent users: API latency <1000ms
- [ ] 1000 concurrent users: API latency <2000ms
- [ ] Error rate <0.1% under all loads
- [ ] No memory leaks detected over 1 hour
- [ ] No database connection issues

---

## OPERATIONAL RUNBOOKS

### Daily Checks (Every Morning)
```bash
# Check system health
docker-compose ps                           # All running?
docker-compose logs --tail=100 | grep ERROR # Any errors?
curl http://localhost:8000/api/health       # API healthy?
```

### Weekly Tasks
- [ ] Review error logs in Sentry
- [ ] Check database disk usage
- [ ] Test backup restoration
- [ ] Review performance metrics
- [ ] Update security patches

### Monthly Tasks
- [ ] Full disaster recovery test
- [ ] Capacity planning review
- [ ] Cost analysis
- [ ] Security audit

---

## INCIDENT RESPONSE

### If API is Unresponsive:
```bash
# 1. Check containers
docker-compose ps
# 2. Check logs
docker-compose logs api_gateway
# 3. Restart if needed
docker-compose restart api_gateway
# 4. Escalate if still not responding
# Contact: DevOps on-call engineer
```

### If Database is Slow:
```bash
# 1. Check connections
docker-compose exec db psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
# 2. Check disk I/O
iostat -x 1
# 3. If high connection count, restart ORM connection pool
docker-compose restart api_gateway
# 4. If disk I/O high, check backups
df -h /var/lib/docker/volumes/
```

### If Payment Service Fails:
```bash
# 1. Check Razorpay API status
# Visit: https://status.razorpay.com
# 2. Verify credentials
docker-compose logs payment_service | grep RAZORPAY
# 3. Test API key
curl -u "KEY_ID:KEY_SECRET" https://api.razorpay.com/v1/health
# 4. If API key invalid, update .env.prod and restart
```

---

## LAUNCH SIGN-OFF

### Development Team
- [ ] Code reviewed and approved
- [ ] All tests passing locally
- [ ] Documentation updated
- [ ] Signed by: _________________ Date: _______

### QA Team
- [ ] UAT completed successfully
- [ ] Performance benchmarks met
- [ ] Security testing passed
- [ ] Signed by: _________________ Date: _______

### DevOps Team
- [ ] Infrastructure validated
- [ ] Monitoring configured
- [ ] Backup tested
- [ ] Runbooks created
- [ ] Signed by: _________________ Date: _______

### Product Owner
- [ ] Feature completeness verified
- [ ] User documentation ready
- [ ] Support team trained
- [ ] Signed by: _________________ Date: _______

---

## GO-LIVE EXECUTION

### T-24 Hours
- [ ] Final code freeze
- [ ] Deploy to staging for final validation
- [ ] Team on standby

### T-0 (Launch Time)
- [ ] Execute deployment
  ```bash
  docker-compose -f docker-compose.yml \
                 -f docker-compose.prod.yml \
                 --env-file .env.prod \
                 up -d
  ```
- [ ] Monitor system metrics closely
- [ ] Run smoke tests every 5 minutes
- [ ] Keep logs visible in terminal

### T+1 Hour
- [ ] All metrics normal
- [ ] No error spikes
- [ ] UAT users testing successfully
- [ ] Enable monitoring alerts

### T+24 Hours
- [ ] Monitor for memory leaks
- [ ] Check database size growth
- [ ] Review error logs
- [ ] Collect feedback from users

### T+7 Days
- [ ] Full review with team
- [ ] Performance analysis
- [ ] Optimization opportunities identified
- [ ] Post-mortem if any issues

---

**✅ WHEN ALL BOXES ARE CHECKED: SYSTEM IS READY FOR PRODUCTION LAUNCH**

**Questions?** Refer to:
- DEPLOYMENT_INTEGRATION_PLAYBOOK.md (step-by-step guide)
- PRODUCTION_INTEGRATION_ANALYSIS.md (architecture & gaps analysis)
- FRONTEND_BACKEND_INTEGRATION_ANALYSIS.md (API contracts & contracts)
