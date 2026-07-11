# 🚀 AGENT TEAM DELEGATION BRIEF
## Feature #1: Razorpay Payment Integration (Parallel Build)

**Date:** June 8, 2026  
**Mission:** Complete booking + Razorpay payment integration  
**Duration:** 6-8 hours (parallel execution)  
**Status:** 🟢 Ready for immediate activation

---

## 📋 EXECUTIVE SUMMARY

**Foundation State:** 80% complete
- ✅ Booking API exists (`/api/booking_routes.py`)
- ✅ Booking service exists (`/services/booking/service.py` - 1823 lines)
- ✅ Database models exist (`/database/models.py`)
- ✅ State machine exists (`/services/booking_state_machine.py`)
- ✅ Frontend wiring exists (`/frontend/src/pages/Bookings.tsx`)
- ❌ **ONLY MISSING:** Razorpay payment integration

**Mission:** Add Razorpay to existing booking system (NOT rebuild)

**Key Constraint:** EXTEND existing code. Do NOT create new files. Do NOT duplicate. Do NOT replace.

---

## 🎯 TEAM ASSIGNMENTS

### **TEAM 1: ARCHITECTURE AUDIT**
**Lead:** Architecture Agent  
**Duration:** 2-3 hours  
**Dependencies:** None (Start immediately)

#### Mission
Deep audit of existing booking system to understand patterns and integration points.

#### Tasks
1. **Read & analyze** `/services/booking/service.py` (1823 lines)
   - Understand circuit breaker pattern
   - Understand distributed lock mechanism
   - Understand fraud detection logic
   - Map integration points for Razorpay
   - Document existing error handling patterns

2. **Review** `/services/booking/manager.py`
   - Seat availability management
   - Lock acquisition/release patterns

3. **Review** `/services/booking_state_machine.py`
   - Current state flow (SEARCH → SELECTED → PASSENGER_INFO → PAYMENT_PENDING → CONFIRMED → TICKETED → CANCELLED)
   - Where Razorpay fits

4. **Review** `/api/booking_routes.py`
   - Current endpoints structure
   - Request/response patterns
   - Error handling patterns

#### Deliverables
- **Architecture Analysis Document** with:
  - Key patterns to preserve
  - Integration points for Razorpay
  - Code style guide (indentation, naming, error handling)
  - Recommendations for Team 2

#### Success Criteria
- Clear understanding of how to extend payment_service.py
- Documented patterns for Team 2 to follow
- Identified all integration points

---

### **TEAM 2: BACKEND PAYMENT SERVICE**
**Lead:** Backend Agent  
**Duration:** 4-6 hours  
**Dependencies:** Team 1 (Wait for Architecture Analysis)

#### Mission
Extend `/services/payment_service.py` with complete Razorpay integration.

#### Tasks
1. **Extend `/services/payment_service.py`** with:
   - Razorpay SDK initialization
   - Order creation method (`create_razorpay_order()`)
   - Payment verification method (`verify_razorpay_signature()`)
   - Webhook handler (`handle_razorpay_webhook()`)
   - Idempotency support for payment operations
   - Distributed lock for concurrent payment handling
   - Circuit breaker for Razorpay API failures
   - Audit logging for all payment events
   - Event publishing for payment state changes

2. **Implementation details:**
   ```python
   # Add to PaymentService class:
   
   async def create_razorpay_order(
       self,
       booking_id: str,
       amount_paise: int,
       customer_email: str,
       customer_phone: str
   ) -> dict:
       """Create Razorpay order. Return order_id."""
       # Use distributed lock
       # Use circuit breaker for API call
       # Publish event: payment.order_created
       # Return: {"order_id": "...", "amount": amount_paise}
   
   async def verify_razorpay_signature(
       self,
       order_id: str,
       payment_id: str,
       signature: str
   ) -> bool:
       """Verify Razorpay webhook signature. Return True/False."""
       # Verify HMAC signature
       # Prevent replay attacks
       # Idempotency: check if payment already processed
       # Return: True if valid
   
   async def handle_razorpay_webhook(self, webhook_data: dict) -> dict:
       """Handle Razorpay payment webhook."""
       # Parse event type
       # Verify signature
       # Update booking state
       # Publish events
       # Audit log
   ```

3. **Preserve existing patterns:**
   - DistributedLock for concurrency control
   - CircuitBreaker for resilience
   - Idempotency handling (BookingIdempotency model)
   - Audit logging (BookingAuditLog model)
   - Event publishing (publish_event)
   - Error handling patterns

#### Files to Extend
- `/services/payment_service.py` (current file)

#### Files to NOT Create
- ❌ Do NOT create `/backend/services/payment_service.py`
- ❌ Do NOT create `/backend/webhooks/razorpay.py`

#### Deliverables
- **Extended `/services/payment_service.py`** with:
  - Razorpay order creation
  - Payment verification
  - Webhook handler
  - All existing patterns preserved
  - Full test coverage (Unit tests for Team 5)
  - Inline documentation

#### Success Criteria
- All Razorpay operations use distributed locks
- All operations are idempotent
- Circuit breaker active for API failures
- Audit logs for every payment event
- Events published for state changes
- No duplicate code created
- Tests pass for all new methods

---

### **TEAM 3: API ENDPOINTS**
**Lead:** API Agent  
**Duration:** 2-3 hours  
**Dependencies:** Team 2 (Wait for payment service complete)

#### Mission
Extend `/api/booking_routes.py` with Razorpay payment endpoints.

#### Tasks
1. **Extend `/api/booking_routes.py`** with endpoints:

   ```python
   @router.post("/v1/booking/payment/initiate")
   async def initiate_payment(request: InitiatePaymentRequest):
       """
       Initiate Razorpay payment.
       
       Request:
       {
           "booking_id": "BOOKING_123",
           "amount": 2500  # in rupees
       }
       
       Response:
       {
           "order_id": "order_ABC123",
           "amount_paise": 250000,
           "status": "pending"
       }
       """
       # Call PaymentService.create_razorpay_order()
       # Handle errors
       # Return order_id + amount for frontend

   @router.post("/v1/booking/payment/verify")
   async def verify_payment(request: VerifyPaymentRequest):
       """
       Verify Razorpay payment signature.
       
       Request:
       {
           "order_id": "order_ABC123",
           "payment_id": "pay_ABC123",
           "signature": "signature_hash"
       }
       
       Response:
       {
           "status": "confirmed",
           "booking_status": "CONFIRMED"
       }
       """
       # Call PaymentService.verify_razorpay_signature()
       # Update booking state to CONFIRMED
       # Return confirmation

   @router.post("/v1/booking/webhook/razorpay")
   async def razorpay_webhook(request: RazorpayWebhookRequest):
       """
       Handle Razorpay webhooks.
       
       Triggers on:
       - payment.captured
       - payment.failed
       - payment.authorized
       """
       # Call PaymentService.handle_razorpay_webhook()
       # Return 200 OK
   ```

2. **Wire to existing patterns:**
   - Use existing error handlers
   - Match existing response format
   - Preserve existing authentication
   - Follow existing API versioning (`/v1/booking/...`)

#### Files to Extend
- `/api/booking_routes.py` (current file)

#### Files to NOT Create
- ❌ Do NOT create `/backend/api/v1/bookings.py`
- ❌ Do NOT create new files

#### Deliverables
- **Extended `/api/booking_routes.py`** with:
  - 3 new payment endpoints
  - Full error handling
  - Request validation
  - Response formatting
  - Integration tests (for Team 5)

#### Success Criteria
- All endpoints follow existing API patterns
- All endpoints properly validated
- All errors handled consistently
- Endpoints tested end-to-end
- Frontend can call these endpoints

---

### **TEAM 4: FRONTEND INTEGRATION**
**Lead:** Frontend Agent  
**Duration:** 3-4 hours  
**Dependencies:** Team 3 (Wait for API endpoints)

#### Mission
Wire payment flow into existing Bookings.tsx component.

#### Tasks
1. **Update `/frontend/src/pages/Bookings.tsx`**:
   - Add payment form state
   - Add "Proceed to Payment" button in booking flow
   - Call `/v1/booking/payment/initiate` endpoint
   - Show Razorpay payment modal/window
   - Handle payment success/failure
   - Update booking status in dashboard

2. **Payment flow in component:**
   ```typescript
   // Add to Bookings.tsx:
   
   const [showPayment, setShowPayment] = useState(false);
   const [orderId, setOrderId] = useState(null);
   
   const handleProceedToPayment = async (bookingId) => {
       // Call API: /v1/booking/payment/initiate
       const { order_id, amount_paise } = await initiatePayment(bookingId);
       setOrderId(order_id);
       setShowPayment(true);
   };
   
   const handlePaymentSuccess = async (paymentId, signature) => {
       // Call API: /v1/booking/payment/verify
       const { status } = await verifyPayment({
           order_id: orderId,
           payment_id: paymentId,
           signature
       });
       // Update booking status to CONFIRMED
       setShowPayment(false);
   };
   ```

3. **Add components:**
   - Payment form component
   - Payment status component
   - Confirmation page
   - Error display

#### Files to Update
- `/frontend/src/pages/Bookings.tsx` (extend existing)
- May create new component files: `/frontend/src/components/PaymentModal.tsx`, `/frontend/src/components/PaymentConfirmation.tsx` (OK for frontend)

#### Deliverables
- **Updated Bookings.tsx** with:
  - Payment flow fully wired
  - User can book → pay → confirm
  - Status updates in real-time
  - Error handling and recovery
  - Mobile-friendly form

#### Success Criteria
- User can complete full booking flow with payment
- Payment status reflected immediately
- Errors handled gracefully
- Mobile responsive
- All existing booking features still work

---

### **TEAM 5: QA & TESTING**
**Lead:** Testing Agent  
**Duration:** 3-4 hours  
**Dependencies:** Teams 2, 3, 4 (Starts after Team 2 completes)

#### Mission
Comprehensive testing of Razorpay payment integration.

#### Tasks
1. **Unit tests for PaymentService:**
   - Test `create_razorpay_order()` with mocked Razorpay API
   - Test `verify_razorpay_signature()` with valid/invalid signatures
   - Test idempotency (same payment twice)
   - Test circuit breaker activation
   - Test error scenarios

2. **Integration tests:**
   - Test `/v1/booking/payment/initiate` endpoint
   - Test `/v1/booking/payment/verify` endpoint
   - Test webhook handler
   - Test booking state transitions with payment
   - Test concurrent payments for same booking

3. **End-to-end tests:**
   - Complete booking flow: Search → Select → Passenger Info → Payment → Confirmed
   - Payment failure recovery
   - Partial refund handling
   - Email notification on success
   - SMS notification on failure

4. **Security tests:**
   - Signature verification
   - Replay attack prevention
   - Idempotency key validation
   - SQL injection tests
   - Authorization checks

5. **Performance tests:**
   - Payment processing latency
   - Concurrent payment load
   - Circuit breaker failover time

#### Deliverables
- **Test suite** with:
  - Unit tests (>95% coverage for payment_service.py)
  - Integration tests
  - E2E test scenarios
  - Performance benchmarks
  - Security validation checklist

#### Success Criteria
- All tests passing
- >95% code coverage for new Razorpay code
- No security vulnerabilities
- Performance acceptable (<500ms per payment)
- All edge cases tested

---

### **TEAM 6: DEVOPS & CONFIGURATION**
**Lead:** DevOps Agent  
**Duration:** 1-2 hours  
**Dependencies:** None (Can start immediately, in parallel)

#### Mission
Configure Razorpay credentials and deployment infrastructure.

#### Tasks
1. **Razorpay setup:**
   - Get Razorpay API keys from test account
   - Get Razorpay secret key
   - Document key management

2. **Environment configuration:**
   - Add to `.env.local` (dev):
     ```
     RAZORPAY_KEY_ID=rzp_test_...
     RAZORPAY_KEY_SECRET=xxxx...
     RAZORPAY_WEBHOOK_SECRET=xxxx...
     ```
   - Add to `.env.staging` (staging)
   - Add to `.env.production` (prod)

3. **Database migrations:**
   - Verify `PaymentIdempotency` table exists
   - Verify `BookingAuditLog` table exists
   - Add indexes if needed

4. **Webhook configuration:**
   - Add webhook endpoint to Razorpay dashboard
   - Set webhook URL: `https://api.routemaster.com/v1/booking/webhook/razorpay`
   - Verify webhook signature secret

5. **Deployment setup:**
   - Create deployment checklist
   - Set up staging deployment
   - Plan production rollout (canary 10% → 50% → 100%)
   - Set up monitoring/alerts for payment failures

6. **Monitoring:**
   - Add metrics: payment success rate, avg processing time
   - Add alerts: payment failures > 5%, webhook errors
   - Create dashboard for payment monitoring

#### Deliverables
- **Configuration files** with:
  - Environment variables for all environments
  - Webhook setup documentation
  - Deployment checklist
  - Monitoring dashboard
  - Runbook for incident response

#### Success Criteria
- Razorpay keys configured correctly
- Webhooks receiving events
- Staging environment ready for testing
- Production deployment plan documented
- Monitoring active

---

## 🔄 DEPENDENCY GRAPH

```
Team 1 (Architecture)  ✓
    ↓
Team 2 (Backend)  ✓ [Also start Team 6 in parallel]
    ↓
Team 3 (API)
    ↓
Team 4 (Frontend)
    ↓
Team 5 (QA) [Also runs in parallel with Teams 2-4]
    ↓
Team 6 (DevOps) [Can run in parallel]
    ↓
🎉 Feature #1 Complete
```

**Timeline:**
- **Hour 0:** Team 1 starts audit, Team 6 starts DevOps setup
- **Hour 2-3:** Team 1 complete, Team 2 starts backend
- **Hour 4-6:** Team 2 complete, Team 3 starts API
- **Hour 6-8:** Team 3 complete, Team 4 starts frontend, Team 5 starts testing
- **Hour 8-10:** All teams complete, Feature #1 ready

**Parallel execution:** 6-8 hours total (not 18+)

---

## 📝 CRITICAL CONSTRAINTS

### ✅ DO THIS
- ✅ Extend existing files
- ✅ Follow existing code patterns
- ✅ Preserve circuit breakers, locks, fraud detection
- ✅ Coordinate between teams
- ✅ Use idempotency for all payment operations
- ✅ Audit log all payment events
- ✅ Publish events for state changes
- ✅ Test thoroughly before handing off

### ❌ DON'T DO THIS
- ❌ Create new files (extend existing)
- ❌ Duplicate code (reuse what's there)
- ❌ Ignore existing patterns (match the codebase)
- ❌ Skip error handling
- ❌ Remove existing functionality
- ❌ Work in isolation (coordinate)

---

## 📂 KEY FILES (REFERENCE)

### Architecture (Read to understand patterns)
- `/services/booking/service.py` (1823 lines - main booking service)
- `/services/booking/manager.py` (seat availability)
- `/services/booking_state_machine.py` (state flow)
- `/api/booking_routes.py` (API endpoints)
- `/database/models.py` (all data models)

### To Extend
- `/services/payment_service.py` ← **Team 2 extends this**
- `/api/booking_routes.py` ← **Team 3 extends this**
- `/frontend/src/pages/Bookings.tsx` ← **Team 4 extends this**

### To Preserve (Don't touch)
- `/services/booking_state_machine.py`
- `/services/booking/manager.py`
- `/database/models.py`
- Existing error handlers
- Existing authentication

---

## 🚨 HANDOFF CHECKLIST

### After Each Team Completes

**Team 1 → Team 2:**
- [ ] Architecture analysis document delivered
- [ ] Integration points documented
- [ ] Code patterns documented
- [ ] Any blockers identified

**Team 2 → Team 3:**
- [ ] `/services/payment_service.py` extended
- [ ] Unit tests passing
- [ ] Methods documented
- [ ] Team 5 can begin testing

**Team 3 → Team 4:**
- [ ] API endpoints tested
- [ ] Endpoint documentation delivered
- [ ] Integration test cases provided

**Team 4 → Product Ready:**
- [ ] Frontend integrated
- [ ] E2E tests passing
- [ ] Mobile tested

**Team 5 (Throughout):**
- [ ] Unit tests ✓
- [ ] Integration tests ✓
- [ ] E2E tests ✓
- [ ] Security validation ✓

**Team 6 (In Parallel):**
- [ ] Dev environment ready ✓
- [ ] Staging environment ready ✓
- [ ] Production deployment plan ✓

---

## 🎯 SUCCESS METRICS

By end of Feature #1:
- ✅ User can book train ticket
- ✅ User can pay via Razorpay
- ✅ Payment confirmation received
- ✅ Email notification sent
- ✅ SMS notification sent
- ✅ Booking status updated to CONFIRMED
- ✅ All tests passing (>95% coverage)
- ✅ Zero critical security issues
- ✅ Performance acceptable (<500ms per payment)

---

## 🚀 ACTIVATION INSTRUCTIONS

**For the User (Gaurav):**

1. **Load this document** and share with agent teams
2. **Activate Team 1** immediately:
   ```python
   # In your agent orchestrator:
   architecture_agent.execute(AGENT_TEAM_DELEGATION_BRIEF, task="TEAM_1_ARCHITECTURE_AUDIT")
   ```

3. **Monitor progress:**
   - Team 1: 0-3h (architectural analysis)
   - Team 2: 2-6h (payment service)
   - Team 3: 4-8h (API endpoints)
   - Team 4: 6-10h (frontend)
   - Team 5: 4-10h (testing)
   - Team 6: 0-2h (DevOps)

4. **Coordinate handoffs:**
   - When Team 1 completes → Start Team 2
   - When Team 2 completes → Start Team 3 + Team 5
   - When Team 3 completes → Start Team 4
   - When all complete → Feature ready for deployment

5. **Expected Result:**
   - Feature #1 complete in 6-8 hours
   - Production-ready code
   - All tests passing
   - Deployment checklist ready

---

## 📞 ESCALATION

If any team gets blocked:
1. Document blocker clearly
2. Notify other teams
3. Coordinate solution (may require brief cross-team sync)
4. Update timeline estimate

---

**Status:** 🟢 READY FOR AGENT TEAM ACTIVATION

All documentation complete. All team briefs clear. All deliverables defined. 

**Activate agents and execute.** ✅

---

**Questions for Agents:**
- Team 1: Ready to audit booking service architecture?
- Team 2: Ready to extend payment service with Razorpay?
- Team 3: Ready to add payment endpoints to API?
- Team 4: Ready to wire frontend to payment flow?
- Team 5: Ready to test everything?
- Team 6: Ready to configure DevOps infrastructure?

**Answer: YES? Then execute Feature #1 in parallel. 🚀**
