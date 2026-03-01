/**
 * Station search hook – cached and deduplicated by query string.
 */

import { useQuery } from "@tanstack/react-query";
import { searchStationsApi } from "@/services/railwayBackApi";

export const STATIONS_QUERY_KEY = "stations";

export function useStations(query: string) {
  const trimmed = query?.trim() ?? "";
  const enabled = trimmed.length >= 2;

  return useQuery({
    queryKey: [STATIONS_QUERY_KEY, trimmed.toLowerCase()],
    queryFn: () => searchStationsApi(trimmed),
    enabled,
    staleTime: 1000 * 60, // 1 min – station list is fairly static
  });
}
