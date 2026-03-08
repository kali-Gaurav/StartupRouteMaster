import { useState, useEffect } from "react";
import { toast } from "@/hooks/use-toast";

/**
 * [45.2] Enhanced Network Status Hook with Toasts and Slow detection.
 */
export function useNetworkStatus() {
  const [online, setOnline] = useState(navigator.onLine);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    // Check for slow connection using Network Information API
    const checkSlow = () => {
      const conn = (navigator as any).connection;
      if (conn) {
        // slow if RTT > 500ms or effective type is 2g/slow-2g
        setSlow(conn.rtt > 500 || ['slow-2g', '2g'].includes(conn.effectiveType));
      }
    };

    const handleOnline = () => {
      setOnline(true);
      toast({
        title: "Back Online",
        description: "Your internet connection has been restored.",
      });
    };

    const handleOffline = () => {
      setOnline(false);
      toast({
        title: "You are Offline",
        description: "Please check your internet connection.",
        variant: "destructive",
      });
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    
    // Initial check
    checkSlow();
    const conn = (navigator as any).connection;
    if (conn) conn.addEventListener('change', checkSlow);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      if (conn) conn.removeEventListener('change', checkSlow);
    };
  }, []);

  return { online, slow };
}
