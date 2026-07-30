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
  const [hasPaid, setHasPaid] = useState(false); // [8.1] Trigger State
  
  // [7.2] Countdown State
  const [timeLeft, setTimeLeft] = useState(900); // 15 mins

  // [7.4] Time Formatting
  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  // [7.3] Timer Logic
  useEffect(() => {
    if (!upiLink || timeLeft <= 0) return;
    
    const timer = setInterval(() => {
      setTimeLeft((prev) => prev - 1);
    }, 1000);
    
    return () => clearInterval(timer);
  }, [upiLink, timeLeft]);

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
              {/* [7.5] Timer Display */}
              <div className="flex justify-center">
                <div className={`text-sm font-bold px-3 py-1 rounded-full border ${timeLeft < 120 ? 'bg-red-50 text-red-600 border-red-200 animate-pulse' : 'bg-blue-50 text-blue-600 border-blue-200'}`}>
                  Session expires in: {formatTime(timeLeft)}
                </div>
              </div>

              <div className="bg-primary/5 border border-primary/20 p-6 rounded-xl flex flex-col items-center">
                <div className="bg-white p-2 rounded-lg shadow-md mb-4 relative group">
                  <QRCodeSVG 
                    id="payment-qr"
                    value={upiLink} 
                    size={256} 
                    level="H" 
                    includeMargin={true}
                    imageSettings={{
                      src: "/logo.png",
                      x: undefined,
                      y: undefined,
                      height: 48,
                      width: 48,
                      excavate: true,
                    }}
                  />
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={() => {
                      const svg = document.getElementById('payment-qr');
                      if (svg) {
                        const svgData = new XMLSerializer().serializeToString(svg);
                        const canvas = document.createElement("canvas");
                        const ctx = canvas.getContext("2d");
                        const img = new Image();
                        img.onload = () => {
                          canvas.width = img.width;
                          canvas.height = img.height;
                          ctx?.drawImage(img, 0, 0);
                          const pngFile = canvas.toDataURL("image/png");
                          const downloadLink = document.createElement("a");
                          downloadLink.download = "RouteMaster-Payment-QR.png";
                          downloadLink.href = pngFile;
                          downloadLink.click();
                        };
                        img.src = "data:image/svg+xml;base64," + btoa(svgData);
                      }
                    }}
                  >
                    Save
                  </Button>
                </div>
                <h3 className="font-bold text-lg mb-1">Scan to Pay ₹39</h3>
                
                {/* [6.2] VPA Display Component */}
                <div className="mt-2 flex flex-col items-center w-full">
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Or pay to UPI ID:</p>
                  <div className="flex items-center gap-2 bg-white border px-3 py-1.5 rounded-lg shadow-sm w-full max-w-[240px] justify-between">
                    <span className="font-mono text-xs truncate">
                      {new URLSearchParams(upiLink.split('?')[1]).get('pa')}
                    </span>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-7 w-7 p-0"
                      onClick={() => {
                        const vpa = new URLSearchParams(upiLink.split('?')[1]).get('pa');
                        if (vpa) {
                          navigator.clipboard.writeText(vpa);
                          // We could use a toast here, but for simplicity we'll just log
                          console.log("VPA Copied");
                        }
                      }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-copy"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                    </Button>
                  </div>
                </div>

                <p className="text-sm text-muted-foreground text-center mt-4">
                  Use any UPI app. Do not close this window.
                </p>
              </div>
              
              <div className="space-y-3">
                {!hasPaid ? (
                  <Button 
                    onClick={() => setHasPaid(true)} 
                    className="w-full bg-green-600 hover:bg-green-700 text-white font-bold h-12"
                  >
                    I have paid successfully
                  </Button>
                ) : (
                  <div className="space-y-3 animate-in slide-in-from-top-2">
                    <label className="text-sm font-medium">Enter Session Code after payment:</label>
                    <div className="flex gap-2">
                      <Input 
                        placeholder="12-digit UTR Number" 
                        value={manualCode}
                        onChange={(e) => {
                          const val = e.target.value.replace(/\D/g, '').slice(0, 12);
                          setManualCode(val);
                        }}
                        className={`font-mono ${manualCode.length > 0 && manualCode.length < 12 ? 'border-orange-400 focus-visible:ring-orange-400' : ''}`}
                        autoFocus
                      />
                      <Button 
                        onClick={handleVerify} 
                        disabled={verifying || manualCode.length !== 12}
                      >
                        {verifying ? <Loader2 className="w-4 h-4 animate-spin" /> : "Verify"}
                      </Button>
                    </div>
                    {manualCode.length > 0 && manualCode.length < 12 && (
                      <p className="text-[10px] text-orange-600">UTR must be exactly 12 digits ({manualCode.length}/12)</p>
                    )}
                    {error && <p className="text-xs text-destructive">{error}</p>}
                    <p className="text-[10px] text-muted-foreground italic">
                      Check your bank app for the Transaction Note (RM_...) or SMS.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

      </DialogContent>
    </Dialog>
  );
};
