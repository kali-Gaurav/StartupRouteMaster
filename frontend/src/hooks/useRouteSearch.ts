/**
 * Route Engine Evolution - React Hooks for SSE Streaming
 * 
 * Provides hooks for:
 * - SSE route search with progressive delivery
 * - Transfer Intelligence Score display
 * - Corridor Safety status
 * 
 * Owner: ORION (Frontend Lead)
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// ============================================================================
// Types
// ============================================================================

export interface RouteSegment {
  train_number: string;
  train_name: string;
  from_station_code: string;
  from_station_name: string;
  to_station_code: string;
  to_station_name: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  class_type: string;
  fare: number;
  availability: 'AVAILABLE' | 'WAITLIST' | 'FULL';
}

export interface Journey {
  journey_id: string;
  segments: RouteSegment[];
  total_duration: number;
  total_fare: number;
  transfers: number;
  departure_time: string;
  arrival_time: string;
  availability_status: 'AVAILABLE' | 'LIMITED' | 'UNAVAILABLE';
  safety_score: number;
  demand_factor: number;
}

export interface EnrichedRoute {
  journey: Journey;
  overall_score: number;
  quality_score: number;
  safety_score: number;
  transfer_score: number;
  risk_level: 'low' | 'medium' | 'high';
  safety_events: SafetyEvent[];
  pareto_rank: number;
}

export interface SafetyEvent {
  event_id: string;
  event_type: 'station_alert' | 'corridor_alert' | 'route_disruption' | 'weather_warning';
  corridor: string;
  stations: string[];
  severity: 'critical' | 'high' | 'moderate' | 'low' | 'minimal';
  description: string;
  start_time: string;
  end_time?: string;
  safety_penalty: number;
}

export interface TransferScore {
  transfer_station: string;
  arrival_train: string;
  departure_train: string;
  connection_time_minutes: number;
  tis_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'unknown';
  historical_success_rate: number;
  indicator: {
    color: 'green' | 'yellow' | 'red';
    icon: string;
    label: string;
  };
  recommendations: string[];
}

export interface SearchProgress {
  stage: 'qpo' | 'raptor' | 'tis' | 'safety' | 'complete';
  progress: number;
  message: string;
}

export interface UseRouteSearchOptions {
  source: string;
  destination: string;
  travelDate: string;
  maxRoutes?: number;
  autoConnect?: boolean;
}

export interface UseRouteSearchReturn {
  routes: EnrichedRoute[];
  isLoading: boolean;
  isConnected: boolean;
  progress: SearchProgress | null;
  error: string | null;
  connectionId: string | null;
  search: () => Promise<void>;
  cancel: () => void;
  reconnect: () => void;
}

// ============================================================================
// SSE Event Types
// ============================================================================

type SSEEventType = 
  | 'connected'
  | 'route_found'
  | 'search_progress'
  | 'search_complete'
  | 'error'
  | 'heartbeat';

interface SSEEvent {
  event: SSEEventType;
  data: string;
  id?: string;
}

// ============================================================================
// Main Hook: useRouteSearch
// ============================================================================

export function useRouteSearch(options: UseRouteSearchOptions): UseRouteSearchReturn {
  const { source, destination, travelDate, maxRoutes = 10, autoConnect = true } = options;
  
  const [routes, setRoutes] = useState<EnrichedRoute[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState<SearchProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connectionId, setConnectionId] = useState<string | null>(null);
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Parse SSE event data
  const parseEventData = useCallback(<T>(data: string): T => {
    return JSON.parse(data) as T;
  }, []);

  // Handle new route found
  const handleRouteFound = useCallback((data: string) => {
    const route = parseEventData<EnrichedRoute>(data);
    setRoutes(prev => {
      // Check if route already exists
      const exists = prev.some(r => r.journey.journey_id === route.journey.journey_id);
      if (exists) return prev;
      
      // Add new route and sort by overall score
      return [...prev, route].sort((a, b) => b.overall_score - a.overall_score);
    });
  }, [parseEventData]);

  // Handle search progress
  const handleProgress = useCallback((data: string) => {
    const progressData = parseEventData<SearchProgress>(data);
    setProgress(progressData);
  }, [parseEventData]);

  // Handle search complete
  const handleComplete = useCallback((data: string) => {
    const result = parseEventData<{ total_routes: number; duration_ms: number }>(data);
    setIsLoading(false);
    setProgress({
      stage: 'complete',
      progress: 100,
      message: `Found ${result.total_routes} routes in ${result.duration_ms}ms`
    });
  }, [parseEventData]);

  // Handle error
  const handleError = useCallback((data: string) => {
    const errorData = parseEventData<{ message: string }>(data);
    setError(errorData.message);
    setIsLoading(false);
    setIsConnected(false);
  }, [parseEventData]);

  // Handle connection established
  const handleConnected = useCallback((data: string) => {
    const connData = parseEventData<{ connection_id: string; timestamp: string }>(data);
    setConnectionId(connData.connection_id);
    setIsConnected(true);
    setError(null);
  }, [parseEventData]);

  // Handle heartbeat
  const handleHeartbeat = useCallback(() => {
    // Update last seen timestamp for connection health
  }, []);

  // Setup SSE event handlers
  const setupEventHandlers = useCallback((eventSource: EventSource) => {
    eventSource.addEventListener('connected', (e: MessageEvent) => {
      handleConnected(e.data);
    });

    eventSource.addEventListener('route_found', (e: MessageEvent) => {
      handleRouteFound(e.data);
    });

    eventSource.addEventListener('search_progress', (e: MessageEvent) => {
      handleProgress(e.data);
    });

    eventSource.addEventListener('search_complete', (e: MessageEvent) => {
      handleComplete(e.data);
    });

    eventSource.addEventListener('error', (e: MessageEvent) => {
      handleError(e.data);
    });

    eventSource.addEventListener('heartbeat', () => {
      handleHeartbeat();
    });

    eventSource.onerror = (e) => {
      console.error('SSE connection error:', e);
      setIsConnected(false);
      setIsLoading(false);
      
      // Auto-reconnect on error (up to 3 times)
      // In production, implement exponential backoff
    };
  }, [handleConnected, handleRouteFound, handleProgress, handleComplete, handleError, handleHeartbeat]);

  // Main search function
  const search = useCallback(async () => {
    // Cleanup previous connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    // Create new abort controller
    abortControllerRef.current = new AbortController();
    
    // Reset state
    setRoutes([]);
    setIsLoading(true);
    setIsConnected(false);
    setProgress(null);
    setError(null);
    setConnectionId(null);

    // Build SSE URL with query parameters
    const params = new URLSearchParams({
      source: source.toUpperCase(),
      destination: destination.toUpperCase(),
      travel_date: travelDate,
      max_routes: maxRoutes.toString()
    });

    const sseUrl = `/api/v1/routes/search/stream?${params.toString()}`;
    
    try {
      // Create SSE connection
      const eventSource = new EventSource(sseUrl, {
        withCredentials: true // Include auth cookies
      });
      
      eventSourceRef.current = eventSource;
      setupEventHandlers(eventSource);
      
    } catch (err) {
      setError('Failed to establish connection');
      setIsLoading(false);
    }
  }, [source, destination, travelDate, maxRoutes, setupEventHandlers]);

  // Cancel search
  const cancel = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    setIsLoading(false);
    setIsConnected(false);
    setProgress(null);
  }, []);

  // Reconnect
  const reconnect = useCallback(() => {
    search();
  }, [search]);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      search();
    }
    
    // Cleanup on unmount
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [autoConnect, search]);

  return {
    routes,
    isLoading,
    isConnected,
    progress,
    error,
    connectionId,
    search,
    cancel,
    reconnect
  };
}

// ============================================================================
// Secondary Hook: useTransferScore
// ============================================================================

export function useTransferScore(
  transferStation: string,
  arrivalTrain: string,
  departureTrain: string,
  connectionTime: number
) {
  const [score, setScore] = useState<TransferScore | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchScore = useCallback(async () => {
    if (!transferStation || !arrivalTrain || !departureTrain) return;

    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        transfer_station: transferStation,
        arrival_train: arrivalTrain,
        departure_train: departureTrain,
        connection_time: connectionTime.toString()
      });

      const response = await fetch(`/api/v1/routes/transfer/score?${params.toString()}`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch transfer score');
      }

      const data = await response.json();
      setScore(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [transferStation, arrivalTrain, departureTrain, connectionTime]);

  useEffect(() => {
    fetchScore();
  }, [fetchScore]);

  return { score, isLoading, error, refetch: fetchScore };
}

// ============================================================================
// Secondary Hook: useCorridorSafety
// ============================================================================

export function useCorridorSafety(source: string, destination: string) {
  const [status, setStatus] = useState<{
    corridor: string;
    safety_score: number;
    risk_level: string;
    active_events: number;
    affected_stations: string[];
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!source || !destination) return;

    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        source: source.toUpperCase(),
        destination: destination.toUpperCase()
      });

      const response = await fetch(`/api/v1/routes/safety/status?${params.toString()}`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch safety status');
      }

      const data = await response.json();
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [source, destination]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return { status, isLoading, error, refetch: fetchStatus };
}

// ============================================================================
// Utility Functions
// ============================================================================

export function getRiskColor(riskLevel: 'low' | 'medium' | 'high'): string {
  switch (riskLevel) {
    case 'low': return 'text-green-600';
    case 'medium': return 'text-yellow-600';
    case 'high': return 'text-red-600';
    default: return 'text-gray-600';
  }
}

export function getRiskBackground(riskLevel: 'low' | 'medium' | 'high'): string {
  switch (riskLevel) {
    case 'low': return 'bg-green-100';
    case 'medium': return 'bg-yellow-100';
    case 'high': return 'bg-red-100';
    default: return 'bg-gray-100';
  }
}

export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours > 0) {
    return `${hours}h ${mins}m`;
  }
  return `${mins}m`;
}

export function formatTime(timeString: string): string {
  if (!timeString) return '--:--';
  // Format: "06:00:00" -> "06:00"
  return timeString.substring(0, 5);
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(amount);
}

export function getTransferIndicator(riskLevel: 'low' | 'medium' | 'high'): {
  icon: string;
  label: string;
  color: string;
} {
  switch (riskLevel) {
    case 'low':
      return { icon: '✅', label: 'Good Connection', color: 'green' };
    case 'medium':
      return { icon: '⚠️', label: 'Medium Risk', color: 'yellow' };
    case 'high':
      return { icon: '❌', label: 'High Risk', color: 'red' };
    default:
      return { icon: '❓', label: 'Unknown', color: 'gray' };
  }
}

export function getSafetyIndicator(safetyScore: number): {
  icon: string;
  label: string;
  color: string;
} {
  if (safetyScore >= 0.9) {
    return { icon: '🛡️', label: 'Safe', color: 'green' };
  } else if (safetyScore >= 0.7) {
    return { icon: '⚠️', label: 'Caution', color: 'yellow' };
  } else {
    return { icon: '🚨', label: 'Avoid', color: 'red' };
  }
}

// ============================================================================
// Export all hooks and utilities
// ============================================================================

export default {
  useRouteSearch,
  useTransferScore,
  useCorridorSafety,
  getRiskColor,
  getRiskBackground,
  formatDuration,
  formatTime,
  formatCurrency,
  getTransferIndicator,
  getSafetyIndicator
};