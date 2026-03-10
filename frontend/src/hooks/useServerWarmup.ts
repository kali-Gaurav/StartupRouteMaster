import { useQuery } from "@tanstack/react-query";
import { fetchWithAuth } from "@/lib/apiClient";

/**
 * Task 19: Graceful API Degradation Hook.
 * Pings the server to check if it's awake (handles cloud cold starts).
 */
export function useServerWarmup() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["server-warmup"],
    queryFn: async () => {
      try {
        const res = await fetch("/api/status/health/live");
        if (!res.ok) throw new Error("Server not responding");
        return res.json();
      } catch (e) {
        throw e;
      }
    },
    retry: 5,
    retryDelay: (attempt) => Math.min(attempt * 1000, 5000),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  return {
    isWakingUp: isLoading,
    isDown: isError && !isLoading,
    status: data?.status
  };
}
