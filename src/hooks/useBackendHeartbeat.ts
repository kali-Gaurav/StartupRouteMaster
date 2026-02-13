/**
 * Backend Availability Heartbeat Hook
 * Polls /health endpoint to monitor backend status
 * Updates UI automatically when backend goes up/down
 */

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { isBackendAvailable } from "@/services/railwayBackApi";

interface UseBackendHeartbeatOptions {
  enabled?: boolean;
  pollInterval?: number; // milliseconds
  onStatusChange?: (isAvailable: boolean) => void;
}

interface UseBackendHeartbeatResult {
  isAvailable: boolean | null;
  isChecking: boolean;
  lastChecked: Date | null;
}

export function useBackendHeartbeat({
  enabled = true,
  pollInterval = 10000, // 10 seconds default
  onStatusChange,
}: UseBackendHeartbeatOptions = {}): UseBackendHeartbeatResult {
  const [lastStatus, setLastStatus] = useState<boolean | null>(null);

  const { data: isAvailable, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ["backend-health"],
    queryFn: async () => {
      try {
        return await isBackendAvailable();
      } catch {
        return false;
      }
    },
    enabled,
    refetchInterval: pollInterval,
    staleTime: pollInterval / 2, // Consider stale after half the poll interval
    retry: 2,
    retryDelay: 1000,
  });

  // Notify on status change
  useEffect(() => {
    if (typeof isAvailable === "boolean" && isAvailable !== lastStatus) {
      setLastStatus(isAvailable);
      onStatusChange?.(isAvailable);
    }
  }, [isAvailable, lastStatus, onStatusChange]);

  return {
    isAvailable: isAvailable ?? null,
    isChecking: isLoading,
    lastChecked: dataUpdatedAt ? new Date(dataUpdatedAt) : null,
  };
}
