import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { supabase } from '@/lib/supabase';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Mail, Lock, User, Phone, AlertCircle, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';

const signupSchema = z.object({
  fullName: z.string().min(2, { message: "Full name must be at least 2 characters" }),
  email: z.string().email({ message: "Invalid email address" }),
  password: z.string().min(6, { message: "Password must be at least 6 characters" }),
  confirmPassword: z.string()
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

const phoneSignupSchema = z.object({
  fullName: z.string().min(2, { message: "Full name must be at least 2 characters" }),
  phone: z.string().min(10, { message: "Phone number must be at least 10 digits" }).regex(/^\+?[1-9]\d{1,14}$/, { message: "Invalid phone number format (e.g. +919876543210)" }),
});

type SignupFormValues = z.infer<typeof signupSchema>;
type PhoneSignupFormValues = z.infer<typeof phoneSignupSchema>;

const SignupPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const { register: registerEmail, handleSubmit: handleSubmitEmail, formState: { errors: emailErrors } } = useForm<SignupFormValues>({
    resolver: zodResolver(signupSchema),
  });

  const { register: registerPhone, handleSubmit: handleSubmitPhone, formState: { errors: phoneErrors } } = useForm<PhoneSignupFormValues>({
    resolver: zodResolver(phoneSignupSchema),
  });

  const onEmailSubmit = async (data: SignupFormValues) => {
    setLoading(true);
    setError(null);
    try {
      const { error: authError } = await supabase.auth.signUp({
        email: data.email,
        password: data.password,
        options: {
          data: {
            full_name: data.fullName,
          }
        }
      });

      if (authError) throw authError;

      setSuccess(true);
      toast.success("Account created!", {
        description: "Please check your email to confirm your account.",
      });
    } catch (err: any) {
        console.error("Signup failed:", err);
        setError(err.message || "Failed to create account. Please try again.");
        toast.error("Signup failed", { description: err.message || "Please try again." });
    } finally {
      setLoading(false);
    }
  };

  const onPhoneSubmit = async (data: PhoneSignupFormValues) => {
    setLoading(true);
    setError(null);
    try {
      // For phone, we use OTP directly for registration
      const { error: authError } = await supabase.auth.signInWithOtp({
        phone: data.phone,
        options: {
          data: {
            full_name: data.fullName,
          }
        }
      });

      if (authError) throw authError;

      toast.success("OTP Sent!", {
        description: `A verification code has been sent to ${data.phone}.`,
      });
      navigate(`/verify-otp?phone=${encodeURIComponent(data.phone)}`);
    } catch (err: any) {
        console.error("Phone registration failed:", err);
        setError(err.message || "Failed to start phone registration. Please try again.");
        toast.error("Registration failed", { description: err.message || "Please try again." });
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
        <Card className="w-full max-w-md shadow-xl border-t-4 border-t-green-500 text-center">
          <CardHeader>
            <div className="flex justify-center mb-4">
              <div className="p-3 bg-green-50 rounded-full">
                <CheckCircle2 className="h-12 w-12 text-green-500" />
              </div>
            </div>
            <CardTitle className="text-2xl font-bold">Check your email</CardTitle>
            <CardDescription className="text-base">
              We've sent a confirmation link to your email address. 
              Please verify your account to continue.
            </CardDescription>
          </CardHeader>
          <CardFooter className="flex justify-center p-6 border-t">
            <Button className="w-full" onClick={() => navigate('/login')}>
              Back to Sign In
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 sm:px-6 lg:px-8">
      <Card className="w-full max-w-md shadow-xl border-t-4 border-t-primary">
        <CardHeader className="space-y-1">
          <CardTitle className="text-3xl font-extrabold tracking-tight text-center">Join RouteMaster</CardTitle>
          <CardDescription className="text-center text-base">
            Create an account to start your journey
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Tabs defaultValue="email" className="w-full">
            <TabsList className="grid w-full grid-cols-2 mb-8">
              <TabsTrigger value="email">Email</TabsTrigger>
              <TabsTrigger value="phone">Phone</TabsTrigger>
            </TabsList>

            <TabsContent value="email">
              <form onSubmit={handleSubmitEmail(onEmailSubmit)} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="emailFullName">Full Name</Label>
                  <div className="relative">
                    <User className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="emailFullName"
                      placeholder="John Doe"
                      className="pl-9"
                      {...registerEmail("fullName")}
                      disabled={loading}
                    />
                  </div>
                  {emailErrors.fullName && <p className="text-xs text-destructive mt-1">{emailErrors.fullName.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="email"
                      type="email"
                      placeholder="m@example.com"
                      className="pl-9"
                      {...registerEmail("email")}
                      disabled={loading}
                    />
                  </div>
                  {emailErrors.email && <p className="text-xs text-destructive mt-1">{emailErrors.email.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="password"
                      type="password"
                      className="pl-9"
                      {...registerEmail("password")}
                      disabled={loading}
                    />
                  </div>
                  {emailErrors.password && <p className="text-xs text-destructive mt-1">{emailErrors.password.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">Confirm Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="confirmPassword"
                      type="password"
                      className="pl-9"
                      {...registerEmail("confirmPassword")}
                      disabled={loading}
                    />
                  </div>
                  {emailErrors.confirmPassword && <p className="text-xs text-destructive mt-1">{emailErrors.confirmPassword.message}</p>}
                </div>
                <Button type="submit" className="w-full py-6 text-lg font-semibold" disabled={loading}>
                  {loading && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
                  {loading ? "Creating account..." : "Sign Up with Email"}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="phone">
              <form onSubmit={handleSubmitPhone(onPhoneSubmit)} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="phoneFullName">Full Name</Label>
                  <div className="relative">
                    <User className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="phoneFullName"
                      placeholder="John Doe"
                      className="pl-9"
                      {...registerPhone("fullName")}
                      disabled={loading}
                    />
                  </div>
                  {phoneErrors.fullName && <p className="text-xs text-destructive mt-1">{phoneErrors.fullName.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="phone">Phone Number</Label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="phone"
                      type="tel"
                      placeholder="+919876543210"
                      className="pl-9"
                      {...registerPhone("phone")}
                      disabled={loading}
                    />
                  </div>
                  <p className="text-[10px] text-muted-foreground">Enter number with country code (e.g. +91 for India)</p>
                  {phoneErrors.phone && <p className="text-xs text-destructive mt-1">{phoneErrors.phone.message}</p>}
                </div>
                <Button type="submit" className="w-full py-6 text-lg font-semibold" disabled={loading}>
                  {loading && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
                  {loading ? "Sending OTP..." : "Sign Up with Phone"}
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </CardContent>
        <CardFooter className="flex justify-center border-t p-6 bg-slate-50/50">
          <p className="text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link to="/login" className="font-bold text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
};

export default SignupPage;
