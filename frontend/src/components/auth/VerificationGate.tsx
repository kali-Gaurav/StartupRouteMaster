import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Loader2, ShieldAlert, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface VerificationGateProps {
  children: React.ReactNode;
}

/**
 * Ensures that the user is verified (Email confirmed) before accessing protected pages.
 * Redirects to the Verify OTP page if email is not confirmed.
 */
export const VerificationGate: React.FC<VerificationGateProps> = ({ children }) => {
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // Allow children if not authenticated (let ProtectedRoute handle auth)
  if (!isAuthenticated) {
    return <>{children}</>;
  }

  // If logged in but NOT verified (no confirmed email)
  if (user && !user.isVerified) {
    // If the user is already on the verify-otp page, don't redirect again
    if (location.pathname === '/verify-otp') {
      return <>{children}</>;
    }

    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50 p-4">
        <div className="w-full max-w-md p-8 bg-white rounded-xl shadow-lg border-t-4 border-t-amber-500 text-center space-y-6">
          <div className="flex justify-center">
            <div className="p-4 bg-amber-50 rounded-full">
              <ShieldAlert className="h-12 w-12 text-amber-500" />
            </div>
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-slate-900">Email Verification Required</h2>
            <p className="text-slate-600">
              Your account at <span className="font-semibold">{user.email}</span> needs to be verified before you can access this feature.
            </p>
          </div>
          
          <div className="flex flex-col gap-3 pt-4">
            <Navigate to={`/verify-otp?email=${encodeURIComponent(user.email || '')}`} replace />
            <Button 
              variant="outline" 
              className="w-full"
              onClick={() => logout()}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Sign Out
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};

export default VerificationGate;
