/**
 * Intelligent Railway Search Hook
 * Handles route source switching, auto-retry, and error handling
 */

import { useState, useCallback } from "react";
import { searchRoutesApi, mapBackendRoutesToRoutes, isBackendAvailable } from "@/services/railwayBackApi";
import { getCachedRoutes, normalizeDate } from "@/data/cachedRoutes";
import type { Route } from "@/data/routes";
import type { RouteSource } from "@/components/RouteSourceToggle";

interface UseRailwaySearchOptions {
  routeSource: RouteSource;
  onError?: (error: Error) => void;
  onSuccess?: (routes: Route[]) => void;
}

interface UseRailwaySearchResult {
  search: (
    source: string,
    destination: string,
    date?: string,
    options?: {
      maxTransfers?: number;
      maxResults?: number;
      sortBy?: string;
    }
  ) => Promise<Route[]>;
  isSearching: boolean;
  error: Error | null;
  lastSearchSource: RouteSource | null;
}

export function useRailwaySearch({
  routeSource,
  onError,
  onSuccess,
}: UseRailwaySearchOptions): UseRailwaySearchResult {
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [lastSearchSource, setLastSearchSource] = useState<RouteSource | null>(null);

  const search = useCallback(
    async (
      source: string,
      destination: string,
      date?: string,
      options?: {
        maxTransfers?: number;
        maxResults?: number;
        sortBy?: string;
      }
    ): Promise<Route[]> => {
      setIsSearching(true);
      setError(null);
      const sourceCode = source.toUpperCase().trim();
      const destCode = destination.toUpperCase().trim();
      const normalizedDate = normalizeDate(date || new Date().toISOString().slice(0, 10));

      try {
        // Strategy 1: If cached mode, try local cache first
        if (routeSource === "cached") {
          const cached = getCachedRoutes(sourceCode, destCode, normalizedDate);
          if (cached) {
            const routes = mapBackendRoutesToRoutes(cached, sourceCode, destCode);
            setLastSearchSource("cached");
            onSuccess?.(routes);
            return routes;
          }
          throw new Error("No cached routes available for this search");
        }

        // Strategy 2: Live mode - try backend
        try {
          const data = await searchRoutesApi(sourceCode, destCode, options?.maxTransfers || 2, options?.maxResults || 50, {
            date: normalizedDate,
            routeSource: "live",
            sortBy: (options?.sortBy || "duration") as "duration" | "cost" | "score",
          });

          const routes = mapBackendRoutesToRoutes(data, sourceCode, destCode);
          setLastSearchSource("live");
          onSuccess?.(routes);
          return routes;
        } catch (liveError) {
          // Strategy 3: Auto-retry with cached if live fails
          const backendAvailable = await isBackendAvailable();
          if (!backendAvailable) {
            // Backend is down, try cached as fallback
            const cached = getCachedRoutes(sourceCode, destCode, normalizedDate);
            if (cached) {
              const routes = mapBackendRoutesToRoutes(cached, sourceCode, destCode);
              setLastSearchSource("cached");
              onSuccess?.(routes);
              return routes;
            }
          }
          throw liveError;
        }
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err));
        setError(error);
        onError?.(error);
        throw error;
      } finally {
        setIsSearching(false);
      }
    },
    [routeSource, onError, onSuccess]
  );

  return {
    search,
    isSearching,
    error,
    lastSearchSource,
  };
}
