/**
 * useUserBookings Hook
 * Fetches and manages user booking history with filtering and pagination
 */

import { useEffect, useState } from 'react';
import { getUserBookings, BookingsResponse } from '@/api/dashboardApi';
import { useAuth } from '@/hooks/useAuth';

interface UseUserBookingsOptions {
  limit?: number;
  offset?: number;
  statusFilter?: string;
}

interface UseUserBookingsReturn extends BookingsResponse {
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  setPage: (offset: number) => void;
  setStatusFilter: (status: string | undefined) => void;
}

export function useUserBookings(options: UseUserBookingsOptions = {}): UseUserBookingsReturn {
  const { token } = useAuth();
  const [limit, setLimit] = useState(options.limit || 50);
  const [offset, setOffset] = useState(options.offset || 0);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(options.statusFilter);
  const [bookings, setBookings] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBookings = async () => {
    if (!token) {
      setError('Authentication required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getUserBookings(token, limit, offset, statusFilter);
      setBookings(data.bookings);
      setTotal(data.total);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch bookings';
      setError(errorMessage);
      setBookings([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBookings();
  }, [token, limit, offset, statusFilter]);

  return {
    bookings,
    total,
    limit,
    offset,
    loading,
    error,
    refetch: fetchBookings,
    setPage: setOffset,
    setStatusFilter,
  };
}
