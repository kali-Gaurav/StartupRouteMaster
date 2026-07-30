/**
 * useDashboardSummary Hook
 * Fetches and manages dashboard summary statistics
 */

import { useEffect, useState } from 'react';
import { getDashboardSummary, DashboardSummary } from '@/api/dashboardApi';
import { useAuth } from '@/hooks/useAuth';

interface UseDashboardSummaryReturn {
  summary: DashboardSummary | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useDashboardSummary(): UseDashboardSummaryReturn {
  const { token } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async () => {
    if (!token) {
      setError('Authentication required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getDashboardSummary(token);
      setSummary(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch dashboard summary';
      setError(errorMessage);
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [token]);

  return {
    summary,
    loading,
    error,
    refetch: fetchSummary,
  };
}
