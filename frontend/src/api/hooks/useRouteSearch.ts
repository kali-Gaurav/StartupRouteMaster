/**
 * Route search mutation – retry and loading state for route search.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  searchRoutesApi,
  type BackendRoutesResponse,
  type SearchRoutesParams,
} from "@/services/railwayBackApi";

export interface RouteSearchVariables {
  source: string;
  destination: string;
  maxTransfers?: number;
  maxResults?: number;
  params?: Partial<SearchRoutesParams>;
}

export const ROUTES_QUERY_KEY = "routes";

export function useRouteSearch() {
  return useMutation({
    mutationFn: async ({
      source,
      destination,
      maxTransfers = 2,
      maxResults = 50,
      params,
    }: RouteSearchVariables): Promise<BackendRoutesResponse> => {
      return searchRoutesApi(source, destination, maxTransfers, maxResults, params);
    },
  });
}

export function useRouteSearchQuery({
  source,
  destination,
  maxTransfers = 2,
  maxResults = 50,
  params,
  enabled = true,
}: RouteSearchVariables & { enabled?: boolean }) {
  const sourceCode = source?.toUpperCase().trim() || "";
  const destCode = destination?.toUpperCase().trim() || "";
  const date = params?.date || new Date().toISOString().slice(0, 10);

  return useQuery({
    queryKey: [ROUTES_QUERY_KEY, sourceCode, destCode, date, maxTransfers, maxResults, params?.routeSource, params?.sortBy],
    queryFn: () => searchRoutesApi(sourceCode, destCode, maxTransfers, maxResults, params),
    enabled: enabled && !!sourceCode && !!destCode,
    staleTime: 1000 * 60 * 5, // 5 minutes
    gcTime: 1000 * 60 * 30, // 30 minutes
  });
}
