# Feature #1: Booking Flow & Payment Integration — Complete Design & Implementation Plan

**Status:** 🎯 Design Phase Complete  
**Target:** Professional booking-to-payment flow with confirmation, history, and admin controls  
**Timeline:** 12-15 hours implementation

---

## PART 1: PRODUCT DESIGN

### 1.1 User Journey

```
User Flow:
  1. Search Results → RouteCard
  2. Click "Book Now"
  3. Modal Opens: BookingFlowModal
     - Step 1: Passenger Details (name, email, phone)
     - Step 2: Seat Selection (if available preview)
     - Step 3: Review (show all selected data + total fare)
     - Step 4: Payment (Razorpay payment page)
  4. Payment Success → Confirmation Page
  5. Email/SMS with ticket & PNR
  6. User can view in Dashboard → Bookings tab

Admin Flow:
  1. Admin → Bookings Dashboard
  2. See all bookings (filter by status, date, user)
  3. See payment status
  4. See IRCTC confirmation status
  5. Action: Manual sync with IRCTC, issue refund, cancel booking
```

### 1.2 Business Workflow

```
Booking Lifecycle:
  PENDING_PAYMENT
    ↓ (user completes payment)
  PAYMENT_CONFIRMED
    ↓ (our system confirms via IRCTC webhook or manual API call)
  TICKET_CONFIRMED (PNR + ticket numbers received)
    ↓ (user travels)
  COMPLETED
    ↓ (optional post-travel: user can rate, review)
  REVIEWED

Alternative Paths:
  PAYMENT_FAILED → User retries or abandons
  TICKET_NOT_ISSUED → Auto-refund after 24h
  USER_CANCELLATION → Refund (70-100% based on timing)
```

### 1.3 Screen Flow

**Screen 1: Route Card → Booking Trigger**
```
RouteCard (existing component)
  - Train number, departure, arrival, duration
  - Available classes (1A, 2A, 3A, SL)
  - Fare
  - [Book Now] button
    → Opens BookingFlowModal
```

**Screen 2: Booking Modal - Step 1 (Passenger Details)**
```
BookingFlowModal (existing component, needs wiring)
  Progress: [1/4] Passenger Details

  Form:
    - Full Name (required)
    - Email (pre-fill from auth, optional change)
    - Phone (pre-fill from auth, optional change)
    - Date of Birth (optional)
    - Gender (required for IRCTC)
    - Seat Preference (choice: any/aisle/window)

  Actions:
    [Cancel] [Next]
```

**Screen 3: Step 2 (Seat Selection / Class Confirmation)**
```
  Progress: [2/4] Select Class & Seat

  Available Classes:
    ☐ 1A (₹5000) — Most comfortable
    ☐ 2A (₹3500) — Premium AC
    ☐ 3A (₹2500) — AC
    ☐ SL (₹1500) — Sleeper

  Once selected, show:
    "Seat selection not available via API. You'll select on IRCTC after payment."
    [Live Occupancy: 234/432 seats available in selected class]

  Actions:
    [Back] [Next]
```

**Screen 4: Step 3 (Review)**
```
  Progress: [3/4] Review Booking

  Summary Card:
    Train: 12951 Rajdhani Express
    Date: June 15, 2026
    From: NDLS 06:00
    To: BCT 16:30
    Duration: 10h 30m

  Passenger:
    Name: John Doe
    Email: john@example.com
    Phone: +91-9999999999
    Gender: Male

  Class: 3A
  Total Fare: ₹2,500
  Taxes: ₹150
  Service Fee: ₹50
  Grand Total: ₹2,700

  Cancellation Policy:
    ✓ Cancel 48h before: 100% refund
    ✓ Cancel 12-48h: 75% refund
    ✓ Cancel <12h: 0% refund (we keep fee)

  ☐ I agree to terms & conditions
  ☐ I agree to privacy policy

  Actions:
    [Back] [Proceed to Payment]
```

**Screen 5: Step 4 (Payment)**
```
  Progress: [4/4] Payment

  Total Amount: ₹2,700

  [Pay with Razorpay]
    → Opens Razorpay payment widget
    → User selects payment method (card, UPI, wallet, bank transfer)
    → Razorpay processes payment
    → Returns to our app

  If Success:
    → Navigate to Confirmation Page
  If Failed:
    → Show error message
    → Allow retry
```

**Screen 6: Confirmation Page**
```
/booking/confirmation/{booking_id}

  Success Banner:
    ✓ Booking Confirmed!
    PNR: TBD (will be assigned by IRCTC within 24h)

  Booking Details:
    Booking ID: BK-202606-001234
    Status: PAYMENT_CONFIRMED (Waiting for IRCTC)
    Date: June 15, 2026
    Train: 12951 Rajdhani Express
    Route: NDLS → BCT
    Class: 3A
    Passenger: John Doe
    Total Paid: ₹2,700

  Timeline:
    ✓ Payment Confirmed (June 8, 14:32)
    ⏳ Waiting for IRCTC confirmation (24h)
    ⏳ Ticket will be issued
    ⏳ You can travel
    ⏳ Complete journey & review

  Actions:
    [Download Confirmation PDF] [View on IRCTC] [Track Booking] [Go to Dashboard]

  Message:
    "We've sent a confirmation email to john@example.com with all booking details.
     Your ticket will be issued within 24 hours. You can check status anytime in Dashboard → Bookings."
```

**Screen 7: Dashboard - Bookings Tab**
```
Dashboard → Bookings

Tabs: [Upcoming] [Past] [Cancelled]

Upcoming Bookings:
  ┌─────────────────────────────────────┐
  │ 12951 Rajdhani Express              │
  │ NDLS → BCT | June 15, 2026          │
  │ Class: 3A | Status: TICKET_CONFIRMED│
  │ PNR: 1234567890                     │
  │                                     │
  │ [View Ticket] [Track] [Cancel]      │
  └─────────────────────────────────────┘

Past Bookings:
  ┌─────────────────────────────────────┐
  │ 12345 Express                       │
  │ NDLS → KTM | June 1, 2026 (Completed)
  │ Class: 2A                           │
  │ PNR: 9876543210                     │
  │                                     │
  │ [View Ticket] [Rate this Trip] [Rebook]
  └─────────────────────────────────────┘
```

---

## PART 2: SYSTEM ARCHITECTURE

### 2.1 Data Flow Diagram

```
Frontend (React)
    ↓
    ├─ RouteCard.tsx [Book Now]
    ↓
    ├─ BookingFlowModal.tsx
    │    ├─ Step 1: Passenger Details → Form state
    │    ├─ Step 2: Class Selection → Select state
    │    ├─ Step 3: Review → Summary state
    │    └─ Step 4: Payment
    │         ↓
    │    Razorpay.loadScript() → Payment Widget
    │         ↓
    └─→ Backend POST /api/v1/bookings/create
           ↓
        Create booking record (status: PENDING_PAYMENT)
        Return booking_id + razorpay_order_id
           ↓
    Razorpay API (razorpay.com)
           ↓
        Payment Processing
           ↓
    Razorpay Webhook → POST /api/v1/webhooks/razorpay
           ↓
        Update booking (status: PAYMENT_CONFIRMED)
        Create payment record
           ↓
    Background Job (async):
        Call IRCTC API / Manual Confirmation
           ↓
        Update booking (status: TICKET_CONFIRMED)
        Store PNR, ticket_no
           ↓
    Email Service
        Send confirmation email with ticket
           ↓
    Frontend (Dashboard)
        User sees updated booking status
```

### 2.2 Microservice Dependencies

```
Booking Service
  ├─ Razorpay Payment Service (external)
  ├─ IRCTC Booking API (external, may not exist)
  ├─ Email Service (SendGrid or Twilio SendGrid)
  ├─ SMS Service (Twilio)
  ├─ Database (Supabase PostgreSQL)
  └─ Redis Cache (order confirmation caching)
```

---

## PART 3: DATABASE DESIGN

### 3.1 Schema

```sql
-- Bookings table
CREATE TABLE bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    
    -- Journey details
    train_number VARCHAR(10) NOT NULL,
    journey_date DATE NOT NULL,
    source_station VARCHAR(10) NOT NULL,
    destination_station VARCHAR(10) NOT NULL,
    class_type VARCHAR(5) NOT NULL, -- 1A, 2A, 3A, SL
    
    -- Passenger details
    passenger_name VARCHAR(100) NOT NULL,
    passenger_email VARCHAR(100),
    passenger_phone VARCHAR(20),
    passenger_gender VARCHAR(10),
    passenger_dob DATE,
    
    -- Pricing
    base_fare DECIMAL(10, 2) NOT NULL,
    taxes DECIMAL(10, 2) DEFAULT 0,
    service_fee DECIMAL(10, 2) DEFAULT 50,
    total_fare DECIMAL(10, 2) NOT NULL,
    
    -- Status tracking
    status VARCHAR(30) NOT NULL, -- PENDING_PAYMENT, PAYMENT_CONFIRMED, TICKET_CONFIRMED, COMPLETED, CANCELLED, REFUNDED
    
    -- IRCTC integration
    pnr VARCHAR(20),
    ticket_number VARCHAR(50),
    seat_number VARCHAR(10),
    coach_number VARCHAR(10),
    
    -- Cancellation
    cancellation_requested_at TIMESTAMP,
    cancellation_reason VARCHAR(255),
    refund_amount DECIMAL(10, 2),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    journey_completed_at TIMESTAMP,
    
    -- Metadata
    metadata JSONB -- any extra data (seat preferences, etc)
);

-- Payments table
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(id),
    
    -- Razorpay details
    razorpay_order_id VARCHAR(50) UNIQUE,
    razorpay_payment_id VARCHAR(50) UNIQUE,
    razorpay_signature VARCHAR(255),
    
    -- Payment details
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    payment_method VARCHAR(50), -- card, upi, wallet, bank_transfer
    status VARCHAR(30) NOT NULL, -- INITIATED, SUCCESS, FAILED, REFUNDED
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    failed_at TIMESTAMP,
    
    -- Error handling
    error_message VARCHAR(500),
    retry_count INT DEFAULT 0,
    
    metadata JSONB
);

-- Tickets table (issued by IRCTC)
CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(id),
    
    pnr VARCHAR(20) UNIQUE NOT NULL,
    ticket_number VARCHAR(50) UNIQUE NOT NULL,
    seat_number VARCHAR(10),
    coach_number VARCHAR(10),
    
    -- IRCTC status
    irctc_status VARCHAR(30), -- CONFIRMED, CHART_NOT_PREPARED, CANCELLED
    chart_status_updated_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Refunds table
CREATE TABLE refunds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(id),
    payment_id UUID NOT NULL REFERENCES payments(id),
    
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(30) NOT NULL, -- INITIATED, SUCCESS, FAILED
    
    razorpay_refund_id VARCHAR(50),
    reason VARCHAR(255),
    
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    metadata JSONB
);

-- Booking reviews (post-journey)
CREATE TABLE booking_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(id),
    
    rating INT CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT,
    
    cleanliness_rating INT,
    comfort_rating INT,
    staff_rating INT,
    food_rating INT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indices for performance
CREATE INDEX idx_bookings_user_id ON bookings(user_id);
CREATE INDEX idx_bookings_status ON bookings(status);
CREATE INDEX idx_bookings_journey_date ON bookings(journey_date);
CREATE INDEX idx_bookings_train_number ON bookings(train_number);
CREATE INDEX idx_payments_booking_id ON payments(booking_id);
CREATE INDEX idx_payments_razorpay_order ON payments(razorpay_order_id);
CREATE INDEX idx_tickets_booking_id ON tickets(booking_id);
CREATE INDEX idx_tickets_pnr ON tickets(pnr);
```

### 3.2 Migrations

```bash
# Migration script to create tables
# backend/database/migrations/002_create_booking_tables.sql

-- Run in Supabase SQL editor
```

---

## PART 4: API DESIGN

### 4.1 REST Endpoints

#### POST /api/v1/bookings/create
**Create a new booking**

Request:
```json
{
  "train_number": "12951",
  "journey_date": "2026-06-15",
  "source_station": "NDLS",
  "destination_station": "BCT",
  "class_type": "3A",
  "passenger_name": "John Doe",
  "passenger_email": "john@example.com",
  "passenger_phone": "+91-9999999999",
  "passenger_gender": "M",
  "passenger_dob": "1990-05-15"
}
```

Response:
```json
{
  "booking_id": "bk-xxxx-xxxx-xxxx",
  "status": "PENDING_PAYMENT",
  "razorpay_order_id": "order_xxxx",
  "razorpay_amount": 270000, // in paise
  "razorpay_currency": "INR",
  "razorpay_key_id": "rzp_live_xxxx",
  "user_id": "user-xxxx",
  "total_fare": 2700,
  "created_at": "2026-06-08T14:32:00Z"
}
```

#### POST /api/v1/bookings/{id}/confirm-payment
**Confirm Razorpay payment (called after payment success)**

Request:
```json
{
  "razorpay_order_id": "order_xxxx",
  "razorpay_payment_id": "pay_xxxx",
  "razorpay_signature": "xxxx"
}
```

Response:
```json
{
  "booking_id": "bk-xxxx",
  "status": "PAYMENT_CONFIRMED",
  "payment_id": "payment-xxxx",
  "message": "Payment confirmed. Waiting for IRCTC ticket issuance."
}
```

#### GET /api/v1/bookings/{id}
**Fetch booking details**

Response:
```json
{
  "id": "bk-xxxx",
  "user_id": "user-xxxx",
  "train_number": "12951",
  "journey_date": "2026-06-15",
  "source_station": "NDLS",
  "destination_station": "BCT",
  "class_type": "3A",
  "passenger_name": "John Doe",
  "status": "TICKET_CONFIRMED",
  "pnr": "1234567890",
  "ticket_number": "001-2345678",
  "seat_number": "32C",
  "coach_number": "A1",
  "total_fare": 2700,
  "created_at": "2026-06-08T14:32:00Z",
  "payment": {
    "id": "payment-xxxx",
    "status": "SUCCESS",
    "amount": 2700,
    "razorpay_payment_id": "pay_xxxx"
  }
}
```

#### GET /api/v1/bookings/my
**Fetch user's bookings (paginated)**

Query params: `?status=TICKET_CONFIRMED&limit=10&offset=0&sort=created_at:desc`

Response:
```json
{
  "bookings": [...],
  "total": 5,
  "page": 1,
  "per_page": 10
}
```

#### POST /api/v1/bookings/{id}/cancel
**Cancel a booking (with refund)**

Request:
```json
{
  "reason": "Change in plans"
}
```

Response:
```json
{
  "booking_id": "bk-xxxx",
  "status": "CANCELLED",
  "refund_amount": 1900,
  "refund_reason": "User requested cancellation",
  "message": "Booking cancelled. Refund will be processed within 3-5 business days."
}
```

#### POST /api/v1/bookings/{id}/review
**Post-booking review**

Request:
```json
{
  "rating": 4,
  "review_text": "Great train, comfortable seats, good food.",
  "cleanliness_rating": 4,
  "comfort_rating": 5,
  "staff_rating": 4,
  "food_rating": 3
}
```

#### POST /api/v1/webhooks/razorpay
**Razorpay webhook (payment confirmation)**

Incoming from Razorpay:
```json
{
  "event": "payment.authorized",
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_xxxx",
        "entity": "payment",
        "amount": 270000,
        "currency": "INR",
        "status": "authorized",
        "method": "card",
        "description": "Booking for train 12951",
        "order_id": "order_xxxx"
      }
    }
  }
}
```

---

## PART 5: FRONTEND COMPONENT DESIGN

### 5.1 Component Tree

```
<BookingFlowModal>
  ├── <BookingStepProgress> (shows 1/4, 2/4, etc)
  ├── <BookingStep1_PassengerDetails>
  ├── <BookingStep2_ClassSelection>
  ├── <BookingStep3_Review>
  ├── <BookingStep4_Payment>
  │   └── <RazorpayPaymentWidget>
  └── <BookingConfirmationStep>
```

### 5.2 State Management

```typescript
interface BookingState {
  // Journey details
  trainNumber: string;
  journeyDate: string;
  sourceStation: string;
  destinationStation: string;
  classType: string;
  
  // Passenger
  passengerName: string;
  passengerEmail: string;
  passengerPhone: string;
  passengerGender: string;
  passengerDob?: string;
  
  // Pricing
  baseFare: number;
  taxes: number;
  serviceFee: number;
  totalFare: number;
  
  // Status
  status: 'PENDING_PAYMENT' | 'PAYMENT_CONFIRMED' | 'TICKET_CONFIRMED';
  step: 1 | 2 | 3 | 4;
  
  // Payment
  razorpayOrderId?: string;
  paymentStatus?: 'SUCCESS' | 'FAILED';
  
  // Metadata
  bookingId?: string;
  createdAt?: string;
}
```

### 5.3 Key Components (Pseudocode)

**BookingFlowModal.tsx** (existing, needs wiring):
```tsx
function BookingFlowModal({ route, onClose }) {
  const [state, dispatch] = useReducer(bookingReducer, initialState);
  
  const handleStepNext = async () => {
    if (state.step === 1) {
      // Validate passenger details
      dispatch({ type: 'SET_STEP', payload: 2 });
    } else if (state.step === 2) {
      // Validate class selection
      dispatch({ type: 'SET_STEP', payload: 3 });
    } else if (state.step === 3) {
      // Create booking on backend
      const response = await api.post('/bookings/create', state);
      dispatch({ type: 'SET_BOOKING', payload: response });
      dispatch({ type: 'SET_STEP', payload: 4 });
    } else if (state.step === 4) {
      // Payment handled by Razorpay
    }
  };
  
  return (
    <Dialog open={true} onOpenChange={onClose}>
      <BookingStepProgress step={state.step} total={4} />
      
      {state.step === 1 && <BookingStep1_PassengerDetails {...} />}
      {state.step === 2 && <BookingStep2_ClassSelection {...} />}
      {state.step === 3 && <BookingStep3_Review {...} />}
      {state.step === 4 && <BookingStep4_Payment {...} />}
      
      <DialogFooter>
        {state.step > 1 && <Button onClick={handleStepBack}>Back</Button>}
        {state.step < 4 && <Button onClick={handleStepNext}>Next</Button>}
        {state.step === 4 && <Button onClick={handlePayment}>Pay Now</Button>}
      </DialogFooter>
    </Dialog>
  );
}
```

**BookingStep4_Payment.tsx**:
```tsx
function BookingStep4_Payment({ booking, onSuccess }) {
  const [isLoading, setIsLoading] = useState(false);
  
  const handlePayment = async () => {
    setIsLoading(true);
    
    const options = {
      key: import.meta.env.VITE_RAZORPAY_KEY,
      amount: booking.razorpay_amount,
      currency: booking.razorpay_currency,
      order_id: booking.razorpay_order_id,
      handler: async (response) => {
        // Verify payment on backend
        const verified = await api.post(`/bookings/${booking.booking_id}/confirm-payment`, {
          razorpay_order_id: response.razorpay_order_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature
        });
        
        onSuccess(verified.booking_id);
      },
      onError: (error) => {
        toast.error("Payment failed. Please retry.");
      }
    };
    
    const razorpay = new window.Razorpay(options);
    razorpay.open();
  };
  
  return (
    <div>
      <p>Total Amount: ₹{booking.razorpay_amount / 100}</p>
      <Button onClick={handlePayment} disabled={isLoading}>
        {isLoading ? 'Processing...' : 'Pay with Razorpay'}
      </Button>
    </div>
  );
}
```

---

## PART 6: BACKEND IMPLEMENTATION PLAN

### 6.1 Folder Structure

```
backend/
├── api/
│   └── v1/
│       ├── bookings.py (NEW)
│       └── payments.py (NEW)
├── services/
│   ├── booking_service.py (NEW)
│   ├── payment_service.py (NEW)
│   └── email_service.py (NEW)
├── database/
│   ├── migrations/
│   │   └── 002_create_booking_tables.sql (NEW)
│   └── models/
│       └── booking_models.py (NEW)
└── webhooks/
    └── razorpay.py (NEW)
```

### 6.2 Files to Create/Modify

1. **backend/database/migrations/002_create_booking_tables.sql** — Create tables
2. **backend/database/models/booking_models.py** — SQLAlchemy models
3. **backend/api/v1/bookings.py** — Endpoints
4. **backend/services/booking_service.py** — Business logic
5. **backend/services/payment_service.py** — Razorpay integration
6. **backend/services/email_service.py** — Email notifications
7. **backend/webhooks/razorpay.py** — Webhook handler
8. **backend/app.py** — Register new routes + webhook

### 6.3 Environment Variables to Add

```
RAZORPAY_KEY_ID=rzp_live_xxxx
RAZORPAY_KEY_SECRET=xxxx
RAZORPAY_WEBHOOK_SECRET=xxxx

SENDGRID_API_KEY=SG.xxxx
SENDGRID_FROM_EMAIL=noreply@routemaster.in

BOOKING_CONFIRMATION_EMAIL_TEMPLATE_ID=xxxx
```

---

## PART 7: IMPLEMENTATION CHECKLIST

### Phase 1: Database Setup (2h)
- [ ] Write migration SQL
- [ ] Run migration in Supabase
- [ ] Create SQLAlchemy models
- [ ] Test model relationships

### Phase 2: Backend Services (4h)
- [ ] Implement BookingService.create_booking()
- [ ] Implement BookingService.update_booking_status()
- [ ] Implement PaymentService.create_razorpay_order()
- [ ] Implement PaymentService.verify_signature()
- [ ] Implement EmailService.send_confirmation()
- [ ] Implement RefundService.initiate_refund()

### Phase 3: API Endpoints (3h)
- [ ] POST /api/v1/bookings/create
- [ ] POST /api/v1/bookings/{id}/confirm-payment
- [ ] GET /api/v1/bookings/{id}
- [ ] GET /api/v1/bookings/my
- [ ] POST /api/v1/bookings/{id}/cancel
- [ ] POST /api/v1/bookings/{id}/review

### Phase 4: Webhook Handler (1.5h)
- [ ] POST /api/v1/webhooks/razorpay
- [ ] Signature verification
- [ ] Event handling (payment.authorized, payment.failed, refund.processed)
- [ ] Test with ngrok locally

### Phase 5: Frontend Integration (3h)
- [ ] Wire BookingFlowModal to create booking endpoint
- [ ] Wire BookingStep4_Payment to Razorpay
- [ ] Wire payment confirmation to redirect
- [ ] Update Dashboard/Bookings tab
- [ ] Add loading states + error handling

### Phase 6: Testing (2h)
- [ ] Unit tests for services
- [ ] Integration test: booking → payment → confirmation
- [ ] Manual test with Razorpay test keys
- [ ] Test refund flow
- [ ] Test email delivery

### Phase 7: Security & Optimization (1.5h)
- [ ] Signature verification
- [ ] Rate limiting on booking creation
- [ ] PCI compliance check
- [ ] Stripe/Razorpay webhook retry logic

---

## PART 8: SUCCESS CRITERIA

### MVP Success = Feature #1 Complete
- [ ] User can search → select route → enter passenger details → payment → get confirmation
- [ ] Booking appears in user dashboard
- [ ] User receives confirmation email
- [ ] Admin can see all bookings
- [ ] Payment webhook works (Razorpay → backend)
- [ ] Refund flow works
- [ ] Error handling for payment failures
- [ ] Performance: <2s booking creation, <1s payment confirmation

---

## PART 9: ROLLOUT PLAN

**Phase A: Internal Testing (Day 1)**
- Deploy to staging
- Test with Razorpay test keys
- Team walks through full flow

**Phase B: Beta Testers (Day 2)**
- Invite 10 beta users
- Test with real payment
- Gather feedback

**Phase C: Production (Day 3)**
- Deploy to production
- Use Razorpay live keys
- Monitor bookings, payments, errors
- Watch email delivery

**Phase D: Post-Launch (Week 1)**
- Analyze booking funnel (search → booking → payment)
- Fix any issues
- Optimize conversion

---

**Next Action:** Begin implementation. Start with database migrations and models.
