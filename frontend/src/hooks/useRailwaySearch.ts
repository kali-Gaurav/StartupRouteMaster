/**
 * Intelligent Railway Search Hook
 * Handles route source switching, auto-retry, streaming, and error handling.
 * [Point 18 & 30] Now attempts Zero-Block SSE streaming first in live mode.
 */

import { useState, useCallback } from "react";
import { searchRoutesApi, loadMoreRoutesApi, mapBackendRoutesToRoutes, isBackendAvailable } from "@/services/railwayBackApi";
import { getCachedRoutes, normalizeDate } from "@/data/cachedRoutes";
import type { Route } from "@/data/routes";
import type { RouteSource } from "@/components/RouteSourceToggle";
import { useStreamingSearch } from "./useStreamingSearch";

interface UseRailwaySearchOptions {
  routeSource: RouteSource;
  onError?: (error: Error) => void;
  onSuccess?: (routes: Route[], suggestions?: any[]) => void;
  /** Called each time a new streaming chunk arrives (for progressive UI) */
  onProgressiveResults?: (routes: Route[]) => void;
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
      useStream?: boolean; // Opt-in to SSE progressive mode
      engineModel?: string;
    }
  ) => Promise<Route[]>;
  isSearching: boolean;
  isStreaming: boolean;  // True while SSE chunks are still arriving
  isComplete: boolean;
  error: Error | null;
  lastSearchSource: RouteSource | null;
  sessionId: string | null;
  cancelSearch: () => void;
  loadMore: (category: string) => Promise<Route[]>;
}

export function useRailwaySearch({
  routeSource,
  onError,
  onSuccess,
  onProgressiveResults,
}: UseRailwaySearchOptions): UseRailwaySearchResult {
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [lastSearchSource, setLastSearchSource] = useState<RouteSource | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentParams, setCurrentParams] = useState<{src: string, dst: string, date: string} | null>(null);

  const {
    startSearch: startStream,
    cancelSearch,
    isStreaming,
    isComplete,
    routes: streamRoutes,
  } = useStreamingSearch(onProgressiveResults);

  const search = useCallback(
    async (
      source: string,
      destination: string,
      date?: string,
      options?: {
        maxTransfers?: number;
        maxResults?: number;
        sortBy?: string;
        useStream?: boolean;
        engineModel?: string;
      }
    ): Promise<Route[]> => {
      setIsSearching(true);
      setError(null);
      const sourceCode = source.toUpperCase().trim();
      const destCode = destination.toUpperCase().trim();
      const normalizedDate = normalizeDate(date || new Date().toISOString().slice(0, 10));
      setCurrentParams({ src: sourceCode, dst: destCode, date: normalizedDate });

      try {
        // Strategy 1: Cached
        if (routeSource === "cached") {
          const cached = getCachedRoutes(sourceCode, destCode, normalizedDate);
          if (cached) {
            const routes = mapBackendRoutesToRoutes(cached, sourceCode, destCode);
            setLastSearchSource("cached");
            setSessionId(null);
            onSuccess?.(routes);
            return routes;
          }
          throw new Error("No cached routes available for this search");
        }

        // Strategy 2: [Point 18 & 30] SSE Streaming (live mode, opt-in)
        if (options?.useStream) {
          try {
            await startStream(sourceCode, destCode, normalizedDate, "ECONOMY");
            setLastSearchSource("live");
            return streamRoutes;
          } catch (streamError) {
            console.warn("Streaming search failed, falling back to REST", streamError);
          }
        }

        // Strategy 3: Standard REST live search
        try {
          const data = await searchRoutesApi(sourceCode, destCode, options?.maxTransfers || 2, options?.maxResults || 50, {
            date: normalizedDate,
            routeSource: "live",
            sortBy: (options?.sortBy || "duration") as "duration" | "cost" | "score",
            engineModel: options?.engineModel,
          });

          const sid = (data as any).session_id || (data as any).data?.pagination?.session_id;
          setSessionId(sid);

          const routes = mapBackendRoutesToRoutes(data, sourceCode, destCode);
          setLastSearchSource("live");
          onSuccess?.(routes, (data as any).data?.suggestions || (data as any).suggestions);
          return routes;
        } catch (liveError) {
          // Strategy 4: Auto-retry with cached if live fails
          const backendAvailable = await isBackendAvailable();
          if (!backendAvailable) {
            const cached = getCachedRoutes(sourceCode, destCode, normalizedDate);
            if (cached) {
              const routes = mapBackendRoutesToRoutes(cached, sourceCode, destCode);
              setLastSearchSource("cached");
              setSessionId(null);
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
    [routeSource, onError, onSuccess, startStream, streamRoutes]
  );

  const loadMore = useCallback(async (category: string): Promise<Route[]> => {
    if (!sessionId || !currentParams) return [];
    
    setIsSearching(true);
    try {
      const data = await loadMoreRoutesApi({
        session_id: sessionId,
        category: category,
        limit: 10
      });

      const moreRoutes = mapBackendRoutesToRoutes(data, currentParams.src, currentParams.dst);
      return moreRoutes;
    } catch (err) {
      console.error("Load more failed", err);
      return [];
    } finally {
      setIsSearching(false);
    }
  }, [sessionId, currentParams]);

  return {
    search,
    loadMore,
    isSearching,
    isStreaming,
    isComplete,
    error,
    lastSearchSource,
    sessionId,
    cancelSearch,
  };
}
