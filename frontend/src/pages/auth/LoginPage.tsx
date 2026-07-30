import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { auth } from '@/lib/firebase';
import { signInWithEmailAndPassword, signInWithPopup, GoogleAuthProvider, GithubAuthProvider } from 'firebase/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Loader2, Mail, Lock, AlertCircle, Github } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const loginSchema = z.object({
  email: z.string().email({ message: "Invalid email address" }),
  password: z.string().min(6, { message: "Password must be at least 6 characters" }),
});

type LoginFormValues = z.infer<typeof loginSchema>;

const LoginPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { register, handleSubmit, formState: { errors } } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const onEmailSubmit = async (data: LoginFormValues) => {
    setLoading(true);
    setError(null);
    try {
      await signInWithEmailAndPassword(auth, data.email, data.password);

      toast.success("Welcome back!", {
        description: "You have successfully signed in.",
      });
      navigate('/dashboard');
    } catch (err: any) {
        console.error("Login failed:", err);
        const msg = err.code === 'auth/invalid-credential' ? 'Invalid email or password.' : (err.message || "Failed to sign in.");
        setError(msg);
        toast.error("Login failed", { description: msg });
    } finally {
      setLoading(false);
    }
  };

  const handleSocialLogin = async (provider: 'google' | 'github') => {
    setLoading(true);
    try {
      const authProvider = provider === 'google' ? new GoogleAuthProvider() : new GithubAuthProvider();
      await signInWithPopup(auth, authProvider);
      navigate('/dashboard');
    } catch (err: any) {
      toast.error(`${provider} login failed`, { description: err.message });
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12 sm:px-6 lg:px-8 selection:bg-primary selection:text-primary-foreground">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(var(--primary),0.05),transparent_50%)] pointer-events-none" />
      
      <Card className="w-full max-w-md shadow-2xl border-t-4 border-t-primary glass relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl -mr-16 -mt-16" />
        
        <CardHeader className="space-y-2 pb-8">
          <div className="mx-auto w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center mb-2">
            <Lock className="w-6 h-6 text-primary" />
          </div>
          <CardTitle className="text-4xl font-black tracking-tighter text-center text-foreground">RouteMaster</CardTitle>
          <CardDescription className="text-center text-base font-medium text-muted-foreground">
            Neural Authentication Gateway
          </CardDescription>
        </CardHeader>
        
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-6 bg-destructive/10 border-destructive/20 text-destructive animate-in fade-in slide-in-from-top-1">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle className="font-black uppercase tracking-widest text-[10px]">Security Alert</AlertTitle>
              <AlertDescription className="font-bold">{error}</AlertDescription>
            </Alert>
          )}

          <div className="grid grid-cols-2 gap-4 mb-8">
            <Button variant="outline" className="w-full py-6 font-bold rounded-2xl border-2 hover:bg-primary/5 transition-all" onClick={() => handleSocialLogin('google')} disabled={loading}>
               <svg className="mr-2 h-5 w-5" viewBox="0 0 24 24">
                 <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                 <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                 <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                 <path d="M12 5.38c1.62 0 3.06.56 4.21 1.66l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 12-4.53z" fill="#EA4335" />
               </svg>
               Google
            </Button>
            <Button variant="outline" className="w-full py-6 font-bold rounded-2xl border-2 hover:bg-primary/5 transition-all" onClick={() => handleSocialLogin('github')} disabled={loading}>
               <Github className="mr-2 h-5 w-5" />
               GitHub
            </Button>
          </div>

          <div className="relative mb-8">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-[10px] uppercase font-black tracking-widest">
              <span className="bg-card px-4 text-muted-foreground">Neural Uplink</span>
            </div>
          </div>

          <form onSubmit={handleSubmit(onEmailSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="email" className="font-black uppercase tracking-widest text-[10px] text-muted-foreground ml-1">Terminal ID (Email)</Label>
              <div className="relative group">
                <Mail className="absolute left-4 top-3.5 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                <Input
                  id="email"
                  type="email"
                  placeholder="name@nexus.com"
                  className="pl-12 py-7 rounded-2xl border-2 bg-muted/30 focus:bg-background transition-all font-bold"
                  {...register("email")}
                  disabled={loading}
                />
              </div>
              {errors.email && <p className="text-[10px] font-black uppercase text-destructive mt-1 ml-1">{errors.email.message}</p>}
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between ml-1">
                <Label htmlFor="password" className="font-black uppercase tracking-widest text-[10px] text-muted-foreground">Access Code</Label>
                <Link to="/forgot-password" size="sm" className="text-[10px] font-black uppercase tracking-widest text-primary hover:text-primary/80 transition-colors">
                  Reset Protocol
                </Link>
              </div>
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
            <Button type="submit" className="w-full py-8 text-lg font-black uppercase tracking-widest rounded-2xl shadow-xl shadow-primary/20 hover:scale-[1.01] active:scale-[0.99] transition-all" disabled={loading}>
              {loading ? (
                <div className="flex items-center gap-3">
                  <Loader2 className="h-6 w-6 animate-spin" />
                  <span>Authorizing...</span>
                </div>
              ) : "Initialize Session"}
            </Button>
          </form>
        </CardContent>
        
        <CardFooter className="flex flex-col gap-4 border-t border-border/50 p-8 bg-muted/20">
          <p className="text-sm text-center text-muted-foreground font-bold">
            Unauthorized?{" "}
            <Link to="/signup" className="text-primary hover:underline font-black uppercase tracking-tighter">
              Register New Entity
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
};

export default LoginPage;
