# Architecture Analysis: Route Master Booking System
## Feature #1 - Razorpay Payment Integration
**Document Version:** 1.0  
**Date:** 2026-06-08  
**Audience:** Team 2-4 (Backend Payment Integration)  
**Status:** READY FOR IMPLEMENTATION

---

## EXECUTIVE SUMMARY

The Route Master booking system (80% complete) uses **production-grade resilience patterns** and a **state machine workflow** that MUST be preserved during Razorpay integration. This document maps integration points, code style standards, and patterns to extend without breaking the existing system.

**Key Finding:** The booking system already has Payment model scaffolding with Razorpay fields (`razorpay_order_id`, `razorpay_payment_id`, `razorpay_signature`). Integration should extend these existing relationships, not create parallel structures.

---

## PART 1: EXISTING ARCHITECTURE PATTERNS

### 1.1 Circuit Breaker Pattern (CRITICAL - PRESERVE)

**Location:** `/backend/services/booking/service.py` (lines 246-258)

The BookingService uses **circuit breakers for resilience** on three external integrations:

```python
# Circuit breakers for external services
self._redis_breaker = circuit_breaker_manager.get_or_create(
    "booking_redis",
    CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
)
self._db_breaker = circuit_breaker_manager.get_or_create(
    "booking_db",
    CircuitConfig(failure_threshold=5, timeout_seconds=60.0, success_threshold=3)
)
self._kafka_breaker = circuit_breaker_manager.get_or_create(
    "booking_kafka",
    CircuitConfig(failure_threshold=3, timeout_seconds=30.0, success_threshold=2)
)
```

**INTEGRATION REQUIREMENT:**
- Add Razorpay circuit breaker with appropriate thresholds:
  ```python
  self._razorpay_breaker = circuit_breaker_manager.get_or_create(
      "booking_razorpay",
      CircuitConfig(
          failure_threshold=5,      # Fail after 5 failures
          timeout_seconds=45.0,     # Razorpay timeout (longer than DB)
          success_threshold=3       # Reset after 3 successes
      )
  )
  ```
- Wrap all Razorpay API calls with: `self._razorpay_breaker.call(razorpay_operation)`
- **CRITICAL:** If circuit opens, return cached payment state (prevent cascading failures)

### 1.2 Distributed Lock Mechanism (CRITICAL - PRESERVE)

**Location:** `/backend/services/booking/service.py` (lines 81-183)

The `DistributedLock` class prevents **race conditions during concurrent bookings**:

```python
class DistributedLock:
    """Redis-based distributed lock for booking operations."""
    
    def __init__(self, redis_client, lock_prefix: str = "booking:lock:"):
    async def acquire(self, lock_id: str, timeout_seconds: int = 30) -> Optional[str]:
    async def release(self, lock_id: str, token: str) -> bool:
    @asynccontextmanager
    async def lock(self, lock_id: str, timeout_seconds: int = 30):
```

**Current Usage:**
```python
async with lock_manager.lock(lock_id, self.LOCK_TIMEOUT_SECONDS):
    # Critical section protected
    return self._create_booking_internal(...)
```

**INTEGRATION REQUIREMENT:**
- Acquire same lock BEFORE initiating Razorpay payment creation
- Lock ID pattern: `f"booking:{user_id}:{travel_date}"`
- Hold lock through payment confirmation phase
- **If payment confirmation fails:** Lock ensures no duplicate payment attempts
- Fallback to local asyncio.Lock if Redis unavailable (lines 104-108)

### 1.3 Idempotency Pattern (CRITICAL - PRESERVE)

**Location:** `/backend/services/booking/service.py` (lines 305-368)

The system implements **idempotency for payment safety** using dual-layer caching:

```python
def _generate_idempotency_key(self, user_id: str, travel_date: str, route_id: str) -> str:
    """Generate a unique idempotency key for a booking request."""
    key_data = f"{user_id}:{travel_date}:{route_id}"
    return f"booking:{hashlib.sha256(key_data.encode()).hexdigest()[:16]}"

async def _check_idempotency(self, idempotency_key: str) -> Optional[Booking]:
    """Check if a booking with this idempotency key already exists."""
    # Try Redis first, fallback to DB
    cached_id = await redis.get(f"idempotency:{idempotency_key}")
    if cached_id:
        return self.db.query(Booking).filter(BookingModel.id == cached_id.decode()).first()
```

**INTEGRATION REQUIREMENT:**
- Generate payment-specific idempotency key:
  ```python
  payment_idempotency_key = f"payment:{booking_id}:{int(amount*100)}"
  ```
- Check Redis/DB before creating Razorpay order
- If payment already exists, return cached payment object (don't create duplicate)
- TTL: 24 hours (idempotency_ttl_hours = 24)

### 1.4 Fraud Detection System (PRESERVE & EXTEND)

**Location:** `/backend/services/booking/service.py` (lines 470-539)

Current fraud checks before booking creation:

```python
def _check_fraud(self, user_id: str, amount: float, booking_id: Optional[str] = None):
    """Perform fraud checks on booking."""
    details = {"flags": [], "risk_score": 0.0}
    
    # Check 1: Amount limits
    if amount > self.booking_config.max_amount_per_booking:  # 100,000
        details["flags"].append("AMOUNT_EXCEEDS_LIMIT")
        return False, "BLOCK", details
    
    # Check 2: 24h booking velocity
    bookings_24h = self.db.query(Booking).filter(
        BookingModel.user_id == user_id,
        BookingModel.created_at >= since_24h
    ).count()
    if bookings_24h >= 5:  # max_bookings_per_user_24h
        details["flags"].append("HIGH_VELOCITY_24H")
        details["risk_score"] += 0.4
    
    # Check 3: 7d booking velocity
    bookings_7d = self.db.query(Booking).filter(...).count()
    if bookings_7d >= 20:  # max_bookings_per_user_7d
        details["flags"].append("HIGH_VELOCITY_7D")
        details["risk_score"] += 0.3
    
    # Check 4: High value flag
    if amount >= 50000:  # high_value_threshold
        details["flags"].append("HIGH_VALUE")
        details["risk_score"] += 0.2
    
    # Decision logic
    if details["risk_score"] >= 0.7:
        decision = "BLOCK"
    elif details["risk_score"] >= 0.4:
        decision = "FLAG"  # Manual review
    else:
        decision = "ALLOW"
```

**BookingFraudCheck Model Storage:**
```python
class BookingFraudCheck(UserBase):
    id: str (UUID)
    booking_id: str (FK to bookings)
    user_id: str (FK to users)
    check_type: str = "COMPREHENSIVE"
    risk_score: float
    flags: List[str]  # e.g., ["HIGH_VELOCITY_24H", "HIGH_VALUE"]
    decision: str  # "ALLOW", "BLOCK", "REVIEW"
    created_at: datetime
```

**INTEGRATION REQUIREMENT:**
- Before Razorpay payment creation, run fraud check
- If risk_score >= 0.7: BLOCK payment initiation → return error
- If risk_score >= 0.4: FLAG for review → create payment with `payment_status: "REVIEW"`
- If risk_score < 0.4: ALLOW payment → proceed normally
- Store fraud flags in `Payment.booking_details['fraud_flags']` for reconciliation

### 1.5 Audit Trail System (CRITICAL - PRESERVE)

**Location:** `/backend/services/booking/service.py` (lines 374-434)

Every booking action is logged to `BookingAuditLog`:

```python
def _log_audit(
    self,
    booking_id: Optional[str],
    pnr_number: Optional[str],
    action: str,
    new_state: str,
    actor_type: str,  # "SYSTEM", "USER", "ADMIN", "API"
    actor_id: Optional[str] = None,
    previous_state: Optional[str] = None,
    amount: Optional[float] = None,
    reason: Optional[str] = None,
    extra_data: Optional[Dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> str:
    """Log an immutable audit entry for booking operations."""
    checksum = hashlib.sha256(
        json.dumps(audit_data, sort_keys=True, default=str).encode()
    ).hexdigest()
    
    audit_entry = BookingAuditLog(
        audit_id=audit_id,
        booking_id=booking_id,
        pnr_number=pnr_number,
        action=action,
        previous_state=previous_state,
        new_state=new_state,
        actor_type=actor_type,
        actor_id=actor_id,
        amount=amount,
        reason=reason,
        extra_data=extra_data,
        ip_address=ip_address,
        user_agent=user_agent,
        checksum=checksum  # Integrity check
    )
```

**BookingAuditLog Model:**
```python
class BookingAuditLog(Base):
    id: int (auto-increment)
    audit_id: str (UUID, unique, indexed)
    booking_id: str (indexed)
    pnr_number: str (indexed)
    action: str  # CREATE, CONFIRM, CANCEL, PAY, REFUND
    previous_state: str
    new_state: str
    actor_type: str
    actor_id: str
    amount: float
    reason: str
    extra_data: JSON  # Metadata
    ip_address: str
    user_agent: str
    checksum: str (SHA256)
    created_at: datetime
```

**INTEGRATION REQUIREMENT:**
Log all payment lifecycle events:

```python
# When Razorpay order created
self._log_audit(
    booking_id=booking_id,
    pnr_number=pnr_number,
    action="PAYMENT_INITIATED",
    new_state="PAYMENT_PENDING",
    actor_type="SYSTEM",
    amount=amount,
    extra_data={
        "razorpay_order_id": order_id,
        "payment_method": "razorpay"
    }
)

# When payment verified
self._log_audit(
    booking_id=booking_id,
    pnr_number=pnr_number,
    action="PAYMENT_VERIFIED",
    new_state="CONFIRMED",
    actor_type="SYSTEM",
    amount=amount,
    extra_data={
        "razorpay_payment_id": payment_id,
        "razorpay_signature": signature
    }
)

# When payment fails
self._log_audit(
    booking_id=booking_id,
    pnr_number=pnr_number,
    action="PAYMENT_FAILED",
    new_state="PAYMENT_FAILED",
    actor_type="SYSTEM",
    amount=amount,
    reason="Razorpay verification failed",
    extra_data={"error_code": error_code}
)
```

---

## PART 2: STATE MACHINE WORKFLOW

**Location:** `/backend/services/booking_state_machine.py`

```
SEARCH 
  ↓
SELECTED 
  ↓
PASSENGER_INFO 
  ↓
PAYMENT_PENDING (← RAZORPAY INTEGRATION POINT)
  ↓
CONFIRMED 
  ↓
TICKETED 
  ↓
CANCELLED (can transition from any state)
```

**Valid State Transitions:**
```python
FLOW_TRANSITIONS = {
    BookingFlowState.SEARCH: [BookingFlowState.SELECTED],
    BookingFlowState.SELECTED: [BookingFlowState.PASSENGER_INFO, BookingFlowState.CANCELLED],
    BookingFlowState.PASSENGER_INFO: [BookingFlowState.PAYMENT_PENDING, BookingFlowState.CANCELLED],
    BookingFlowState.PAYMENT_PENDING: [BookingFlowState.CONFIRMED, BookingFlowState.CANCELLED],
    BookingFlowState.CONFIRMED: [BookingFlowState.TICKETED, BookingFlowState.CANCELLED],
    BookingFlowState.TICKETED: [BookingFlowState.CANCELLED],
    BookingFlowState.CANCELLED: [],
}
```

**INTEGRATION REQUIREMENT:**
- When creating Razorpay order: transition PASSENGER_INFO → PAYMENT_PENDING
- When payment verified: transition PAYMENT_PENDING → CONFIRMED
- When payment fails: transition PAYMENT_PENDING → CANCELLED (NOT BLOCKED)
- Use `BookingStateMachine.transition(booking, new_state)` for all state changes

---

## PART 3: DATABASE MODELS - PAYMENT INTEGRATION

### 3.1 Payment Model (PRIMARY INTEGRATION POINT)

**Location:** `/backend/database/models/core.py` (lines 1078-1105)

```python
class Payment(UserBase):
    """Payment transaction details."""
    __tablename__ = "payments"
    
    id: str (UUID, PK)
    booking_id: str (FK to bookings) [indexed]
    razorpay_order_id: str [indexed]        # ← Razorpay order ID
    razorpay_payment_id: str                # ← Razorpay payment ID
    razorpay_signature: str                 # ← Webhook signature
    user_id: str (FK to users) [indexed]
    route_id: str (FK to precalculated_routes) [indexed]
    amount: float (required)
    status: str = "pending"                 # pending, success, failed, refunded
    payment_method: str                     # e.g., "razorpay"
    payment_channel: str                    # e.g., "card", "netbanking", "upi"
    merchant_vpa: str                       # For UPI tracking
    refund_id: str [indexed]
    refund_status: str = "NOT_APPLICABLE"   # NOT_APPLICABLE, PENDING, SUCCESS, FAILED
    refund_amount: float
    created_at: datetime
    updated_at: datetime
```

**Relationships:**
```python
booking = relationship("Booking", backref="payments")
user = relationship("User", backref="payments", foreign_keys=[user_id])
route = relationship("PrecalculatedRoute", foreign_keys=[route_id])
unlocked_route = relationship("UnlockedRoute", back_populates="payment")
```

**FIELDS ALREADY SCAFFOLD FOR RAZORPAY:**
- `razorpay_order_id` - Store order ID from Razorpay create order response
- `razorpay_payment_id` - Capture from payment.capture() or webhook
- `razorpay_signature` - Store for webhook verification

### 3.2 Booking Model (DEPENDENT)

**Location:** `/backend/database/models/core.py` (lines 209-260)

```python
class Booking(UserBase):
    id: str (UUID, PK)
    pnr_number: str (unique, indexed)
    user_id: str (FK)
    travel_date: date [indexed]
    booking_status: str = "pending" [indexed]  # pending, confirmed, cancelled, etc.
    payment_status: str = "pending"            # pending, completed, failed
    escrow_status: EscrowStatus enum           # CREATED, UTR_SUBMITTED, VERIFIED, etc.
    amount_paid: float
    upi_tx_id: str (unique, indexed)
    utr_number: str (unique, indexed)
    booking_details: JSON                       # Store price breakdown, fraud flags
    train_number: str
    route_id: str
    journey_id: str [indexed]
    class_type: str
    from_station_code: str
    to_station_code: str
    ticket_pdf_url: str
    created_at: datetime
    
    # Relationships
    user = relationship("User", back_populates="bookings")
    passenger_details = relationship("PassengerDetails", back_populates="booking")
```

**KEY FIELD FOR INTEGRATION:**
- `booking_details` (JSON) - Store payment metadata:
  ```json
  {
    "razorpay_order_id": "order_...",
    "razorpay_payment_id": "pay_...",
    "fraud_flags": ["HIGH_VALUE"],
    "price_breakdown": {...},
    "surge_applied": 1.2,
    "seat_allocation": {...}
  }
  ```

### 3.3 Support Models

**BookingIdempotency Model:** (lines 261-276)
```python
class BookingIdempotency(UserBase):
    idempotency_key: str (PK)
    booking_id: str (FK to bookings)
    request_hash: str
    expires_at: datetime
```
Used to prevent duplicate payment processing.

**PaymentTransaction Model:** (lines 1106-1131)
```python
class PaymentTransaction(UserBase):
    payment_id: str (PK)
    booking_id: str (FK) [indexed]
    amount: float
    method: str  # "razorpay", "upi", "card", etc.
    status: str  # pending, success, failed, refunded
    provider_reference: str  # Razorpay's transaction ID
    utr_number: str (indexed)
    created_at, updated_at: datetime
```

---

## PART 4: API ROUTE STRUCTURE & PATTERNS

**Location:** `/backend/api/booking_routes.py`

### 4.1 Endpoint Patterns

```python
@router.post("/", response_model=BookingResponse, status_code=201)
async def create_booking(
    request: BookingRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Creates booking with automatic payment initiation."""
    try:
        booking_service = get_booking_service(db)
        result = await booking_service.create_booking(request, user.id)
        
        if result.status.value in ["failed", "error"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Booking creation failed"
            )
        
        return BookingResponse(...)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating booking: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 4.2 Endpoint Naming Convention

- **POST** `/api/v1/bookings/` - Create booking (with payment)
- **GET** `/api/v1/bookings/{booking_id}` - Get booking details
- **POST** `/{booking_id}/confirm-payment` - Confirm payment (NEW - FOR RAZORPAY)
- **POST** `/{booking_id}/cancel` - Cancel booking + refund
- **GET** `/pnr/{pnr_number}` - Public PNR lookup

**NEW ENDPOINT NEEDED:**
```python
@router.post("/{booking_id}/payment-callback", status_code=200)
async def payment_callback(
    booking_id: str,
    payload: dict,  # Razorpay webhook
    db: Session = Depends(get_db)
):
    """Handle Razorpay webhook callbacks."""
    # Verify signature
    # Update payment status
    # Transition booking state
    # Log audit
```

### 4.3 Error Handling Pattern

```python
try:
    booking_service = get_booking_service(db)
    # ... operation ...
except HTTPException:
    raise  # Re-raise HTTP errors
except Exception as e:
    logger.error(f"Error: {e}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error"
    )
```

**REQUIREMENT:** All Razorpay errors must be caught and returned as HTTPException with:
- 400 Bad Request: Invalid input, verification failed
- 402 Payment Required: Insufficient funds
- 503 Service Unavailable: Razorpay down (circuit breaker open)
- 500 Internal Server Error: Unexpected errors

---

## PART 5: SEAT AVAILABILITY MANAGER (RELATED PATTERN)

**Location:** `/backend/services/booking/manager.py`

The `SeatAvailabilityManager` demonstrates the **resilience pattern** Team 2 should follow:

```python
class SeatAvailabilityManager:
    def __init__(self, rapid_client: RapidAPIClient):
        # Circuit breakers for API and DB
        self._api_breaker = circuit_breaker_manager.get_or_create(
            "seat_availability_api",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
                success_threshold=3
            )
        )
        
        # Retry policy
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
```

**COPY THIS PATTERN FOR RAZORPAY:**
- Circuit breaker with failure/success thresholds
- Retry policy with exponential backoff + jitter
- Metrics tracking for observability
- Health check endpoints

---

## PART 6: CODE STYLE GUIDE & NAMING CONVENTIONS

### 6.1 Naming Patterns

**Methods:**
- Sync: `create_booking()`, `_check_fraud()`
- Async: `create_booking_async()`, `_check_idempotency()`
- Private: `_` prefix (e.g., `_create_booking_internal()`)
- Boolean: `is_*` or `*_allowed` (e.g., `is_monitoring_active`, `fraud_allowed`)

**Variables:**
- Snake case: `booking_id`, `user_id`, `razorpay_order_id`
- Constants: UPPER_CASE (e.g., `MAX_RETRIES = 3`)
- Data classes with `@dataclass` decorator

**Database Models:**
- Mapped columns: Use SQLAlchemy 2.0 style with `Mapped[Type]`
- Foreign keys: `Column(ForeignKey("table.id"))`
- Indexed frequently: `index=True` for queries

### 6.2 Error Handling Pattern

```python
try:
    result = await operation()
    if not result:
        raise ValueError("Operation returned None")
except HTTPException:
    raise  # Re-raise HTTP errors
except DBAPIError as e:
    logger.error(f"Database error: {e}")
    self.db.rollback()
    return None
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise HTTPException(status_code=500, detail="Internal server error")
finally:
    # Cleanup if needed
    pass
```

### 6.3 Logging Pattern

```python
logger = logging.getLogger(__name__)

logger.debug(f"🔒 Acquired lock: {lock_id}")  # Debug with emoji
logger.info(f"Booking created: {pnr_number}")  # Info level
logger.warning(f"⚠️ Booking flagged: {fraud_flags}")  # Warnings with emoji
logger.error(f"❌ Payment failed: {error}")  # Errors with emoji
```

### 6.4 Type Hints

```python
from typing import Optional, Dict, List, Any, Tuple

def _check_fraud(
    self,
    user_id: str,
    amount: float,
    booking_id: Optional[str] = None
) -> Tuple[bool, str, Dict]:
    """Return: (is_allowed, decision, details)"""
    pass

async def _check_idempotency(self, idempotency_key: str) -> Optional[Booking]:
    """Return booking if idempotent, None otherwise."""
    pass
```

---

## PART 7: INTEGRATION POINTS FOR RAZORPAY PAYMENT

### 7.1 Booking Creation Flow (MODIFIED FOR RAZORPAY)

**Current Flow:**
```
1. User submits BookingRequest
2. Validate date & fraud check
3. Generate idempotency key
4. Acquire distributed lock
5. Create Booking (status: pending)
6. Generate PNR
7. Reserve seat inventory
8. Add passenger details
9. Commit to DB
10. Publish booking.created event
```

**MODIFIED FLOW WITH RAZORPAY:**
```
1. User submits BookingRequest
2. Validate date & fraud check
3. Generate idempotency key
4. Check idempotency cache (return if exists)
5. Acquire distributed lock
6. Fraud check (return decision)
7. Create Booking (status: pending, payment_status: pending)
8. Generate PNR
9. CALL RAZORPAY: Create order with booking_id in notes
10. Store razorpay_order_id in Booking.booking_details
11. Reserve seat inventory (optimistic - can rollback)
12. Add passenger details
13. Transition booking state: PASSENGER_INFO → PAYMENT_PENDING
14. Log audit: PAYMENT_INITIATED
15. Commit to DB
16. Return BookingResponse with payment_url (Razorpay checkout)
```

### 7.2 Payment Verification Flow (NEW - WEBHOOK DRIVEN)

**Webhook Handler:**
```
1. Receive Razorpay webhook (payment.authorized or payment.captured)
2. Verify signature: verify_payment_signature(payload, razorpay_secret)
3. Look up booking by razorpay_order_id
4. Check idempotency (prevent duplicate processing)
5. Acquire lock (same as booking)
6. Verify payment amount matches Booking.amount_paid
7. Update Payment record:
   - status: "success"
   - razorpay_payment_id: payload.payment_id
   - razorpay_signature: payload.signature
8. Update Booking:
   - payment_status: "completed"
   - booking_status: "confirmed"
9. Transition state: PAYMENT_PENDING → CONFIRMED
10. Log audit: PAYMENT_VERIFIED
11. Trigger side effects:
    - Issue ticket (call IRCTC API if needed)
    - Send confirmation email
    - Publish booking.confirmed event
12. Commit to DB
```

### 7.3 Payment Failure & Refund Flow (NEW)

**On Payment Failure:**
```
1. Webhook: payment.failed or payment.expired
2. Look up booking
3. Acquire lock
4. Update Payment: status = "failed", reason = webhook.reason
5. Transition state: PAYMENT_PENDING → CANCELLED
6. Release seat inventory (unlocking seats)
7. Log audit: PAYMENT_FAILED
8. Send user notification
9. Commit
```

**On Refund:**
```
1. User initiates refund (POST /{booking_id}/cancel)
2. Verify booking is in CONFIRMED state
3. Call Razorpay: refund(payment_id, amount)
4. Update Payment: refund_status = "PENDING", refund_id = response.refund_id
5. Wait for refund webhook confirmation
6. On webhook: refund_status = "SUCCESS"
7. Update Booking: payment_status = "refunded"
8. Update BookingAuditLog: action = "REFUND"
```

---

## PART 8: RECOMMENDATIONS FOR TEAM 2

### 8.1 Immediate Action Items

**MUST DO:**
1. Create `PaymentService` class extending the `BookingService` pattern
2. Add Razorpay circuit breaker to BookingService init
3. Implement webhook signature verification (use Razorpay SDK)
4. Add three new audit log action types: "PAYMENT_INITIATED", "PAYMENT_VERIFIED", "PAYMENT_FAILED"
5. Extend `Booking.booking_details` JSON schema to include Razorpay fields
6. Create idempotency key for payments: `f"payment:{booking_id}:{int(amount*100)}"`

**MUST NOT DO:**
- Create parallel Payment creation logic (extend existing Payment model)
- Skip circuit breaker pattern (will cause cascade failures)
- Process webhooks without signature verification (security risk)
- Release locks before payment confirmation (race condition risk)
- Log sensitive data (no card numbers, API keys, signatures in logs)

### 8.2 Database Changes Required

```sql
-- Already exists, ensure indexed:
ALTER TABLE payments ADD INDEX idx_razorpay_order_id (razorpay_order_id);
ALTER TABLE payments ADD INDEX idx_razorpay_payment_id (razorpay_payment_id);

-- Add to Booking.booking_details schema:
-- {
--   "razorpay_order_id": "order_...",
--   "fraud_flags": [...],
--   "payment_method": "card|upi|netbanking",
--   "price_breakdown": {...}
-- }
```

### 8.3 Configuration Management

**New Config Values Needed:**
```python
# config.py or environment variables
RAZORPAY_KEY_ID = "rzp_live_..."
RAZORPAY_KEY_SECRET = "secret_..."
RAZORPAY_WEBHOOK_SECRET = "whsec_..."

# Circuit breaker
RAZORPAY_FAILURE_THRESHOLD = 5
RAZORPAY_TIMEOUT_SECONDS = 45
RAZORPAY_SUCCESS_THRESHOLD = 3

# Retry
RAZORPAY_MAX_RETRIES = 3
RAZORPAY_INITIAL_DELAY = 0.5
RAZORPAY_MAX_DELAY = 10.0

# Fraud
PAYMENT_HIGH_VALUE_THRESHOLD = 50000
PAYMENT_MAX_VELOCITY_24H = 10  # Bookings with payments
```

### 8.4 Testing Checklist

```python
# Unit Tests Required
- test_create_razorpay_order_success()
- test_create_razorpay_order_failure()
- test_verify_webhook_signature_valid()
- test_verify_webhook_signature_invalid()
- test_idempotency_prevents_duplicate_payment()
- test_circuit_breaker_opens_on_failures()
- test_fraud_check_blocks_high_value()
- test_lock_prevents_concurrent_payments()
- test_state_transition_payment_pending_to_confirmed()
- test_refund_releases_inventory()
- test_webhook_timeout_handling()
- test_concurrent_payments_same_user()

# Integration Tests Required
- test_end_to_end_booking_with_payment()
- test_payment_timeout_and_retry()
- test_payment_failure_with_cancellation()
- test_partial_refund_handling()
- test_concurrent_webhook_processing()

# Load Tests Required
- test_100_concurrent_bookings()
- test_webhook_spike_handling()
- test_lock_contention_performance()
```

### 8.5 Monitoring & Observability

**Metrics to Track:**
```python
# In BookingService metrics
- payment.razorpay.orders_created (counter)
- payment.razorpay.orders_failed (counter)
- payment.razorpay.verification_time_ms (histogram)
- payment.razorpay.webhook_processing_time_ms (histogram)
- circuit_breaker.razorpay.state (gauge: CLOSED/OPEN/HALF_OPEN)
- lock.acquisition_time_ms (histogram)
- fraud_check.risk_score (histogram)
- fraud_check.blocked (counter)
```

**Alerts to Set Up:**
```
- circuit_breaker.razorpay.state == OPEN
- payment.razorpay.orders_failed > 10 in 5min
- webhook_processing_time > 5000ms
- lock_acquisition_time > 30s
- fraud_check.blocked > 100 in 1h
```

---

## PART 9: RELATED SERVICES & DEPENDENCIES

### 9.1 Services to Integrate With

**BookingService** (Primary)
- Location: `/backend/services/booking/service.py`
- Method: Extend for payment operations
- Pattern: Use existing circuit breakers, locks, audit logging

**SeatAvailabilityManager** (Reference Pattern)
- Location: `/backend/services/booking/manager.py`
- Pattern: Circuit breaker + retry + metrics
- Learning: How to handle external API resilience

**NotificationService** (Webhook)
- Location: `/backend/services/communication/notifications.py`
- Purpose: Send payment confirmation/failure emails
- Integration: Trigger after payment state changes

**EventProducer** (Analytics)
- Location: `/backend/services/orchestration/event_producer.py`
- Purpose: Publish payment events to Kafka
- Integration: Fire `payment.verified`, `payment.failed` events

### 9.2 Files NOT to Touch (Read-Only)

- `/backend/services/booking_state_machine.py` - State machine is locked
- `/backend/database/models/core.py` - Only add to JSON fields
- `/backend/core/resilience/core.py` - Circuit breaker core (stable)
- `/backend/api/booking_routes.py` - Only add new endpoints

---

## PART 10: DEBT & KNOWN ISSUES

### 10.1 Current Limitations

1. **SeatAvailabilityManager** uses old-style imports (relative paths)
   - Fix: Update imports to use absolute paths when refactoring

2. **Booking.booking_details** is JSON - no schema validation
   - Recommendation: Add Pydantic model for type safety:
   ```python
   class BookingDetailsSchema(BaseModel):
       razorpay_order_id: Optional[str]
       fraud_flags: List[str]
       price_breakdown: Dict[str, float]
   ```

3. **Lock fallback to local asyncio.Lock** not Redis-safe for distributed
   - Risk: If Redis down, multiple instances can create duplicate bookings
   - Mitigation: Always require Redis in production

4. **Idempotency TTL hardcoded to 24h**
   - Should be: `IDEMPOTENCY_TTL_HOURS` config

5. **Fraud check runs BEFORE lock acquisition**
   - Risk: Duplicate fraud checks if request retried
   - Fix: Move fraud check inside lock critical section

### 10.2 Technical Debt to Avoid

**DON'T:**
- Add synchronous payment calls (will block event loop)
- Create new Lock implementation (use existing)
- Skip audit logging for "safety" (defeats compliance)
- Use booking_id as payment idempotency key (not unique for retries)
- Cache Payment models in Redis without TTL (memory leak)

---

## PART 11: PRODUCTION READINESS CHECKLIST

- [ ] Circuit breaker configured and tested
- [ ] Distributed lock acquired before payment creation
- [ ] Idempotency check implemented
- [ ] Fraud check runs before payment
- [ ] Audit log records all payment events
- [ ] State transitions follow FSM rules
- [ ] Webhook signature verified
- [ ] Webhook re-processing idempotent
- [ ] Refund flow tested end-to-end
- [ ] Error handling covers all Razorpay error codes
- [ ] Metrics instrumented for all operations
- [ ] Load test passes with 100 concurrent users
- [ ] Chaos testing: simulate Razorpay timeout
- [ ] Documentation includes example payloads
- [ ] Runbook prepared for payment failures

---

## APPENDIX A: FILE LOCATIONS REFERENCE

**Booking Service:**
- `/backend/services/booking/service.py` (1823 lines)
  - CircuitBreaker setup: lines 246-258
  - DistributedLock: lines 81-183
  - Fraud check: lines 470-539
  - Audit logging: lines 374-434
  - Idempotency: lines 305-368
  - create_booking_async: lines 617-722

**Managers:**
- `/backend/services/booking/manager.py` (323 lines)
  - SeatAvailabilityManager pattern: full file

**State Machine:**
- `/backend/services/booking_state_machine.py` (73 lines)
  - State definitions: lines 6-14
  - Transitions: lines 22-30

**API Routes:**
- `/backend/api/booking_routes.py` (276 lines)
  - Endpoint patterns: all endpoints

**Database Models:**
- `/backend/database/models/core.py` (1600+ lines)
  - Booking model: lines 209-260
  - Payment model: lines 1078-1105
  - BookingIdempotency: lines 261-276
  - BookingFraudCheck: lines 1333-1353
  - BookingAuditLog: lines 1462-1491

---

## DOCUMENT HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-06-08 | Architecture Team 1 | Initial analysis from codebase audit |

---

**END OF DOCUMENT**

Document Status: READY FOR TEAM 2-4 IMPLEMENTATION

For questions, refer to Session 5 MVP Build Plan and contact Architecture Team 1.
