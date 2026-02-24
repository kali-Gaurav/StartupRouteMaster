import Fuse from "fuse.js";
import { Station as StationRefined, stationsRefined } from "./stations_refined";

// Popular Indian Railway Stations
export type Station = StationRefined;

export const stations: Station[] = stationsRefined;

// Initialize Fuse.js for high-performance fuzzy search
const fuse = new Fuse(stations, {
  keys: [
    { name: "code", weight: 2.0 },
    { name: "name", weight: 1.5 },
    { name: "city", weight: 1.0 }
  ],
  threshold: 0.35,
  distance: 100,
  minMatchCharLength: 1, // Start searching from 1 char for intelligent codes
  includeScore: true,
});

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
export const searchStations = (query: string): Station[] => {
  if (!query || typeof query !== "string") return [];
  const upperQuery = String(query).trim().toUpperCase();
  if (!upperQuery) return [];

  // Short queries (1-2 chars) - prioritise codes
  if (upperQuery.length < 3) {
    return stations
      .filter(s => s.code.startsWith(upperQuery))
      .sort((a, b) => (b.isJunction ? 1 : 0) - (a.isJunction ? 1 : 0))
      .slice(0, 5);
  }

  const results = fuse.search(upperQuery);

  // Sorting results intelligently
  const sorted = results.sort((a, b) => {
    const sA = a.score || 1;
    const sB = b.score || 1;

    // 1. Exact Code gets absolute priority
    if (a.item.code === upperQuery) return -1;
    if (b.item.code === upperQuery) return 1;

    // 2. Starts with Name gets high priority
    const startsA = a.item.name.toUpperCase().startsWith(upperQuery);
    const startsB = b.item.name.toUpperCase().startsWith(upperQuery);
    if (startsA && !startsB) return -1;
    if (startsB && !startsA) return 1;

    // 3. Junction status boost
    if (a.item.isJunction && !b.item.isJunction && sA < sB + 0.1) return -1;
    if (b.item.isJunction && !a.item.isJunction && sB < sA + 0.1) return 1;

    return sA - sB;
  });

  return sorted.slice(0, 10).map(r => r.item);
};
