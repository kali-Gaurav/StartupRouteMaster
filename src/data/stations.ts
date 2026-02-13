import stationData from "./station_search_data.json";

// Popular Indian Railway Stations
export interface Station {
  code: string;
  name: string;
  city: string;
  state: string;
}

export const stations: Station[] = stationData.stations;

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

export const searchStations = (query: string): Station[] => {
  if (!query || typeof query !== "string") return [];
  const upperQuery = String(query).trim().toUpperCase();
  if (!upperQuery) return [];

  // Try exact city match first
  let filtered = stations.filter(
    (s) => s?.city && String(s.city).toUpperCase() === upperQuery
  );

  // If no exact city match, search by station code (exact or prefix) then name
  if (filtered.length === 0) {
    filtered = stations.filter(
      (s) =>
        (s?.code && String(s.code).toUpperCase().startsWith(upperQuery)) ||
        (s?.code && String(s.code).toUpperCase() === upperQuery) ||
        (s?.name && String(s.name).toUpperCase().includes(upperQuery)) ||
        (s?.city && String(s.city).toUpperCase().includes(upperQuery))
    );
  }

  // Fuzzy: if still no results, match by tokens (e.g. "new del" → New Delhi)
  if (filtered.length === 0) {
    const tokens = upperQuery.split(/\s+/).filter(Boolean);
    if (tokens.length > 0) {
      filtered = stations.filter((s) => {
        const name = String(s?.name ?? "").toUpperCase();
        const code = String(s?.code ?? "").toUpperCase();
        const city = String(s?.city ?? "").toUpperCase();
        return tokens.every(
          (t) => name.includes(t) || code.includes(t) || city.includes(t)
        );
      });
    }
  }

  // Sort with smart prioritization
  return filtered.sort((a, b) => {
    const aCode = (a?.code && String(a.code).toUpperCase()) || "";
    const bCode = (b?.code && String(b.code).toUpperCase()) || "";
    const aName = (a?.name && String(a.name).toUpperCase()) || "";
    const bName = (b?.name && String(b.name).toUpperCase()) || "";
    
    // Priority 1: Exact code match
    const aCodeExact = aCode === upperQuery ? 0 : 1;
    const bCodeExact = bCode === upperQuery ? 0 : 1;
    if (aCodeExact !== bCodeExact) return aCodeExact - bCodeExact;
    
    // Priority 2: Code starts with query
    const aCodeStarts = aCode.startsWith(upperQuery) ? 0 : 1;
    const bCodeStarts = bCode.startsWith(upperQuery) ? 0 : 1;
    if (aCodeStarts !== bCodeStarts) return aCodeStarts - bCodeStarts;
    
    // Priority 3: Major junctions first
    const aIsMajor = aName.includes("JN") || aName.includes("JUNCTION") || aName.includes("TERMINUS") || aName.includes("CENTRAL");
    const bIsMajor = bName.includes("JN") || bName.includes("JUNCTION") || bName.includes("TERMINUS") || bName.includes("CENTRAL");
    if (aIsMajor && !bIsMajor) return -1;
    if (!aIsMajor && bIsMajor) return 1;
    
    // Priority 4: Shorter names (more relevant)
    if (aName.length !== bName.length) return aName.length - bName.length;
    
    // Priority 5: Alphabetical
    return aName.localeCompare(bName);
  }).slice(0, 50);
};
