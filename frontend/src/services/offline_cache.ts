
/**
 * [P17] L0 Offline Cache Service.
 * Persists high-value search results in IndexedDB for low-connectivity zones.
 */

import { openDB, IDBPDatabase } from 'idb';

const DB_NAME = 'RouteMaster_L0';
const STORE_NAME = 'search_cache';

class OfflineSearchCache {
  private db: Promise<IDBPDatabase>;

  constructor() {
    this.db = openDB(DB_NAME, 1, {
      upgrade(db) {
        db.createObjectStore(STORE_NAME, { keyPath: 'query_key' });
      },
    });
  }

  async cacheResult(source: string, destination: string, data: any) {
    const query_key = `${source}_${destination}_${new Date().toISOString().split('T')[0]}`;
    const db = await this.db;
    await db.put(STORE_NAME, {
      query_key,
      data,
      timestamp: Date.now()
    });
    console.log(`💾 [OFFLINE] Search cached: ${query_key}`);
  }

  async getCachedResult(source: string, destination: string) {
    const query_key = `${source}_${destination}_${new Date().toISOString().split('T')[0]}`;
    const db = await this.db;
    const result = await db.get(STORE_NAME, query_key);
    
    if (result && (Date.now() - result.timestamp < 14400000)) { // 4 hour freshness
      return result.data;
    }
    return null;
  }
}

export const offlineSearch = new OfflineSearchCache();
