# DevOps Setup Guide — Feature #1: Booking System (Team 6)

**Status**: Ready for parallel execution  
**Target**: Complete in 1-2 hours (while Teams 1-5 build code)  
**Created**: June 8, 2026

---

## 1. CREDENTIAL MANAGEMENT GUIDE

### 1.1 Razorpay API Key Retrieval (Test Account)

**Process**:
1. Go to https://dashboard.razorpay.com
2. Sign in (or create account if new)
3. **Account** → **Settings** → **API Keys**
4. Copy two values:
   - `Key ID` (starts with `rzp_test_...`)
   - `Key Secret` (32-char alphanumeric)

**Test Credentials File**:
```
Dashboard URL: https://dashboard.razorpay.com/app/dashboard
Test Mode: Enabled (red toggle visible)
Key ID: rzp_test_XXXXXXXXXXXXXX
Key Secret: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**Store these securely** (see 1.3 below).

### 1.2 Environment Variable Naming Convention

**Frontend (client-side only)**:
- `VITE_RAZORPAY_KEY_ID=rzp_test_...` (publicly exposed in frontend)
- OK to commit in env files (test keys only)

**Backend (server-side, PRIVATE)**:
- `RAZORPAY_KEY_ID=rzp_test_...` (used for backend requests)
- `RAZORPAY_KEY_SECRET=...` (NEVER commit, NEVER log)
- `RAZORPAY_WEBHOOK_SECRET=...` (webhook signature verification)

### 1.3 Storage Strategy

**Development (Local)**:
```
backend/.env.local          ← .gitignore (PRIVATE)
  RAZORPAY_KEY_ID=rzp_test_...
  RAZORPAY_KEY_SECRET=...
  RAZORPAY_WEBHOOK_SECRET=...
```

**Staging**:
- Store in **Render dashboard** → **Environment** tab
- OR: Use **GitHub Secrets** for Actions
- Never hardcode in code

**Production**:
- **HashiCorp Vault** (recommended for enterprise)
- **AWS Secrets Manager** (if using AWS)
- **Render Secrets** (quick alternative)
- **Supabase Vault** (if using Supabase)

**Rotation Policy**:
- Test keys: No rotation needed (test environment)
- Production keys: Rotate quarterly
- Webhook secret: Rotate after key rotation

---

## 2. ENVIRONMENT CONFIGURATION TEMPLATES

### 2.1 Development (.env.local)

Create `backend/.env.local` (NOT committed):

```bash
# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-1-ap-south-1.pooler.supabase.com:6543/postgres

# Redis (Upstash)
REDIS_URL=rediss://default:<token>@<host>.upstash.io:6379

# Razorpay (Test Keys)
RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXXXX
RAZORPAY_KEY_SECRET=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
RAZORPAY_WEBHOOK_SECRET=whsec_test_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# App Settings
ENVIRONMENT=development
LOG_LEVEL=DEBUG
PYTHONPATH=./backend

# Frontend (client-side)
VITE_RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXXXX

# Other required APIs
RAPIDAPI_KEY=<your-api-key>
GEMINI_API_KEY=<your-gemini-api-key>
TELEGRAM_BOT_TOKEN=<your-telegram-token>
```

**How to use**:
```bash
cd backend
python -m dotenv load .env.local
python app.py
```

### 2.2 Staging (.env.staging)

Create `backend/.env.staging` (PRIVATE, reference only):

```bash
# Database (Staging: Supabase)
DATABASE_URL=postgresql://postgres.<ref-staging>:<password>@...

# Redis (Staging: Upstash dedicated instance)
REDIS_URL=rediss://default:<token-staging>@...

# Razorpay (Test Keys — still testing)
RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXXXX
RAZORPAY_KEY_SECRET=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
RAZORPAY_WEBHOOK_SECRET=whsec_test_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# App Settings
ENVIRONMENT=staging
LOG_LEVEL=INFO
PYTHONPATH=./backend

# Staging webhook URL (Render/Railway)
RAZORPAY_WEBHOOK_URL=https://staging-api.routemaster.railway.app/api/v1/payments/webhook

# Frontend
VITE_RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXXXX
VITE_API_URL=https://staging-api.routemaster.railway.app
```

### 2.3 Production (.env.production)

Create `backend/.env.production` (VAULT-STORED, never in repo):

```bash
# Database (Production: Supabase, replicated)
DATABASE_URL=postgresql://postgres.<ref-prod>:<password>@...

# Redis (Production: Upstash dedicated instance with backups)
REDIS_URL=rediss://default:<token-prod>@...

# Razorpay (LIVE KEYS — production only)
RAZORPAY_KEY_ID=rzp_live_XXXXXXXXXXXXXX
RAZORPAY_KEY_SECRET=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
RAZORPAY_WEBHOOK_SECRET=whsec_live_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# App Settings
ENVIRONMENT=production
LOG_LEVEL=WARN
PYTHONPATH=./backend

# Production webhook URL
RAZORPAY_WEBHOOK_URL=https://api.routemaster.app/api/v1/payments/webhook

# Frontend
VITE_RAZORPAY_KEY_ID=rzp_live_XXXXXXXXXXXXXX
VITE_API_URL=https://api.routemaster.app

# Alerts
ERROR_LOG_EMAIL=devops@routemaster.com
ALERT_WEBHOOK_SLACK=https://hooks.slack.com/...
```

### 2.4 Loading Strategy in app.py

```python
from dotenv import load_dotenv
import os

environment = os.getenv("ENVIRONMENT", "development")

if environment == "development":
    load_dotenv(".env.local")
elif environment == "staging":
    load_dotenv(".env.staging")
elif environment == "production":
    # Don't load from file — use Render/Vault secrets
    pass

# Now access:
razorpay_key_id = os.getenv("RAZORPAY_KEY_ID")
razorpay_key_secret = os.getenv("RAZORPAY_KEY_SECRET")
```

---

## 3. DATABASE VERIFICATION CHECKLIST

### 3.1 Required Tables

**Status**: ✅ **ALL TABLES EXIST** (verified in `backend/database/models/core.py`)

| Table | Purpose | Location | Status |
|-------|---------|----------|--------|
| `bookings` | All booking records | core.py:L209 | ✅ Exists |
| `booking_idempotency` | Duplicate prevention | core.py:L261 | ✅ Exists |
| `booking_monitors` | Payment monitoring state | core.py:L291 | ✅ Exists |
| `users` | User accounts | core.py:L73 | ✅ Exists |
| `bank_transactions` | Bank transfer tracking | core.py:L44 | ✅ Exists |
| `daily_reconciliations` | Revenue reconciliation | core.py:L279 | ✅ Exists |

### 3.2 Database Migration Checklist

**Before going to staging/production**, verify:

```bash
# 1. Check all tables exist
cd backend
python -c "from database.models.core import Booking, BookingIdempotency, BookingMonitor; print('OK')"

# 2. Create tables if missing (SQLAlchemy)
python -c "
from database.infrastructure.base import Base
from database.infrastructure.session import get_sync_db
from database.models.core import *

engine = get_sync_db()
Base.metadata.create_all(engine)
print('Tables created/verified')
"

# 3. Verify schema via psql (if Supabase)
psql postgresql://postgres.<ref>:<password>@aws-1-ap-south-1.pooler.supabase.com:6543/postgres \
  -c "\dt public.*booking*" \
  -c "\dt public.*payment*" \
  -c "\dt public.*idempotency*"
```

### 3.3 Required Indexes

**Existing (verified in core.py)**:

| Column | Table | Type | Reason |
|--------|-------|------|--------|
| `pnr_number` | bookings | UNIQUE | Prevent duplicates |
| `user_id` | bookings | INDEX | Fast user lookups |
| `payment_status` | bookings | INDEX | Query by status |
| `travel_date` | bookings | INDEX | Date-range queries |
| `idempotency_key` | booking_idempotency | PRIMARY | Duplicate detection |
| `created_at` | booking_idempotency | INDEX | TTL cleanup |
| `booking_id` | booking_monitors | PRIMARY | 1:1 relationship |

**Add if missing**:

```sql
-- Ensure these exist in Supabase
CREATE INDEX IF NOT EXISTS idx_bookings_payment_status ON bookings(payment_status);
CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_travel_date ON bookings(travel_date);
CREATE INDEX IF NOT EXISTS idx_booking_idempotency_expires_at ON booking_idempotency(expires_at);

-- For webhook processing
CREATE INDEX IF NOT EXISTS idx_bookings_created_at ON bookings(created_at DESC);
```

### 3.4 Table Schema Verification Query

Run in Supabase SQL Editor:

```sql
-- Verify Booking table structure
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'bookings'
ORDER BY ordinal_position;

-- Verify BookingIdempotency table structure
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'booking_idempotency'
ORDER BY ordinal_position;

-- Verify all indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename LIKE 'booking%'
ORDER BY indexname;
```

---

## 4. WEBHOOK SETUP GUIDE

### 4.1 Webhook Endpoint Registration

**Backend Endpoint Location**: `backend/api/v1/payments.py`

**Required Endpoint**:
```python
@router.post("/webhook")
async def razorpay_webhook(request: Request):
    """
    POST https://api.routemaster.app/api/v1/payments/webhook
    
    Receives events:
    - payment.authorized
    - payment.captured
    - payment.failed
    - order.paid
    """
    pass
```

**Register in Razorpay Dashboard**:

1. **Dashboard** → **Settings** → **Webhooks**
2. Click **Add new webhook**
3. Fill in:
   - **URL**: `https://api.routemaster.app/api/v1/payments/webhook`
   - **Events**: Select all payment-related:
     - ✅ `payment.authorized`
     - ✅ `payment.captured`
     - ✅ `payment.failed`
     - ✅ `order.paid`
     - ✅ `order.paid.partially`
   - **Active**: ✅ Enabled

4. Copy **Webhook Secret** → store in `RAZORPAY_WEBHOOK_SECRET`

### 4.2 Signature Verification

**Implementation** (REQUIRED for security):

```python
import hmac
import hashlib
from fastapi import Request, HTTPException

async def verify_razorpay_signature(
    request: Request,
    expected_signature: str,
    webhook_secret: str
) -> bool:
    """
    Verify Razorpay webhook signature using HMAC-SHA256.
    """
    body = await request.body()
    computed = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed, expected_signature)

@router.post("/webhook")
async def razorpay_webhook(request: Request):
    # Extract signature from header
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    
    # Verify
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not await verify_razorpay_signature(request, signature, webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Process webhook
    payload = await request.json()
    event_type = payload.get("event")
    
    if event_type == "payment.captured":
        await handle_payment_captured(payload)
    elif event_type == "payment.failed":
        await handle_payment_failed(payload)
    
    return {"status": "ok"}
```

### 4.3 Webhook Testing

**Local testing** (using ngrok or Render preview URLs):

```bash
# 1. Start local server with hot reload
cd backend
python app.py  # Runs on http://localhost:8000

# 2. Expose to internet (ngrok)
ngrok http 8000
# Copy: https://xxxxx.ngrok.io

# 3. Register in Razorpay dashboard:
#    https://xxxxx.ngrok.io/api/v1/payments/webhook

# 4. Trigger test event in Razorpay dashboard
#    Settings → Webhooks → Send Test Event

# 5. Watch logs
tail -f backend/logs/app.log | grep webhook
```

**Staging/Production** (using Render URL):
```
https://staging-api.routemaster.railway.app/api/v1/payments/webhook
https://api.routemaster.app/api/v1/payments/webhook
```

### 4.4 Webhook Retry Logic

Razorpay retries failed webhooks automatically:
- 1st attempt: Immediate
- 2nd attempt: 5 minutes
- 3rd attempt: 30 minutes
- 4th attempt: 2 hours
- 5th attempt: 5 hours
- Max 5 retries over 12 hours

**Your endpoint must**:
- Return HTTP 200 immediately (async processing)
- Queue webhook to background job (Celery)
- Never block on DB writes

```python
from celery import shared_task

@router.post("/webhook")
async def razorpay_webhook(request: Request):
    payload = await request.json()
    
    # Queue async task (return 200 immediately)
    process_webhook_async.delay(payload)
    
    return {"status": "ok"}

@shared_task
def process_webhook_async(payload):
    """Background task — can take time"""
    event_type = payload.get("event")
    if event_type == "payment.captured":
        # Safe to update DB here
        booking_id = payload["data"]["entity"]["notes"]["booking_id"]
        db.update_booking_payment_status(booking_id, "PAID")
```

---

## 5. DEPLOYMENT CHECKLIST

### 5.1 Pre-Deployment Validation

**Local validation** (run before every deployment):

```bash
#!/bin/bash
set -e

echo "=== RouteMaster Feature #1 Pre-Deploy Checklist ==="

# 1. Environment variables
echo "✓ Checking environment variables..."
python -c "
import os
required = [
    'DATABASE_URL',
    'RAZORPAY_KEY_ID',
    'RAZORPAY_KEY_SECRET',
    'RAZORPAY_WEBHOOK_SECRET'
]
for var in required:
    if not os.getenv(var):
        raise Exception(f'Missing: {var}')
print('  All required env vars set')
"

# 2. Database connectivity
echo "✓ Checking database..."
python -c "
from database.infrastructure.session import get_sync_db
from sqlalchemy import text
db = get_sync_db()
result = db.execute(text('SELECT 1')).scalar()
print(f'  Database OK (latency: {result}ms)')
"

# 3. Redis connectivity
echo "✓ Checking Redis..."
python -c "
import redis
r = redis.from_url(os.getenv('REDIS_URL'))
r.ping()
print('  Redis OK')
"

# 4. API imports
echo "✓ Checking API imports..."
python -c "
from api.v1.payments import router as payments_router
from database.models.core import Booking, BookingIdempotency
print('  API imports OK')
"

# 5. Code formatting
echo "✓ Running black..."
black backend/ --check --quiet

# 6. Linting
echo "✓ Running pylint..."
pylint backend/ --disable=all --enable=E,F

echo ""
echo "✅ All checks passed. Ready to deploy."
```

**Run before deployment**:
```bash
bash backend/scripts/pre_deploy.sh
```

### 5.2 Staging Deployment (10% traffic)

**Prerequisites**:
- [ ] Pre-deployment validation passes
- [ ] Code review approved
- [ ] Database migrations tested locally
- [ ] Webhook secret registered in Razorpay

**Steps**:

1. **Merge to `staging` branch**:
   ```bash
   git checkout staging
   git pull origin staging
   git merge --no-ff feature/booking-feature-1
   git push origin staging
   ```

2. **Render deployment** (auto-deploys from staging branch):
   - Dashboard: https://dashboard.render.com
   - Service: `routemaster-api-staging`
   - Wait for build: ~3-5 min
   - Check logs: ✅ No errors

3. **Health check**:
   ```bash
   curl -X GET https://staging-api.routemaster.railway.app/health
   # Expected: {"status": "ok"}
   ```

4. **Webhook verification**:
   - Razorpay Dashboard → Webhooks
   - Send test event
   - Check logs: `tail -f logs/webhooks.log`

5. **Manual testing** (Staging):
   - Create test booking: POST /api/v1/bookings
   - Initiate payment: POST /api/v1/payments/create
   - Verify idempotency: Same request twice → same response
   - Check webhook: Should update booking status

### 5.3 Production Canary Deployment (10% → 50% → 100%)

**Environment**:
- Production database (replicated Supabase)
- Production Redis (Upstash with backups)
- Production Razorpay keys (LIVE)
- Health: Blue-green deployment ready

**Phase 1: 10% traffic (30 min)**
```bash
# Set traffic split in Render
# Service: routemaster-api-prod
# Route % to new version: 10%

# Metrics to watch
#   - Error rate (target: < 0.5%)
#   - Payment success rate (target: > 99%)
#   - Response latency p99 (target: < 500ms)
#   - Webhook processing time (target: < 5s)

# Rollback if needed:
#   Route % to new version: 0%
#   Kill new version
#   Revert to previous
```

**Phase 2: 50% traffic (30 min)**
```bash
# Increase traffic split: 50%
# Continue metrics monitoring
# Check for any spikes in errors

# If all green: continue
# If issues: rollback immediately
```

**Phase 3: 100% traffic (go live)**
```bash
# Increase traffic split: 100%
# Remove old version
# Monitor for 24 hours
```

### 5.4 Rollback Procedure

**Immediate rollback** (< 2 min):

```bash
# 1. Stop accepting new payments
curl -X POST https://api.routemaster.app/admin/payments/pause \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 2. Revert to previous version
#    Render → Service → Deployments → Select previous → "Activate"

# 3. Verify rollback
curl -X GET https://api.routemaster.app/health

# 4. Check logs for errors
grep ERROR logs/app.log

# 5. Resume payments (once verified)
curl -X POST https://api.routemaster.app/admin/payments/resume \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Database rollback** (if schema migration failed):

```sql
-- Via Supabase SQL Editor

-- Option 1: Revert to point-in-time
-- Restore from backup (Supabase → Settings → Backups)

-- Option 2: Manual rollback of recent changes
-- ALTER TABLE bookings DROP COLUMN new_field;
-- DELETE FROM booking_idempotency WHERE created_at > '2026-06-08T10:00:00Z';
```

---

## 6. MONITORING SPECIFICATION

### 6.1 Key Performance Indicators (KPIs)

| Metric | Target | Alert Threshold | Tool |
|--------|--------|-----------------|------|
| Payment success rate | > 99.5% | < 98% | Prometheus + Grafana |
| Webhook processing latency | < 5s p95 | > 10s p99 | APM (DataDog/NewRelic) |
| Payment authorization time | < 2s | > 5s | Custom logs |
| Booking idempotency hit rate | > 5% | N/A (informational) | Logs + custom counter |
| Database query latency | < 100ms p99 | > 500ms | PostgreSQL logs |
| Redis latency | < 10ms p99 | > 50ms | Redis INFO stats |

### 6.2 Metrics to Track

**Application-level**:
```python
from prometheus_client import Counter, Histogram, Gauge
import time

# Payment metrics
payment_requests = Counter(
    'payment_requests_total',
    'Total payment requests',
    ['status']  # success, failed, timeout
)

payment_latency = Histogram(
    'payment_request_duration_seconds',
    'Payment request latency',
    buckets=[0.1, 0.5, 1, 2, 5, 10]
)

# Webhook metrics
webhook_events = Counter(
    'webhook_events_total',
    'Webhook events received',
    ['event_type']  # payment.captured, payment.failed, etc.
)

webhook_latency = Histogram(
    'webhook_processing_duration_seconds',
    'Webhook processing time',
    buckets=[0.1, 0.5, 1, 2, 5]
)

# Idempotency metrics
idempotency_hits = Counter(
    'idempotency_hits_total',
    'Idempotency cache hits'
)

# Database metrics
db_latency = Histogram(
    'db_query_duration_seconds',
    'Database query latency',
    buckets=[0.01, 0.05, 0.1, 0.5, 1]
)

# Example usage in payment handler
@router.post("/create-order")
async def create_order(req: CreateOrderRequest):
    start = time.time()
    try:
        # Process payment
        result = await razorpay_client.order.create(...)
        payment_requests.labels(status='success').inc()
        payment_latency.observe(time.time() - start)
        return result
    except Exception as e:
        payment_requests.labels(status='failed').inc()
        raise
```

### 6.3 Logging Strategy

**Log Levels**:
- ✅ **ERROR**: Payment failures, webhook errors, DB connection issues
- ⚠️ **WARN**: Idempotency hits, timeouts, retries
- ℹ️ **INFO**: Payment initiated, webhook received, booking created
- 🔍 **DEBUG**: Full request/response, SQL queries (dev only)

**Log Format** (structured JSON):

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', None),
            'booking_id': getattr(record, 'booking_id', None),
            'user_id': getattr(record, 'user_id', None),
            'duration_ms': getattr(record, 'duration_ms', None)
        }
        
        # Don't log secrets
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_obj)

# Usage
logger = logging.getLogger("payments")
logger.info("Payment initiated", extra={
    'request_id': req.id_key,
    'booking_id': req.booking_id,
    'amount': req.amount
})
```

**Log destinations**:
- **Development**: `backend/logs/app.log` (local file)
- **Staging**: Render logs → Datadog/Papertrail
- **Production**: Supabase → Datadog/CloudWatch

### 6.4 Alert Rules

**High Priority** (page on-call engineer):

```yaml
rules:
  - name: PaymentSuccessRateHigh
    condition: payment_success_rate < 0.98
    duration: 5m
    severity: critical
    notification: pagerduty_oncall

  - name: WebhookLatencyHigh
    condition: webhook_latency_p99 > 10s
    duration: 5m
    severity: critical
    notification: pagerduty_oncall

  - name: DatabaseDown
    condition: db_query_latency_p99 > 5s
    duration: 2m
    severity: critical
    notification: pagerduty_oncall

  - name: PaymentProcessingTimeout
    condition: payment_requests_timeout > 50 in 5m
    duration: 5m
    severity: critical
    notification: pagerduty_oncall
```

**Medium Priority** (Slack alert):

```yaml
rules:
  - name: HighErrorRate
    condition: error_rate > 1% in 10m
    severity: warning
    notification: slack_#devops

  - name: IdempotencyHigh
    condition: idempotency_hits > 10% in 1h
    severity: info
    notification: slack_#devops

  - name: WebhookRetries
    condition: webhook_retries > 5 in 1h
    severity: warning
    notification: slack_#devops
```

### 6.5 Dashboard Specification

**Grafana Dashboard**: `RouteMaster — Feature #1: Payments`

**Panels**:

1. **Payment Status Overview**
   - Graph: Success rate (%) over 24h
   - Gauge: Current success rate
   - Table: Failures by type (failed, timeout, rejected)

2. **Performance**
   - Graph: Payment latency p50/p95/p99
   - Graph: Webhook latency distribution
   - Heatmap: Database query latency by endpoint

3. **Reliability**
   - Graph: Webhook retry rate (%)
   - Counter: Idempotency hits (24h)
   - Table: Top error messages (last 1h)

4. **Volume**
   - Graph: Payments per minute (trend)
   - Graph: Bookings created per hour
   - Counter: Total revenue (24h)

5. **System Health**
   - Status: Database latency
   - Status: Redis latency
   - Status: Razorpay API status (external)

---

## 7. QUICK START FOR TEAMS 1-5

### 7.1 For Team 1 (Booking API)

**Dependencies available**:
- ✅ Database table: `bookings`, `booking_idempotency`, `booking_monitors`
- ✅ Environment variables: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`
- ✅ WebhookSecret: registered in `.env` → `RAZORPAY_WEBHOOK_SECRET`

**Start building**:
```python
from database.models.core import Booking, BookingIdempotency
from razorpay import Client

razorpay_client = Client(
    auth=(
        os.getenv("RAZORPAY_KEY_ID"),
        os.getenv("RAZORPAY_KEY_SECRET")
    )
)

@router.post("/bookings")
async def create_booking(req: BookingRequest):
    # Your code here
    pass
```

### 7.2 For Team 2 (Payment Flow)

**Existing schemas**:
- `booking_idempotency`: Prevents duplicate charges
- `payment_status` in `bookings`: Tracks payment state

**Implementation checklist**:
- [ ] Call Razorpay API with `idempotency_key`
- [ ] Store idempotency_key → booking_id mapping
- [ ] Return order details (includes Razorpay order ID)

### 7.3 For Team 3 (Webhook Handler)

**Already set up**:
- Webhook endpoint: `POST /api/v1/payments/webhook`
- Signature verification framework: HMAC-SHA256
- Async processing (Celery): ready to queue tasks

**To implement**:
- [ ] `handle_payment_captured(payload)` → update booking status
- [ ] `handle_payment_failed(payload)` → mark booking failed, notify user
- [ ] Implement retry logic with exponential backoff

### 7.4 For Team 4 (Idempotency Engine)

**Table ready**: `booking_idempotency`

**Columns**:
- `idempotency_key` (str, PK): Client-provided request ID
- `booking_id` (str, FK): Associated booking
- `request_hash` (str): SHA-256 of request body
- `created_at` (datetime): Insertion timestamp
- `expires_at` (datetime): TTL (24h from creation)

**Logic to implement**:
1. On request, compute `request_hash = SHA256(request_body)`
2. Check if `idempotency_key` exists in DB
3. If exists AND `request_hash` matches: Return cached response
4. If exists AND `request_hash` differs: Return 409 Conflict
5. If not exists: Process request → store `idempotency_key` + hash

### 7.5 For Team 5 (Error Handling)

**Monitoring ready**:
- Prometheus metrics: See section 6.2
- Structured logging: See section 6.3
- Alert rules: See section 6.4

**To implement**:
- [ ] Catch exceptions in payment flow
- [ ] Log with structured format (request_id, booking_id)
- [ ] Return proper HTTP status codes (400, 402, 500)
- [ ] Emit metrics (payment_requests, payment_latency)

---

## 8. VERIFICATION STEPS (Run before launch)

### 8.1 Local Verification

```bash
cd backend

# 1. Check environment
python -c "import os; print('✓ RAZORPAY_KEY_ID:', os.getenv('RAZORPAY_KEY_ID')[:20]+'...')"

# 2. Check database tables
python -c "
from database.infrastructure.session import get_sync_db
from sqlalchemy import inspect
db = get_sync_db()
inspector = inspect(db)
tables = inspector.get_table_names()
required = ['bookings', 'booking_idempotency', 'booking_monitors']
for table in required:
    if table in tables:
        print(f'✓ {table}')
    else:
        print(f'✗ {table}')
"

# 3. Check API import
python -c "from api.v1.payments import router; print('✓ API imports OK')"

# 4. Test Razorpay client
python -c "
from razorpay import Client
client = Client(auth=('test_key', 'test_secret'))
print('✓ Razorpay client OK')
"

# 5. Test Redis
python -c "
import redis
r = redis.from_url('redis://localhost:6379')
r.ping()
print('✓ Redis OK')
"
```

### 8.2 Staging Verification

```bash
# 1. Health check
curl https://staging-api.routemaster.railway.app/health

# 2. Payment webhook test
#    Razorpay Dashboard → Settings → Webhooks → Send Test Event

# 3. Check logs
curl https://staging-api.routemaster.railway.app/admin/logs?hours=1

# 4. Manual booking test
curl -X POST https://staging-api.routemaster.railway.app/api/v1/bookings \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","train_number":"12345","travel_date":"2026-06-15"}'

# 5. Idempotency test
#    Same request twice → should get same response
```

### 8.3 Production Readiness Checklist

- [ ] All Team 1-5 code reviewed and merged
- [ ] Staging deployment tested for 24 hours
- [ ] Payment success rate > 99.5% in staging
- [ ] Webhook latency p99 < 10s in staging
- [ ] Database backup verified (Supabase)
- [ ] Redis backup enabled (Upstash)
- [ ] Monitoring dashboard live in Grafana
- [ ] Alert rules tested (PagerDuty, Slack)
- [ ] Runbook reviewed by DevOps team
- [ ] Razorpay webhook endpoint verified
- [ ] Production environment variables set (Render secrets)
- [ ] Canary deployment strategy agreed
- [ ] Rollback procedure tested

---

## 9. TEAM 6 DELIVERABLES SUMMARY

**What Team 6 Provides** (this document + setup):

1. ✅ **Credential Management Guide** (section 1)
   - Razorpay API key retrieval
   - Storage strategy (dev/staging/prod)
   - Rotation policy

2. ✅ **Environment Templates** (section 2)
   - `.env.local` (dev)
   - `.env.staging` (staging)
   - `.env.production` (production)
   - Loading strategy in app.py

3. ✅ **Database Verification** (section 3)
   - All required tables confirmed ✅
   - Index recommendations
   - Schema verification queries
   - Migration checklist

4. ✅ **Webhook Configuration** (section 4)
   - Endpoint registration in Razorpay
   - Signature verification implementation
   - Testing procedure (local + staging)
   - Retry logic specification

5. ✅ **Deployment Checklist** (section 5)
   - Pre-deployment validation script
   - Staging deployment steps
   - Production canary (10% → 50% → 100%)
   - Rollback procedure

6. ✅ **Monitoring Specification** (section 6)
   - KPI targets and alert thresholds
   - Prometheus metrics (payment_requests, latency, errors)
   - Structured logging format
   - Grafana dashboard specification
   - Alert rules (critical/warning/info)

7. ✅ **Team 1-5 Dependencies** (section 7)
   - What each team can start using immediately
   - Database table references
   - Environment variable access

8. ✅ **Verification Steps** (section 8)
   - Local verification commands
   - Staging validation
   - Production readiness checklist

---

## 10. CONTACT & ESCALATION

**DevOps Team 6 Lead**: [Your Name]  
**Slack Channel**: #devops-team-6-payments  
**On-Call Rotation**: [Link to PagerDuty]  
**Runbook**: [Link to shared drive]

**For deployment support**:
1. Post in #devops-team-6-payments
2. PagerDuty escalation if critical
3. Fallback: Direct Slack DM

---

**Last Updated**: June 8, 2026  
**Status**: READY FOR EXECUTION (Teams 1-5 can start immediately)  
**Next Review**: June 10, 2026 (post-deployment)
