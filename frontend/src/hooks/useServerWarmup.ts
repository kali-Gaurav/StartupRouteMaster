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
        // Use fetchWithAuth to ensure it hits the correct backend URL (8000)
        // and uses the /api prefix correctly.
        const res = await fetchWithAuth("/health/live");
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
