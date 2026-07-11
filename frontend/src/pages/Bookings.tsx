/**
 * My Bookings – protected page showing booking history with integrated payment flow.
 * Features:
 * - Payment initiation (Razorpay integration)
 * - Real-time status updates
 * - Error handling & recovery
 * - Mobile-friendly design
 */

import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useBookings } from "@/api/hooks/useBookings";
import { getAllTickets } from "@/lib/ticketStore";
import { HistorySkeleton } from "@/components/skeletons";
import { Ticket, AlertCircle, ChevronLeft, ChevronRight, Hash, ShieldCheck, Clock, CreditCard, CheckCircle, AlertTriangle, Loader } from "lucide-react";
import { Button } from "@/components/ui/button";
import { type Booking, getSegmentPnrs, type SegmentPNR } from "@/api/booking";
import { cn } from "@/lib/utils";
import { initiatePayment, verifyPayment, cancelPayment } from "@/api/paymentFlow";
import { useToast } from "@/hooks/use-toast";

function SegmentPNRList({ journeyId }: { journeyId: string }) {
  const [pnrs, setPnrs] = useState<SegmentPNR[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function fetchPnrs() {
      setLoading(true);
      try {
        const data = await getSegmentPnrs(journeyId);
        setPnrs(data);
      } catch (err) {
        console.error("Failed to fetch segment PNRs", err);
      } finally {
        setLoading(false);
      }
    }
    if (journeyId) fetchPnrs();
  }, [journeyId]);

  if (loading) return <div className="mt-2 h-4 w-24 bg-muted animate-pulse rounded" />;
  if (pnrs.length === 0) return null;

  return (
    <div className="mt-4 pt-4 border-t border-border/50">
      <h4 className="text-[10px] font-black uppercase tracking-widest text-muted-foreground mb-2 flex items-center gap-1">
        <ShieldCheck size={10} className="text-primary" /> Segment PNR Tracking
      </h4>
      <div className="flex flex-wrap gap-2">
        {pnrs.map((p) => (
          <div key={p.id} className="bg-primary/5 border border-primary/10 rounded-lg px-3 py-2 flex flex-col gap-0.5">
            <span className="text-[10px] font-bold text-muted-foreground">Train {p.train_number}</span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-black text-primary">{p.pnr}</span>
              <BadgeCheck size={12} className="text-emerald-500" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const BadgeCheck = ({ className, size }: { className?: string; size?: number }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size || 16}
    height={size || 16}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="3"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
    <path d="m9 12 2 2 4-4" />
  </svg>
);

// Payment Modal Component
interface PaymentModalProps {
  isOpen: boolean;
  booking: Booking | null;
  isLoading: boolean;
  error: string | null;
  onClose: () => void;
  onSuccess: () => void;
}

function PaymentModal({ isOpen, booking, isLoading, error, onClose, onSuccess }: PaymentModalProps) {
  const [paymentInitiated, setPaymentInitiated] = useState(false);
  const [orderId, setOrderId] = useState<string | null>(null);
  const [amountPaise, setAmountPaise] = useState<number | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setPaymentInitiated(false);
      setOrderId(null);
      setAmountPaise(null);
    }
  }, [isOpen]);

  const handleInitiatePayment = async () => {
    if (!booking?.id) return;

    try {
      setPaymentInitiated(true);
      const response = await initiatePayment(booking.id);

      if (response.razorpay_order_id && response.amount_paise) {
        setOrderId(response.razorpay_order_id);
        setAmountPaise(response.amount_paise);

        // Load Razorpay script and open checkout
        openRazorpayCheckout(response);
      }
    } catch (err) {
      console.error("Payment initiation failed:", err);
      setPaymentInitiated(false);
    }
  };

  const openRazorpayCheckout = (response: any) => {
    // Load Razorpay script if not already loaded
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => {
      if ((window as any).Razorpay) {
        const razorpay = new (window as any).Razorpay({
          key: response.razorpay_key_id,
          order_id: response.razorpay_order_id,
          amount: response.amount_paise,
          currency: "INR",
          name: "Route Master",
          description: `Booking #${booking?.pnr_number || booking?.id.slice(0, 8)}`,
          handler: async (paymentResponse: any) => {
            await handlePaymentSuccess(paymentResponse);
          },
          prefill: {
            email: (window as any).__authEmail || "",
            contact: (window as any).__authPhone || "",
          },
          theme: {
            color: "#1f2937",
          },
          modal: {
            ondismiss: () => {
              setPaymentInitiated(false);
            },
          },
        });
        razorpay.open();
      }
    };
    document.body.appendChild(script);
  };

  const handlePaymentSuccess = async (paymentResponse: any) => {
    if (!booking?.id || !orderId) return;

    try {
      const verifyResponse = await verifyPayment({
        booking_id: booking.id,
        razorpay_order_id: orderId,
        razorpay_payment_id: paymentResponse.razorpay_payment_id,
        razorpay_signature: paymentResponse.razorpay_signature,
      });

      if (verifyResponse.status === "success") {
        setPaymentInitiated(false);
        onSuccess();
      } else {
        throw new Error(verifyResponse.message || "Payment verification failed");
      }
    } catch (err) {
      console.error("Payment verification failed:", err);
      setPaymentInitiated(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg max-w-md w-full p-6 shadow-xl">
        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
          <CreditCard className="w-5 h-5" />
          Complete Payment
        </h3>

        {booking && (
          <div className="mb-6 p-4 bg-muted/50 rounded-lg">
            <div className="flex justify-between mb-2">
              <span className="text-sm text-muted-foreground">PNR:</span>
              <span className="font-mono font-bold">{booking.pnr_number || booking.id.slice(0, 8)}</span>
            </div>
            <div className="flex justify-between items-baseline">
              <span className="text-sm text-muted-foreground">Amount:</span>
              <span className="text-xl font-bold text-green-600">₹{(booking.amount_paid || 0).toFixed(2)}</span>
            </div>
          </div>
        )}

        {error && (
          <div className="mb-4 p-3 bg-destructive/10 text-destructive text-sm rounded-lg flex gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>{error}</div>
          </div>
        )}

        <div className="space-y-3">
          <Button
            onClick={handleInitiatePayment}
            disabled={isLoading || paymentInitiated}
            className="w-full"
            size="lg"
          >
            {paymentInitiated ? (
              <>
                <Loader className="w-4 h-4 mr-2 animate-spin" />
                Opening Payment Gateway...
              </>
            ) : (
              <>
                <CreditCard className="w-4 h-4 mr-2" />
                Pay Now with Razorpay
              </>
            )}
          </Button>

          <Button
            onClick={onClose}
            variant="outline"
            className="w-full"
            disabled={paymentInitiated}
          >
            Cancel
          </Button>
        </div>

        <p className="text-xs text-muted-foreground text-center mt-4">
          Powered by Razorpay. Your payment is secured with 256-bit encryption.
        </p>
      </div>
    </div>
  );
}

// Payment Confirmation Component
interface PaymentConfirmationProps {
  isOpen: boolean;
  status: "success" | "error" | null;
  message: string;
  onClose: () => void;
}

function PaymentConfirmation({ isOpen, status, message, onClose }: PaymentConfirmationProps) {
  if (!isOpen || !status) return null;

  const isSuccess = status === "success";

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg max-w-sm w-full p-6 shadow-xl text-center">
        {isSuccess ? (
          <>
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h3 className="text-lg font-bold mb-2">Payment Successful!</h3>
          </>
        ) : (
          <>
            <AlertTriangle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h3 className="text-lg font-bold mb-2">Payment Failed</h3>
          </>
        )}

        <p className="text-sm text-muted-foreground mb-6">{message}</p>

        <Button onClick={onClose} className="w-full">
          {isSuccess ? "View Booking" : "Try Again"}
        </Button>
      </div>
    </div>
  );
}

function BookingsContent() {
  const [page, setPage] = useState(0);
  const limit = 20;
  const { data: bookingsData, isLoading: loading, error: queryError, refetch } = useBookings({ skip: page * limit, limit });
  const { toast } = useToast();

  // Handle various response shapes from useBookings hook
  const bookings: Booking[] = Array.isArray(bookingsData)
    ? bookingsData
    : (bookingsData as any)?.bookings || [];

  const error = queryError ? (queryError instanceof Error ? queryError.message : "Failed to load bookings") : null;
  const localTickets = getAllTickets();

  // Payment flow state
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [selectedBooking, setSelectedBooking] = useState<Booking | null>(null);
  const [paymentLoading, setPaymentLoading] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [paymentConfirmation, setPaymentConfirmation] = useState<{
    isOpen: boolean;
    status: "success" | "error" | null;
    message: string;
  }>({
    isOpen: false,
    status: null,
    message: "",
  });

  const handleOpenPayment = (booking: Booking) => {
    if (booking.payment_status === "completed") {
      toast({
        title: "Already Paid",
        description: "This booking has already been paid.",
        variant: "default",
      });
      return;
    }

    setSelectedBooking(booking);
    setPaymentError(null);
    setShowPaymentModal(true);
  };

  const handlePaymentSuccess = () => {
    setShowPaymentModal(false);
    setPaymentConfirmation({
      isOpen: true,
      status: "success",
      message: "Your booking is now confirmed. You will receive a ticket shortly.",
    });
    // Refresh bookings list
    setTimeout(() => {
      refetch();
    }, 1500);
  };

  const handlePaymentFailure = (errorMsg: string) => {
    setPaymentError(errorMsg);
    setPaymentConfirmation({
      isOpen: true,
      status: "error",
      message: errorMsg || "Payment could not be processed. Please try again.",
    });
  };

  const closePaymentModal = () => {
    setShowPaymentModal(false);
    setSelectedBooking(null);
    setPaymentError(null);
  };

  const closeConfirmation = () => {
    setPaymentConfirmation({
      isOpen: false,
      status: null,
      message: "",
    });
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="container mx-auto px-4 py-8 flex-1">
        <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
          <Ticket className="w-7 h-7" />
          My Bookings
        </h1>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-destructive/10 text-destructive flex items-center gap-2">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span>{error}</span>
            <button
              type="button"
              onClick={() => refetch()}
              className="ml-auto text-sm underline hover:no-underline"
            >
              Retry
            </button>
          </div>
        )}

        {localTickets.length > 0 && (
          <section className="mb-8">
            <h2 className="text-lg font-semibold text-foreground mb-3">Recent tickets (this device)</h2>
            <p className="text-sm text-muted-foreground mb-3">
              Open or share your ticket anytime. Stored on this device.
            </p>
            <ul className="space-y-3">
              {localTickets.slice(0, 10).map((t) => (
                <li key={t.id}>
                  <Link
                    to={`/ticket/${encodeURIComponent(t.id)}`}
                    className="block rounded-xl border border-border p-4 bg-card hover:border-primary/40 transition-colors"
                  >
                    <div className="flex flex-wrap justify-between gap-2">
                      <span className="font-medium">{t.originName} → {t.destName}</span>
                      <span className="text-sm text-muted-foreground">
                        {t.travelDate ? new Date(t.travelDate + "T12:00:00").toLocaleDateString("en-IN") : "—"}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 font-mono">{t.reference}</p>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        <h2 className="text-lg font-semibold text-foreground mb-3">Booking history</h2>
        {loading ? (
          <HistorySkeleton count={5} />
        ) : bookings.length === 0 ? (
          <div className="rounded-xl border border-border bg-muted/30 p-6 text-center text-muted-foreground">
            <p className="font-medium">No server bookings yet</p>
            <p className="text-sm mt-1">Bookings from this account will appear here.</p>
            <a href="/" className="inline-block mt-3 text-primary hover:underline">Search routes →</a>
          </div>
        ) : (
          <>
            <ul className="space-y-4">
              {bookings.map((b: Booking) => (
                <li
                  key={b.id || b.pnr_number || Math.random()}
                  className="rounded-xl border border-border p-5 bg-card hover:border-primary/40 transition-all hover:shadow-md"
                >
                  <div className="flex flex-wrap justify-between gap-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-bold text-lg">
                          {(b.booking_details as any)?.origin || (b.booking_details as any)?.source || "Unknown"} → {(b.booking_details as any)?.destination || (b.booking_details as any)?.dest || "Unknown"}
                        </span>
                        {b.booking_status && (
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-black uppercase tracking-tighter ${
                            b.booking_status === "confirmed" ? "bg-green-100 text-green-800" :
                            b.booking_status === "ticket_sent" ? "bg-blue-100 text-blue-800 border border-blue-200" :
                            b.booking_status === "pending_manual" ? "bg-purple-100 text-purple-800 animate-pulse" :
                            b.booking_status === "pending" ? "bg-yellow-100 text-yellow-800" :
                            b.booking_status === "cancelled" ? "bg-red-100 text-red-800" :
                            "bg-gray-100 text-gray-800"
                          }`}>
                            {b.booking_status.replace('_', ' ')}
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1.5"><Clock size={14}/> {b.travel_date ? new Date(b.travel_date + "T12:00:00").toLocaleDateString("en-IN", { dateStyle: 'medium' }) : "—"}</span>
                        {b.pnr_number && <span className="font-mono bg-secondary/50 px-1.5 py-0.5 rounded text-foreground font-bold">PNR: {b.pnr_number}</span>}
                        {b.amount_paid > 0 && <span>Amount: ₹{b.amount_paid.toFixed(2)}</span>}
                      </div>
                      
                      {/* Integrated Segment PNR Tracking */}
                      {b.id && <SegmentPNRList journeyId={b.id} />}
                      
                      {b.created_at && (
                        <p className="text-[10px] text-muted-foreground mt-3 font-medium uppercase tracking-widest opacity-60">
                          Transaction ID: {b.id.slice(0, 12).toUpperCase()} • {new Date(b.created_at).toLocaleString("en-IN")}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-col gap-2">
                      {b.payment_status !== "completed" && b.booking_status === "pending" ? (
                        <Button
                          onClick={() => handleOpenPayment(b)}
                          className="w-full sm:w-auto"
                          size="sm"
                          disabled={paymentLoading}
                        >
                          <CreditCard className="w-4 h-4 mr-2" />
                          Pay Now
                        </Button>
                      ) : b.pnr_number ? (
                        <Link
                          to={`/ticket/${encodeURIComponent(b.pnr_number)}`}
                          className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-bold hover:opacity-90 transition-opacity"
                        >
                          View Ticket
                        </Link>
                      ) : null}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            {/* Pagination */}
            {bookings.length >= limit && (
              <div className="flex items-center justify-between mt-6 pt-4 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Page {page + 1}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={bookings.length < limit}
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            )}
          </>
        )}
      </main>
      <Footer />

      {/* Payment Modal */}
      <PaymentModal
        isOpen={showPaymentModal}
        booking={selectedBooking}
        isLoading={paymentLoading}
        error={paymentError}
        onClose={closePaymentModal}
        onSuccess={handlePaymentSuccess}
      />

      {/* Payment Confirmation */}
      <PaymentConfirmation
        isOpen={paymentConfirmation.isOpen}
        status={paymentConfirmation.status}
        message={paymentConfirmation.message}
        onClose={closeConfirmation}
      />
    </div>
  );
}

export default function Bookings() {
  return (
    <ProtectedRoute>
      <BookingsContent />
    </ProtectedRoute>
  );
}
