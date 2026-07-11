# Team 4: Frontend Payment Integration - Complete Implementation

**Status:** READY FOR TEAM 3 API INTEGRATION  
**Date:** 2026-06-08  
**Frontend Developer:** Team 4  
**Backend Awaiting:** Team 3 (API endpoints)

---

## DELIVERABLES COMPLETED

### 1. Updated Bookings.tsx (Main Page Component)
**Location:** `/frontend/src/pages/Bookings.tsx`

**Changes:**
- Added payment flow state management (showPaymentModal, selectedBooking, paymentLoading)
- Integrated payment initiation on "Pay Now" button click
- Real-time booking status updates after successful payment
- Error handling with retry capability
- Mobile-responsive payment UI
- Payment confirmation modal with success/failure states

**Key Features:**
```typescript
// Payment Modal Integration
<PaymentModal
  isOpen={showPaymentModal}
  booking={selectedBooking}
  isLoading={paymentLoading}
  error={paymentError}
  onClose={closePaymentModal}
  onSuccess={handlePaymentSuccess}
/>

// Payment Confirmation Modal
<PaymentConfirmation
  isOpen={paymentConfirmation.isOpen}
  status={paymentConfirmation.status}
  message={paymentConfirmation.message}
  onClose={closeConfirmation}
/>
```

### 2. PaymentModal Component (Inline in Bookings.tsx)
**Features:**
- Razorpay checkout integration
- Payment amount display
- Order ID tracking
- Error messaging
- Loading states
- Accessibility-friendly design
- Mobile-friendly (full-width on small screens)

**User Flow:**
1. Click "Pay Now" button on booking card
2. Payment modal opens showing amount & PNR
3. Click "Pay Now with Razorpay"
4. Razorpay checkout opens
5. User completes payment
6. Frontend verifies signature with backend
7. Success/failure confirmation displayed
8. Bookings list refreshes automatically

### 3. Payment API Layer
**Location:** `/frontend/src/api/paymentFlow.ts`

**Endpoints Called:**
- `POST /api/v1/booking/payment/initiate` - Create Razorpay order
- `POST /api/v1/booking/payment/verify` - Verify payment signature
- `POST /api/v1/booking/payment/cancel` - Cancel payment (optional)
- `GET /api/v1/booking/{id}/payment-status` - Check payment status

**Functions Exported:**
```typescript
initiatePayment(bookingId: string)
  → InitiatePaymentResponse
  
verifyPayment(request: VerifyPaymentRequest)
  → VerifyPaymentResponse

cancelPayment(request: CancelPaymentRequest)
  → CancelPaymentResponse

getPaymentStatus(bookingId: string)
  → {status, order_id, payment_id}

setupPaymentTimeout(bookingId, timeoutMs)
  → NodeJS.Timeout (auto-cancel after 15 mins)

handlePaymentError(error)
  → string (user-friendly error message)
```

### 4. Payment Status Components
**Location:** `/frontend/src/components/PaymentStatusBadge.tsx`

**Components:**
- `PaymentStatusBadge` - Visual indicator for payment status
  - Shows: Paid (green), Pending Payment (yellow), Failed (red), Refunded (blue)
  - Customizable size and styling
  
- `PaymentTimeline` - Visual journey tracker
  - Initiated → Pending → Verified → Confirmed
  - Shows timestamps
  - Progress bar animation

---

## WAITING FOR TEAM 3 - API SPECIFICATION

### Required Endpoints

**1. POST /api/v1/booking/payment/initiate**
```json
{
  "request": {
    "booking_id": "uuid"
  },
  "response": {
    "razorpay_key_id": "rzp_live_...",
    "razorpay_order_id": "order_...",
    "amount_paise": 50000,
    "currency": "INR",
    "booking_id": "uuid",
    "status": "initiated"
  },
  "errors": {
    "400": "Invalid booking ID",
    "402": "Payment required (amount = 0)",
    "403": "Booking already paid",
    "500": "Failed to create Razorpay order"
  }
}
```

**2. POST /api/v1/booking/payment/verify**
```json
{
  "request": {
    "booking_id": "uuid",
    "razorpay_order_id": "order_...",
    "razorpay_payment_id": "pay_...",
    "razorpay_signature": "sig_..."
  },
  "response": {
    "status": "success",
    "booking_id": "uuid",
    "booking_status": "confirmed",
    "payment_status": "completed",
    "message": "Payment verified successfully",
    "pnr_number": "1234567890"
  },
  "errors": {
    "400": "Invalid signature",
    "404": "Booking not found",
    "409": "Duplicate payment (idempotency)",
    "500": "Verification failed"
  }
}
```

**3. POST /api/v1/booking/payment/cancel**
```json
{
  "request": {
    "booking_id": "uuid",
    "order_id": "order_...",
    "reason": "User cancelled"
  },
  "response": {
    "status": "success",
    "booking_id": "uuid",
    "message": "Payment cancelled"
  }
}
```

### Implementation Checklist for Team 3

- [ ] Circuit breaker for Razorpay API (see ARCHITECTURE_ANALYSIS_TEAM_1.md Part 1.1)
- [ ] Distributed lock acquisition before payment (Part 1.2)
- [ ] Idempotency check using payment key (Part 1.3)
- [ ] Fraud check before payment initiation (Part 1.4)
- [ ] Audit logging for all payment events (Part 1.5)
- [ ] State machine transitions: PASSENGER_INFO → PAYMENT_PENDING → CONFIRMED (Part 2)
- [ ] Razorpay signature verification (security critical)
- [ ] Webhook handler for payment callbacks
- [ ] Error handling for all Razorpay error codes
- [ ] Refund flow implementation

---

## TESTING CHECKLIST

### Unit Tests (Frontend)
- [ ] PaymentModal renders correctly
- [ ] PaymentModal disables button while loading
- [ ] Error messages display properly
- [ ] Cancel button closes modal
- [ ] Payment confirmation shows success/failure
- [ ] Toast notifications appear on payment events

### Integration Tests
- [ ] E2E: Search → Select → Passenger Info → Payment → Confirmed
- [ ] Payment timeout after 15 minutes cancels booking
- [ ] Duplicate payment verification (idempotency)
- [ ] Network error recovery
- [ ] Failed payment allows retry
- [ ] Successful payment updates booking status in real-time

### Manual Testing (With Team 3 Backend)
```bash
# 1. Create a test booking
- Navigate to search page
- Select a route
- Enter passenger details
- Confirm (booking created with payment_status: "pending")

# 2. Initiate payment
- Go to My Bookings
- Click "Pay Now" on pending booking
- Verify order_id created in backend

# 3. Complete payment
- Use Razorpay test cards:
  * Success: 4111111111111111 (any expiry, any CVV)
  * Failure: 4000000000000002
- Verify payment signature
- Check booking status updates to "confirmed"

# 4. Verify PNR assignment
- Check that ticket was issued
- Verify PNR appears in booking details

# 5. Test failure scenarios
- Cancel payment mid-flow
- Network timeout during verification
- Duplicate payment verification
```

### Load Testing
- [ ] 100 concurrent bookings + payments
- [ ] Payment timeout handling under load
- [ ] Lock contention with 50+ concurrent users
- [ ] Webhook spike handling (1000+ /min)

---

## FILE STRUCTURE

```
frontend/
├── src/
│   ├── pages/
│   │   └── Bookings.tsx                    ✅ UPDATED (payment flow)
│   ├── api/
│   │   ├── booking.ts                      ✅ EXISTS (no changes)
│   │   ├── payment.ts                      ✅ EXISTS (legacy - keep for compat)
│   │   └── paymentFlow.ts                  ✅ NEW (Team 3 integration)
│   ├── hooks/
│   │   ├── useBookingFlow.ts               ✅ EXISTS (no changes)
│   │   └── use-toast.ts                    ✅ EXISTS (notifications)
│   └── components/
│       └── PaymentStatusBadge.tsx          ✅ NEW (status display)
└── package.json                            (no changes needed)
```

---

## ENVIRONMENT CONFIGURATION

**No frontend configuration needed** - Backend provides Razorpay key in API response.

**Browser Requirements:**
- Razorpay checkout script loaded from CDN: `https://checkout.razorpay.com/v1/checkout.js`
- TLS 1.2+ for secure payment gateway

**Optional:** Store user preferences in localStorage:
```typescript
// Auto-fill payment form
localStorage.setItem("__authEmail", userEmail);
localStorage.setItem("__authPhone", userPhone);
```

---

## KNOWN LIMITATIONS & FUTURE IMPROVEMENTS

### Current Phase (MVP)
- Single payment method (Razorpay only)
- No saved payment methods
- No installment plans
- No partial payments

### Phase 2 (Post-MVP)
- Multiple payment gateways (Stripe, PayPal fallback)
- Saved payment methods for repeat customers
- Installment plans for high-value bookings
- Refund UI in Bookings page
- Payment receipt download

### Technical Debt to Address
- PaymentModal component could be extracted to separate file for reusability
- Add Zustand/Redux store for payment state if app grows
- Implement payment analytics tracking
- Add internationalization (i18n) for payment messages
- Rate limiting on payment attempts (5 per booking)

---

## DEBUGGING & MONITORING

### Frontend Debugging

**Payment Initiation Issues:**
```typescript
// Check browser console
window.__bookingDebug = {
  lastBooking: selectedBooking,
  lastError: paymentError,
  lastResponse: window.__lastPaymentResponse
};
```

**Razorpay Script Issues:**
```javascript
// In browser console
console.log(window.Razorpay ? "Razorpay loaded" : "Not loaded");
```

**Network Issues:**
```
DevTools → Network tab → Filter by "payment"
Check response headers and payloads
```

### Error Codes to Watch For

| Code | Meaning | User Action |
|------|---------|------------|
| 400 | Invalid input | Refresh page, try again |
| 402 | Amount is 0 | Contact support |
| 403 | Already paid | Refresh page (duplicate check) |
| 409 | Duplicate payment | Idempotency working (no action) |
| 503 | Razorpay down | Retry in 5 minutes |
| 500 | Server error | Contact support |

---

## INTEGRATION WITH TEAM 5 (QA)

**What Team 5 Will Test:**
- Full booking flow from search to confirmation
- Payment status updates
- Error recovery
- Mobile responsiveness
- Accessibility (WCAG 2.1 AA)
- Performance (Lighthouse)

**What Team 5 Needs:**
- Test bookings to practice payment flow
- Razorpay test account credentials
- Backend staging environment
- Test data (stations, routes, trains)

---

## ROLLOUT PLAN

### Phase 1: Internal Testing (Day 1-2)
- [ ] Team 3 & 4 testing together with staging backend
- [ ] Payment flow works end-to-end
- [ ] Error cases handled gracefully
- [ ] Monitoring alerts configured

### Phase 2: Team 5 QA (Day 3-4)
- [ ] Full test suite execution
- [ ] Edge case testing
- [ ] Load testing
- [ ] Security review

### Phase 3: Production Rollout (Day 5)
- [ ] Deploy to production
- [ ] Monitor payment success rate (target: >95%)
- [ ] Monitor error rates (target: <1%)
- [ ] Run incident response drills

---

## SUCCESS METRICS

**Target Metrics:**
- Payment success rate: >95% (Razorpay typical: 92-94%)
- Payment verification latency: <2 seconds
- Booking confirmation latency: <5 seconds
- UI responsiveness: Lighthouse >90
- Error recovery success: >90%

**Monitoring Dashboards:**
- Payment initiation rate (per minute)
- Payment verification success rate (%)
- Average payment time (seconds)
- Error rate by type
- Lock contention (ms)

---

## SUPPORT & ESCALATION

**During Development (Team 3 waiting):**
- Frontend: Team 4 (payment UI logic)
- Backend: Team 3 (API endpoints, Razorpay integration)
- Architecture: Team 1 (patterns, resilience)

**Questions/Blockers:**
1. Post in #team-4-payment Slack
2. Tag @team-3 for API questions
3. Tag @team-1 for architecture questions
4. Escalate payment failures to Team 3 on-call

---

## QUICK REFERENCE

### Key Files Modified
- `/frontend/src/pages/Bookings.tsx` - Main component

### Key Files Created
- `/frontend/src/api/paymentFlow.ts` - API layer
- `/frontend/src/components/PaymentStatusBadge.tsx` - Status display

### Key Dependencies
- `razorpay` - Payment gateway (loaded via CDN)
- `react-query` - Caching & refetch
- `lucide-react` - Icons

### Backend Handoff
See `/ARCHITECTURE_ANALYSIS_TEAM_1.md` for full backend integration guide.

---

**Document Status:** READY FOR TEAM 3 HANDOFF

For questions, contact Team 4 Frontend Lead or reference ARCHITECTURE_ANALYSIS_TEAM_1.md Part 7.

Generated: 2026-06-08
