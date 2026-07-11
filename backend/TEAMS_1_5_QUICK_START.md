# Feature #1: Booking System — Teams 1-5 Quick Start

**Status**: DevOps infrastructure ready (Team 6 complete)  
**Your responsibility**: Build the 5 components in parallel  
**Integration point**: All components meet at `/api/v1/payments/webhook`

---

## What Team 6 Has Done For You

- ✅ All database tables created (`bookings`, `booking_idempotency`, `booking_monitors`)
- ✅ Environment variables configured (dev/staging/prod)
- ✅ Webhook signature verification framework ready
- ✅ Deployment checklist + monitoring spec complete
- ✅ Pre-deployment validation script ready

**See** `DEVOPS_SETUP_TEAM_6.md` for full details.

---

## Team 1: Booking API (Endpoints)

**Your files**:
- `backend/api/v1/bookings.py` (create)
- `backend/database/models/core.py` (already has `Booking` table)

**What's available**:

```python
from database.models.core import Booking
from database.infrastructure.session import get_sync_db

# Create booking
booking = Booking(
    id=str(uuid.uuid4()),
    user_id=req.user_id,
    train_number=req.train_number,
    travel_date=req.travel_date,
    from_station_code=req.from_code,
    to_station_code=req.to_code,
    class_type=req.class_type,
    booking_status="pending",
    payment_status="pending",
    created_at=datetime.utcnow()
)
db.add(booking)
db.commit()
```

**Endpoints to build**:

1. **POST /api/v1/bookings** — Create booking (pending status)
   - Input: user_id, train_number, travel_date, passengers[], from_code, to_code, class_type
   - Output: booking_id, status, amount_estimate
   - Database: Insert into `bookings` (status='pending', payment_status='pending')

2. **GET /api/v1/bookings/{id}** — Get booking details
   - Input: booking_id
   - Output: Full booking with passenger details
   - Database: Query `bookings` + `passenger_details`

3. **GET /api/v1/bookings/user/{user_id}** — List user's bookings
   - Input: user_id
   - Output: [booking, booking, ...]
   - Database: Filter `bookings.user_id = user_id`

**Test locally**:
```bash
curl -X POST http://localhost:8000/api/v1/bookings \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "train_number": "12345",
    "travel_date": "2026-06-15",
    "from_code": "NDLS",
    "to_code": "BCT",
    "class_type": "AC2"
  }'
```

---

## Team 2: Payment Flow (Razorpay Orders)

**Your files**:
- `backend/api/v1/payments.py` (create)
- Uses `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` from env

**What's available**:

```python
import os
from razorpay import Client

razorpay_client = Client(
    auth=(
        os.getenv("RAZORPAY_KEY_ID"),
        os.getenv("RAZORPAY_KEY_SECRET")
    )
)

# Create order
order = razorpay_client.order.create(
    data={
        "amount": int(amount * 100),  # Razorpay uses paise
        "currency": "INR",
        "receipt": f"booking_{booking_id}",
        "notes": {
            "booking_id": booking_id,
            "user_id": user_id
        }
    }
)
```

**Endpoints to build**:

1. **POST /api/v1/payments/create** — Initialize payment
   - Input: booking_id, amount, idempotency_key (client-generated)
   - Output: razorpay_order_id, order_key (for frontend)
   - Logic:
     - Check idempotency: If exists, return cached response
     - Create Razorpay order
     - Store idempotency_key → booking_id mapping
     - Return order details

2. **POST /api/v1/payments/verify** — Verify payment after capture
   - Input: razorpay_payment_id, razorpay_signature
   - Output: {status: "verified", booking_id}
   - Logic:
     - Verify signature using `RAZORPAY_WEBHOOK_SECRET`
     - Update booking.payment_status = "verified" (NOT "paid" yet)

**Idempotency implementation** (critical):

```python
from database.models.core import BookingIdempotency
import hashlib

@router.post("/create")
async def create_payment(req: CreatePaymentRequest, db: Session):
    # Compute request hash
    request_hash = hashlib.sha256(
        json.dumps(req.dict(), sort_keys=True).encode()
    ).hexdigest()
    
    # Check if idempotency key already exists
    existing = db.query(BookingIdempotency).filter(
        BookingIdempotency.idempotency_key == req.idempotency_key
    ).first()
    
    if existing:
        # Return cached response
        if existing.request_hash != request_hash:
            return {"error": "Idempotency key with different request"}
        # Return cached order details from DB
        cached_booking = db.query(Booking).filter(
            Booking.id == existing.booking_id
        ).first()
        return {"order_id": cached_booking.razorpay_order_id}
    
    # New request — create order
    order = razorpay_client.order.create({
        "amount": int(req.amount * 100),
        "currency": "INR",
        "receipt": f"booking_{req.booking_id}",
        "notes": {"booking_id": req.booking_id}
    })
    
    # Store idempotency
    idempotency = BookingIdempotency(
        idempotency_key=req.idempotency_key,
        booking_id=req.booking_id,
        request_hash=request_hash,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=1)
    )
    db.add(idempotency)
    
    # Update booking with order ID
    booking = db.query(Booking).get(req.booking_id)
    booking.razorpay_order_id = order['id']
    db.commit()
    
    return {"order_id": order['id'], "key": os.getenv("VITE_RAZORPAY_KEY_ID")}
```

---

## Team 3: Webhook Handler

**Your files**:
- `backend/api/v1/payments.py` (in same file as Team 2, or separate)
- Signature verification framework already in DEVOPS guide

**Endpoint to build**:

**POST /api/v1/payments/webhook** — Razorpay webhook receiver

```python
from fastapi import Request, HTTPException
import hmac
import hashlib
import json

@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Session):
    # 1. Verify signature
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    
    body = await request.body()
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    expected_sig = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # 2. Parse event
    payload = await request.json()
    event_type = payload.get("event")
    
    # 3. Queue async processing (Celery)
    # Return 200 immediately so Razorpay doesn't retry
    process_webhook_async.delay(event_type, payload)
    
    return {"status": "received"}


# Async task (Celery)
from celery import shared_task

@shared_task
def process_webhook_async(event_type: str, payload: dict):
    """Background task — safe to take time here"""
    
    if event_type == "payment.captured":
        handle_payment_captured(payload)
    elif event_type == "payment.failed":
        handle_payment_failed(payload)
    elif event_type == "order.paid":
        handle_order_paid(payload)


def handle_payment_captured(payload: dict):
    """Update booking status when payment captured"""
    from database.infrastructure.session import get_sync_db
    
    db = get_sync_db()
    
    # Extract booking ID from webhook
    booking_id = payload["data"]["entity"]["notes"]["booking_id"]
    
    # Update booking status
    booking = db.query(Booking).get(booking_id)
    booking.payment_status = "captured"
    booking.razorpay_payment_id = payload["data"]["entity"]["id"]
    booking.amount_paid = payload["data"]["entity"]["amount"] / 100  # Convert paise to INR
    
    db.commit()
    
    # Send confirmation email/SMS to user


def handle_payment_failed(payload: dict):
    """Handle failed payment"""
    booking_id = payload["data"]["entity"]["notes"]["booking_id"]
    
    booking = db.query(Booking).get(booking_id)
    booking.payment_status = "failed"
    booking.error_message = payload["data"]["entity"].get("error_description")
    
    db.commit()
    
    # Notify user of failure


def handle_order_paid(payload: dict):
    """Handle order.paid event (alternative to payment.captured)"""
    # Similar to handle_payment_captured
    pass
```

**Testing your webhook locally**:

```bash
# Terminal 1: Start server
cd backend
python app.py

# Terminal 2: Send test event
python scripts/test_webhook.py \
  --environment development \
  --booking-id test-booking-123 \
  --amount 5000 \
  --test captured

# Check logs
grep "payment.captured" logs/app.log
```

---

## Team 4: Idempotency Engine

**Your files**:
- `backend/core/idempotency.py` (create utility functions)

**What's available**:

```python
from database.models.core import BookingIdempotency
import hashlib
import json

class IdempotencyEngine:
    @staticmethod
    def compute_hash(data: dict) -> str:
        """Compute SHA-256 hash of request"""
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
    
    @staticmethod
    def check(db: Session, idempotency_key: str) -> Optional[BookingIdempotency]:
        """Check if idempotency key exists"""
        return db.query(BookingIdempotency).filter(
            BookingIdempotency.idempotency_key == idempotency_key
        ).first()
    
    @staticmethod
    def store(
        db: Session,
        idempotency_key: str,
        booking_id: str,
        request_data: dict
    ) -> BookingIdempotency:
        """Store new idempotency record"""
        
        request_hash = IdempotencyEngine.compute_hash(request_data)
        
        record = BookingIdempotency(
            idempotency_key=idempotency_key,
            booking_id=booking_id,
            request_hash=request_hash,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=1)
        )
        
        db.add(record)
        db.commit()
        
        return record
    
    @staticmethod
    def cleanup_expired(db: Session):
        """Remove expired idempotency records"""
        db.query(BookingIdempotency).filter(
            BookingIdempotency.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
```

**Logic to implement**:

1. **On every payment request**:
   - Compute request hash
   - Check if idempotency_key exists
   - If yes: Compare hash
     - If match: Return cached response
     - If mismatch: Return 409 Conflict
   - If no: Process request → store idempotency record

2. **TTL cleanup**:
   - Records expire after 24 hours
   - Run cleanup job daily: `IdempotencyEngine.cleanup_expired(db)`

3. **Client must provide idempotency_key**:
   - Frontend generates UUID: `idempotency_key = uuid.uuid4()`
   - Include in every payment request
   - Same key → same response (guaranteed)

---

## Team 5: Error Handling & Monitoring

**Your files**:
- `backend/api/v1/payments.py` (error handling)
- `backend/utils/metrics.py` (monitoring)

**What's available**:

```python
from prometheus_client import Counter, Histogram
import time
import logging

logger = logging.getLogger("payments")

# Metrics
payment_requests = Counter(
    'payment_requests_total',
    'Total payment requests',
    ['status']  # success, failed, timeout, invalid_signature
)

payment_latency = Histogram(
    'payment_request_duration_seconds',
    'Payment request latency',
    buckets=[0.1, 0.5, 1, 2, 5, 10]
)

webhook_latency = Histogram(
    'webhook_processing_duration_seconds',
    'Webhook processing time',
    buckets=[0.1, 0.5, 1, 2, 5]
)

# Example in payment endpoint
@router.post("/create")
async def create_payment(req: CreatePaymentRequest, db: Session):
    start = time.time()
    request_id = str(uuid.uuid4())
    
    logger.info(f"Payment request started", extra={
        'request_id': request_id,
        'booking_id': req.booking_id
    })
    
    try:
        # Your logic here
        result = await razorpay_client.order.create(...)
        
        payment_requests.labels(status='success').inc()
        payment_latency.observe(time.time() - start)
        
        logger.info(f"Payment order created", extra={
            'request_id': request_id,
            'booking_id': req.booking_id,
            'duration_ms': (time.time() - start) * 1000
        })
        
        return result
        
    except RazorpayException as e:
        payment_requests.labels(status='failed').inc()
        
        logger.error(f"Razorpay error", extra={
            'request_id': request_id,
            'booking_id': req.booking_id,
            'error': str(e)
        })
        
        raise HTTPException(status_code=402, detail="Payment failed")
        
    except Exception as e:
        payment_requests.labels(status='error').inc()
        
        logger.error(f"Unexpected error", extra={
            'request_id': request_id,
            'booking_id': req.booking_id,
            'error': str(e)
        }, exc_info=True)
        
        raise HTTPException(status_code=500, detail="Internal error")
```

**HTTP Status Codes**:

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Order created, payment verified |
| 400 | Bad request | Missing booking_id, invalid amount |
| 401 | Unauthorized | Invalid webhook signature |
| 402 | Payment required | Razorpay rejected payment |
| 409 | Conflict | Idempotency key with different request |
| 500 | Server error | Database down, Razorpay timeout |

**Logging format** (structured JSON):

```
{
  "timestamp": "2026-06-08T10:30:45Z",
  "level": "INFO",
  "logger": "payments",
  "message": "Payment order created",
  "request_id": "abc-123-def",
  "booking_id": "booking-456",
  "duration_ms": 250
}
```

**Metrics to emit**:

- `payment_requests_total[status=success|failed|timeout|conflict]`
- `payment_request_duration_seconds` (histogram)
- `webhook_events_total[event_type=payment.captured|payment.failed]`
- `webhook_processing_duration_seconds` (histogram)
- `idempotency_hits_total`

---

## Integration Points

**All teams meet here**:

1. **Team 1 → Booking created** (status='pending')
2. **Team 2 → Razorpay order initialized** (linked to booking)
3. **Frontend → User pays via Razorpay** (renders checkout form)
4. **Team 3 → Webhook received** (Razorpay notifies backend)
5. **Team 4 → Idempotency verified** (no duplicate charges)
6. **Team 5 → Metrics logged** (success rate, latency tracked)

**Flow diagram**:
```
[Frontend]
    |
    v
[Team 1: Create Booking] → DB: bookings
    |
    v
[Team 2: Create Order] → Razorpay API
    |
    v
[Frontend: Payment] ← Razorpay Checkout
    |
    v
[User Pays]
    |
    v
[Razorpay: Send Webhook] → HTTP POST
    |
    v
[Team 3: Verify Signature]
    |
    v
[Team 4: Check Idempotency]
    |
    v
[Team 5: Log + Metrics]
    |
    v
[Team 1: Update Booking Status]
```

---

## Testing Checklist

**For each team**:

- [ ] Endpoint returns correct HTTP status
- [ ] Data persists in database
- [ ] Error handling works (invalid input, DB errors)
- [ ] Metrics are emitted
- [ ] Logs are structured JSON

**Integration test** (all teams together):

```bash
# 1. Create booking (Team 1)
curl -X POST http://localhost:8000/api/v1/bookings -d '...'
# Expected: {booking_id, status: pending}

# 2. Initialize payment (Team 2)
curl -X POST http://localhost:8000/api/v1/payments/create \
  -d '{booking_id, amount, idempotency_key}'
# Expected: {order_id, key}

# 3. Send webhook (Team 3 test)
python scripts/test_webhook.py --test captured --booking-id <id>
# Expected: 200 OK in webhook endpoint

# 4. Check idempotency (Team 4 test)
# Send same payment request twice
curl ... → first time gets {order_id}
curl ... → second time gets same {order_id} (cached)

# 5. Check metrics (Team 5 test)
curl http://localhost:8000/metrics | grep payment_requests_total
# Expected: payment_requests_total{status="success"} 2.0
```

---

## Environment Variables Available

All teams can access:

```python
import os

# Razorpay
os.getenv("RAZORPAY_KEY_ID")           # For Team 2
os.getenv("RAZORPAY_KEY_SECRET")       # For Team 2
os.getenv("RAZORPAY_WEBHOOK_SECRET")   # For Team 3

# Database
os.getenv("DATABASE_URL")              # All teams

# App
os.getenv("ENVIRONMENT")               # development/staging/production
os.getenv("LOG_LEVEL")                 # DEBUG/INFO/WARN/ERROR
```

---

## Quick Help

**Database tables ready for you**:
```python
from database.models.core import (
    Booking,
    BookingIdempotency,
    BookingMonitor,
    PassengerDetails,
    User
)
```

**Pre-deployment validation**:
```bash
bash backend/scripts/pre_deploy.sh
```

**Test webhook locally**:
```bash
python backend/scripts/test_webhook.py --environment development
```

**Check logs**:
```bash
tail -f backend/logs/app.log | grep -i payment
```

---

## Contact

- **DevOps**: See `DEVOPS_SETUP_TEAM_6.md` section 10
- **Database schema**: `backend/database/models/core.py`
- **Full setup guide**: `backend/DEVOPS_SETUP_TEAM_6.md`

**Build fast, integrate early, test continuously.**
