/**
 * Global network status: show a subtle banner when offline or slow.
 */

import { useNetworkStatus } from "@/hooks/useNetworkStatus";
import { WifiOff, AlertCircle } from "lucide-react";

export function NetworkStatusBanner() {
  const { online, slow } = useNetworkStatus();

  if (online && !slow) return null;

  return (
    <div
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-2 px-4 py-2 rounded-lg shadow-lg bg-foreground text-background text-sm font-medium"
      role="status"
      aria-live="polite"
    >
      {!online ? (
        <>
          <WifiOff className="w-4 h-4 shrink-0" />
          <span>You're offline. Some features may be unavailable.</span>
        </>
      ) : slow ? (
        <>
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>Connection is slow. Responses may be delayed.</span>
        </>
      ) : null}
    </div>
  );
}
