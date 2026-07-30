# Payment Flow Integration Guide

## Overview

This directory contains the payment integration with Razorpay via Team 3's backend API.

## Files

### `paymentFlow.ts`
Core payment API functions for:
- Initiating payments (creating Razorpay orders)
- Verifying payments (signature verification)
- Cancelling payments
- Checking payment status
- Error handling

### `payment.ts` (Legacy)
Legacy payment functions - kept for backward compatibility. New code should use `paymentFlow.ts`.

## Usage Example

```typescript
// In a React component (e.g., Bookings.tsx)
import { initiatePayment, verifyPayment } from "@/api/paymentFlow";

// Step 1: Initiate payment
const handlePay = async (bookingId: string) => {
  const response = await initiatePayment(bookingId);
  // response: {
  //   razorpay_key_id: "rzp_live_...",
  //   razorpay_order_id: "order_...",
  //   amount_paise: 50000,
  //   ...
  // }
  
  // Open Razorpay checkout with response.razorpay_order_id
  openRazorpayCheckout(response);
};

// Step 2: After user completes payment, verify signature
const handlePaymentSuccess = async (paymentResponse) => {
  const verify = await verifyPayment({
    booking_id: bookingId,
    razorpay_order_id: response.razorpay_order_id,
    razorpay_payment_id: paymentResponse.razorpay_payment_id,
    razorpay_signature: paymentResponse.razorpay_signature,
  });
  // verify: { status: "success", booking_status: "confirmed", ... }
};
```

## API Flow Diagram

```
Frontend                          Backend (Team 3)
├─ User clicks "Pay Now"
├─ initiatePayment(bookingId)
│  └─ POST /api/v1/booking/payment/initiate
│     ├─ Check distributed lock
│     ├─ Run fraud check
│     ├─ Create Razorpay order
│     └─ Return: { razorpay_order_id, amount_paise, ... }
│
├─ Open Razorpay checkout (browser)
│  └─ User enters card/UPI details
│  └─ Razorpay processes payment
│
├─ User completes payment
│  └─ Razorpay returns: { razorpay_payment_id, razorpay_signature }
│
├─ verifyPayment(...)
│  └─ POST /api/v1/booking/payment/verify
│     ├─ Verify Razorpay signature (security)
│     ├─ Check idempotency
│     ├─ Update booking: PAYMENT_PENDING → CONFIRMED
│     ├─ Log audit trail
│     └─ Return: { status: "success", ... }
│
└─ Show confirmation modal
   └─ Refresh bookings list
```

## Error Handling

All errors are converted to user-friendly messages:

```typescript
import { handlePaymentError } from "@/api/paymentFlow";

try {
  await initiatePayment(bookingId);
} catch (error) {
  const message = handlePaymentError(error);
  // message: "Network error. Please check your connection..."
  toast.error(message);
}
```

## Testing with Razorpay Test Cards

In Razorpay test mode, use these test cards:

| Card | Number | Status |
|------|--------|--------|
| Success | 4111111111111111 | Payment succeeds |
| Decline | 4000000000000002 | Payment fails |

Expiry: Any future date  
CVV: Any 3-4 digits

## Environment Variables

No frontend env vars needed. Backend provides Razorpay key in API response.

## Related Components

- **`/pages/Bookings.tsx`** - Main payment UI integration
- **`/components/PaymentStatusBadge.tsx`** - Visual status display
- **`/hooks/useBookings.ts`** - Fetch bookings with React Query

## Backend Integration Checklist

- [ ] `/api/v1/booking/payment/initiate` endpoint implemented
- [ ] `/api/v1/booking/payment/verify` endpoint implemented
- [ ] Razorpay order creation in backend
- [ ] Signature verification working
- [ ] Idempotency checks implemented
- [ ] Booking state machine updated
- [ ] Audit logging in place
- [ ] Distributed lock acquired
- [ ] Fraud check running
- [ ] Webhook handler for async confirmation

## Debugging

Enable debug logging in browser console:

```typescript
// In Bookings.tsx or any component
window.__paymentDebug = true;

// Then in paymentFlow.ts (add this)
if (window.__paymentDebug) {
  console.log("Payment API:", { request, response });
}
```

## Performance Notes

- Payment initiation: ~500ms (includes Razorpay API call)
- Payment verification: ~1-2s (includes database write)
- Razorpay checkout load: ~1-2s (CDN script)
- Total flow: ~3-5 seconds for user completion

## Security

- All payment data transferred via HTTPS
- Razorpay handles PCI compliance
- Frontend never sees full card numbers
- Signature verification prevents tampering
- Idempotency prevents duplicate charges

## Support

For issues:
1. Check browser console for errors
2. Review API responses in Network tab
3. Check backend logs for payment failures
4. Contact Team 3 for backend issues
