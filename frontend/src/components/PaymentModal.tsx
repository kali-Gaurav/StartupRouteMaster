/**
 * Payment Modal
 * Handles ₹39 service fee payment via Zero-Gateway UPI
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/context/AuthContext';
import { checkPaymentStatus } from '@/lib/paymentApi';
import { fetchWithAuth } from '@/lib/apiClient';
import { Loader2, CheckCircle2, IndianRupee, ShieldCheck, Zap } from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';

interface PaymentModalProps {
  open: boolean;
  onClose: () => void;
  routeOrigin: string;
  routeDestination: string;
  trainNo?: string;
  travelDate?: string;
  routeId?: string;
  onSuccess: (paymentOrderId: string) => void;
}

export const PaymentModal: React.FC<PaymentModalProps> = ({
  open,
  onClose,
  routeOrigin,
  routeDestination,
  trainNo,
  travelDate,
  routeId,
  onSuccess,
}) => {
  const { user, token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [alreadyPaid, setAlreadyPaid] = useState(false);
  const [error, setError] = useState('');
  
  // Escrow state
  const [sessionCode, setSessionCode] = useState('');
  const [upiLink, setUpiLink] = useState('');
  const [manualCode, setManualCode] = useState('');
  const [verifying, setVerifying] = useState(false);

  const checkExistingPayment = useCallback(async () => {
    setChecking(true);
    try {
      const response = await checkPaymentStatus(routeId || '', travelDate || '');
      if (response.paid) {
        setAlreadyPaid(true);
      }
    } catch (err: unknown) {
      console.error('Failed to check payment status:', err);
    } finally {
      setChecking(false);
    }
  }, [routeId, travelDate]);

  useEffect(() => {
    if (open && token) {
      checkExistingPayment();
    } else {
      // Reset state on close
      setSessionCode('');
      setUpiLink('');
      setManualCode('');
      setError('');
    }
  }, [open, token, checkExistingPayment]);

  const handlePaymentInitiate = async () => {
    if (!token || !user || !routeId) {
      setError('Please login and select a valid route to continue');
      return;
    }

    setError('');
    setLoading(true);

    try {
      const response = await fetchWithAuth('/payments/create_session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ journey_id: routeId, amount: 39.0 })
      });
      
      const data = await response.json();
      if (!data.success) throw new Error(data.detail || 'Failed to initiate payment');
      
      setSessionCode(data.session_code);
      setUpiLink(data.upi_link);
    } catch (err: any) {
      setError(err.message || 'Failed to initiate payment');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (!manualCode.trim()) {
      setError("Please enter the session code shown after payment");
      return;
    }
    
    setVerifying(true);
    setError('');
    try {
      const response = await fetchWithAuth('/payments/confirm_manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ journey_id: routeId, session_code: manualCode })
      });
      
      const data = await response.json();
      if (!data.success) throw new Error(data.detail || 'Invalid session code');
      
      onSuccess(sessionCode);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Verification failed');
    } finally {
      setVerifying(false);
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
              You have already unlocked this route. Proceeding to view details...
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
          </div>

          <Button onClick={handleProceedWithoutPayment} className="w-full" size="lg">
            View Route Details
          </Button>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold">Unlock Route Details</DialogTitle>
          <DialogDescription>
            Pay our one-time service fee to unlock full segment data and booking
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 my-6">
          {!upiLink ? (
            <>
              {/* Price Card */}
              <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">One-Time Unlock Fee</p>
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
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5" />
                  <div>
                    <p className="font-medium">Full Route Visibility</p>
                    <p className="text-sm text-muted-foreground">See all train numbers and layover details</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <ShieldCheck className="h-5 w-5 text-purple-600 mt-0.5" />
                  <div>
                    <p className="font-medium">Direct UPI Payment</p>
                    <p className="text-sm text-muted-foreground">Zero gateway fees. 100% Secure.</p>
                  </div>
                </div>
              </div>

              {/* Error Message */}
              {error && <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">{error}</div>}

              {/* Payment Button */}
              <Button onClick={handlePaymentInitiate} disabled={loading} className="w-full h-12 text-lg font-semibold" size="lg">
                {loading ? <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Processing...</> : <><IndianRupee className="mr-2 h-5 w-5" /> Pay ₹39 Now</>}
              </Button>
            </>
          ) : (
            <div className="space-y-6 animate-in fade-in">
              <div className="bg-primary/5 border border-primary/20 p-6 rounded-xl flex flex-col items-center">
                <div className="bg-white p-2 rounded-lg shadow-sm mb-4">
                  <QRCodeSVG value={upiLink} size={160} level="H" />
                </div>
                <h3 className="font-bold text-lg mb-1">Scan to Pay ₹39</h3>
                <p className="text-sm text-muted-foreground text-center">
                  Use any UPI app. Do not close this window.
                </p>
              </div>
              
              <div className="space-y-3">
                <label className="text-sm font-medium">Enter Session Code after payment:</label>
                <div className="flex gap-2">
                  <Input 
                    placeholder="e.g. A1B2C3" 
                    value={manualCode}
                    onChange={(e) => setManualCode(e.target.value)}
                    className="font-mono uppercase"
                  />
                  <Button onClick={handleVerify} disabled={verifying || !manualCode}>
                    {verifying ? <Loader2 className="w-4 h-4 animate-spin" /> : "Verify"}
                  </Button>
                </div>
                {error && <p className="text-xs text-destructive">{error}</p>}
              </div>
            </div>
          )}
        </div>

      </DialogContent>
    </Dialog>
  );
};
