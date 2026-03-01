// Station typings and simple cache; no hardcoded list in production
export interface Station {
  code: string;
  name: string;
  city: string;
  state: string;
  isJunction?: boolean;
}

// local static list removed to avoid bundling huge dataset
export const stations: Station[] = [];

// since we have no local data, fuse search is not used

// Cache for stations fetched from API (backend); used by getStationByCode
const stationCache = new Map<string, Station>();

export function addStationsToCache(stationList: Station[]): void {
  stationList.forEach((s) => {
    const code = s?.code;
    if (code != null && String(code).trim()) stationCache.set(String(code).toUpperCase(), s);
  });
}

export const getStationByCode = (code: string): Station | undefined => {
  const upper = code?.toUpperCase();
  if (!upper) return undefined;
  const cached = stationCache.get(upper);
  if (cached) return cached;
  return stations.find((s) => s.code.toUpperCase() === upper);
};

/**
 * Intelligent refined station search
 * Logic:
 * 1. Exact Code Match (e.g. "NDLS")
 * 2. Starts with Code (e.g. "ND")
 * 3. Starts with Name (e.g. "NEW")
 * 4. Junctions with fuzzy match
 * 5. General Fuzzy
 */
// local search helper now returns empty list; backend search is used instead
export const searchStations = (_query: string): Station[] => {
  return [];
};
