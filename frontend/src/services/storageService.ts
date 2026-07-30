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
  id?: string; // combination of source_destination
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
    // version 2 existed previously; bump to 3 to add count index on favorites
    this.version(2).stores({
      cachedRoutes: '++id, [source+destination], timestamp',
      userStats: 'id',
      recentSearches: '++id, timestamp, [source+destination]',
      favorites: '[source+destination]'
    });

    // upgrade path for schema change to version 3
    this.version(3).stores({
      cachedRoutes: '++id, [source+destination], timestamp',
      userStats: 'id',
      recentSearches: '++id, timestamp, [source+destination]',
      // now index count so we can orderBy('count') without SchemaError
      favorites: '[source+destination], count'
    }).upgrade(async (trans) => {
      // during upgrade, ensure existing objects have count property (should already)
      const favs = await trans.table('favorites').toArray();
      for (const f of favs) {
        if (typeof f.count !== 'number') {
          f.count = 0;
          await trans.table('favorites').put(f);
        }
      }
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
    const id = `${src}_${dest}`;
    const fav = await db.favorites.get([src, dest]);
    if (fav) {
      await db.favorites.update([src, dest], { count: (fav.count || 0) + 1 });
    } else {
      await db.favorites.add({ id, source: src, destination: dest, count: 1 });
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
    // safe fallback if count index isn't yet available (during upgrade)
    const hasCountIndex = db.favorites.schema.indexes.some(idx => idx.name === 'count');
    let results;
    if (hasCountIndex) {
      results = await db.favorites.orderBy('count').reverse().limit(limit).toArray();
    } else {
      // fetch everything then sort in JS
      const all = await db.favorites.toArray();
      all.sort((a, b) => (b.count || 0) - (a.count || 0));
      results = all.slice(0, limit);
    }
    return results.map(f => ({ ...f, id: f.id || `${f.source}_${f.destination}` }));
  },

  async removeFavorite(id: string) {
    if (id.includes('_')) {
      const [source, destination] = id.split('_');
      await db.favorites.delete([source, destination]);
    } else {
      // Try deleting by primary key if it's not the composite one
      await db.favorites.delete(id);
    }
  }
};

