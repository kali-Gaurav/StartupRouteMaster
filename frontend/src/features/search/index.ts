/**
 * Search feature – re-exports for feature-based structure.
 */

export { StationSearch } from "@/components/StationSearch";
export {
  searchStationsApi,
  searchRoutesApi,
  mapBackendRoutesToRoutes,
  getStatsRailway,
  healthCheckRailway,
  isBackendAvailable,
  getPopularRoutes,
  type BackendRoutesResponse,
  type SearchRoutesParams,
} from "@/services/railwayBackApi";
export { useStations, useRouteSearch } from "@/api/hooks";
