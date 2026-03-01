/**
 * Query invalidation strategy: which mutations invalidate which caches.
 * Use after mutations so UI shows fresh data without manual refetch.
 *
 * Invalidation rules:
 * - invalidateBookingsCache: after createBookingRedirect (payment success), cancel booking.
 * - invalidateSearchCache: after admin updates stations (if ever).
 */
import { queryClient } from "@/infrastructure/queryClient";
import { getBookingHistory } from "@/lib/paymentApi";
import { BOOKINGS_QUERY_KEY } from "@/api/hooks/useBookings";
import { STATIONS_QUERY_KEY } from "@/api/hooks/useStations";

/** Invalidate bookings list (e.g. after create booking, cancel, or payment). */
export function invalidateBookingsCache(): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: BOOKINGS_QUERY_KEY });
}

/** Prefetch bookings so the My Bookings page feels instant (e.g. on nav link hover). Call only when authenticated. Guards against prefetch storms: skips if cache already has fresh data. */
export function prefetchBookings(): void {
  const state = queryClient.getQueryState(BOOKINGS_QUERY_KEY);
  if (state?.dataUpdatedAt && state.dataUpdatedAt > 0) {
    const staleTime = 1000 * 60 * 2;
    if (Date.now() - state.dataUpdatedAt < staleTime) return;
  }
  queryClient.prefetchQuery({
    queryKey: BOOKINGS_QUERY_KEY,
    queryFn: async () => {
      const res = await getBookingHistory() as any;
      if (!res?.success) throw new Error(res?.message || "Failed to load bookings");
      return res.bookings ?? [];
    },
    staleTime: 1000 * 60 * 2,
  });
}

/** Invalidate station search cache (e.g. after admin updates stations). */
export function invalidateSearchCache(): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: [STATIONS_QUERY_KEY] });
}

/** Invalidate all search-related caches (stations + any route cache keys if added later). */
export function invalidateAllSearchCache(): Promise<void> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: [STATIONS_QUERY_KEY] }),
  ]).then(() => undefined);
}
