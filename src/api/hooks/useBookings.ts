/**
 * Bookings data hook – cached, with background refresh and retry.
 */

import { useQuery } from "@tanstack/react-query";
import { getBookingHistory } from "@/lib/paymentApi";
import { useAuth } from "@/context/AuthContext";

export const BOOKINGS_QUERY_KEY = ["bookings"] as const;

export function useBookings() {
  const { isAuthenticated } = useAuth();

  return useQuery({
    queryKey: BOOKINGS_QUERY_KEY,
    queryFn: async ({ signal }) => {
      const res = await getBookingHistory(signal);
      if (!res?.success) throw new Error(res?.message || "Failed to load bookings");
      return res.data ?? res.bookings ?? [];
    },
    enabled: isAuthenticated,
    staleTime: 1000 * 60 * 2, // 2 min – bookings list changes less often
  });
}
