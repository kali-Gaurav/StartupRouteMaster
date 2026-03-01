/**
 * Network status for global offline/slow indicator.
 */

import { useState, useEffect } from "react";

export interface NetworkStatus {
  online: boolean;
  /** True when navigator.connection suggests slow (e.g. 4g or reduced). */
  slow?: boolean;
}

/**
 * Subscribe to online/offline and optionally effective connection type.
 * Use with NetworkStatusBanner for consistent UX.
 */
export function useNetworkStatus(): NetworkStatus {
  const [online, setOnline] = useState(
    typeof navigator !== "undefined" ? navigator.onLine : true
  );
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    setOnline(navigator.onLine);

    // @ts-expect-error - connection is not in all TS libs
    const conn = navigator.connection ?? navigator.mozConnection ?? navigator.webkitConnection;
    if (conn) {
      const updateSlow = () => {
        const effective = conn.effectiveType;
        setSlow(effective === "slow-2g" || effective === "2g" || conn.saveData === true);
      };
      conn.addEventListener("change", updateSlow);
      updateSlow();
      return () => {
        window.removeEventListener("online", handleOnline);
        window.removeEventListener("offline", handleOffline);
        conn.removeEventListener("change", updateSlow);
      };
    }

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return { online, slow };
}
