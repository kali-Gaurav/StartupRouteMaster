import Dexie, { Table } from 'dexie';
import { Route } from '@/data/routes';

export interface CachedRoute {
  id?: number;
  source: string;
  destination: string;
  routes: Route[];
  timestamp: number;
}

export interface UserStats {
  id: string;
  totalBookings: number;
  totalSearches: number;
  lastSearch?: string;
}

export interface RecentSearch {
  id?: number;
  source: string;
  destination: string;
  timestamp: number;
}

export interface FavoriteRoute {
  source: string;
  destination: string;
  count: number;
}

export class AppDatabase extends Dexie {
  cachedRoutes!: Table<CachedRoute>;
  userStats!: Table<UserStats>;
  recentSearches!: Table<RecentSearch>;
  favorites!: Table<FavoriteRoute>;

  constructor() {
    super('RailAssistantDB');
    this.version(2).stores({
      cachedRoutes: '++id, [source+destination], timestamp',
      userStats: 'id',
      recentSearches: '++id, timestamp, [source+destination]',
      favorites: '[source+destination]'
    });
  }
}

export const db = new AppDatabase();

export const storageService = {
  async addRecentSearch(source: string, destination: string) {
    const src = source.toUpperCase();
    const dest = destination.toUpperCase();
    
    await db.recentSearches.add({
      source: src,
      destination: dest,
      timestamp: Date.now()
    });

    // Track favorites
    const fav = await db.favorites.get([src, dest]);
    if (fav) {
      await db.favorites.update([src, dest], { count: (fav.count || 0) + 1 });
    } else {
      await db.favorites.add({ source: src, destination: dest, count: 1 });
    }
  },

  async getRecentSearches(limit = 5) {
    return db.recentSearches.orderBy('timestamp').reverse().limit(limit).toArray();
  },

  async cacheRoutes(source: string, destination: string, routes: any[]) {
    try {
      await db.cachedRoutes.put({
        source: source.toUpperCase(),
        destination: destination.toUpperCase(),
        routes,
        timestamp: Date.now()
      });
    } catch (err) {
      console.error("Failed to cache routes", err);
    }
  },

  async getCachedRoutes(source: string, destination: string): Promise<any[] | null> {
    try {
      const entry = await db.cachedRoutes
        .where('[source+destination]')
        .equals([source.toUpperCase(), destination.toUpperCase()])
        .first();
      
      // Cache remains valid for 24 hours
      if (entry && (Date.now() - entry.timestamp < 24 * 60 * 60 * 1000)) {
        return entry.routes;
      }
      return null;
    } catch (err) {
      return null;
    }
  },

  async getFavorites(limit = 5) {
    return db.favorites.orderBy('count').reverse().limit(limit).toArray();
  }
};
  }
}
