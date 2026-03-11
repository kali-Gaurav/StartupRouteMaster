import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Loader2 } from 'lucide-react';

interface VerificationGateProps {
  children: React.ReactNode;
}

/**
 * Ensures that the user is verified (Email/Phone) before accessing the page.
 * If not verified, redirects to the OTP verification page.
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

  // If not logged in at all, ProtectedRoute should have caught this, 
  // but we'll return children and let ProtectedRoute handle it.
  if (!isAuthenticated) {
    return <>{children}</>;
  }

  // If logged in but NOT verified
  if (user && !user.isVerified) {
    const contactInfo = user.phone || user.email;
    const paramKey = user.phone ? 'phone' : 'email';
    
    // Redirect to verify-otp with the relevant query param
    return <Navigate to={`/verify-otp?${paramKey}=${encodeURIComponent(contactInfo || '')}`} replace />;
  }

  return <>{children}</>;
};

export default VerificationGate;
