/**
 * Bookings data hook – cached, with background refresh and retry.
 */

import { useQuery } from "@tanstack/react-query";
import { getBookings } from "@/api/booking";
import { useAuth } from "@/context/AuthContext";

export const BOOKINGS_QUERY_KEY = ["bookings"] as const;

export function useBookings(params?: { skip?: number; limit?: number }) {
  const { isAuthenticated } = useAuth();

  return useQuery({
    queryKey: [...BOOKINGS_QUERY_KEY, params?.skip ?? 0, params?.limit ?? 20],
    queryFn: async ({ signal }) => {
      const res = await getBookings(params, signal);
      return res.bookings ?? [];
    },
    enabled: isAuthenticated,
    staleTime: 1000 * 60 * 2, // 2 min – bookings list changes less often
  });
}
