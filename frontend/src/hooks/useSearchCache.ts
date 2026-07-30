import { useState, useCallback, useEffect } from 'react';
import { get, set, keys, del } from 'idb-keyval';

/**
 * useSearchCache (Suggestion #7 & #22)
 * Upgraded to use IndexedDB for high-capacity asynchronous storage.
 */
export function useSearchCache() {
  const [cache, _setCache] = useState<Record<string, any>>({});

  // Initialize from IndexedDB
  useEffect(() => {
    async function loadAll() {
      const allKeys = await keys();
      const searchKeys = allKeys.filter(k => typeof k === 'string' && k.startsWith('search:'));
      const initialCache: Record<string, any> = {};
      
      for (const key of searchKeys) {
        initialCache[key as string] = await get(key);
      }
      _setCache(initialCache);
    }
    loadAll();
  }, []);

  const getCachedResults = useCallback((src: string, dst: string, date: string) => {
    const key = `search:${src}:${dst}:${date}`;
    return cache[key];
  }, [cache]);

  const saveToCache = useCallback(async (src: string, dst: string, date: string, results: any) => {
    const key = `search:${src}:${dst}:${date}`;
    
    // Save to state for instant access
    _setCache(prev => ({ ...prev, [key]: results }));
    
    // Save to IndexedDB (asynchronous, high capacity)
    await set(key, results);

    // Maintenance: keep only last 50 entries
    const allKeys = await keys();
    const searchKeys = allKeys.filter(k => typeof k === 'string' && k.startsWith('search:'));
    if (searchKeys.length > 50) {
      await del(searchKeys[0]);
    }
  }, []);

  return { getCachedResults, saveToCache };
}
