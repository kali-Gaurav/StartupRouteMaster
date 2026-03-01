/**
 * Protects routes that require authentication.
 * Redirects to home (or login) when not authenticated; shows optional message.
 */

import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

interface ProtectedRouteProps {
  children: React.ReactNode;
  /** Where to redirect when not authenticated. Default "/". */
  redirectTo?: string;
}

export function ProtectedRoute({ children, redirectTo = "/" }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="w-8 h-8 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to={redirectTo} state={{ from: location, message: "Please log in to continue." }} replace />;
  }

  return <>{children}</>;
}
