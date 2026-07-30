/**
 * Shared full-page loading state for consistent UX.
 */

import { Loader2 } from "lucide-react";

interface LoadingScreenProps {
  message?: string;
  className?: string;
}

export function LoadingScreen({ message = "Loading...", className }: LoadingScreenProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center min-h-[40vh] text-muted-foreground ${className ?? ""}`}
      role="status"
      aria-live="polite"
      aria-label={message}
    >
      <Loader2 className="w-12 h-12 animate-spin mb-4" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
