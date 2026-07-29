/**
 * useUserPayments Hook
 * Fetches and manages user payment history with pagination
 */

import { useEffect, useState } from 'react';
import { getUserPayments, PaymentsResponse } from '@/api/dashboardApi';
import { useAuth } from '@/hooks/useAuth';

interface UseUserPaymentsOptions {
  limit?: number;
  offset?: number;
}

interface UseUserPaymentsReturn extends PaymentsResponse {
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  setPage: (offset: number) => void;
}

export function useUserPayments(options: UseUserPaymentsOptions = {}): UseUserPaymentsReturn {
  const { token } = useAuth();
  const [limit, setLimit] = useState(options.limit || 50);
  const [offset, setOffset] = useState(options.offset || 0);
  const [payments, setPayments] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPayments = async () => {
    if (!token) {
      setError('Authentication required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getUserPayments(token, limit, offset);
      setPayments(data.payments);
      setTotal(data.total);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch payments';
      setError(errorMessage);
      setPayments([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPayments();
  }, [token, limit, offset]);

  return {
    payments,
    total,
    limit,
    offset,
    loading,
    error,
    refetch: fetchPayments,
    setPage: setOffset,
  };
}
