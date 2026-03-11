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
import { Loader2, Mail, Lock, Phone, AlertCircle, Github } from 'lucide-react';
import { toast } from 'sonner';

const loginSchema = z.object({
  email: z.string().email({ message: "Invalid email address" }),
  password: z.string().min(6, { message: "Password must be at least 6 characters" }),
});

const phoneSchema = z.object({
  phone: z.string().min(10, { message: "Phone number must be at least 10 digits" }).regex(/^\+?[1-9]\d{1,14}$/, { message: "Invalid phone number format (e.g. +919876543210)" }),
});

type LoginFormValues = z.infer<typeof loginSchema>;
type PhoneFormValues = z.infer<typeof phoneSchema>;

const LoginPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { register: registerEmail, handleSubmit: handleSubmitEmail, formState: { errors: emailErrors } } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const { register: registerPhone, handleSubmit: handleSubmitPhone, formState: { errors: phoneErrors } } = useForm<PhoneFormValues>({
    resolver: zodResolver(phoneSchema),
  });

  const onEmailSubmit = async (data: LoginFormValues) => {
    setLoading(true);
    setError(null);
    try {
      const { error: authError } = await supabase.auth.signInWithPassword({
        email: data.email,
        password: data.password,
      });

      if (authError) throw authError;

      toast.success("Welcome back!", {
        description: "You have successfully signed in.",
      });
      navigate('/dashboard');
    } catch (err: any) {
        console.error("Login failed:", err);
        setError(err.message || "Failed to sign in. Please check your credentials.");
        toast.error("Login failed", { description: err.message || "Please try again." });
    } finally {
      setLoading(false);
    }
  };

  const onPhoneSubmit = async (data: PhoneFormValues) => {
    setLoading(true);
    setError(null);
    try {
      const { error: authError } = await supabase.auth.signInWithOtp({
        phone: data.phone,
      });

      if (authError) throw authError;

      toast.success("OTP Sent!", {
        description: `A verification code has been sent to ${data.phone}.`,
      });
      navigate(`/verify-otp?phone=${encodeURIComponent(data.phone)}`);
    } catch (err: any) {
        console.error("OTP request failed:", err);
        setError(err.message || "Failed to send OTP. Please try again.");
        toast.error("OTP failed", { description: err.message || "Please try again." });
    } finally {
      setLoading(false);
    }
  };

  const handleSocialLogin = async (provider: 'google' | 'github') => {
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider,
        options: {
          redirectTo: `${window.location.origin}/dashboard`,
        }
      });
      if (error) throw error;
    } catch (err: any) {
      toast.error(`${provider} login failed`, { description: err.message });
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 sm:px-6 lg:px-8">
      <Card className="w-full max-w-md shadow-xl border-t-4 border-t-primary">
        <CardHeader className="space-y-1">
          <CardTitle className="text-3xl font-extrabold tracking-tight text-center">RouteMaster</CardTitle>
          <CardDescription className="text-center text-base">
            Your high-performance travel companion
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
              <TabsTrigger value="phone">Phone (OTP)</TabsTrigger>
            </TabsList>

            <TabsContent value="email">
              <form onSubmit={handleSubmitEmail(onEmailSubmit)} className="space-y-4">
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
                  <div className="flex items-center justify-between">
                    <Label htmlFor="password">Password</Label>
                    <Link to="/forgot-password" size="sm" className="text-xs font-medium text-primary hover:underline">
                      Forgot password?
                    </Link>
                  </div>
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
                <Button type="submit" className="w-full py-6 text-lg font-semibold" disabled={loading}>
                  {loading && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
                  {loading ? "Signing in..." : "Sign In"}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="phone">
              <form onSubmit={handleSubmitPhone(onPhoneSubmit)} className="space-y-4">
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
                  {loading ? "Sending OTP..." : "Send Verification Code"}
                </Button>
              </form>
            </TabsContent>
          </Tabs>
          
          <div className="relative mt-8">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-2 text-muted-foreground font-medium">Fast Access</span>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-4">
            <Button variant="outline" className="w-full py-5" onClick={() => handleSocialLogin('google')} disabled={loading}>
               <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
                 <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                 <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                 <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                 <path d="M12 5.38c1.62 0 3.06.56 4.21 1.66l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 12-4.53z" fill="#EA4335" />
               </svg>
               Google
            </Button>
            <Button variant="outline" className="w-full py-5" onClick={() => handleSocialLogin('github')} disabled={loading}>
               <Github className="mr-2 h-4 w-4" />
               GitHub
            </Button>
          </div>
        </CardContent>
        <CardFooter className="flex flex-col gap-4 border-t p-6 bg-slate-50/50">
          <p className="text-sm text-center text-muted-foreground w-full">
            New to RouteMaster?{" "}
            <Link to="/signup" className="font-bold text-primary hover:underline">
              Create an account
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
};

export default LoginPage;
