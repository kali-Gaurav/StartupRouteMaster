/**
 * Authentication Modal
 * Handles Phone OTP, Email OTP, and Google OAuth
 */

import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { sendOTP, verifyOTP, googleAuth } from '@/lib/authApi';
import { useAuth } from '@/context/AuthContext';
import { sendOTPSchema, verifyOTPSchema } from '@/lib/schemas/authSchema';
import { Loader2, Phone, Mail, CheckCircle2 } from 'lucide-react';

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ open, onClose, onSuccess }) => {
  const { login } = useAuth();
  const [authMethod, setAuthMethod] = useState<'phone' | 'email'>('phone');
  const [step, setStep] = useState<'input' | 'verify'>('input');
  const [contact, setContact] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const resetForm = () => {
    setStep('input');
    setContact('');
    setOtp('');
    setError('');
    setMessage('');
  };

  const handleSendOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    const data = authMethod === 'phone' ? { phone: contact } : { email: contact };
    const parsed = sendOTPSchema.safeParse(data);
    if (!parsed.success) {
      const first = parsed.error.flatten().fieldErrors?.phone?.[0] ?? parsed.error.flatten().fieldErrors?.email?.[0] ?? parsed.error.message;
      setError(first ?? 'Invalid input');
      return;
    }
    setLoading(true);
    try {
      const response = await sendOTP(parsed.data);

      if (response.success) {
        setMessage(response.message);
        setStep('verify');
      } else {
        setError(response.message || 'Failed to send OTP');
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Network error. Please try again.';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const data = authMethod === 'phone' ? { phone: contact, otp } : { email: contact, otp };
    const parsed = verifyOTPSchema.safeParse(data);
    if (!parsed.success) {
      const first = parsed.error.flatten().fieldErrors?.otp?.[0] ?? parsed.error.message;
      setError(first ?? 'Invalid OTP');
      return;
    }
    setLoading(true);
    try {
      const response = await verifyOTP(parsed.data);

      if (response.success && response.token && response.user) {
        login(response.token, response.user, response.refresh_token);
        setMessage('Login successful!');
        
        setTimeout(() => {
          onClose();
          resetForm();
          onSuccess?.();
        }, 1000);
      } else {
        setError(response.message || 'Invalid OTP');
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Network error. Please try again.';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleAuth = async () => {
    setLoading(true);
    setError('');
    try {
      // Simulate Google OAuth popup and token reception
      console.log('Opening Google OAuth popup...');
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      const mockIdToken = 'mock_google_token_' + Math.random().toString(36).substring(7);
      const response = await googleAuth(mockIdToken);

      if (response.success && response.token && response.user) {
        login(response.token, response.user, response.refresh_token);
        setMessage('Google login successful!');
        
        setTimeout(() => {
          onClose();
          resetForm();
          onSuccess?.();
        }, 1000);
      } else {
        setError(response.message || 'Google authentication failed');
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Google authentication error. Please try again.';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleResendOTP = async () => {
    setOtp('');
    setError('');
    setMessage('');
    setLoading(true);

    try {
      const data = authMethod === 'phone' ? { phone: contact } : { email: contact };
      const response = await sendOTP(data);

      if (response.success) {
        setMessage('OTP resent successfully!');
      } else {
        setError(response.message || 'Failed to resend OTP');
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Network error. Please try again.';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      resetForm();
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold text-center">
            Welcome to Railway Manager
          </DialogTitle>
        </DialogHeader>

        <Tabs value={authMethod} onValueChange={(v: string) => setAuthMethod(v as 'phone' | 'email')} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="phone" className="flex items-center gap-2">
              <Phone className="h-4 w-4" />
              Phone
            </TabsTrigger>
            <TabsTrigger value="email" className="flex items-center gap-2">
              <Mail className="h-4 w-4" />
              Email
            </TabsTrigger>
          </TabsList>

          <TabsContent value="phone" className="space-y-4 mt-6">
            {step === 'input' ? (
              <form onSubmit={handleSendOTP} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="phone">Phone Number</Label>
                  <Input
                    id="phone"
                    type="tel"
                    placeholder="+91 9876543210"
                    value={contact}
                    onChange={(e) => setContact(e.target.value)}
                    required
                    disabled={loading}
                  />
                  <p className="text-xs text-muted-foreground">
                    Enter your phone number with country code
                  </p>
                </div>

                {error && (
                  <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
                    {error}
                  </div>
                )}

                {message && (
                  <div className="text-sm text-green-600 bg-green-50 p-3 rounded-md flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4" />
                    {message}
                  </div>
                )}

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending OTP...
                    </>
                  ) : (
                    'Send OTP'
                  )}
                </Button>
              </form>
            ) : (
              <form onSubmit={handleVerifyOTP} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="otp">Enter OTP</Label>
                  <Input
                    id="otp"
                    type="text"
                    placeholder="123456"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    required
                    maxLength={6}
                    disabled={loading}
                    autoFocus
                  />
                  <p className="text-xs text-muted-foreground">
                    OTP sent to {contact}
                  </p>
                </div>

                {error && (
                  <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
                    {error}
                  </div>
                )}

                {message && (
                  <div className="text-sm text-green-600 bg-green-50 p-3 rounded-md flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4" />
                    {message}
                  </div>
                )}

                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setStep('input')}
                    disabled={loading}
                    className="flex-1"
                  >
                    Back
                  </Button>
                  <Button type="submit" className="flex-1" disabled={loading}>
                    {loading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Verifying...
                      </>
                    ) : (
                      'Verify OTP'
                    )}
                  </Button>
                </div>

                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleResendOTP}
                  disabled={loading}
                  className="w-full text-sm"
                >
                  Didn't receive? Resend OTP
                </Button>
              </form>
            )}
          </TabsContent>

          <TabsContent value="email" className="space-y-4 mt-6">
            {step === 'input' ? (
              <form onSubmit={handleSendOTP} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={contact}
                    onChange={(e) => setContact(e.target.value)}
                    required
                    disabled={loading}
                  />
                </div>

                {error && (
                  <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
                    {error}
                  </div>
                )}

                {message && (
                  <div className="text-sm text-green-600 bg-green-50 p-3 rounded-md flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4" />
                    {message}
                  </div>
                )}

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending OTP...
                    </>
                  ) : (
                    'Send OTP'
                  )}
                </Button>
              </form>
            ) : (
              <form onSubmit={handleVerifyOTP} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="otp-email">Enter OTP</Label>
                  <Input
                    id="otp-email"
                    type="text"
                    placeholder="123456"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    required
                    maxLength={6}
                    disabled={loading}
                    autoFocus
                  />
                  <p className="text-xs text-muted-foreground">
                    OTP sent to {contact}
                  </p>
                </div>

                {error && (
                  <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
                    {error}
                  </div>
                )}

                {message && (
                  <div className="text-sm text-green-600 bg-green-50 p-3 rounded-md flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4" />
                    {message}
                  </div>
                )}

                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setStep('input')}
                    disabled={loading}
                    className="flex-1"
                  >
                    Back
                  </Button>
                  <Button type="submit" className="flex-1" disabled={loading}>
                    {loading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Verifying...
                      </>
                    ) : (
                      'Verify OTP'
                    )}
                  </Button>
                </div>

                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleResendOTP}
                  disabled={loading}
                  className="w-full text-sm"
                >
                  Didn't receive? Resend OTP
                </Button>
              </form>
            )}
          </TabsContent>
        </Tabs>

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-background px-2 text-muted-foreground">Or continue with</span>
          </div>
        </div>

        <Button
          variant="outline"
          onClick={handleGoogleAuth}
          className="w-full"
          disabled={loading}
        >
          <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="currentColor"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="currentColor"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="currentColor"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          Google
        </Button>

        <p className="text-xs text-center text-muted-foreground mt-4">
          By continuing, you agree to our Terms of Service and Privacy Policy
        </p>
      </DialogContent>
    </Dialog>
  );
};
