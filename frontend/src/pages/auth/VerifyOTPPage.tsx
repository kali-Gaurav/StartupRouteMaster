import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { supabase } from '@/lib/supabase';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Loader2, ShieldCheck, AlertCircle, ArrowLeft, Mail } from 'lucide-react';
import { toast } from 'sonner';

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
      const { error: verifyError } = await supabase.auth.verifyOtp({
        email: email!,
        token: otp,
        type: 'signup', // Try signup type first, then magiclink
      });

      if (verifyError) {
        // Try fallback type
        const { error: fallbackError } = await supabase.auth.verifyOtp({
          email: email!,
          token: otp,
          type: 'magiclink',
        });
        if (fallbackError) throw fallbackError;
      }

      toast.success("Verified!", {
        description: "Your account has been successfully verified.",
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
      const { error: resendError } = await supabase.auth.signInWithOtp({ email: email! });
      if (resendError) throw resendError;
      toast.success("Code Resent", { description: "A new verification code has been sent to your email." });
    } catch (err: any) {
      toast.error("Failed to resend code", { description: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
      <Card className="w-full max-w-md shadow-xl border-t-4 border-t-primary">
        <CardHeader className="space-y-1">
          <div className="flex justify-center mb-2">
            <div className="p-3 bg-primary/10 rounded-full">
              <Mail className="h-8 w-8 text-primary" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold text-center">Verify Your Email</CardTitle>
          <CardDescription className="text-center">
            Enter the 6-digit code sent to <span className="font-semibold text-foreground">{email}</span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Verification Failed</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleVerify} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="otp" className="sr-only">One-Time Password</Label>
              <Input
                id="otp"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="000000"
                className="text-center text-3xl tracking-[1rem] font-bold py-8"
                maxLength={6}
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                disabled={loading}
                autoFocus
              />
            </div>
            <Button type="submit" className="w-full py-6 text-lg font-semibold" disabled={loading || otp.length < 6}>
              {loading && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
              {loading ? "Verifying..." : "Verify Code"}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex flex-col gap-4 border-t p-6 bg-slate-50/50">
          <div className="flex items-center justify-between w-full text-sm">
            <button 
              onClick={() => navigate('/login')}
              className="flex items-center text-muted-foreground hover:text-primary transition-colors"
            >
              <ArrowLeft className="mr-1 h-4 w-4" />
              Back to Login
            </button>
            <button 
              onClick={handleResend}
              disabled={loading}
              className="text-primary font-semibold hover:underline disabled:opacity-50"
            >
              Resend Code
            </button>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
};

export default VerifyOTPPage;
