/**
 * Bookings feature – re-exports for feature-based structure.
 */

export { useBookingFlow } from "@/hooks/useBookingFlow";
export { PaymentModal } from "@/components/PaymentModal";
export {
  createPaymentOrder,
  verifyPayment,
  checkPaymentStatus,
  createBookingRedirect,
  getBookingHistory,
  openRazorpayCheckout,
} from "@/lib/paymentApi";
export { useBookings, BOOKINGS_QUERY_KEY } from "@/api/hooks/useBookings";
export { bookingRedirectSchema, createOrderSchema } from "@/lib/schemas/bookingSchema";
