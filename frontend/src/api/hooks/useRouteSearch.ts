/**
 * Route search mutation – retry and loading state for route search.
 */

import { useMutation } from "@tanstack/react-query";
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
