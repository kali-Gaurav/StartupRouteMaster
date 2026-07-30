/**
 * Predictive Preload Service
 * Pre-caches potential routes in IndexedDB for instant offline access
 */
import { storageService } from './storageService';
import { searchRoutesApi, mapBackendRoutesToRoutes } from './railwayBackApi';

// Fallback "popular" routes for zero-data users
const POPULAR_ROUTES = [
  { source: "NDLS", destination: "MMCT" },
  { source: "CSTM", destination: "PUNE" },
  { source: "HWH", destination: "MAS" },
  { source: "SBC", destination: "MAO" }
];

export const predictivePreloadService = {
  /**
   * Preload likely routes based on current focus
   */
  async preloadPotentialRoutes(source: string) {
    console.log(`[Predictive] Preloading routes starting from ${source}`);
    
    // In a real app, this would fetch from a "Frequently Traveled" API or local history
    // For now, we seed the most common destinations from this source
    const commonDestinations = ["NDLS", "MMCT", "HWH", "BCT", "MAS"];

    console.log(`[Predictive] Common destinations from ${source}: ${commonDestinations.join(", ")}`);
    
    for (const dest of commonDestinations) {
      if (dest !== source) {
        (this as any)._cacheRoute(source, dest);
      }
    }
  },

  /**
   * Cold start: preload generic high-traffic routes
   */
  async seedPopularRoutes() {
    for (const route of POPULAR_ROUTES) {
      await (this as any)._cacheRoute(route.source, route.destination);
    }
  },

  async _cacheRoute(src: string, dest: string) {
    const now = new Date();
    const dateStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
    const existing = await storageService.getCachedRoutes(src, dest, dateStr);
    
    if (!existing) {
      try {
        const result = await searchRoutesApi(src, dest, 2, 20, { date: dateStr, routeSource: "live", sortBy: "duration" });
        const mappedRoutes = mapBackendRoutesToRoutes(result, src, dest);
        await storageService.cacheRoutes(src, dest, dateStr, mappedRoutes);
        console.log(`[Predictive] Cached ${src}-${dest} successfully.`);
      } catch (e) {
        console.warn(`[Predictive] Failed to cache ${src}-${dest}`, e);
      }
    }
  }
};
