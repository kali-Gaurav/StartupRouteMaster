/**
 * Multi-Transfer Route API Service
 * Integrates with the Flask multi-transfer route generation engine
 */

import { getApiUrl } from '@/lib/utils';

export interface TransferRoute {
  from: string;
  to: string;
  transfers: number;
  route: string[];
  hops?: number;
  segments?: string[];
}

export interface RouteSearchResult {
  origin: string;
  destination: string;
  date: string;
  direct: TransferRoute[];
  one_transfer: TransferRoute[];
  two_transfer: TransferRoute[];
  three_transfer: TransferRoute[];
  metadata?: {
    timestamp: string;
    search_time_ms: number;
    total_routes: number;
  };
}

export interface TrainSchedule {
  train_no: string;
  train_name: string;
  schedule: any[];
}

export interface PriceInfo {
  origin: string;
  destination: string;
  prices: {
    train_no: string;
    class: string;
    fare: number;
  }[];
  avg_fare: number;
}

export interface SeatAvailability {
  train_no: string;
  availability: {
    station: string;
    '1A': number;
    '2A': number;
    '3A': number;
    'SL': number;
  }[];
}

export interface StationInfo {
  code: string;
  name: string;
}

/**
 * Search for multi-transfer routes between two stations
 */
export async function searchRoutes(
  origin: string,
  destination: string,
  day: string = 'Mon',
  maxTransfers: number = 3
): Promise<RouteSearchResult> {
  const payload = {
    origin: origin.toUpperCase(),
    destination: destination.toUpperCase(),
    day: day.charAt(0).toUpperCase() + day.slice(1).toLowerCase(),
    max_transfers: maxTransfers,
  };

  const url = getApiUrl('/api/v2/search-routes');
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to search routes');
  }

  return response.json();
}

/**
 * Get list of stations for autocomplete
 */
export async function getStations(search?: string): Promise<StationInfo[]> {
  let url = getApiUrl('/api/v2/stations');
  if (search) {
    url += `?search=${encodeURIComponent(search)}`;
  }

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error('Failed to fetch stations');
  }

  const data = await response.json();
  return data.stations || [];
}

/**
 * Get train schedule (all stations and timings)
 */
export async function getTrainSchedule(trainNo: string): Promise<TrainSchedule> {
  const url = getApiUrl(`/api/v2/train/${trainNo}/schedule`);
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error('Failed to fetch train schedule');
  }

  return response.json();
}

/**
 * Get pricing for a specific route
 */
export async function getPrices(
  origin: string,
  destination: string
): Promise<PriceInfo> {
  const url = getApiUrl(
    `/api/v2/prices/${origin.toUpperCase()}/${destination.toUpperCase()}`
  );
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error('Failed to fetch prices');
  }

  return response.json();
}

/**
 * Get seat availability for a train
 */
export async function getSeatAvailability(trainNo: string): Promise<SeatAvailability> {
  const url = getApiUrl(`/api/v2/train/${trainNo}/seats`);
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error('Failed to fetch seat availability');
  }

  return response.json();
}

/**
 * Health check endpoint
 */
export async function healthCheck(): Promise<boolean> {
  try {
    const url = getApiUrl('/api/v2/health');
    const response = await fetch(url);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Get system statistics
 */
export async function getStats() {
  const url = getApiUrl('/api/v2/stats');
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error('Failed to fetch stats');
  }

  return response.json();
}

/**
 * Format route data for display
 */
export function formatRoute(route: TransferRoute): {
  displayText: string;
  stationCount: number;
  transferCount: number;
} {
  const stationCount = route.route?.length || 0;
  const transferCount = route.transfers || 0;

  let displayText = route.route?.join(' → ') || 'Unknown route';
  if (displayText.length > 100) {
    displayText = route.route?.[0] + ' → ... → ' + route.route?.[stationCount - 1] || displayText;
  }

  return {
    displayText,
    stationCount,
    transferCount,
  };
}

/**
 * Get transfer route details
 */
export async function getTransferRouteDetails(
  routes: TransferRoute[],
  transferCount: number
): Promise<Map<string, any>> {
  const details = new Map();

  for (const route of routes.slice(0, 3)) {
    // Limit to first 3 for performance
    try {
      const trains = route.segments || [];
      for (const trainNo of trains) {
        if (trainNo && !details.has(trainNo)) {
          const schedule = await getTrainSchedule(trainNo);
          details.set(trainNo, schedule);
        }
      }
    } catch (error) {
      console.error(`Failed to fetch details for route:`, error);
    }
  }

  return details;
}
