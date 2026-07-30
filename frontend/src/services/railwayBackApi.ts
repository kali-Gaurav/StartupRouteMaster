/**
 * Railway Backend API (backend FastAPI)
 * Stations from stations_master, routes from train_routes / route_finder.
 */

import { getRailwayApiUrl } from '@/lib/utils';
import type { Route, RouteSegment } from '@/data/routes';
import { type Station } from '@/data/stations';
import { v3Fetch } from '@/lib/apiClient';

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
  const res = await fetch(getRailwayApiUrl(`/api/v1/stations/suggest?${params.toString()}`), {
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
  departure: string;
  arrival: string;
  distance?: number;
  time_minutes?: number;
  fare?: number | null;
  availability?: string | null;
}

export interface BackendJourneyLeg {
  train_number: string;
  train_name: string;
  from_station_code: string;
  to_station_code: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes?: number;
  fare?: number;
  distance?: number;
  metadata?: Record<string, any>;
}

export interface BackendJourney {
  journey_id: string;
  train_no?: string;
  train_name?: string;
  departure_time?: string;
  arrival_time?: string;
  total_duration?: number;
  total_cost?: number;
  total_distance?: number;
  availability_status?: string;
  reliability_score?: number;
  reliability_badge?: 'green' | 'yellow' | 'red';
  num_transfers: number;
  is_locked?: boolean;
  legs?: BackendJourneyLeg[];
  metadata?: Record<string, any>;
}

export interface BackendRoutesResponse {
  status?: string;
  source: string;
  destination: string;
  routes?: {
    direct?: BackendJourney[];
    one_transfer?: BackendJourney[];
    two_transfer?: BackendJourney[];
    three_plus_transfer?: BackendJourney[];
    three_transfer?: BackendJourney[];
  };
  data?: {
    journeys: BackendJourney[];
    grouped_journeys: {
      top_3_confirmed_fastest: BackendJourney[];
      top_10_fastest_total: BackendJourney[];
      top_5_optimal: BackendJourney[];
      direct: BackendJourney[];
      one_transfer: BackendJourney[];
      two_transfer: BackendJourney[];
      three_plus_transfer: BackendJourney[];
      alternative_sorted: BackendJourney[];
    };
    pagination: {
      total_results: number;
      current_page: number;
      limit: number;
      has_next: boolean;
      total_pages: number;
      session_id?: string;
    };
    next_cursor?: string | number;
  };
  stations?: Record<string, Station>;
  journey_message?: string;
  booking_tips?: string[];
  message?: string;
  reasons?: string[];
  suggestions?: any[];
  metadata?: {
    engine?: string;
    latency_ms?: number;
    cached?: boolean;
    surge_level?: number;
    corridor_pressure?: number;
    edr_nudges?: Array<{
      id: string;
      type: string;
      headline: string;
      description: string;
      incentive: string;
      target_route?: string;
    }>;
    shadow_guide?: {
      message: string;
      tone: string;
      safety_tip?: string;
      food_recommendation?: string;
    };
  };
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
  sortBy?: 'duration' | 'cost' | 'score';
  correlationId?: string;
  routeSource?: string;
  discoveryOnly?: boolean;
  engineModel?: string;
  womenSafetyPriority?: boolean;
}

export interface LoadMoreParams {
  session_id: string;
  category: string;
  limit?: number;
}

function defaultDate(): string {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

export async function searchRoutesApi(
  source: string,
  destination: string,
  _maxTransfers: number = 2,
  _maxResults: number = 50,
  params?: Partial<SearchRoutesParams>
): Promise<BackendRoutesResponse> {
  const src = String(source ?? '').trim();
  const dest = String(destination ?? '').trim();
  const date = params?.date?.trim() || defaultDate();

  const queryParams = new URLSearchParams({
    source: src,
    destination: dest,
    date: date,
    budget: params?.sortBy === 'cost' ? 'economy' : 'all',
    multi_modal: 'true',
    limit: _maxResults.toString(),
    persona: params?.sortBy === 'cost' ? 'ECONOMY' : (params?.sortBy === 'score' ? 'EMERGENCY' : 'BUSINESS')
  });

  if (params?.routeSource) {
    queryParams.append('source_type', params.routeSource);
  }

  if (params?.discoveryOnly) {
    queryParams.append('discovery_only', 'true');
  }

  if (params?.engineModel) {
    queryParams.append('engine_model', params.engineModel);
  }
  
  if (params?.womenSafetyPriority) {
    queryParams.append('women_safety_priority', 'true');
  }

  const url = getRailwayApiUrl(`/api/v1/search/routes?${queryParams.toString()}`);

  const headers: HeadersInit = { 'Accept': 'application/json' };
  if (params?.correlationId) headers['X-Correlation-Id'] = params.correlationId;

  const res = await fetch(url, {
    method: 'GET',
    headers
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || `Routes search failed: ${res.status}`);
  }

  return (await res.json()) as BackendRoutesResponse;
}

export async function loadMoreRoutesApi(params: LoadMoreParams): Promise<BackendRoutesResponse> {
  const queryParams = new URLSearchParams({
    session_id: params.session_id,
    category: params.category,
    limit: (params.limit || 10).toString()
  });

  const url = getRailwayApiUrl(`/api/v3/search/load_more?${queryParams.toString()}`);
  const res = await fetch(url);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Load more failed: ${res.status}`);
  }

  return (await res.json()) as BackendRoutesResponse;
}

function formatTime(t: string | undefined): string {
  if (!t) return '--:--';
  const parts = String(t).trim().split(':');
  if (parts.length >= 2) return `${parts[0].padStart(2, '0')}:${parts[1].padStart(2, '0')}`;
  return t;
}

export function mapBackendRoutesToRoutes(
  data: BackendRoutesResponse,
  _source: string,
  _destination: string
): Route[] {
  const routes: Route[] = [];
  const stationsMap = data.stations || {};

  const getStationName = (code: string): string => {
    const fromMap = Object.values(stationsMap).find(s => s.code === code);
    return fromMap ? fromMap.name : code;
  };

  const backendJourneys = data.data?.journeys || [];
  const mostOptimalIds = new Set((data.data?.grouped_journeys?.top_5_optimal || []).map((j: BackendJourney) => j.journey_id));
  
  backendJourneys.forEach(j => {
    const rid = j.journey_id;
    let category = j.num_transfers === 0 ? 'DIRECT' : `${j.num_transfers} TRANSFER${j.num_transfers > 1 ? 'S' : ''}`;
    
    // If it's in the most_optimal group, override category
    if (mostOptimalIds.has(rid)) {
      category = 'OPTIMAL';
    }
    
    const segments: RouteSegment[] = [];
    if (j.legs) {
      j.legs.forEach((leg, index) => {
        // Backend may send station codes as from_station_code OR from_station
        const fromCode = leg.from_station_code || (leg as any).from_station || "";
        const toCode = leg.to_station_code || (leg as any).to_station || "";
        segments.push({
          routeId: rid,
          category,
          segment: index,
          trainNumber: leg.train_number || j.train_no || "N/A",
          trainName: leg.train_name || (leg as any).train_name || `Train ${leg.train_number}`,
          from: fromCode,
          to: toCode,
          fromName: getStationName(fromCode),
          toName: getStationName(toCode),
          departure: formatTime(leg.departure_time),
          arrival: formatTime(leg.arrival_time),
          distance: leg.distance ?? (leg as any).distance_km ?? 0,
          duration: leg.duration_minutes ?? (leg as any).duration ?? 0,
          waitBefore: 0,
          liveSeatAvailability: j.availability_status ?? 'UNKNOWN',
          liveFare: leg.fare ?? 0,
          seatAvailable: (j.availability_status || '').toUpperCase().includes('AVAILABLE'),
          metadata: leg.metadata || {}
        });
      });
    }

    routes.push({
      id: rid,
      category,
      segments,
      totalTime: j.total_duration ?? (j as any).total_duration_minutes ?? 0,
      totalCost: j.total_cost ?? (j as any).total_fare ?? 0,
      totalTransfers: j.num_transfers ?? (j as any).transfer_count ?? 0,
      totalDistance: j.total_distance ?? (j as any).total_distance_km ?? 0,
      liveFareTotal: j.total_cost ?? (j as any).total_fare ?? 0,
      seatProbability: j.reliability_score ?? 0.85,
      reliabilityBadge: j.reliability_badge,
      isLocked: j.is_locked ?? true,
      safetyScore: (j as any).safety_score ?? j.metadata?.safety_score ?? 100,
      metadata: j.metadata,
      redistribution_options: j.metadata?.redistribution_options || []
    });
  });

  return routes;
}

export async function isBackendAvailable(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000); // 2s timeout
    const res = await fetch(getRailwayApiUrl('/health'), { 
      signal: controller.signal,
      headers: { 'Cache-Control': 'no-cache' }
    });
    clearTimeout(timeoutId);
    return res.ok;
  } catch (_err) {
    return false;
  }
}

/**
 * Unlock full journey details after ₹49 fee.
 */
export async function unlockJourneyDetailsApi(
  journeyId: string,
  travelDate: string
): Promise<any> {
  const params = new URLSearchParams({ travel_date: travelDate });
  const url = getRailwayApiUrl(`/v2/journey/${journeyId}/unlock-details?${params.toString()}`);
  
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Unlock failed: ${res.status}`);
  }
  return res.json();
}

export async function getTrainStatusApi(trainNumber: string): Promise<any> {
  const res = await fetch(getRailwayApiUrl(`/api/v1/live/train/${trainNumber}`));
  if (!res.ok) throw new Error('Failed to fetch train status');
  const raw = await res.json();

  // Normalize rappid.in response into the shape TrainTracking.tsx expects:
  // statusData.live_status.{train_name, delay_minutes, current_station, next_station, badge_color}
  // statusData.estimated_position.{progress_percentage, last_station.name, next_station.name}
  const route: any[] = raw.route || [];
  const total = route.length;
  const currentIdx = route.findIndex((s: any) => s.is_current);
  const progressPct = total > 1
    ? Math.round((currentIdx >= 0 ? currentIdx / (total - 1) : 0) * 100)
    : 0;

  const lastStation = currentIdx > 0 ? route[currentIdx - 1] : (route[0] || null);
  const nextStation = currentIdx >= 0 && currentIdx + 1 < total ? route[currentIdx + 1] : (route[total - 1] || null);

  return {
    ...raw,
    // Fields TrainTracking.tsx reads via statusData.live_status.*
    live_status: {
      train_name: raw.train_name || `Train ${trainNumber}`,
      train_number: raw.train_number || trainNumber,
      delay_minutes: raw.delay_minutes || 0,
      current_station: raw.current_station || '',
      next_station: raw.next_station || '',
      status_label: raw.status_label || 'On Time',
      badge_color: raw.badge_color || 'green',
      on_time: raw.on_time ?? true,
      updated: raw.updated || '',
      route: route,
    },
    // Fields TrainTracking.tsx reads via statusData.estimated_position.*
    estimated_position: {
      progress_percentage: progressPct,
      last_station: lastStation ? { name: lastStation.station_name, code: '' } : null,
      next_station: nextStation ? { name: nextStation.station_name, code: '' } : null,
      current_station_name: raw.current_station || '',
    },
  };
}

export async function getStatsRailway(): Promise<{ total_stations?: number; total_trains?: number }> {
  try {
    const res = await fetch(getRailwayApiUrl('/stats'), { signal: AbortSignal.timeout(5000) });
    if (!res.ok) return {};
    return res.json();
  } catch {
    return {};
  }
}

export function getSearchHistory(): any[] {
  try {
    const data = localStorage.getItem('rm_search_history');
    return data ? JSON.parse(data) : [];
  } catch { return []; }
}

/**
 * [Phase 6] Claims a Sovereign Intelligence incentive.
 */
export async function claimIncentiveApi(data: {
  amount: number;
  nudge_id: string;
  description?: string;
  type?: string;
}) {
  return v3Fetch<any>("/v3/intelligence/sovereign/claim", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

/**
 * [Phase 6] Retrieves the user's Sovereign Wallet summary.
 */
export async function getSovereignWalletApi() {
  return v3Fetch<any>("/v3/intelligence/sovereign/wallet");
}

/**
 * [Phase 7] Records an A/B testing conversion for Sovereign Intelligence.
 */
export async function recordAbConversionApi(data: {
  experiment_id?: string;
  variant: string;
  goal?: string;
}) {
  return v3Fetch<any>("/v3/intelligence/ab/convert", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}
