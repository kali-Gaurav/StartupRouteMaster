/**
 * useSavedRoutes Hook
 * Manages user's saved routes (both from API and localStorage)
 */

import { useEffect, useState } from 'react';
import { getSavedRoutes, SavedRoute } from '@/api/dashboardApi';
import { useAuth } from '@/hooks/useAuth';

interface UseSavedRoutesReturn {
  routes: SavedRoute[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  addRoute: (route: SavedRoute) => void;
  removeRoute: (routeId: string) => void;
}

export function useSavedRoutes(): UseSavedRoutesReturn {
  const { token } = useAuth();
  const [routes, setRoutes] = useState<SavedRoute[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRoutes = async () => {
    if (!token) {
      // Load from localStorage if not authenticated
      try {
        const saved = localStorage.getItem('saved_routes');
        setRoutes(saved ? JSON.parse(saved) : []);
      } catch {
        setRoutes([]);
      }
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getSavedRoutes(token);
      setRoutes(data.routes);
      // Sync to localStorage
      localStorage.setItem('saved_routes', JSON.stringify(data.routes));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch saved routes';
      setError(errorMessage);
      // Fall back to localStorage
      try {
        const saved = localStorage.getItem('saved_routes');
        setRoutes(saved ? JSON.parse(saved) : []);
      } catch {
        setRoutes([]);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRoutes();
  }, [token]);

  const addRoute = (route: SavedRoute) => {
    const updated = [...routes, route];
    setRoutes(updated);
    localStorage.setItem('saved_routes', JSON.stringify(updated));
  };

  const removeRoute = (routeId: string) => {
    const updated = routes.filter(r => r.id !== routeId);
    setRoutes(updated);
    localStorage.setItem('saved_routes', JSON.stringify(updated));
  };

  return {
    routes,
    loading,
    error,
    refetch: fetchRoutes,
    addRoute,
    removeRoute,
  };
}
