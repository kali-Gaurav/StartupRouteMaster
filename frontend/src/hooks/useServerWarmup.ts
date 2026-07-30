import { useQuery } from "@tanstack/react-query";
import { getRailwayApiUrl } from "@/lib/utils";

/**
 * Pings the backend health endpoint to check if the server is awake.
 * On Render free tier, the server sleeps after 15 min inactivity and takes
 * ~10-20s to wake up on first request.
 *
 * IMPORTANT: This is NON-BLOCKING. The app renders immediately; we only
 * show the warmup screen if PROD + the server is genuinely unreachable after
 * the first attempt (not just slow).
 */
export function useServerWarmup() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["server-warmup"],
    queryFn: async () => {
      const res = await fetch(getRailwayApiUrl("/health"), {
        method: "GET",
        signal: AbortSignal.timeout(8000), // 8s timeout per attempt
      });
      if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
      return res.json();
    },
    retry: 3,
    retryDelay: (attempt) => Math.min(attempt * 2000, 6000), // 2s, 4s, 6s
    staleTime: 1000 * 60 * 2, // cache for 2 min
    // Don't block the UI — only show warmup screen after first failure confirmed
    gcTime: 1000 * 60 * 5,
  });

  return {
    // Only show warmup screen if: production AND still loading AND no data yet
    // This prevents the screen from showing during normal fast loads
    isWakingUp: import.meta.env.PROD && isLoading && !data,
    isDown: isError && !isLoading,
    status: data?.status ?? "unknown",
  };
}
