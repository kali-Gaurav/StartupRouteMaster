import { useState, useEffect, useRef, useCallback } from "react";
import { Loader2, IndianRupee, CheckCircle2, ShieldCheck, QrCode, CreditCard, XCircle, TicketCheck, RefreshCw, Shield, ExternalLink, Copy } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import Confetti from "react-confetti";
import { useAuth } from "@/context/AuthContext";
import { useBookingFlowContext } from "@/context/BookingFlowContext";
import {
  initiateEscrowBooking,
  submitEscrowUtr,
  getEscrowBookingStatus,
  BookingResponse
} from "@/lib/paymentApi";
import { invalidateBookingsCache } from "@/lib/queryInvalidation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Stepper, Step } from "@/components/ui/stepper";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";

const ESCROW_STEPS: Step[] = [
  { id: 'CREATED', label: 'Payment Pending', description: 'Scan QR or enter UTR manually' },
  { id: 'UTR_SUBMITTED', label: 'Verifying Payment', description: 'Confirming funds in escrow' },
  { id: 'VERIFIED', label: 'Payment Secured', description: 'Funds safely held in escrow' },
  { id: 'BOOKING_INITIATED', label: 'AI Booking', description: 'Automated IRCTC navigation' },
  { id: 'COMPLETED', label: 'Ticket Confirmed', description: 'PNR has been generated' }
];

const STATUS_TO_INDEX: Record<string, number> = {
  'CREATED': 0,
  'UTR_SUBMITTED': 1,
  'VERIFIED': 2,
  'BOOKING_INITIATED': 3,
  'COMPLETED': 4,
  'FAILED': 4 
};

/**
 * Task 5: Enhanced Payment Polling Hook
 */
function usePaymentPolling(bookingId: string | undefined, onComplete: (booking: BookingResponse) => void) {
  const [latestBooking, setLatestBooking] = useState<BookingResponse | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const poll = useCallback(async () => {
    if (!bookingId) return;
    try {
      const res = await getEscrowBookingStatus(bookingId);
      setLatestBooking(res);
      if (res.escrow_status === 'COMPLETED' || res.escrow_status === 'FAILED') {
        onComplete(res);
        return;
      }
      // Continue polling
      timerRef.current = setTimeout(poll, 3000);
    } catch (e) {
      console.error("Polling error", e);
      timerRef.current = setTimeout(poll, 5000); // Retry later on error
    }
  }, [bookingId, onComplete]);

  useEffect(() => {
    if (bookingId) {
      poll();
      
      // Task 22: Resume immediately on reconnect
      const handleOnline = () => {
        console.log("Network restored, resuming poll...");
        if (timerRef.current) clearTimeout(timerRef.current);
        poll();
      };
      window.addEventListener('online', handleOnline);
      return () => {
        window.removeEventListener('online', handleOnline);
        if (timerRef.current) clearTimeout(timerRef.current);
      };
    }
  }, [bookingId, poll]);

  return latestBooking;
}

/**
 * Task 17: QR Expiry Timer Component
 */
function PaymentTimer({ createdAt, onExpire }: { createdAt: string, onExpire: () => void }) {
  const [timeLeft, setTimeLeft] = useState<number>(15 * 60); // 15 minutes

  useEffect(() => {
    const created = new Date(createdAt).getTime();
    const interval = setInterval(() => {
      const now = new Date().getTime();
      const diff = Math.floor((created + 15 * 60 * 1000 - now) / 1000);
      if (diff <= 0) {
        clearInterval(interval);
        setTimeLeft(0);
        onExpire();
      } else {
        setTimeLeft(diff);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [createdAt, onExpire]);

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;

  return (
    <div className={cn(
      "flex items-center gap-2 px-3 py-1.5 rounded-full font-mono text-xs font-bold border",
      timeLeft < 60 ? "bg-red-50 text-red-600 border-red-200 animate-pulse" : "bg-slate-50 text-slate-600 border-slate-200"
    )}>
      <Clock className="w-3.5 h-3.5" />
      <span>{minutes.toString().padStart(2, '0')}:{seconds.toString().padStart(2, '0')}</span>
    </div>
  );
}

export function BookingPaymentStep() {
  const { user, token } = useAuth();
  const {
    route,
    travelDate,
    originName,
    destName,
    setPaymentSuccess,
    setError,
    goToStep,
  } = useBookingFlowContext();

  const [initialBooking, setInitialBooking] = useState<BookingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [utrNumber, setUtrNumber] = useState("");
  const [utrSubmitting, setUtrSubmitting] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);
  const [windowSize, setWindowSize] = useState({ width: window.innerWidth, height: window.innerHeight });

  // WebSocket Live Logs & Captcha State
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [captchaImage, setCaptchaImage] = useState<string | null>(null);
  const [captchaInput, setCaptchaInput] = useState("");
  const [captchaSubmitting, setCaptchaSubmitting] = useState(false);
  
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [liveLogs]);

  // Task 16: Session Lock - Prevent navigation during active worker
  useEffect(() => {
    if (booking?.escrow_status === 'BOOKING_INITIATED') {
      const handleBeforeUnload = (e: BeforeUnloadEvent) => {
        e.preventDefault();
        e.returnValue = "Your booking is in progress. Leaving now will cause the session to fail.";
      };
      window.addEventListener('beforeunload', handleBeforeUnload);
      return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }
  }, [booking?.escrow_status]);

  // Mobile check for Task 3
  const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

  useEffect(() => {
    const handleResize = () => setWindowSize({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleComplete = useCallback((final: BookingResponse) => {
    if (final.escrow_status === 'COMPLETED') {
      setShowConfetti(true);
      setTimeout(() => setShowConfetti(false), 5000);
      invalidateBookingsCache();
    }
  }, []);

  const polledBooking = usePaymentPolling(initialBooking?.id, handleComplete);
  const booking = polledBooking || initialBooking;

  // Task 42: Live WebSocket Logging
  useEffect(() => {
    if (!booking?.id) return;
    
    // Determine WS URL based on current origin
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" 
                 ? "localhost:8000" 
                 : window.location.host;
    const wsUrl = `${protocol}//${host}/api/v2/booking/ws/${booking.id}`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "booking_log") {
          setLiveLogs((prev) => [...prev, data.message]);
        } else if (data.type === "captcha_required") {
          setCaptchaImage(data.image);
        }
      } catch (e) {
        console.error("WS Parse Error", e);
      }
    };

    return () => {
      ws.close();
    };
  }, [booking?.id]);

  const submitCaptcha = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!booking?.id || !captchaInput) return;
    setCaptchaSubmitting(true);
    try {
      const tokenStr = localStorage.getItem("auth_token");
      await fetch(`http://localhost:8000/api/v2/booking/${booking.id}/captcha`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${tokenStr}`
        },
        body: JSON.stringify({ captcha: captchaInput })
      });
      setCaptchaImage(null); // Hide UI
      setCaptchaInput("");
      toast({ title: "CAPTCHA Submitted", description: "Worker is continuing..." });
    } catch (err: any) {
      toast({ title: "CAPTCHA Error", description: err.message, variant: "destructive" });
    } finally {
      setCaptchaSubmitting(false);
    }
  };

  const handleInitiate = async () => {
    if (!token || !user || !route?.id) {
      setError("Please sign in or provide a valid route.");
      return;
    }
    
    setLoading(true);
    try {
      const idemKey = `idem_${route.id}_${travelDate}_${Date.now()}`;
      const res = await initiateEscrowBooking({ journey_id: route.id }, idemKey);
      setInitialBooking(res);
    } catch (err: any) {
      setError(err.message || "Failed to initiate booking");
    } finally {
      setLoading(false);
    }
  };

  const handleUtrSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!booking?.id || utrNumber.length !== 12) {
      toast({ title: "Invalid UTR", description: "Please enter a 12-digit number", variant: "destructive" });
      return;
    }
    setUtrSubmitting(true);
    try {
      const res = await submitEscrowUtr(booking.id, utrNumber);
      setInitialBooking(res);
      toast({ title: "UTR Submitted", description: "Verifying with your bank..." });
    } catch (err: any) {
      setError(err.message || "Failed to submit UTR");
    } finally {
      setUtrSubmitting(false);
    }
  };

  const copyUpiId = () => {
    // Extract VPA from upi_url (pa parameter) or use default
    const urlParams = new URLSearchParams(booking?.upi_url?.split('?')[1]);
    const upiId = urlParams.get('pa') || "anthonynagar1122-1@oksbi";
    navigator.clipboard.writeText(upiId);
    if (navigator.vibrate) navigator.vibrate(50); // Task 1.7 Haptic Feedback
    toast({ title: "UPI ID Copied", description: upiId });
  };

  const openUpiApp = () => {
    if (booking?.upi_url) {
      if (navigator.vibrate) navigator.vibrate([50, 50, 50]); // Task 1.7
      window.location.href = booking.upi_url;
      // Task 1.8 & 9.9 Fallback logic: If the app doesn't open, we could show a toast after a delay.
      setTimeout(() => {
        if (!document.hidden) {
          toast({ title: "Couldn't open app", description: "Please scan the QR or copy the UPI ID manually.", variant: "destructive" });
        }
      }, 2500);
    }
  };

  const shareOnWhatsApp = () => {
    const upiId = "anthonynagar1122-1@oksbi";
    const amount = Number(booking?.amount_paid).toFixed(2);
    const text = `Hey! Please pay ₹${amount} to ${upiId} using any UPI app for my RouteMaster Train Booking. Use note: ${booking?.upi_tx_id}`;
    const waUrl = `https://wa.me/?text=${encodeURIComponent(text)}`;
    window.open(waUrl, '_blank');
  };

  /**
   * Task 15: Initializing Skeleton
   */
  if (loading) {
    return (
      <div className="space-y-6 max-w-2xl mx-auto py-10">
        <div className="flex flex-col items-center justify-center space-y-4">
          <div className="w-16 h-16 rounded-full border-4 border-primary/20 border-t-primary animate-spin" />
          <h2 className="text-xl font-bold animate-pulse">Initializing Secure Escrow...</h2>
          <p className="text-sm text-muted-foreground">Setting up your private transaction pipeline.</p>
        </div>
        <div className="grid grid-cols-1 gap-4 opacity-50">
          <Card className="h-32 animate-pulse bg-muted" />
          <Card className="h-48 animate-pulse bg-muted" />
        </div>
      </div>
    );
  }

  if (!booking) {
    return (
      <div className="space-y-6 max-w-2xl mx-auto py-4">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-3xl font-bold tracking-tight">Final Step: Secure Booking</h1>
          <div className="bg-emerald-500/10 text-emerald-600 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 border border-emerald-500/20">
            <Shield className="w-3.5 h-3.5" />
            Zero Gateway Fee
          </div>
        </div>

        <Card className="glass-card overflow-hidden">
          <CardContent className="p-8">
            <div className="flex items-center justify-between mb-6">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Journey Summary</p>
                <h3 className="text-xl font-bold">{originName} → {destName}</h3>
                <p className="text-xs text-muted-foreground mt-1">Travel Date: {travelDate}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground mb-1">Total to Pay</p>
                <div className="flex items-baseline gap-1 justify-end">
                  <IndianRupee className="h-6 w-6 text-primary" />
                  <span className="text-4xl font-black text-primary">{route?.total_cost || 0}</span>
                </div>
              </div>
            </div>

            <div className="space-y-4 border-t border-border/50 pt-6">
               <div className="flex gap-3">
                 <div className="bg-primary/10 p-2 rounded-lg"><ShieldCheck className="w-5 h-5 text-primary" /></div>
                 <div>
                   <p className="text-sm font-semibold">Funds Held in Escrow</p>
                   <p className="text-xs text-muted-foreground">Your money is safe. We only pay IRCTC once your seat is secured.</p>
                 </div>
               </div>
               <div className="flex gap-3">
                 <div className="bg-primary/10 p-2 rounded-lg"><CheckCircle2 className="w-5 h-5 text-primary" /></div>
                 <div>
                   <p className="text-sm font-semibold">AI Automated Booking</p>
                   <p className="text-xs text-muted-foreground">Our Ghost Worker handles the IRCTC login and form filling instantly.</p>
                 </div>
               </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex gap-3 pt-2">
          <Button variant="outline" className="h-14 px-8 rounded-xl" onClick={() => goToStep("availability")} disabled={loading}>
            Back
          </Button>
          <Button className="flex-1 h-14 text-lg font-bold rounded-xl hover-elevate shadow-lg shadow-primary/20" onClick={handleInitiate} disabled={loading}>
            <ArrowRight className="h-5 w-5 mr-2" />
            Initialize Escrow Pipeline
          </Button>
        </div>
      </div>
    );
  }

  const currentStepIndex = STATUS_TO_INDEX[booking.escrow_status] ?? 0;
  const isFailed = booking.escrow_status === 'FAILED';
  const isCompleted = booking.escrow_status === 'COMPLETED';

  return (
    <div className="space-y-8 relative">
      {showConfetti && <Confetti width={windowSize.width} height={windowSize.height} recycle={false} numberOfPieces={500} gravity={0.15} />}
      
      <div className="flex flex-col lg:grid lg:grid-cols-12 gap-8 items-start">
        
        {/* Left: Payment Area (7 cols) */}
        <div className="lg:col-span-7 space-y-6 w-full">
          
          <Card className="glass-card overflow-hidden shadow-sm">
            <div className="bg-muted/50 p-4 border-b flex justify-between items-center">
              <h3 className="font-semibold flex items-center gap-2">
                <TicketCheck className="w-4 h-4 text-primary" />
                Booking Summary
              </h3>
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-primary/10 text-primary text-[10px] font-bold uppercase tracking-widest">
                ID: {booking.id.slice(0, 8)}
              </div>
            </div>
            <CardContent className="p-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider mb-1">Passengers</p>
                  <p className="font-bold text-sm">{(booking as any).passenger_details?.length || 1} Adult(s)</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider mb-1">Train Number</p>
                  <p className="font-mono font-bold text-sm tracking-widest">{(booking as any).train_number || "N/A"}</p>
                </div>
                <div className="col-span-2 pt-2 border-t border-border/40 space-y-1">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-muted-foreground">IRCTC Ticket Fare</span>
                    <span className="font-semibold">₹{(Number(booking.amount_paid) - 49.00).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-muted-foreground">Platform Service Fee</span>
                    <span className="font-semibold">₹49.00</span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-muted-foreground">Gateway Processing Fee</span>
                    <span className="text-emerald-600 font-bold">₹0.00 (Zero)</span>
                  </div>
                  <div className="pt-2 border-t border-border/20">
                    <p className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider mb-1">Total Amount to Pay</p>
                    <p className="text-3xl font-black text-foreground">₹{Number(booking.amount_paid).toFixed(2)}</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Success / Failure Overlays */}
          {isCompleted ? (
            <Card className="bg-gradient-to-br from-emerald-500/10 to-emerald-500/5 border-emerald-500/20 shadow-xl">
              <CardContent className="p-10 text-center space-y-4">
                <div className="w-20 h-20 bg-emerald-500 rounded-full flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/30 animate-float">
                  <CheckCircle2 className="w-10 h-10 text-white" />
                </div>
                <h2 className="text-3xl font-black text-emerald-700 dark:text-emerald-400 tracking-tight">Booking Confirmed!</h2>
                <p className="text-muted-foreground">Your AI-automated booking was successful.</p>
                
                <div className="glass-card rounded-2xl p-6 inline-block mt-6 w-full max-w-sm border-emerald-500/30 bg-white/50 backdrop-blur-md">
                  <p className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.2em] mb-2">Confirmed PNR Number</p>
                  <p className="text-4xl font-mono font-black tracking-widest text-foreground bg-clip-text">
                    {booking.pnr_number}
                  </p>
                </div>
                <div className="pt-6">
                  <Button onClick={() => setPaymentSuccess(booking.id, null)} size="lg" className="h-14 px-10 rounded-2xl font-bold bg-emerald-600 hover:bg-emerald-700 transition-all shadow-lg shadow-emerald-600/20">
                    Go to Dashboard
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : isFailed ? (
            <Card className="bg-destructive/5 border-destructive/20 py-10">
              <CardContent className="text-center space-y-4">
                <XCircle className="w-16 h-16 text-destructive mx-auto mb-2" />
                <h2 className="text-2xl font-black text-destructive tracking-tight">Booking Failed</h2>
                <p className="text-muted-foreground max-w-xs mx-auto">
                  {booking.escrow_message || "We could not secure your ticket. Any deducted funds will be automatically refunded within 3-5 days."}
                </p>
                {/* Task 16: Session Lock - Allow Try Again only on failure */}
                <Button variant="outline" onClick={() => { setInitialBooking(null); setUtrNumber(""); }} className="h-12 px-8 rounded-xl font-bold">
                  Try Again
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
              {/* QR Section */}
              {booking.escrow_status === 'CREATED' && (
                <Card className="overflow-hidden border-primary/20 shadow-xl bg-white">
                  <CardContent className="p-0 flex flex-col md:flex-row items-stretch">
                    <div className="p-8 flex flex-col items-center justify-center border-b md:border-b-0 md:border-r border-border shrink-0 bg-white">
                      <div className="p-3 rounded-2xl border-2 border-muted shadow-sm hover:scale-105 transition-transform duration-500 relative">
                        <QRCodeSVG 
                          value={booking.upi_url || ""}
                          size={180}
                          level="H"
                          includeMargin={true}
                        />
                      </div>
                      <Button variant="ghost" size="sm" onClick={copyUpiId} className="mt-4 text-[10px] uppercase font-black tracking-widest text-muted-foreground">
                        <Copy className="w-3 h-3 mr-1" /> Copy UPI ID
                      </Button>
                    </div>
                    <div className="p-8 flex flex-col justify-center bg-card/30 flex-1 relative">
                      {/* Task 17: Expiry Timer */}
                      <div className="absolute top-4 right-4">
                        <PaymentTimer 
                          createdAt={(booking as any).created_at || new Date().toISOString()} 
                          onExpire={() => toast({ title: "Session Expired", variant: "destructive" })} 
                        />
                      </div>

                      <div className="w-12 h-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mb-4">
                        <QrCode className="w-6 h-6" />
                      </div>
                      <h3 className="text-xl font-black mb-2 tracking-tight">Scan & Pay via UPI</h3>
                      <p className="text-sm text-muted-foreground leading-relaxed mb-6">
                        Open GPay, PhonePe, or Paytm and scan this QR code to transfer exactly <strong>₹{Number(booking.amount_paid).toFixed(2)}</strong>.
                      </p>
                      
                      {isMobile ? (
                        <div className="flex flex-col gap-3 w-full">
                          <Button onClick={openUpiApp} className="w-full h-12 rounded-xl font-bold bg-[#0f172a] hover:bg-[#1e293b] shadow-lg shadow-slate-200">
                            <ExternalLink className="w-4 h-4 mr-2" />
                            Open UPI App
                          </Button>
                          <Button onClick={shareOnWhatsApp} variant="outline" className="w-full h-12 rounded-xl font-bold border-green-200 text-green-700 hover:bg-green-50">
                            <svg className="w-4 h-4 mr-2 fill-current" viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.353-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.506-.174-.007-.373-.008-.573-.008-.2 0-.523.074-.797.373-.273.3-.1.747.1 1.147.2.4 1.48 2.54 3.585 4.416 2.013 1.792 3.528 2.31 4.199 2.388.671.079 1.282.042 1.765-.03.539-.079 1.658-.677 1.89-1.333.232-.656.232-1.218.162-1.33-.07-.113-.258-.177-.555-.326zm-5.472 7.618c-2.067 0-4.087-.556-5.862-1.608l-.42-.25-4.355 1.143 1.163-4.247-.274-.436c-1.153-1.832-1.762-3.96-1.762-6.147 0-6.342 5.158-11.5 11.515-11.5 3.073 0 5.961 1.198 8.129 3.37 2.168 2.172 3.36 5.061 3.36 8.13 0 6.345-5.159 11.502-11.515 11.502zm0-24c-6.904 0-12.515 5.611-12.515 12.515 0 2.213 5.78 4.301 1.587 6.22l-1.685 6.152 6.291-1.651c1.847.1.007 3.732 1.426 5.864 1.917 1.397 4.213 2.133 6.526 2.133 6.905 0 12.515-5.61 12.515-12.515 0-6.904-5.61-12.515-12.515-12.515z"/></svg>
                            Request via WhatsApp
                          </Button>
                        </div>
                      ) : (
                        <Button onClick={shareOnWhatsApp} variant="outline" className="w-full h-12 rounded-xl font-bold border-green-200 text-green-700 hover:bg-green-50">
                          <ExternalLink className="w-4 h-4 mr-2" />
                          Request Payment from Friend
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* UTR Submission */}
              {(booking.escrow_status === 'CREATED' || booking.escrow_status === 'UTR_SUBMITTED') && (
                <Card className="glass-card shadow-lg border-border/40">
                  <CardContent className="p-6">
                    <div className="flex items-start gap-4 mb-6">
                      <div className="w-12 h-12 rounded-2xl bg-secondary text-secondary-foreground flex items-center justify-center shrink-0">
                        <CreditCard className="w-6 h-6" />
                      </div>
                      <div>
                        <h3 className="text-base font-black tracking-tight">Verify Payment Manually</h3>
                        <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
                          If the system doesn't auto-detect your payment, enter the 12-digit UTR number from your UPI app.
                        </p>
                      </div>
                    </div>

                    <form onSubmit={handleUtrSubmit} className="flex gap-3">
                      <Input 
                        placeholder="12-digit UPI UTR" 
                        maxLength={12}
                        className="font-mono text-lg h-14 uppercase border-2 focus-visible:ring-primary/20 tracking-[0.2em]" 
                        value={utrNumber}
                        onChange={(e) => setUtrNumber(e.target.value.replace(/\D/g, ""))}
                        disabled={booking.escrow_status !== 'CREATED' || utrSubmitting}
                      />
                      <Button 
                        type="submit" 
                        size="lg"
                        className="h-14 px-8 font-black rounded-xl hover-elevate"
                        disabled={booking.escrow_status !== 'CREATED' || utrSubmitting || utrNumber.length !== 12}
                      >
                        {utrSubmitting ? <Loader2 className="w-5 h-5 animate-spin" /> : "Verify"}
                      </Button>
                    </form>
                    
                    {booking.escrow_status === 'UTR_SUBMITTED' && (
                      <div className="mt-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-700 text-sm flex items-center gap-3 animate-pulse">
                        <RefreshCw className="w-5 h-5 animate-spin shrink-0" />
                        <span className="font-semibold">Verifying transaction with banking network. Please stay on this page...</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>

        {/* Right: Pipeline Stepper (5 cols) */}
        <div className="lg:col-span-5 w-full relative">
          <div className="sticky top-24">
            <Card className="glass-card shadow-2xl border-t border-white/40 overflow-hidden">
              <div className="h-1.5 w-full bg-gradient-to-r from-primary via-accent to-primary" />
              <CardContent className="p-8">
                <h3 className="font-black text-lg mb-10 flex items-center gap-2 tracking-tight uppercase">
                  <span className="relative flex h-3 w-3">
                    {!isCompleted && !isFailed && (
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                    )}
                    <span className={cn(
                      "relative inline-flex rounded-full h-3 w-3",
                      isCompleted ? "bg-emerald-500" : isFailed ? "bg-destructive" : "bg-primary"
                    )}></span>
                  </span>
                  Live Pipeline Status
                </h3>
                
                <div className="pl-2">
                  <Stepper 
                    steps={ESCROW_STEPS} 
                    currentStepIndex={currentStepIndex} 
                    isFailed={isFailed}
                  />
                </div>

                {/* Live Message Bubbles */}
                {(booking.escrow_message || !isCompleted) && !isFailed && (
                  <div className="mt-10 p-4 rounded-2xl bg-secondary/50 border border-border/40 space-y-2 animate-in fade-in zoom-in-95 duration-500">
                    <p className="text-[10px] font-black text-muted-foreground uppercase tracking-widest flex justify-between">
                      <span>Ghost Worker Logs</span>
                      {!isCompleted && <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" /> Live</span>}
                    </p>
                    <div className="max-h-32 overflow-y-auto space-y-1.5 pr-2 custom-scrollbar">
                      {liveLogs.length > 0 ? (
                        liveLogs.map((log, idx) => (
                          <p key={idx} className={cn(
                            "text-sm font-medium italic transition-opacity duration-300",
                            idx === liveLogs.length - 1 ? "text-foreground" : "text-muted-foreground opacity-60"
                          )}>
                            {log}
                          </p>
                        ))
                      ) : (
                        <p className="text-sm font-medium text-foreground italic">
                          {booking.escrow_message || "Awaiting payment initialization..."}
                        </p>
                      )}
                      <div ref={logEndRef} />
                    </div>
                  </div>
                )}

                {/* Human-in-the-Loop CAPTCHA Solver */}
                {captchaImage && (
                  <div className="mt-6 p-4 rounded-2xl bg-amber-50 border border-amber-200 shadow-md animate-in fade-in zoom-in duration-300">
                    <div className="flex justify-between items-center mb-2">
                      <h4 className="text-sm font-bold text-amber-900 flex items-center gap-2">
                        <Shield className="w-4 h-4" />
                        IRCTC Captcha Required
                      </h4>
                      <Button variant="ghost" size="sm" onClick={() => setCaptchaInput("REFRESH")} className="h-6 text-xs px-2 bg-amber-100 text-amber-900 hover:bg-amber-200">
                        <RefreshCw className="w-3 h-3 mr-1" /> Reload
                      </Button>
                    </div>
                    <div className="bg-white p-2 rounded-xl mb-3 flex justify-center border border-amber-100">
                      <img src={captchaImage} alt="IRCTC Captcha" className="max-w-full h-auto rounded" />
                    </div>
                    <form onSubmit={submitCaptcha} className="flex gap-2">
                      <Input 
                        placeholder="Enter letters/numbers" 
                        value={captchaInput}
                        onChange={(e) => setCaptchaInput(e.target.value)}
                        className="bg-white"
                        disabled={captchaSubmitting}
                      />
                      <Button type="submit" disabled={!captchaInput || captchaSubmitting}>
                        {captchaSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Submit"}
                      </Button>
                    </form>
                  </div>
                )}
              </CardContent>
            </Card>
            
            <div className="mt-6 flex items-center gap-2 justify-center text-[10px] text-muted-foreground uppercase font-black tracking-widest opacity-50">
              <ShieldCheck className="w-3 h-3" />
              End-to-End Encrypted Escrow
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
