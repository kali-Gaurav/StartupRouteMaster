/**
 * Inline payment step for the booking flow.
 * Uses same APIs as PaymentModal: createPaymentOrder, openRazorpayCheckout, verifyPayment, createBookingRedirect.
 */

import { useState, useEffect } from "react";
import { Loader2, IndianRupee, CheckCircle2, ShieldCheck, Clock, Zap } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useBookingFlowContext } from "@/context/BookingFlowContext";
import {
  createPaymentOrder,
  verifyPayment,
  consumeRedirectToken,
  openRazorpayCheckout,
  checkPaymentStatus,
  createBookingRedirect,
} from "@/lib/paymentApi";
import { invalidateBookingsCache } from "@/lib/queryInvalidation";
import { logEvent } from "@/lib/observability";
import { Button } from "@/components/ui/button";
import { BookingStepSkeleton } from "@/components/skeletons";

const UNLOCK_PRICE = 39; // Price for unlocking route details

export function BookingPaymentStep() {
  const { user, token } = useAuth();
  const {
    route,
    travelDate,
    originName,
    destName,
    setPaymentSuccess,
    setUnlockSuccess, // New: from context
    setError,
    goToStep,
    isUnlockFlow, // New: from context
  } = useBookingFlowContext();

  const [checking, setChecking] = useState(true);
  const [alreadyPaid, setAlreadyPaid] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setLocalError] = useState("");

  const routeOrigin = route?.segments[0]?.from ?? "";
  const routeDest = route?.segments[route.segments.length - 1]?.to ?? "";
  const trainNo = route?.segments[0]?.trainNumber ?? "";

  const paymentAmount = isUnlockFlow ? UNLOCK_PRICE : 49; // Use UNLOCK_PRICE for unlock flow

  useEffect(() => {
    if (isUnlockFlow) {
      // For unlock flow, we assume it's a new payment each time, no "already paid" check for now.
      setChecking(false);
      return;
    }

    if (token && route?.id && travelDate) {
      checkPaymentStatus(route.id, travelDate)
        .then((res) => res?.already_paid_booking && setAlreadyPaid(true)) // Use already_paid_booking from new API
        .catch(() => {})
        .finally(() => setChecking(false));
    } else {
      setChecking(false);
    }
  }, [token, route?.id, travelDate, isUnlockFlow]);

  const handlePayment = async () => {
    if (!token || !user || !route) {
      setLocalError("Please sign in to continue or route information is missing.");
      setError("Please sign in to continue or route information is missing.");
      return;
    }

    if (!route?.id) {
      setLocalError("Route information missing.");
      setError("Route information missing.");
      return;
    }

    setLocalError("");
    setError(null);
    setLoading(true);

    try {
      const createOrderData = isUnlockFlow
        ? { route_id: route.id, travel_date: travelDate, is_unlock_payment: true }
        : {
            route_id: route.id, // Ensure route_id is always sent
            route_origin: routeOrigin,
            route_destination: routeDest,
            train_no: trainNo,
            travel_date: travelDate,
            is_unlock_payment: false,
          };

      const orderResponse = await createPaymentOrder(createOrderData);

      if (!orderResponse.success) {
        throw new Error(orderResponse.message || "Failed to create order");
      }
      if (orderResponse.already_paid && !isUnlockFlow) { // Only check for already_paid for booking flow
        setAlreadyPaid(true);
        setLoading(false);
        return;
      }

      const order = orderResponse.order; // This order object needs to contain key_id, amount, currency, order_id (razorpay)
      const internalPaymentId = orderResponse.payment_id; // Our internal payment ID

      openRazorpayCheckout(
        order,
        user,
        async (paymentResponse: any) => {
          try {
            const verifyResponse = await verifyPayment({
              payment_id: internalPaymentId, // Our internal payment ID
              razorpay_order_id: paymentResponse.razorpay_order_id,
              razorpay_payment_id: paymentResponse.razorpay_payment_id,
              razorpay_signature: paymentResponse.razorpay_signature,
            });

            if (!verifyResponse.success) {
              throw new Error("Verification failed");
            }

            if (isUnlockFlow) {
              setUnlockSuccess(route.id);
            } else {
              const redirectToken = verifyResponse.redirect_token; // Assume redirect_token is returned for booking flow
              if (redirectToken) {
                const consumeResponse = await consumeRedirectToken(redirectToken);
                if (!consumeResponse?.success || !consumeResponse?.order) {
                  throw new Error("Payment confirmation invalid. Please contact support.");
                }
              }
              const redirectResponse = await createBookingRedirect({
                payment_order_id: internalPaymentId, // Use internal payment ID here
                origin: routeOrigin,
                destination: routeDest,
                train_no: trainNo,
                travel_date: travelDate,
                travel_class: "SL",
              });
              await invalidateBookingsCache();
              const url = redirectResponse?.irctc_url ?? null;
              setPaymentSuccess(internalPaymentId, url); // Use internalPaymentId as orderId
            }
          } catch (err: any) {
            const msg = err.message || "Payment verification failed";
            setLocalError(msg);
            setError(msg);
            logEvent("payment_failed", { phase: "verify", isUnlockFlow }, "error");
          } finally {
            setLoading(false);
          }
        },
        (err: any) => {
          const msg = err.message || "Payment failed";
          setLocalError(msg);
          setError(msg);
          setLoading(false);
          logEvent("payment_failed", { phase: "gateway", isUnlockFlow }, "error");
        }
      );
    } catch (err: any) {
      const msg = err.message || "Failed to start payment";
      setLocalError(msg);
      setError(msg);
      setLoading(false);
      logEvent("payment_failed", { phase: "order", isUnlockFlow }, "error");
    }
  };

  const handleAlreadyPaidProceed = () => {
    setPaymentSuccess("already_paid", null);
  };

  if (checking) {
    return (
      <div className="space-y-2">
        <BookingStepSkeleton />
        <p className="text-center text-sm text-muted-foreground">Checking payment status...</p>
      </div>
    );
  }

  if (alreadyPaid && !isUnlockFlow) { // Only show "already paid" for booking flow
    return (
      <div className="space-y-6">
        <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-4 flex items-center gap-3">
          <CheckCircle2 className="h-10 w-10 text-green-600 dark:text-green-400 shrink-0" />
          <div>
            <p className="font-semibold text-foreground">Already paid for this route</p>
            <p className="text-sm text-muted-foreground">Valid for 7 days. Continue to IRCTC.</p>
          </div>
        </div>
        <Button className="w-full" size="lg" onClick={handleAlreadyPaidProceed}>
          Continue to IRCTC booking
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground">
        {isUnlockFlow ? "Unlock Route Details" : "Complete payment"}
      </h3>

      <div className="rounded-xl border-2 border-primary/20 bg-primary/5 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm text-muted-foreground mb-1">
              {isUnlockFlow ? "One-time unlock fee" : "One-time service fee"}
            </p>
            <div className="flex items-baseline gap-1">
              <IndianRupee className="h-7 w-7 text-primary" />
              <span className="text-4xl font-bold text-primary">{paymentAmount}</span>
            </div>
          </div>
          <div className="h-14 w-14 rounded-full bg-primary/20 flex items-center justify-center">
            <Zap className="h-7 w-7 text-primary" />
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          Route: <strong>{originName} → {destName}</strong>
        </p>
      </div>

      <ul className="space-y-2 text-sm">
        {isUnlockFlow ? (
          <>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
              Full segment details including train numbers and timings
            </li>
            <li className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-primary shrink-0" />
              Direct booking links
            </li>
            <li className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary shrink-0" />
              Secure payment via Razorpay
            </li>
          </>
        ) : (
          <>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
              Pre-filled IRCTC checkout
            </li>
            <li className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-primary shrink-0" />
              Valid for 7 days
            </li>
            <li className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary shrink-0" />
              Secure payment via Razorpay
            </li>
          </>
        )}
      </ul>

      {error && (
        <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm space-y-2">
          <p>{error}</p>
          <p className="text-muted-foreground text-xs">
            Check your connection and try again. You can go back and choose another route if needed.
          </p>
        </div>
      )}

      <div className="flex gap-3">
        {!isUnlockFlow && ( // Hide back button for unlock flow
          <Button type="button" variant="outline" onClick={() => goToStep("availability")} disabled={loading}>
            Back
          </Button>
        )}
        <Button className="flex-1" onClick={handlePayment} disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <IndianRupee className="h-4 w-4 mr-2" />
              {isUnlockFlow ? `Pay ₹${paymentAmount} and unlock` : `Pay ₹${paymentAmount} and continue`}
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
