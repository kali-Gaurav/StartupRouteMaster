/**
 * Predictive Preload Service
 * Pre-caches potential routes in IndexedDB for instant offline access
 */
import { storageService } from './storageService';

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
    const existing = await storageService.getCachedRoutes(src, dest);
    
    if (!existing) {
      // Mocking a background fetch. In a real app, this calls the backend
      // and saves the response into Dexie.
      const mockResult: any[] = [
        { id: "101", name: "SF Express", type: "Superfast", time: "10:00" },
        { id: "102", name: "SF Express 2", type: "SF", time: "22:00" }
      ];
      
      await storageService.cacheRoutes(src, dest, mockResult);
      console.log(`[Predictive] Cached ${src}-${dest}`);
    }
  }
};
