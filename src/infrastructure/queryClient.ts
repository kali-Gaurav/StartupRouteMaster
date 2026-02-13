/**
 * Shared TanStack Query client.
 * Central place for default cache, retry, and stale-while-revalidate behavior.
 */

import { QueryClient } from "@tanstack/react-query";

const STALE_TIME_MS = 1000 * 60 * 5;   // 5 min – data considered fresh
const GC_TIME_MS = 1000 * 60 * 10;     // 10 min – unused data kept in cache
const RETRY_COUNT = 2;
const RETRY_DELAY_MS = 1000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: STALE_TIME_MS,
      gcTime: GC_TIME_MS,
      retry: RETRY_COUNT,
      retryDelay: RETRY_DELAY_MS,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});
