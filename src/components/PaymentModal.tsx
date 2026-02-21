/**
 * Payment Modal
 * Handles ₹49 service fee payment via Razorpay
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/AuthContext';
import { createPaymentOrder, verifyPayment, consumeRedirectToken, openRazorpayCheckout, checkPaymentStatus } from '@/lib/paymentApi';
import { Loader2, CheckCircle2, IndianRupee, ShieldCheck, Clock, Zap } from 'lucide-react';

interface PaymentModalProps {
  open: boolean;
  onClose: () => void;
  routeOrigin: string;
  routeDestination: string;
  trainNo?: string;
  travelDate?: string;
  onSuccess: (paymentOrderId: string) => void;
}

export const PaymentModal: React.FC<PaymentModalProps> = ({
  open,
  onClose,
  routeOrigin,
  routeDestination,
  trainNo,
  travelDate,
  onSuccess,
}) => {
  const { user, token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [alreadyPaid, setAlreadyPaid] = useState(false);
  const [error, setError] = useState('');

  const checkExistingPayment = useCallback(async () => {
    setChecking(true);
    try {
      const response = await checkPaymentStatus(routeOrigin, routeDestination);
      if (response.paid) {
        setAlreadyPaid(true);
      }
    } catch (err: unknown) {
      console.error('Failed to check payment status:', err);
    } finally {
      setChecking(false);
    }
  }, [routeOrigin, routeDestination]);

  useEffect(() => {
    if (open && token) {
      checkExistingPayment();
    }
  }, [open, token, checkExistingPayment]);

  const handlePayment = async () => {
    if (!token || !user) {
      setError('Please login to continue');
      return;
    }

    setError('');
    setLoading(true);

    try {
      // Step 1: Create order
      const orderResponse = await createPaymentOrder({
        route_origin: routeOrigin,
        route_destination: routeDestination,
        train_no: trainNo,
        travel_date: travelDate,
      });

      if (!orderResponse.success) {
        throw new Error(orderResponse.message || 'Failed to create order');
      }

      if (orderResponse.already_paid) {
        setAlreadyPaid(true);
        setLoading(false);
        return;
      }

      const order = orderResponse.order;

      // Step 2: Open Razorpay checkout
      openRazorpayCheckout(
        order,
        user,
        async (paymentResponse: unknown) => {
          try {
            const verifyResponse = await verifyPayment(paymentResponse as any); // Cast here as openRazorpayCheckout callback is tricky
            if (!verifyResponse.success) {
              setError('Payment verification failed. Please contact support.');
              return;
            }
            if (verifyResponse.redirect_token) {
              const consumeResponse = await consumeRedirectToken(verifyResponse.redirect_token);
              if (!consumeResponse?.success) {
                setError('Payment confirmation invalid. Please contact support.');
                return;
              }
            }
            onSuccess(order.order_id);
            onClose();
          } catch (err: unknown) {
            setError('Payment verification failed: ' + (err instanceof Error ? err.message : 'Unknown error'));
          } finally {
            setLoading(false);
          }
        },
        (err: Error) => {
          setError(err.message || 'Payment failed');
          setLoading(false);
        }
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to initiate payment');
      setLoading(false);
    }
  };

  const handleProceedWithoutPayment = () => {
    onSuccess('');
    onClose();
  };

  if (checking) {
    return (
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent className="sm:max-w-lg">
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
            <p className="text-muted-foreground">Checking payment status...</p>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  if (alreadyPaid) {
    return (
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-2xl">
              <CheckCircle2 className="h-6 w-6 text-green-600" />
              Already Paid
            </DialogTitle>
            <DialogDescription>
              You have already paid for this route. Proceeding to IRCTC booking...
            </DialogDescription>
          </DialogHeader>

          <div className="bg-green-50 border border-green-200 rounded-lg p-6 my-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="h-12 w-12 bg-green-100 rounded-full flex items-center justify-center">
                <CheckCircle2 className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="font-semibold text-green-900">Payment Active</p>
                <p className="text-sm text-green-700">Valid for 7 days</p>
              </div>
            </div>
            <div className="text-sm text-green-800">
              <strong>Route:</strong> {routeOrigin} → {routeDestination}
            </div>
          </div>

          <Button onClick={handleProceedWithoutPayment} className="w-full" size="lg">
            Continue to IRCTC Booking
          </Button>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold">Complete Your Booking</DialogTitle>
          <DialogDescription>
            Pay our one-time service fee to unlock IRCTC booking
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 my-6">
          {/* Price Card */}
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-sm text-muted-foreground mb-1">One-Time Service Fee</p>
                <div className="flex items-baseline gap-1">
                  <IndianRupee className="h-8 w-8 text-blue-600" />
                  <span className="text-5xl font-bold text-blue-600">39</span>
                </div>
              </div>
              <div className="h-16 w-16 bg-blue-100 rounded-full flex items-center justify-center">
                <Zap className="h-8 w-8 text-blue-600" />
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              For complete route: <strong>{routeOrigin} → {routeDestination}</strong>
            </p>
          </div>

          {/* Benefits */}
          <div className="space-y-3">
            <h3 className="font-semibold text-sm text-muted-foreground">What you get:</h3>
            
            <div className="flex items-start gap-3">
              <div className="mt-0.5">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="font-medium">Direct IRCTC Integration</p>
                <p className="text-sm text-muted-foreground">
                  Pre-filled booking details for instant checkout
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="mt-0.5">
                <Clock className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="font-medium">Valid for 7 Days</p>
                <p className="text-sm text-muted-foreground">
                  Use anytime within a week
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="mt-0.5">
                <ShieldCheck className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="font-medium">Secure Payment</p>
                <p className="text-sm text-muted-foreground">
                  100% safe via Razorpay
                </p>
              </div>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md border border-red-200">
              {error}
            </div>
          )}

          {/* Payment Button */}
          <div className="space-y-3">
            <Button
              onClick={handlePayment}
              disabled={loading}
              className="w-full h-12 text-lg font-semibold"
              size="lg"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <IndianRupee className="mr-2 h-5 w-5" />
                  Pay ₹49 Now
                </>
              )}
            </Button>

            <p className="text-xs text-center text-muted-foreground">
              Powered by Razorpay • 100% Secure
            </p>
          </div>
        </div>

        <div className="border-t pt-4">
          <p className="text-xs text-center text-muted-foreground">
            Note: This is a service fee for using our platform. Actual train ticket cost will be paid on IRCTC.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
