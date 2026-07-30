# FEATURE #1: BOOKING & PAYMENT — REFINED IMPLEMENTATION SPEC

**Based on:** Deep codebase analysis  
**Status:** Ready to implement  
**Estimated Time:** 3-4 hours  
**Target Completion:** Today (Aug 1)

---

## PART A: ANALYSIS FINDINGS → SPEC

### What Already Exists (Don't Recreate)
✅ **Payment Service** (backend/services/payment_service.py)
- Razorpay order creation
- Webhook handler (3 event types)
- Signature verification
- Idempotency checking
- Audit logging
- Mock payment service for testing

✅ **Database Schema** (backend/database/models/core.py)
- Booking model (20 fields, comprehensive)
- BookingIdempotency model
- BookingAuditLog model
- BookingMonitor model

✅ **Frontend API Clients** (frontend/src/api/paymentFlow.ts)
- initiatePayment()
- verifyPayment()
- cancelPayment()

✅ **Schemas & Validation** (backend/schemas/booking.py)
- BookingStatus enum (9 states)
- BookingRequest/Response
- PassengerDetails validation

### What's Missing (Must Build)

| Component | Location | Status | Action |
|-----------|----------|--------|--------|
| **Booking Service Consolidation** | backend/services/ | 🔴 Multiple files | Pick main file, consolidate |
| **API Routes** | backend/api/v1/bookings.py | 🔴 Deprecated | Rebuild from scratch |
| **Webhook Receiver** | backend/api/v1/webhooks/ | 🔴 Missing | Create new endpoint |
| **Frontend State** | frontend/src/store/ | 🔴 Missing | Create Redux store |
| **Booking Flow Components** | frontend/src/components/ | 🟡 Partial | Complete & wire |
| **Email Notifications** | backend/services/ | 🔴 Missing | Add after payment |
| **Integration Tests** | backend/tests/ | 🔴 Missing | Add e2e tests |

---

## PART B: IMPLEMENTATION SPEC

### DECISION #1: Booking Service Consolidation

**Current Situation:**
- `backend/services/booking_service.py` → 3 lines (deprecated)
- `backend/services/booking/service.py` → 1,823 lines (likely real)
- `backend/services/agent_booking_service.py` → Agent bookings
- `backend/services/booking_verification_service.py` → Verification

**Decision:** 
We'll treat `booking/service.py` as main, and integrate with it rather than rewrite. First implementation will focus on the critical path: Booking → Payment → Confirmation.

### DECISION #2: API Route Strategy

**Plan:**
- Create clean `/api/v1/bookings` router
- Keep it simple: only CRITICAL endpoints for MVP
- Other complex logic stays in services

**Endpoints to Implement:**

```python
POST /api/v1/bookings
  │ Create booking
  ├─ Input: BookingRequest (from_station, to_station, passengers, date, class)
  ├─ Output: BookingResponse (booking_id, status)
  └─ Status: INITIATED

POST /api/v1/bookings/{booking_id}/payment/initiate
  │ Create Razorpay order
  ├─ Input: booking_id
  ├─ Output: razorpay_order_id, amount_paise
  └─ Calls: PaymentService.create_razorpay_order()

POST /api/v1/bookings/{booking_id}/payment/verify
  │ Verify payment & confirm booking
  ├─ Input: razorpay_order_id, razorpay_payment_id, razorpay_signature
  ├─ Output: booking_status, pnr_number
  └─ Calls: PaymentService.handle_razorpay_webhook()

POST /webhook/razorpay
  │ Razorpay webhook callback (CRITICAL)
  ├─ Input: Razorpay event (payment.authorized, payment.captured, payment.failed)
  ├─ Output: {status: "processed"}
  └─ Calls: PaymentService.handle_razorpay_webhook()

GET /api/v1/bookings/{booking_id}
  │ Get booking status
  ├─ Input: booking_id
  └─ Output: Complete booking details

POST /api/v1/bookings/{booking_id}/cancel
  │ Cancel booking & refund
  ├─ Input: reason
  └─ Calls: PaymentService.process_refund()
```

### DECISION #3: Frontend State Management

**Current:** No state management visible
**Plan:** Minimal Redux store (just for booking flow)

**Redux Store Structure:**
```typescript
bookingSlice: {
  current: {
    id: string
    status: BookingStatus
    passengers: PassengerDetails[]
    trainInfo: TrainInfo
    totalAmount: number
  }
  payment: {
    razorpayOrderId: string
    status: 'pending' | 'processing' | 'success' | 'failed'
    error?: string
  }
  loading: boolean
  error?: string
}
```

### DECISION #4: Testing Strategy

**Phase 1: Unit Tests** (existing infrastructure)
- Test payment service methods (already mostly done)
- Test booking state machine transitions

**Phase 2: Integration Tests** (new, critical)
- Test booking creation → payment initiation
- Test payment webhook → booking confirmation
- Test error scenarios

**Phase 3: E2E Tests** (using mock payment)
- Full user flow: search → book → pay → confirm

---

## PART C: FILES TO CREATE/MODIFY

### Backend Files

#### 1. CREATE: `backend/api/v1/bookings_router.py` (NEW FILE)
```python
from fastapi import APIRouter, Depends, HTTPException
from backend.schemas.booking import BookingRequest, BookingResponse
from backend.services.payment_service import PaymentService
from backend.database import get_db

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])

@router.post("", response_model=BookingResponse)
async def create_booking(request: BookingRequest, db=Depends(get_db)):
    """Create a new booking"""
    # Implementation here

@router.post("/{booking_id}/payment/initiate")
async def initiate_payment(booking_id: str, db=Depends(get_db)):
    """Initiate Razorpay payment"""
    # Implementation here

@router.post("/{booking_id}/payment/verify")
async def verify_payment(booking_id: str, data: dict, db=Depends(get_db)):
    """Verify payment signature and confirm booking"""
    # Implementation here

@router.get("/{booking_id}")
async def get_booking(booking_id: str, db=Depends(get_db)):
    """Get booking details"""
    # Implementation here

@router.post("/{booking_id}/cancel")
async def cancel_booking(booking_id: str, reason: str, db=Depends(get_db)):
    """Cancel booking and process refund"""
    # Implementation here
```

#### 2. CREATE: `backend/api/v1/webhooks_router.py` (NEW FILE)
```python
from fastapi import APIRouter, Request, HTTPException
from backend.services.payment_service import PaymentService

router = APIRouter(prefix="/webhook", tags=["webhooks"])

@router.post("/razorpay")
async def handle_razorpay_webhook(request: Request):
    """
    Razorpay webhook callback
    Handles: payment.authorized, payment.captured, payment.failed
    """
    payload = await request.json()
    signature = request.headers.get("X-Razorpay-Signature")
    
    service = PaymentService(db)
    result = await service.handle_razorpay_webhook(payload, signature)
    return result
```

#### 3. MODIFY: `backend/main.py`
```python
# Add these routers to FastAPI app:
from backend.api.v1 import bookings_router, webhooks_router

app.include_router(bookings_router.router)
app.include_router(webhooks_router.router)
```

#### 4. VERIFY: `backend/database/models/core.py`
- Confirm Booking model exists (it does ✓)
- Confirm BookingIdempotency exists (it does ✓)
- Confirm BookingAuditLog exists (it does ✓)
- Check if Payment table needed separately (current code embeds in Booking)

#### 5. UPDATE: `.env.example`
```bash
RAZORPAY_KEY_ID=your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
SENDGRID_API_KEY=your_sendgrid_key
SENDGRID_FROM_EMAIL=noreply@routemaster.app
```

### Frontend Files

#### 1. CREATE: `frontend/src/store/bookingSlice.ts` (NEW FILE)
```typescript
import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { BookingStatus, PassengerDetails } from "@/types";

interface BookingState {
  current: {
    id?: string;
    status: BookingStatus;
    passengers: PassengerDetails[];
    totalAmount: number;
  };
  payment: {
    razorpayOrderId?: string;
    status: "pending" | "processing" | "success" | "failed";
    error?: string;
  };
  loading: boolean;
  error?: string;
}

const initialState: BookingState = {
  current: {
    status: "initiated",
    passengers: [],
    totalAmount: 0,
  },
  payment: {
    status: "pending",
  },
  loading: false,
};

export const bookingSlice = createSlice({
  name: "booking",
  initialState,
  reducers: {
    // Actions...
  },
});
```

#### 2. MODIFY: `frontend/src/pages/Bookings.tsx`
- Wire to Redux store
- Add multi-step form (passenger details)
- Integrate payment flow
- Add success/error pages

#### 3. COMPLETE: `frontend/src/components/BookingFlowModal.tsx`
- Step 1: Passenger details form
- Step 2: Review & confirm
- Step 3: Payment (Razorpay modal)
- Step 4: Confirmation

#### 4. CREATE: `frontend/src/components/BookingConfirmation.tsx`
- Show PNR, ticket details
- Email/SMS confirmation status
- Download ticket option

#### 5. CREATE: `frontend/src/hooks/useBookingFlow.ts`
```typescript
export function useBookingFlow() {
  const dispatch = useDispatch();
  const booking = useSelector(state => state.booking);
  
  const createBooking = async (request: BookingRequest) => {
    // Call API
  };
  
  const initiatePayment = async (bookingId: string) => {
    // Call API
  };
  
  const verifyPayment = async (paymentData: VerifyPaymentRequest) => {
    // Call API
  };
  
  return { booking, createBooking, initiatePayment, verifyPayment };
}
```

### Test Files

#### 1. CREATE: `backend/tests/test_booking_flow.py`
```python
import pytest
from backend.api.v1.bookings_router import router

@pytest.mark.asyncio
async def test_create_booking():
    """Test booking creation"""
    # Implementation

@pytest.mark.asyncio
async def test_payment_flow():
    """Test booking → payment → confirmation flow"""
    # Implementation

@pytest.mark.asyncio
async def test_webhook_handling():
    """Test Razorpay webhook handling"""
    # Implementation
```

#### 2. CREATE: `frontend/src/__tests__/integration/bookingFlow.test.tsx`
```typescript
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Bookings } from "@/pages/Bookings";

describe("Booking Flow", () => {
  it("should complete full booking → payment → confirmation flow", async () => {
    // Implementation
  });
});
```

---

## PART D: IMPLEMENTATION CHECKLIST

### Backend Implementation
- [ ] Create `bookings_router.py` with all 5 endpoints
- [ ] Create `webhooks_router.py` with Razorpay handler
- [ ] Update `main.py` to include routers
- [ ] Test each endpoint with Postman/curl
- [ ] Verify payment service integration
- [ ] Test with mock payment service
- [ ] Add error handling & validation
- [ ] Add logging
- [ ] Update .env example

### Frontend Implementation
- [ ] Create Redux bookingSlice
- [ ] Create useBookingFlow hook
- [ ] Complete BookingFlowModal (4 steps)
- [ ] Create BookingConfirmation component
- [ ] Wire Bookings.tsx to backend
- [ ] Add error boundaries
- [ ] Add loading states
- [ ] Test with mock API
- [ ] Test Razorpay integration (sandbox)

### Testing
- [ ] Unit tests for payment service
- [ ] Integration tests (booking → payment → confirmation)
- [ ] E2E test with mock payment
- [ ] Test error scenarios
- [ ] Test webhook signature verification

### Documentation
- [ ] API documentation (endpoints, request/response)
- [ ] Booking lifecycle diagram
- [ ] Payment flow sequence diagram
- [ ] Deployment checklist

---

## PART E: SUCCESS CRITERIA

Feature #1 is DONE when:

✅ **User can complete full flow:**
1. Search for route (existing)
2. Click "Book Now"
3. Enter passenger details
4. Review & confirm
5. Pay via Razorpay (test mode)
6. See PNR confirmation
7. Receive email confirmation

✅ **Booking appears in:**
- Database (booking record)
- User dashboard (bookings list)
- Admin dashboard (all bookings)

✅ **Payment handling:**
- Razorpay webhook processes correctly
- Refunds work
- Idempotency prevents duplicates
- Audit log records all actions

✅ **Error handling:**
- Payment failed → user can retry
- Network error → graceful recovery
- Invalid data → validation errors

✅ **Tests pass:**
- Unit tests: 100%
- Integration tests: End-to-end flow
- E2E test: Full user scenario

---

## PART F: DEPENDENCY MAPPING

```
Feature #1 (Booking & Payment) - INDEPENDENT
    ↓ (enables)
Feature #2 (User Dashboard) - Needs booking data ✓
    ↓
Feature #3 (Notifications) - Needs booking & payment events ✓
    ↓
Feature #4 (Telegram Bot) - Needs booking queries ✓
    ↓
Feature #5 (Admin Dashboard) - Needs all booking/payment data ✓
```

**Key Point:** Once Feature #1 works, Features #2-5 will be much easier because they just CONSUME the booking data already created.

---

## PART G: TIME ESTIMATE BREAKDOWN

| Task | Estimate | Notes |
|------|----------|-------|
| Backend routing (5 endpoints) | 1 hour | Use existing payment service |
| Frontend Redux store | 30 mins | Simple store |
| Frontend components (complete) | 1.5 hours | Wire to backend |
| Testing & debugging | 1 hour | E2E flow |
| Docs & cleanup | 30 mins | Commit messages, env setup |
| **TOTAL** | **~4 hours** | **Today if we start now** |

---

**Spec Ready for Implementation**
**Next Step:** Start LOOP #1, STEP 3 (Rapid Implementation)
