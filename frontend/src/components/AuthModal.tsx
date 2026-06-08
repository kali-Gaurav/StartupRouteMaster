/**
 * Authentication Modal
 * Handles Phone, Email, and Google OAuth using Firebase
 */

import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { auth } from '@/lib/firebase';
import { 
  signInWithPopup, 
  GoogleAuthProvider, 
  signInWithEmailAndPassword,
  RecaptchaVerifier,
  signInWithPhoneNumber
} from 'firebase/auth';
import { Loader2, Phone, Mail, CheckCircle2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ open, onClose, onSuccess }) => {
  const [authMethod, setAuthMethod] = useState<'phone' | 'email'>('phone');
  const [step, setStep] = useState<'input' | 'verify'>('input');
  const [contact, setContact] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [confirmationResult, setConfirmationResult] = useState<any>(null);

  const resetForm = () => {
    setStep('input');
    setContact('');
    setOtp('');
    setError('');
    setMessage('');
    setConfirmationResult(null);
  };

  const setupRecaptcha = () => {
    if (!(window as any).recaptchaVerifier) {
      (window as any).recaptchaVerifier = new RecaptchaVerifier(auth, 'recaptcha-container', {
        'size': 'invisible',
        'callback': () => {}
      });
    }
  };

  const handleSendOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setLoading(true);
    
    try {
      if (authMethod === 'phone') {
        setupRecaptcha();
        const appVerifier = (window as any).recaptchaVerifier;
        const result = await signInWithPhoneNumber(auth, contact, appVerifier);
        setConfirmationResult(result);
        setMessage('OTP sent to your phone.');
        setStep('verify');
      } else {
        // For email in this modal, we'll suggest using the full login page or implement a quick password login
        setError('Please use the dedicated Login page for email access.');
      }
    } catch (err: any) {
      console.error('OTP Error:', err);
      setError(err.message || 'Failed to send OTP');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      if (confirmationResult) {
        await confirmationResult.confirm(otp);
        setMessage('Login successful!');
        setTimeout(() => {
          onClose();
          resetForm();
          onSuccess?.();
        }, 1000);
      }
    } catch (err: any) {
      setError(err.message || 'Invalid OTP');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleAuth = async () => {
    setLoading(true);
    setError('');
    try {
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
      onClose();
      onSuccess?.();
    } catch (err: any) {
      setError(err.message || 'Google authentication failed');
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
        <div id="recaptcha-container"></div>
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold text-center">
            Welcome to RouteMaster
          </DialogTitle>
          <DialogDescription className="text-center">
            Sign in to access your bookings and travel assistant
          </DialogDescription>
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
                </div>

                {error && (
                  <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md flex items-start gap-2">
                    <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : 'Send OTP'}
                </Button>
              </form>
            ) : (
              <form onSubmit={handleVerifyOTP} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="otp">Enter OTP</Label>
                  <Input
                    id="otp"
                    type="text"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    required
                    disabled={loading}
                  />
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : 'Verify OTP'}
                </Button>
              </form>
            )}
          </TabsContent>

          <TabsContent value="email" className="space-y-4 mt-6 text-center">
            <p className="text-sm text-muted-foreground">
              Please use the dedicated login page for email and password access.
            </p>
            <Button variant="outline" className="w-full" onClick={() => window.location.href = '/login'}>
              Go to Login Page
            </Button>
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

        <Button variant="outline" onClick={handleGoogleAuth} className="w-full" disabled={loading}>
          Google
        </Button>
      </DialogContent>
    </Dialog>
  );
};
