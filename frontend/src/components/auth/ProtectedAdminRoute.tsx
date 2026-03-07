import React from "react";
import { Navigate } from "react-router-dom";

/**
 * Task 1.5: Protected route for Admin Ops and Analytics.
 * Checks for admin_token in localStorage.
 */
export default function ProtectedAdminRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("admin_token");
  
  // In a real prod app, we would validate the token with the server here
  // or decode it to check expiry.
  
  if (!token) {
    return <Navigate to="/admin/auth" replace />;
  }

  return <>{children}</>;
}
