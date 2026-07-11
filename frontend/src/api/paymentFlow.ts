/**
 * Payment Flow API — Razorpay integration with Team 3 backend
 * Handles: Payment initiation, verification, and error recovery
 *
 * Integration Points:
 * - /v1/booking/payment/initiate → Create Razorpay order
 * - /v1/booking/payment/verify → Verify signature & update booking
 * - /v1/booking/payment/cancel → Cancel payment & release inventory
 */

import { v3Fetch } from "@/lib/apiClient";

// Payment initiation request/response
export interface InitiatePaymentRequest {
  booking_id: string;
}

export interface InitiatePaymentResponse {
  razorpay_key_id: string;
  razorpay_order_id: string;
  amount_paise: number; // Amount in paise (1 INR = 100 paise)
  currency: string;
  booking_id: string;
  status: "pending" | "initiated";
}

// Payment verification request/response
export interface VerifyPaymentRequest {
  booking_id: string;
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface VerifyPaymentResponse {
  status: "success" | "failed";
  booking_id: string;
  booking_status: "confirmed" | "payment_failed" | "payment_pending";
  payment_status: "completed" | "failed";
  message: string;
  pnr_number?: string;
  order_id?: string;
}

// Payment cancellation
export interface CancelPaymentRequest {
  booking_id: string;
  order_id: string;
  reason?: string;
}

export interface CancelPaymentResponse {
  status: "success" | "failed";
  booking_id: string;
  message: string;
}

// Error response
export interface PaymentErrorResponse {
  error: string;
  code: string;
  details?: Record<string, unknown>;
}

/**
 * Initiate payment - Create Razorpay order
 *
 * Flow:
 * 1. Calls /v1/booking/payment/initiate with booking_id
 * 2. Backend:
 *    - Acquires distributed lock
 *    - Runs fraud check
 *    - Creates Razorpay order
 *    - Stores order_id in Payment record
 *    - Transitions booking: PASSENGER_INFO → PAYMENT_PENDING
 *    - Logs audit: PAYMENT_INITIATED
 * 3. Returns order details for checkout
 */
export async function initiatePayment(
  bookingId: string
): Promise<InitiatePaymentResponse> {
  try {
    const response = await v3Fetch("/api/v1/booking/payment/initiate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ booking_id: bookingId }),
    });

    return response as InitiatePaymentResponse;
  } catch (error) {
    console.error("Payment initiation failed:", error);
    throw new Error(
      error instanceof Error
        ? error.message
        : "Failed to initiate payment. Please try again."
    );
  }
}

/**
 * Verify payment - Confirm Razorpay signature and update booking
 *
 * Flow:
 * 1. Calls /v1/booking/payment/verify with payment details
 * 2. Backend:
 *    - Verifies Razorpay signature (security)
 *    - Checks idempotency (prevent duplicate processing)
 *    - Acquires lock
 *    - Updates Payment: status = "success"
 *    - Updates Booking: payment_status = "completed", booking_status = "confirmed"
 *    - Transitions state: PAYMENT_PENDING → CONFIRMED
 *    - Issues ticket (async)
 *    - Logs audit: PAYMENT_VERIFIED
 *    - Publishes event: booking.confirmed
 * 3. Returns confirmation with booking details
 */
export async function verifyPayment(
  request: VerifyPaymentRequest
): Promise<VerifyPaymentResponse> {
  try {
    const response = await v3Fetch("/api/v1/booking/payment/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });

    return response as VerifyPaymentResponse;
  } catch (error) {
    console.error("Payment verification failed:", error);
    throw new Error(
      error instanceof Error
        ? error.message
        : "Payment verification failed. Please contact support."
    );
  }
}

/**
 * Cancel payment - Release inventory and handle payment cleanup
 *
 * Flow:
 * 1. Calls /v1/booking/payment/cancel with order_id
 * 2. Backend:
 *    - Looks up booking by order_id
 *    - Acquires lock
 *    - If payment pending: Cancel Razorpay order
 *    - Release seat inventory
 *    - Transition: PAYMENT_PENDING → CANCELLED
 *    - Log audit: PAYMENT_CANCELLED
 *    - Notify user
 * 3. Returns confirmation
 */
export async function cancelPayment(
  request: CancelPaymentRequest
): Promise<CancelPaymentResponse> {
  try {
    const response = await v3Fetch("/api/v1/booking/payment/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });

    return response as CancelPaymentResponse;
  } catch (error) {
    console.error("Payment cancellation failed:", error);
    throw new Error(
      error instanceof Error
        ? error.message
        : "Failed to cancel payment. Please try again."
    );
  }
}

/**
 * Get payment status - Check current payment state
 */
export async function getPaymentStatus(
  bookingId: string
): Promise<{ status: string; order_id?: string; payment_id?: string }> {
  try {
    const response = await v3Fetch(
      `/api/v1/booking/${encodeURIComponent(bookingId)}/payment-status`
    );
    return response;
  } catch (error) {
    console.error("Failed to fetch payment status:", error);
    throw error;
  }
}

/**
 * Handle payment timeout (user didn't complete within time limit)
 * Automatically cancels the payment after 15 minutes
 */
export function setupPaymentTimeout(
  bookingId: string,
  timeoutMs: number = 15 * 60 * 1000
): NodeJS.Timeout {
  return setTimeout(async () => {
    try {
      await cancelPayment({
        booking_id: bookingId,
        reason: "Payment timeout - not completed within time limit",
      });
    } catch (error) {
      console.warn("Failed to auto-cancel expired payment:", error);
    }
  }, timeoutMs);
}

/**
 * Error handler for payment operations
 */
export function handlePaymentError(error: unknown): string {
  if (error instanceof Error) {
    const message = error.message.toLowerCase();

    // Network errors
    if (message.includes("network") || message.includes("offline")) {
      return "Network error. Please check your connection and try again.";
    }

    // Verification failures
    if (message.includes("signature") || message.includes("verification")) {
      return "Payment verification failed. This payment has been cancelled.";
    }

    // Razorpay API errors
    if (message.includes("razorpay")) {
      return "Payment gateway error. Please try again later.";
    }

    // Insufficient funds
    if (message.includes("insufficient") || message.includes("declined")) {
      return "Payment was declined. Please try another payment method.";
    }

    // Fraud check blocks
    if (message.includes("fraud") || message.includes("flagged")) {
      return "This transaction has been flagged for review. Please contact support.";
    }

    return error.message;
  }

  return "An unexpected error occurred. Please try again.";
}

/**
 * Payment state machine - Track payment lifecycle
 */
export enum PaymentState {
  INITIATED = "initiated",
  PENDING = "pending",
  AUTHORIZED = "authorized",
  CAPTURED = "captured",
  FAILED = "failed",
  REFUNDED = "refunded",
  EXPIRED = "expired",
}

/**
 * Valid state transitions for payment
 */
export const PAYMENT_TRANSITIONS: Record<PaymentState, PaymentState[]> = {
  [PaymentState.INITIATED]: [
    PaymentState.PENDING,
    PaymentState.EXPIRED,
    PaymentState.FAILED,
  ],
  [PaymentState.PENDING]: [
    PaymentState.AUTHORIZED,
    PaymentState.FAILED,
    PaymentState.EXPIRED,
  ],
  [PaymentState.AUTHORIZED]: [
    PaymentState.CAPTURED,
    PaymentState.FAILED,
    PaymentState.REFUNDED,
  ],
  [PaymentState.CAPTURED]: [PaymentState.REFUNDED],
  [PaymentState.FAILED]: [],
  [PaymentState.REFUNDED]: [],
  [PaymentState.EXPIRED]: [],
};

/**
 * Validate payment state transition
 */
export function isValidPaymentTransition(
  from: PaymentState,
  to: PaymentState
): boolean {
  return PAYMENT_TRANSITIONS[from]?.includes(to) ?? false;
}
