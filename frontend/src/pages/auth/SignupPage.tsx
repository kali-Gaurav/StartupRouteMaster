import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { auth } from '@/lib/firebase';
import { createUserWithEmailAndPassword, updateProfile, sendEmailVerification } from 'firebase/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Loader2, Mail, Lock, User, AlertCircle, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const signupSchema = z.object({
  fullName: z.string().min(2, { message: "Full name must be at least 2 characters" }),
  email: z.string().email({ message: "Invalid email address" }),
  password: z.string().min(6, { message: "Password must be at least 6 characters" }),
  confirmPassword: z.string()
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

type SignupFormValues = z.infer<typeof signupSchema>;

const SignupPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const { register, handleSubmit, formState: { errors } } = useForm<SignupFormValues>({
    resolver: zodResolver(signupSchema),
  });

  const onEmailSubmit = async (data: SignupFormValues) => {
    setLoading(true);
    setError(null);
    try {
      const userCredential = await createUserWithEmailAndPassword(auth, data.email, data.password);
      
      // Update display name
      await updateProfile(userCredential.user, {
        displayName: data.fullName
      });

      // Send verification email
      await sendEmailVerification(userCredential.user);

      setSuccess(true);
      toast.success("Account created!", {
        description: "Please check your email to confirm your account.",
      });
    } catch (err: any) {
        console.error("Signup failed:", err);
        const msg = err.code === 'auth/email-already-in-use' ? 'Email already in use.' : (err.message || "Failed to create account.");
        setError(msg);
        toast.error("Signup failed", { description: msg });
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12 selection:bg-primary selection:text-primary-foreground">
        <Card className="w-full max-w-md shadow-2xl border-t-4 border-t-emerald-500 glass text-center relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-3xl -mr-16 -mt-16" />
          <CardHeader className="space-y-4 pb-8">
            <div className="flex justify-center">
              <div className="p-4 bg-emerald-500/10 rounded-2xl">
                <CheckCircle2 className="h-12 w-12 text-emerald-500" />
              </div>
            </div>
            <CardTitle className="text-3xl font-black tracking-tighter">Check your email</CardTitle>
            <CardDescription className="text-base font-medium">
              We've sent a neural confirmation link to your email. 
              Please verify your identity to continue.
            </CardDescription>
          </CardHeader>
          <CardFooter className="flex justify-center p-8 border-t border-border/50 bg-muted/20">
            <Button className="w-full py-6 rounded-2xl font-black uppercase tracking-widest shadow-xl shadow-primary/20 hover:scale-[1.02] transition-all" onClick={() => navigate('/login')}>
              Back to Terminal Access
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12 sm:px-6 lg:px-8 selection:bg-primary selection:text-primary-foreground">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(var(--primary),0.05),transparent_50%)] pointer-events-none" />
      
      <Card className="w-full max-w-md shadow-2xl border-t-4 border-t-primary glass relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl -mr-16 -mt-16" />
        
        <CardHeader className="space-y-2 pb-8">
          <div className="mx-auto w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center mb-2">
            <User className="w-6 h-6 text-primary" />
          </div>
          <CardTitle className="text-4xl font-black tracking-tighter text-center">Join RouteMaster</CardTitle>
          <CardDescription className="text-center text-base font-medium text-muted-foreground">
            Register your travel identity
          </CardDescription>
        </CardHeader>
        
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-6 bg-destructive/10 border-destructive/20 text-destructive animate-in fade-in slide-in-from-top-1">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle className="font-black uppercase tracking-widest text-[10px]">Registry Alert</AlertTitle>
              <AlertDescription className="font-bold">{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit(onEmailSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="fullName" className="font-black uppercase tracking-widest text-[10px] text-muted-foreground ml-1">Entity Name (Full Name)</Label>
              <div className="relative group">
                <User className="absolute left-4 top-3.5 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                <Input
                  id="fullName"
                  placeholder="Gaurav Nagar"
                  className="pl-12 py-7 rounded-2xl border-2 bg-muted/30 focus:bg-background transition-all font-bold"
                  {...register("fullName")}
                  disabled={loading}
                />
              </div>
              {errors.fullName && <p className="text-[10px] font-black uppercase text-destructive mt-1 ml-1">{errors.fullName.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="font-black uppercase tracking-widest text-[10px] text-muted-foreground ml-1">Terminal ID (Email)</Label>
              <div className="relative group">
                <Mail className="absolute left-4 top-3.5 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                <Input
                  id="email"
                  type="email"
                  placeholder="gaurav@nexus.com"
                  className="pl-12 py-7 rounded-2xl border-2 bg-muted/30 focus:bg-background transition-all font-bold"
                  {...register("email")}
                  disabled={loading}
                />
              </div>
              {errors.email && <p className="text-[10px] font-black uppercase text-destructive mt-1 ml-1">{errors.email.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="font-black uppercase tracking-widest text-[10px] text-muted-foreground ml-1">Secure Code (Password)</Label>
              <div className="relative group">
                <Lock className="absolute left-4 top-3.5 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  className="pl-12 py-7 rounded-2xl border-2 bg-muted/30 focus:bg-background transition-all font-bold"
                  {...register("password")}
                  disabled={loading}
                />
              </div>
              {errors.password && <p className="text-[10px] font-black uppercase text-destructive mt-1 ml-1">{errors.password.message}</p>}
            </div>

            <Button type="submit" className="w-full py-8 text-lg font-black uppercase tracking-widest rounded-2xl shadow-xl shadow-primary/20 hover:scale-[1.01] transition-all" disabled={loading}>
              {loading ? (
                <div className="flex items-center gap-3">
                  <Loader2 className="h-6 w-6 animate-spin" />
                  <span>Registering...</span>
                </div>
              ) : "Initialize Account"}
            </Button>
          </form>
        </CardContent>
        
        <CardFooter className="flex flex-col gap-4 border-t border-border/50 p-8 bg-muted/20">
          <p className="text-sm text-center text-muted-foreground font-bold">
            Already Registered?{" "}
            <Link to="/login" className="text-primary hover:underline font-black uppercase tracking-tighter">
              Secure Login
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
};

export default SignupPage;
