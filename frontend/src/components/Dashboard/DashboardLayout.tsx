/**
 * Dashboard Layout Component
 * Provides the main layout structure for the user dashboard
 */

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface DashboardLayoutProps {
  children: ReactNode;
  className?: string;
  sidebar?: ReactNode;
}

export function DashboardLayout({ children, className, sidebar }: DashboardLayoutProps) {
  return (
    <div className={cn("grid grid-cols-1 lg:grid-cols-3 gap-8", className)}>
      <div className="lg:col-span-2">
        {children}
      </div>
      {sidebar && (
        <div className="lg:col-span-1">
          {sidebar}
        </div>
      )}
    </div>
  );
}

export default DashboardLayout;
