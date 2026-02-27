/**
 * Railway Backend API (backend FastAPI)
 * Stations from stations_master, routes from train_routes / route_finder.
 */

import { getRailwayApiUrl } from '@/lib/utils';
import type { Route, RouteSegment } from '@/data/routes';
import { type Station } from '@/data/stations';
import { storageService } from './storageService';

export interface FareRow {
  class_code: string;
  total_fare?: number | null;
  availability?: string | null;
}

export interface BackendStation {
  station_code: string;
  station_name?: string | null;
  city?: string | null;
  state?: string | null;
  is_junction?: number | null;
  geo_hash?: string | null;
}

export interface StationSuggestionPayload {
  code: string;
  name?: string | null;
  city?: string | null;
  state?: string | null;
}

const STATION_SUGGEST_MIN_LENGTH = 2;
const STATION_SUGGEST_MAX_LIMIT = 25;
const DEFAULT_STATION_SUGGEST_LIMIT = 15;
const STATION_RESOLVE_LIMIT = 5;

export async function suggestStationsApi(
  query: string,
  signal?: AbortSignal,
  limit: number = DEFAULT_STATION_SUGGEST_LIMIT
): Promise<Station[]> {
  const trimmed = query?.trim() ?? '';
  if (trimmed.length < STATION_SUGGEST_MIN_LENGTH) return [];
  const effectiveLimit = Math.min(limit, STATION_SUGGEST_MAX_LIMIT);
  const params = new URLSearchParams({
    q: trimmed,
    limit: String(effectiveLimit),
  });
  // Backend prefix is /api/stations/suggest (getRailwayApiUrl adds /api)
  const res = await fetch(getRailwayApiUrl(`/stations/suggest?${params.toString()}`), {
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const message = (err as { detail?: string }).detail ?? `Station suggest failed: ${res.status}`;
    throw new Error(message);
  }
  const payload = (await res.json()) as StationSuggestionPayload[];
  return payload
    .map((item) => ({
      code: (item.code ?? '').trim(),
      name: (item.name ?? item.code ?? '').trim(),
      city: (item.city ?? '').trim(),
      state: (item.state ?? '').trim(),
      isJunction: false,
    }))
    .filter((station) => station.code.length > 0 && station.name.length > 0);
}

export interface BackendDirectRoute {
  train_no: string;
  train_name?: string;
  train_type?: string;
  departure: string;
  arrival: string;
  departure_stop_id?: number;
  arrival_stop_id?: number;
  distance?: number;
  time_minutes?: number;
  time_str?: string;
  day_diff?: number;
  /** Fare (cheapest class) for this segment; included in /routes response */
  fare?: number | null;
  /** Seat availability string for this segment; included in /routes response */
  availability?: string | null;
  availability_summary?: {
    probability?: number;
    status?: string;
  };
}

export interface BackendOneTransferRoute {
  type: 'one_transfer';
  leg1: BackendDirectRoute;
  leg2: BackendDirectRoute;
  junction: string;
  waiting_time_minutes: number;
  total_distance: number;
  total_time_minutes: number;
  availability_summary?: {
    probability?: number;
  };
}

export interface BackendTwoTransferRoute {
  type: 'two_transfer';
  leg1: BackendDirectRoute;
  leg2: BackendDirectRoute;
  leg3: BackendDirectRoute;
  junction1: string;
  junction2: string;
  waiting1_minutes?: number;
  waiting2_minutes?: number;
  total_time_minutes?: number;
  total_distance?: number;
  availability_summary?: {
    probability?: number;
  };
}

export interface BackendThreeTransferRoute {
  type: 'three_transfer';
  leg1: BackendDirectRoute;
  leg2: BackendDirectRoute;
  leg3: BackendDirectRoute;
  leg4: BackendDirectRoute;
  junction1: string;
  junction2: string;
  junction3: string;
  waiting1_minutes?: number;
  waiting2_minutes?: number;
  waiting3_minutes?: number;
  total_time_minutes?: number;
  total_distance?: number;
  availability_summary?: {
    probability?: number;
  };
}

export interface BackendJourney {
  journey_id: string;
  train_no?: string;
  train_name?: string;
  departure_time?: string;
  arrival_time?: string;
  travel_time?: string;
  cheapest_fare?: number;
  availability_status?: string;
  num_transfers: number;
}

export interface BackendRoutesResponse {
  source: string;
  destination: string;
  journeys?: BackendJourney[];
  routes: {
    direct: BackendDirectRoute[];
    one_transfer: BackendOneTransferRoute[];
    two_transfer: BackendTwoTransferRoute[];
    three_transfer: BackendThreeTransferRoute[];
  };
  stations?: Record<string, Station>;
  journey_message?: string;
  booking_tips?: string[];
  message?: string;
}

export async function searchStationsApi(q: string, signal?: AbortSignal): Promise<Station[]> {
  return suggestStationsApi(q, signal);
}

export async function resolveStationCode(query: string, signal?: AbortSignal): Promise<Station | null> {
  const trimmed = (query ?? "").trim();
  if (trimmed.length < 1) return null;
  const suggestions = await suggestStationsApi(trimmed, signal, STATION_RESOLVE_LIMIT);
  if (suggestions.length === 0) return null;
  const normalized = trimmed.toUpperCase();
  const exactByCode = suggestions.find((station) => station.code.toUpperCase() === normalized);
  if (exactByCode) return exactByCode;
  const exactByName = suggestions.find((station) => (station.name ?? "").toUpperCase() === normalized);
  return exactByName ?? suggestions[0];
}

export interface SearchRoutesParams {
  source: string;
  destination: string;
  maxTransfers?: number;
  maxResults?: number;
  date?: string;
  dateWindow?: number;
  confirmedOnly?: boolean;
  sortBy?: 'duration' | 'cost' | 'score';
  /** Phase 6 flow tracker: send with GET /routes for ROUTE_FETCHED recording */
  correlationId?: string;
}

/** Default travel date (today) in YYYY-MM-DD for cache-friendly requests */
function defaultDate(): string {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

/**
 * Search routes from backend GET /routes.
 * Normalizes station codes (uppercase), defaults date to today, retries on 504 with lighter params.
 * Falls back to local IndexedDB cache if backend is unavailable.
 */
export async function searchRoutesApi(
  source: string,
  destination: string,
  _maxTransfers: number = 2,
  _maxResults: number = 50,
  params?: Partial<SearchRoutesParams & { routeSource?: 'live' | 'cached' }>
): Promise<BackendRoutesResponse> {
  const src = String(source ?? '').trim();
  const dest = String(destination ?? '').trim();
  const date = params?.date?.trim() || defaultDate();

  const doFetch = () => {
    // Backend expects POST /api/search/ with SearchRequestSchema
    const payload = {
      source: src,
      destination: dest,
      date: date,
      budget: params?.sortBy === 'cost' ? 'economy' : 'all',
      multi_modal: false, // Trains-only focus
      journey_type: 'single'
    };
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json'
    };
    if (params?.correlationId) headers['X-Correlation-Id'] = params.correlationId;
    
    return fetch(getRailwayApiUrl('/search/'), {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });
  };

  try {
    const res = await doFetch();
    
    if (!res.ok) {
      // If backend exists but returns error, try cache
      const cached = await storageService.getCachedRoutes(src.toUpperCase(), dest.toUpperCase());
      if (cached) return { routes: cached, source: 'offline-cache' } as any;
      
      const err = await res.json().catch(() => ({}));
      const msg = typeof err.message === 'string' ? err.message : (Array.isArray(err.detail) ? err.detail[0]?.msg : err.detail);
      throw new Error(msg || `Routes search failed: ${res.status}`);
    }

    const data = (await res.json()) as BackendRoutesResponse;
    // Cache the successful results for future offline use
    if (data.routes && (data.routes.direct.length > 0 || data.routes.one_transfer.length > 0)) {
      storageService.cacheRoutes(src.toUpperCase(), dest.toUpperCase(), data.routes as any);
    }
    return data;
  } catch (error) {
    console.warn("Backend route search failed, attempting to serve from cache", error);
    const cached = await storageService.getCachedRoutes(src.toUpperCase(), dest.toUpperCase());
    if (cached) {
      return { 
        routes: cached, 
        source: 'offline-cache',
        message: 'You are viewing cached routes because you are offline.' 
      } as any;
    }
    throw error;
  }
}

/**
 * Integrated Unified Search (POST /v2/search/unified)
 */
export async function unifiedSearchApi(
  source: string,
  destination: string,
  date: string,
  passengers: number = 1
): Promise<BackendJourney[]> {
  const res = await fetch(getRailwayApiUrl('/v2/search/unified'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source: source,
      destination: destination,
      date: date, // Schema in integrated_search.py uses 'date' from SearchRequest
      num_passengers: passengers
    })
  });
  
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || 'Unified search failed');
  }
  return res.json();
}

/**
 * Unlock Journey Details (GET /v2/journey/{id}/unlock-details)
 */
export async function unlockJourneyDetailsApi(
  journeyId: string,
  date: string,
  coach: string = 'AC_THREE_TIER',
  age: number = 30
): Promise<unknown> {
  const params = new URLSearchParams({
    travel_date: date,
    coach_preference: coach,
    passenger_age: String(age)
  });
  
  const res = await fetch(getRailwayApiUrl(`/v2/journey/${journeyId}/unlock-details?${params.toString()}`));
  
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || 'Unlock details failed');
  }
  return res.json();
}

/** Format time "HH:MM:SS" to "HH:MM" */
function formatTime(t: string | undefined): string {
  if (!t) return '--:--';
  const parts = String(t).trim().split(':');
  if (parts.length >= 2) return `${parts[0].padStart(2, '0')}:${parts[1].padStart(2, '0')}`;
  return t;
}

/**
 * Map backend response to frontend Route[]
 */
export function mapBackendRoutesToRoutes(
  data: BackendRoutesResponse,
  source: string,
  destination: string
): Route[] {
  const routes: Route[] = [];
  let routeId = 0;
  const stationsMap = data.stations || {};

  const getStationName = (id: number | undefined, code: string): string => {
    if (id && stationsMap[String(id)]) {
      return stationsMap[String(id)].name;
    }
    // Fallback search in map by code
    const fromMap = Object.values(stationsMap).find(s => s.code === code);
    return fromMap ? fromMap.name : code;
  };

  const makeSegment = (
    train: BackendDirectRoute,
    fromCode: string,
    toCode: string,
    waitBefore: number,
    rid: string,
    category: string
  ): RouteSegment => {
    const fare = train.fare != null ? Number(train.fare) : 0;
    const availability = train.availability != null ? String(train.availability) : (train.availability_summary?.status ?? '—');
    
    // Resolve names for display
    const fromName = getStationName(train.departure_stop_id, fromCode);
    const toName = getStationName(train.arrival_stop_id, toCode);

    return {
      routeId: rid,
      category,
      segment: 0,
      trainNumber: String(train.train_no),
      trainName: train.train_name || `Train ${train.train_no}`,
      from: fromCode,
      to: toCode,
      fromName,
      toName,
      departure: formatTime(train.departure),
      arrival: formatTime(train.arrival),
      distance: train.distance ?? 0,
      duration: train.time_minutes ?? 0,
      waitBefore,
      liveSeatAvailability: availability,
      liveFare: fare,
      seatAvailable: availability.toUpperCase().startsWith('AVAILABLE'),
    };
  };

  // Direct routes
  const directList = data.routes?.direct ?? [];
  directList.forEach((train: BackendDirectRoute) => {
    routeId++;
    const rid = `route_${routeId}`;
    const category = 'DIRECT';
    const seg = makeSegment(train, source, destination, 0, rid, category);
    const totalFare = seg.liveFare ?? 0;
    const directSeatProb = Number(train.availability_summary?.probability ?? (seg.seatAvailable ? 0.85 : 0.1));
    routes.push({
      id: rid,
      category,
      segments: [seg],
      totalTime: train.time_minutes ?? 0,
      totalCost: totalFare,
      totalTransfers: 0,
      totalDistance: train.distance ?? 0,
      liveFareTotal: totalFare,
      seatProbability: directSeatProb,
      safetyScore: 100,
    });
  });

  // One-transfer routes
  const oneTransferList = (data.routes?.one_transfer ?? []) as BackendOneTransferRoute[];
  oneTransferList.forEach((r: BackendOneTransferRoute) => {
    routeId++;
    const rid = `route_${routeId}`;
    const category = '1 TRANSFER';
    const junctionName = getStationName(r.leg1.arrival_stop_id, r.junction);
    
    const seg1 = makeSegment(r.leg1, source, r.junction, 0, rid, category);
    const seg2 = makeSegment(r.leg2, r.junction, destination, r.waiting_time_minutes ?? 0, rid, category);
    
    seg1.toName = junctionName;
    seg2.fromName = junctionName;
    seg1.segment = 1;
    seg2.segment = 2;
    
    const totalFare = (seg1.liveFare ?? 0) + (seg2.liveFare ?? 0);
    const oneProb = Number(r.availability_summary?.probability ?? Math.min(seg1.seatAvailable ? 0.85 : 0.1, seg2.seatAvailable ? 0.85 : 0.1));
    routes.push({
      id: rid,
      category,
      segments: [seg1, seg2],
      totalTime: r.total_time_minutes ?? 0,
      totalCost: totalFare,
      totalTransfers: 1,
      totalDistance: r.total_distance ?? 0,
      liveFareTotal: totalFare,
      seatProbability: oneProb,
      safetyScore: 100,
    });
  });

  // Two-transfer routes
  const twoTransferList = (data.routes?.two_transfer ?? []) as BackendTwoTransferRoute[];
  twoTransferList.forEach((r) => {
    routeId++;
    const rid = `route_${routeId}`;
    const category = '2 TRANSFERS';
    const j1 = r.junction1 ?? '';
    const j2 = r.junction2 ?? '';
    
    const j1Name = getStationName(r.leg1.arrival_stop_id, j1);
    const j2Name = getStationName(r.leg2.arrival_stop_id, j2);

    const seg1 = makeSegment(r.leg1, source, j1, 0, rid, category);
    const seg2 = makeSegment(r.leg2, j1, j2, r.waiting1_minutes ?? 0, rid, category);
    const seg3 = makeSegment(r.leg3, j2, destination, r.waiting2_minutes ?? 0, rid, category);
    
    seg1.toName = j1Name;
    seg2.fromName = j1Name;
    seg2.toName = j2Name;
    seg3.fromName = j2Name;
    
    seg1.segment = 1;
    seg2.segment = 2;
    seg3.segment = 3;
    const totalFare = (seg1.liveFare ?? 0) + (seg2.liveFare ?? 0) + (seg3.liveFare ?? 0);
    const twoProb = Number(r.availability_summary?.probability ?? Math.min(seg1.seatAvailable ? 0.85 : 0.1, seg2.seatAvailable ? 0.85 : 0.1, seg3.seatAvailable ? 0.85 : 0.1));
    routes.push({
      id: rid,
      category,
      segments: [seg1, seg2, seg3],
      totalTime: r.total_time_minutes ?? 0,
      totalCost: totalFare,
      totalTransfers: 2,
      totalDistance: r.total_distance ?? 0,
      liveFareTotal: totalFare,
      seatProbability: twoProb,
      safetyScore: 100,
    });
  });

  // Three-transfer routes
  const threeTransferList = (data.routes?.three_transfer ?? []) as BackendThreeTransferRoute[];
  threeTransferList.forEach((r) => {
    routeId++;
    const rid = `route_${routeId}`;
    const category = '3 TRANSFERS';
    const j1 = r.junction1 ?? '';
    const j2 = r.junction2 ?? '';
    const j3 = r.junction3 ?? '';
    const seg1 = makeSegment(r.leg1, source, j1, 0, rid, category);
    const seg2 = makeSegment(r.leg2, j1, j2, r.waiting1_minutes ?? 0, rid, category);
    const seg3 = makeSegment(r.leg3, j2, j3, r.waiting2_minutes ?? 0, rid, category);
    const seg4 = makeSegment(r.leg4, j3, destination, r.waiting3_minutes ?? 0, rid, category);
    seg1.segment = 1;
    seg2.segment = 2;
    seg3.segment = 3;
    seg4.segment = 4;
    const totalFare = (seg1.liveFare ?? 0) + (seg2.liveFare ?? 0) + (seg3.liveFare ?? 0) + (seg4.liveFare ?? 0);
    const threeProb = Number(r.availability_summary?.probability ?? Math.min(seg1.seatAvailable ? 0.85 : 0.1, seg2.seatAvailable ? 0.85 : 0.1, seg3.seatAvailable ? 0.85 : 0.1, seg4.seatAvailable ? 0.85 : 0.1));
    routes.push({
      id: rid,
      category,
      segments: [seg1, seg2, seg3, seg4],
      totalTime: r.total_time_minutes ?? 0,
      totalCost: totalFare,
      totalTransfers: 3,
      totalDistance: r.total_distance ?? 0,
      liveFareTotal: totalFare,
      seatProbability: threeProb,
      safetyScore: 100,
    });
  });

  // Sort by total time
  routes.sort((a, b) => a.totalTime - b.totalTime);
  return routes;
}

/**
 * Health check backend GET /health
 */
export async function healthCheckRailway(): Promise<boolean> {
  try {
    const res = await fetch(getRailwayApiUrl('/health'));
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Stats from backend GET /stats (for display)
 */
export async function getStatsRailway(): Promise<{ total_stations?: number; total_trains?: number; total_routes?: number }> {
  const res = await fetch(getRailwayApiUrl('/stats'));
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

// ==========================================================================
// LOCAL STORAGE UTILITIES - Frontend works independently without bot/backend
// Provides offline capability and local search history
// ==========================================================================

const STORAGE_KEYS = {
  SEARCH_HISTORY: 'rm_search_history',
  FAVORITE_ROUTES: 'rm_favorite_routes',
  CACHED_STATIONS: 'rm_cached_stations',
  USER_PREFERENCES: 'rm_user_preferences',
  LAST_SEARCH: 'rm_last_search',
};

export interface SearchHistoryItem {
  origin: { code: string; name: string };
  destination: { code: string; name: string };
  date?: string;
  timestamp: number;
  resultsCount?: number;
}

export interface FavoriteRoute {
  origin: { code: string; name: string };
  destination: { code: string; name: string };
  label?: string;
  addedAt: number;
}

/**
 * Save search to local history (works offline)
 */
export function saveSearchToHistory(
  origin: { code: string; name: string },
  destination: { code: string; name: string },
  date?: string,
  resultsCount?: number
): void {
  try {
    const history = getSearchHistory();
    const newItem: SearchHistoryItem = {
      origin,
      destination,
      date,
      timestamp: Date.now(),
      resultsCount,
    };
    
    // Remove duplicates (same origin/destination)
    const filtered = history.filter(
      h => !(h.origin.code === origin.code && h.destination.code === destination.code)
    );
    
    // Add new item at the beginning, limit to 20
    const updated = [newItem, ...filtered].slice(0, 20);
    localStorage.setItem(STORAGE_KEYS.SEARCH_HISTORY, JSON.stringify(updated));
  } catch (e) {
    console.warn('Could not save search history:', e);
  }
}

/**
 * Get search history from local storage
 */
export function getSearchHistory(): SearchHistoryItem[] {
  try {
    const data = localStorage.getItem(STORAGE_KEYS.SEARCH_HISTORY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

/**
 * Clear search history
 */
export function clearSearchHistory(): void {
  try {
    localStorage.removeItem(STORAGE_KEYS.SEARCH_HISTORY);
  } catch (e) {
    console.warn('Could not clear search history:', e);
  }
}

/**
 * Add route to favorites (works offline)
 */
export function addFavoriteRoute(
  origin: { code: string; name: string },
  destination: { code: string; name: string },
  label?: string
): void {
  try {
    const favorites = getFavoriteRoutes();
    const newFav: FavoriteRoute = {
      origin,
      destination,
      label: label || `${origin.name} → ${destination.name}`,
      addedAt: Date.now(),
    };
    
    // Check if already exists
    const exists = favorites.some(
      f => f.origin.code === origin.code && f.destination.code === destination.code
    );
    if (exists) return;
    
    const updated = [newFav, ...favorites].slice(0, 50);
    localStorage.setItem(STORAGE_KEYS.FAVORITE_ROUTES, JSON.stringify(updated));
  } catch (e) {
    console.warn('Could not save favorite route:', e);
  }
}

/**
 * Get favorite routes from local storage
 */
export function getFavoriteRoutes(): FavoriteRoute[] {
  try {
    const data = localStorage.getItem(STORAGE_KEYS.FAVORITE_ROUTES);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

/**
 * Remove route from favorites
 */
export function removeFavoriteRoute(originCode: string, destinationCode: string): void {
  try {
    const favorites = getFavoriteRoutes();
    const updated = favorites.filter(
      f => !(f.origin.code === originCode && f.destination.code === destinationCode)
    );
    localStorage.setItem(STORAGE_KEYS.FAVORITE_ROUTES, JSON.stringify(updated));
  } catch (e) {
    console.warn('Could not remove favorite route:', e);
  }
}

/**
 * Cache stations locally for offline access
 */
export function cacheStations(stations: Station[]): void {
  try {
    const existing = getCachedStations();
    const merged = [...existing];
    
    for (const station of stations) {
      if (!merged.some(s => s.code === station.code)) {
        merged.push(station);
      }
    }
    
    // Keep only 500 most recent
    localStorage.setItem(STORAGE_KEYS.CACHED_STATIONS, JSON.stringify(merged.slice(0, 500)));
  } catch (e) {
    console.warn('Could not cache stations:', e);
  }
}

/**
 * Get cached stations (for offline search)
 */
export function getCachedStations(): Station[] {
  try {
    const data = localStorage.getItem(STORAGE_KEYS.CACHED_STATIONS);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

/**
 * Search cached stations offline
 */
export function searchCachedStations(query: string): Station[] {
  if (!query || query.length < 2) return [];
  const q = query.toLowerCase();
  const stations = getCachedStations();
  return stations.filter(
    s => s.code.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)
  ).slice(0, 20);
}

/**
 * Save user preferences
 */
export function saveUserPreferences(prefs: Record<string, unknown>): void {
  try {
    const existing = getUserPreferences();
    const updated = { ...existing, ...prefs };
    localStorage.setItem(STORAGE_KEYS.USER_PREFERENCES, JSON.stringify(updated));
  } catch (e) {
    console.warn('Could not save preferences:', e);
  }
}

/**
 * Get user preferences
 */
export function getUserPreferences(): Record<string, unknown> {
  try {
    const data = localStorage.getItem(STORAGE_KEYS.USER_PREFERENCES);
    return data ? JSON.parse(data) : {};
  } catch {
    return {};
  }
}

/**
 * Check if backend is reachable
 */
export async function isBackendAvailable(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    
    const res = await fetch(getRailwayApiUrl('/health/live'), {
      signal: controller.signal,
    });
    
    clearTimeout(timeout);
    return res.ok;
  } catch {
    return false;
  }
}

interface PopularRoute {
  origin: string;
  origin_name: string;
  destination: string;
  destination_name: string;
}

/**
 * Get popular routes (works offline with fallback)
 */
export async function getPopularRoutes(limit: number = 5): Promise<PopularRoute[]> {
  try {
    const res = await fetch(getRailwayApiUrl(`/api/popular-routes?limit=${limit}`));
    if (res.ok) {
      const data = await res.json();
      return (data.popular_routes || []) as PopularRoute[];
    }
  } catch {
    // Fallback to hardcoded popular routes for offline
  }
  
  // Offline fallback
  return [
    { origin: 'NDLS', origin_name: 'New Delhi', destination: 'BCT', destination_name: 'Mumbai Central' },
    { origin: 'HWH', origin_name: 'Howrah', destination: 'NDLS', destination_name: 'New Delhi' },
    { origin: 'MAS', origin_name: 'Chennai Central', destination: 'SBC', destination_name: 'Bangalore' },
  ];
}
