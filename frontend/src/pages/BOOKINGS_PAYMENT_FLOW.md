# Bookings Page - Payment Flow Architecture

## Page Structure

```
Bookings Page (/bookings)
├── Navbar
├── Main Content
│   ├── Header "My Bookings"
│   ├── Error Alert (if any)
│   ├── Recent Tickets Section (local storage)
│   ├── Booking History Section
│   │   ├── Booking Card #1
│   │   │   ├── Trip info: "A → B"
│   │   │   ├── Status badge
│   │   │   ├── Date, PNR, Amount
│   │   │   └── [Action Button]
│   │   │       ├── "Pay Now" (if payment_status: pending)
│   │   │       └── "View Ticket" (if payment_status: completed)
│   │   ├── Booking Card #2
│   │   └── ...
│   └── Pagination Controls
├── PaymentModal (if showPaymentModal)
│   ├── Amount display
│   ├── [Pay Now with Razorpay] button
│   └── [Cancel] button
├── PaymentConfirmation (if confirmation open)
│   ├── Success state: ✅ "Payment Successful!"
│   └── Error state: ❌ "Payment Failed"
└── Footer
```

## User Interaction Flow

```
┌─────────────────────────────────────────────────────────────┐
│ USER SEES: "My Bookings" page with list                     │
│            Booking: Delhi → Mumbai (Pending) - ₹5000        │
│            [Pay Now] button visible                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
                    USER CLICKS "PAY NOW"
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ PaymentModal Opens                                           │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Complete Payment                                        │ │
│ │ PNR: ABC123456          Amount: ₹5,000                 │ │
│ │ [Pay Now with Razorpay]      [Cancel]                  │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓
                USER CLICKS "PAY NOW"
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Frontend Action:                                            │
│  1. setPaymentInitiated(true)                               │
│  2. Call: initiatePayment(bookingId)                        │
│     POST /api/v1/booking/payment/initiate                   │
└─────────────────────────────────────────────────────────────┘
                           ↓ (API call)
┌─────────────────────────────────────────────────────────────┐
│ Backend (Team 3):                                           │
│  1. Acquire distributed lock                               │
│  2. Run fraud check                                        │
│  3. Create Razorpay order                                  │
│  4. Store razorpay_order_id                                │
│  5. Transition: PASSENGER_INFO → PAYMENT_PENDING           │
│  6. Log audit: PAYMENT_INITIATED                           │
│  Response: {                                               │
│    razorpay_order_id: "order_...",                         │
│    razorpay_key_id: "rzp_live_...",                        │
│    amount_paise: 500000                                    │
│  }                                                         │
└─────────────────────────────────────────────────────────────┘
                           ↓ (Response)
┌─────────────────────────────────────────────────────────────┐
│ Frontend Action:                                            │
│  1. Load Razorpay script from CDN                           │
│  2. Initialize Razorpay checkout with order_id             │
│  3. Call razorpay.open()                                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ USER SEES: Razorpay Checkout Modal                          │
│            "Complete your payment"                         │
│            Payment options: Card, UPI, NetBanking         │
│                                                            │
│ USER ENTERS: Payment details                               │
│  - Card number or UPI ID                                   │
│  - OTP/Password                                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
                 RAZORPAY PROCESSES PAYMENT
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ PAYMENT SUCCESS                                             │
│                                                            │
│ Razorpay Returns:                                          │
│  {                                                         │
│    razorpay_payment_id: "pay_...",                         │
│    razorpay_signature: "sig_..."                           │
│  }                                                         │
│                                                            │
│ Frontend handler: async (paymentResponse) => {             │
│   Call: verifyPayment(...)                                 │
│   POST /api/v1/booking/payment/verify                      │
│ }                                                          │
└─────────────────────────────────────────────────────────────┘
                           ↓ (API call)
┌─────────────────────────────────────────────────────────────┐
│ Backend (Team 3):                                           │
│  1. Verify Razorpay signature (security critical)          │
│  2. Check idempotency (prevent duplicate)                  │
│  3. Acquire lock                                           │
│  4. Update Payment: status = "success"                     │
│  5. Update Booking:                                        │
│     - payment_status: "completed"                          │
│     - booking_status: "confirmed"                          │
│  6. Transition: PAYMENT_PENDING → CONFIRMED                │
│  7. Issue ticket (async)                                   │
│  8. Log audit: PAYMENT_VERIFIED                            │
│  Response: {                                               │
│    status: "success",                                      │
│    booking_status: "confirmed",                            │
│    payment_status: "completed",                            │
│    pnr_number: "1234567890"                                │
│  }                                                         │
└─────────────────────────────────────────────────────────────┘
                           ↓ (Response)
┌─────────────────────────────────────────────────────────────┐
│ PaymentModal Closes                                        │
│ PaymentConfirmation Opens:                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ✅ Payment Successful!                                  │ │
│ │ Your booking is now confirmed.                         │ │
│ │ You will receive a ticket shortly.                     │ │
│ │ [View Booking]                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓ (auto 1.5s delay)
┌─────────────────────────────────────────────────────────────┐
│ Frontend Action:                                            │
│  1. Refresh bookings list: refetch()                        │
│  2. Close confirmation modal                               │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ USER SEES: "My Bookings" page                              │
│            Booking: Delhi → Mumbai (CONFIRMED) - ₹5000     │
│            PNR: 1234567890                                 │
│            [View Ticket] button (instead of Pay Now)       │
└─────────────────────────────────────────────────────────────┘
```

## Component State Diagram

```
BookingsContent
├── State: page, bookings, loading, error
├── State: showPaymentModal (false → true → false)
├── State: selectedBooking (null → Booking → null)
├── State: paymentLoading (false → true → false)
├── State: paymentError (null → "error" → null)
└── State: paymentConfirmation
    ├── isOpen: false → true → false
    ├── status: null → "success"/"error" → null
    └── message: "" → "message" → ""

PaymentModal (when showPaymentModal = true)
├── Props: isOpen, booking, isLoading, error
├── State: paymentInitiated (false → true → false)
├── State: orderId (null → "order_..." → null)
└── State: amountPaise (null → number → null)

PaymentConfirmation (when paymentConfirmation.isOpen = true)
├── Props: isOpen, status, message
└── Renders: success or error UI
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────┐
│ initiatePayment() FAILS                                 │
│  └─ Razorpay API error                                  │
│  └─ Network timeout                                     │
│  └─ Database error                                      │
│  └─ Lock acquisition timeout                            │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ Frontend catch block:                                   │
│  1. setPaymentInitiated(false)                          │
│  2. setPaymentError(userFriendlyMessage)               │
│  3. Show error in PaymentModal                          │
│  4. User can retry or cancel                            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ verifyPayment() FAILS                                   │
│  └─ Invalid signature                                   │
│  └─ Duplicate payment (already verified)               │
│  └─ Database error                                      │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ Frontend catch block:                                   │
│  1. setPaymentInitiated(false)                          │
│  2. Show PaymentConfirmation with status: "error"      │
│  3. User clicks "Try Again" → restart flow             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ RAZORPAY PAYMENT FAILS (user declined, etc)            │
│  └─ Payment declined                                    │
│  └─ Timeout                                             │
│  └─ User cancels                                        │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ Razorpay triggers ondismiss callback:                   │
│  1. setPaymentInitiated(false)                          │
│  2. Modal shows error state                             │
│  3. User can close and try another booking             │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

```
User Input (click "Pay Now")
         ↓
  React State Update
  ├─ showPaymentModal: true
  ├─ selectedBooking: booking
  └─ paymentError: null
         ↓
  Component Re-render (PaymentModal visible)
         ↓
  User Input (click "Pay Now with Razorpay")
         ↓
  initiatePayment(bookingId)
         ↓
  API Request
         ↓
  Backend Processing
         ↓
  API Response
         ↓
  React State Update
  ├─ paymentInitiated: true
  ├─ orderId: "order_..."
  ├─ amountPaise: 500000
  └─ paymentError: null
         ↓
  Razorpay Script Load
         ↓
  Razorpay Checkout Open
         ↓
  User Completes Payment
         ↓
  Razorpay Callback Handler
         ↓
  verifyPayment(...)
         ↓
  API Request
         ↓
  Backend Processing
         ↓
  API Response
         ↓
  React State Update
  ├─ showPaymentModal: false
  ├─ paymentConfirmation: {isOpen: true, status: "success"}
  └─ Trigger refetch() after 1.5s
         ↓
  Component Re-render (Confirmation modal visible)
         ↓
  Bookings List Refreshed
         ↓
  User Sees Updated Status
```

## Mobile Responsiveness

```
Desktop (1024px+)
├─ PaymentModal: max-width 448px (md)
├─ Buttons: w-auto inline
└─ Padding: p-6

Tablet (640px - 1023px)
├─ PaymentModal: max-width 400px
├─ Buttons: w-auto
└─ Padding: p-4

Mobile (375px - 639px)
├─ PaymentModal: w-full p-4
├─ Buttons: w-full (full width)
└─ Padding: p-4
└─ Text: text-sm for readability
```

## Loading States

```
Loading Scenarios:
1. Initial bookings load
   ├─ HistorySkeleton shown
   └─ Once loaded: real bookings

2. Payment initiation
   ├─ Button: [Loader] Opening Payment Gateway...
   └─ Once response: Razorpay opens

3. Payment verification
   ├─ Modal: Loading state
   └─ Once response: Confirmation shown

4. Bookings refresh after payment
   ├─ Bookings list refreshes in background
   ├─ React Query handles caching
   └─ New status displayed
```

## Key Implementation Details

### PaymentModal Component

**Responsibilities:**
1. Display booking amount & PNR
2. Handle "Pay Now" click
3. Load Razorpay script dynamically
4. Initialize Razorpay checkout
5. Pass payment response to handler
6. Show loading & error states
7. Prevent duplicate submissions

**Key Code:**
```typescript
// Load Razorpay and open checkout
const openRazorpayCheckout = (response: any) => {
  const script = document.createElement("script");
  script.src = "https://checkout.razorpay.com/v1/checkout.js";
  script.onload = () => {
    const razorpay = new (window as any).Razorpay({
      key: response.razorpay_key_id,
      order_id: response.razorpay_order_id,
      amount: response.amount_paise,
      handler: async (paymentResponse) => {
        await handlePaymentSuccess(paymentResponse);
      },
    });
    razorpay.open();
  };
  document.body.appendChild(script);
};
```

### PaymentConfirmation Component

**Responsibilities:**
1. Show success/error state
2. Display user-friendly message
3. Provide next action button
4. Auto-close or require user action

**States:**
```
Success: ✅ Green UI, "View Booking" button
Error:   ❌ Red UI, "Try Again" button
```

### BookingsContent Logic

**On "Pay Now" click:**
```typescript
const handleOpenPayment = (booking: Booking) => {
  // Guard: don't reopen if already paid
  if (booking.payment_status === "completed") {
    toast({ title: "Already Paid" });
    return;
  }

  // Set state
  setSelectedBooking(booking);
  setPaymentError(null);
  setShowPaymentModal(true);
};
```

**On payment success:**
```typescript
const handlePaymentSuccess = () => {
  // Close modal
  setShowPaymentModal(false);

  // Show confirmation
  setPaymentConfirmation({
    isOpen: true,
    status: "success",
    message: "Your booking is now confirmed...",
  });

  // Refresh after 1.5s delay
  setTimeout(() => {
    refetch();
  }, 1500);
};
```

---

**This document describes the complete payment flow implementation in the Bookings page.**  
**For API details, see `/frontend/src/api/README_PAYMENT_INTEGRATION.md`**  
**For integration specs, see `/TEAM_4_PAYMENT_INTEGRATION.md`**
