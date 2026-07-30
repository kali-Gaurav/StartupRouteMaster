import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { auth } from '@/lib/firebase';
import { signInWithCustomToken } from 'firebase/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Loader2, ShieldCheck, AlertCircle, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import { verifyOTP, sendOTP } from '@/api/auth';

const VerifyOTPPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const email = searchParams.get('email');

  useEffect(() => {
    if (!email) {
      navigate('/login');
    }
  }, [email, navigate]);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (otp.length < 6) {
      setError("Please enter the 6-digit code");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      // Step 1: Verify OTP with our backend — returns a Firebase custom token
      const response = await verifyOTP({ email: email!, otp });

      if (!response.token) {
        throw new Error("No token received from server.");
      }

      // Step 2: Exchange the Firebase custom token for a real Firebase ID token.
      // This triggers onAuthStateChanged in AuthContext so the session is established.
      await signInWithCustomToken(auth, response.token);

      toast.success("Verified!", {
        description: "Your identity has been confirmed. Welcome!",
      });
      navigate('/dashboard');
    } catch (err: any) {
      console.error("Verification failed:", err);
      setError(err.message || "Invalid or expired code. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setLoading(true);
    try {
      await sendOTP({ email: email! });
      toast.success("Code Resent", { description: "A new verification code has been sent to your email." });
    } catch (err: any) {
      toast.error("Failed to resend code", { description: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12 selection:bg-primary selection:text-primary-foreground">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(var(--primary),0.05),transparent_50%)] pointer-events-none" />
      
      <Card className="w-full max-w-md shadow-2xl border-t-4 border-t-primary glass relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl -mr-16 -mt-16" />
        
        <CardHeader className="space-y-2 pb-8 text-center">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
            <ShieldCheck className="h-10 w-10 text-primary animate-pulse" />
          </div>
          <CardTitle className="text-3xl font-black tracking-tighter">Verify Identity</CardTitle>
          <CardDescription className="text-base font-medium">
            Enter the 6-digit pulse code sent to <br />
            <span className="font-black text-foreground underline decoration-primary/30 decoration-2 underline-offset-4">{email}</span>
          </CardDescription>
        </CardHeader>
        
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-6 bg-destructive/10 border-destructive/20 text-destructive animate-in fade-in slide-in-from-top-1">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle className="font-black uppercase tracking-widest text-[10px]">Verification Failure</AlertTitle>
              <AlertDescription className="font-bold">{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleVerify} className="space-y-8">
            <div className="space-y-4">
              <Label htmlFor="otp" className="sr-only">One-Time Password</Label>
              <Input
                id="otp"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="000000"
                className="text-center text-4xl tracking-[1rem] font-black py-10 rounded-2xl border-2 bg-muted/30 focus:bg-background transition-all shadow-inner"
                maxLength={6}
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                disabled={loading}
                autoFocus
              />
              <p className="text-[10px] text-center font-black uppercase text-muted-foreground tracking-[0.2em]">Enter Secure Token</p>
            </div>
            
            <Button type="submit" className="w-full py-8 text-lg font-black uppercase tracking-widest rounded-2xl shadow-xl shadow-primary/20 hover:scale-[1.01] transition-all" disabled={loading || otp.length < 6}>
              {loading ? (
                <div className="flex items-center gap-3">
                  <Loader2 className="h-6 w-6 animate-spin" />
                  <span>Synchronizing...</span>
                </div>
              ) : "Authenticate Access"}
            </Button>
          </form>
        </CardContent>
        
        <CardFooter className="flex flex-col gap-4 border-t border-border/50 p-8 bg-muted/20">
          <div className="flex items-center justify-between w-full">
            <button 
              onClick={() => navigate('/login')}
              className="flex items-center text-[10px] font-black uppercase tracking-widest text-muted-foreground hover:text-primary transition-colors"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Abort
            </button>
            <button 
              onClick={handleResend}
              disabled={loading}
              className="text-[10px] font-black uppercase tracking-widest text-primary hover:underline disabled:opacity-50"
            >
              Request New Token
            </button>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
};

export default VerifyOTPPage;
