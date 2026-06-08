/**
 * Route Engine Evolution - Route Search Component
 * 
 * Main component for SSE-powered route search with:
 * - Progressive route delivery
 * - Transfer Intelligence Score indicators
 * - Corridor Safety status
 * 
 * Owner: ORION (Frontend Lead)
 */

import React, { useState } from 'react';
import { 
  useRouteSearch, 
  useCorridorSafety,
  formatDuration, 
  formatTime, 
  formatCurrency,
  getRiskColor,
  getRiskBackground,
  getTransferIndicator,
  getSafetyIndicator,
  EnrichedRoute,
  SearchProgress
} from '../../hooks/useRouteSearch';

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Search Form Component
 */
const SearchForm: React.FC<{
  onSearch: (source: string, destination: string, date: string) => void;
  isLoading: boolean;
}> = ({ onSearch, isLoading }) => {
  const [source, setSource] = useState('');
  const [destination, setDestination] = useState('');
  const [date, setDate] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (source && destination && date) {
      onSearch(source, destination, date);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4 bg-white rounded-lg shadow">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            From
          </label>
          <input
            type="text"
            value={source}
            onChange={(e) => setSource(e.target.value.toUpperCase())}
            placeholder="e.g., NDLS"
            maxLength={5}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 uppercase"
            disabled={isLoading}
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            To
          </label>
          <input
            type="text"
            value={destination}
            onChange={(e) => setDestination(e.target.value.toUpperCase())}
            placeholder="e.g., BCT"
            maxLength={5}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 uppercase"
            disabled={isLoading}
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Date
          </label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
        </div>
      </div>
      
      <button
        type="submit"
        disabled={isLoading || !source || !destination || !date}
        className={`w-full py-2 px-4 rounded-md font-medium text-white transition-colors ${
          isLoading 
            ? 'bg-gray-400 cursor-not-allowed' 
            : 'bg-blue-600 hover:bg-blue-700'
        }`}
      >
        {isLoading ? 'Searching...' : 'Search Routes'}
      </button>
    </form>
  );
};

/**
 * Progress Indicator Component
 */
const ProgressIndicator: React.FC<{
  progress: SearchProgress | null;
}> = ({ progress }) => {
  if (!progress) return null;

  const stages = [
    { key: 'qpo', label: 'Planning' },
    { key: 'raptor', label: 'Searching' },
    { key: 'tis', label: 'Scoring' },
    { key: 'safety', label: 'Safety Check' }
  ];

  const currentIndex = stages.findIndex(s => s.key === progress.stage);

  return (
    <div className="p-4 bg-blue-50 rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-blue-800">
          {progress.message || 'Searching...'}
        </span>
        <span className="text-sm text-blue-600">
          {progress.progress}%
        </span>
      </div>
      
      <div className="flex items-center space-x-2">
        {stages.map((stage, index) => (
          <React.Fragment key={stage.key}>
            <div className={`flex items-center ${
              index <= currentIndex ? 'text-blue-600' : 'text-gray-300'
            }`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${
                index < currentIndex 
                  ? 'bg-blue-600 text-white' 
                  : index === currentIndex 
                    ? 'bg-blue-200 animate-pulse' 
                    : 'bg-gray-200'
              }`}>
                {index < currentIndex ? '✓' : index + 1}
              </div>
              <span className="ml-2 text-xs hidden sm:inline">{stage.label}</span>
            </div>
            {index < stages.length - 1 && (
              <div className={`flex-1 h-0.5 ${
                index < currentIndex ? 'bg-blue-600' : 'bg-gray-200'
              }`} />
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};

/**
 * Transfer Indicator Component
 */
const TransferIndicator: React.FC<{
  riskLevel: 'low' | 'medium' | 'high' | 'unknown';
  score?: number;
  compact?: boolean;
}> = ({ riskLevel, score, compact = false }) => {
  const indicator = getTransferIndicator(riskLevel);

  if (compact) {
    return (
      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
        indicator.color === 'green' ? 'bg-green-100 text-green-800' :
        indicator.color === 'yellow' ? 'bg-yellow-100 text-yellow-800' :
        indicator.color === 'red' ? 'bg-red-100 text-red-800' :
        'bg-gray-100 text-gray-800'
      }`}>
        <span className="mr-1">{indicator.icon}</span>
        {indicator.label}
      </span>
    );
  }

  return (
    <div className={`p-3 rounded-lg ${getRiskBackground(riskLevel)}`}>
      <div className="flex items-center space-x-2">
        <span className="text-2xl">{indicator.icon}</span>
        <div>
          <div className={`font-medium ${getRiskColor(riskLevel)}`}>
            {indicator.label}
          </div>
          {score !== undefined && (
            <div className="text-sm text-gray-600">
              Score: {score.toFixed(0)}/100
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * Safety Badge Component
 */
const SafetyBadge: React.FC<{
  safetyScore: number;
  compact?: boolean;
}> = ({ safetyScore, compact = false }) => {
  const indicator = getSafetyIndicator(safetyScore);

  return (
    <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
      indicator.color === 'green' ? 'bg-green-100 text-green-800' :
      indicator.color === 'yellow' ? 'bg-yellow-100 text-yellow-800' :
      'bg-red-100 text-red-800'
    }`}>
      <span className="mr-1">{indicator.icon}</span>
      {indicator.label} ({safetyScore.toFixed(0)}%)
    </div>
  );
};

/**
 * Route Card Component
 */
const RouteCard: React.FC<{
  route: EnrichedRoute;
  onSelect: (route: EnrichedRoute) => void;
  isSelected?: boolean;
}> = ({ route, onSelect, isSelected }) => {
  const { journey } = route;
  const hasTransfers = journey.transfers > 0;

  return (
    <div 
      className={`p-4 border rounded-lg cursor-pointer transition-all ${
        isSelected 
          ? 'border-blue-500 bg-blue-50 shadow-md' 
          : 'border-gray-200 hover:border-blue-300 hover:shadow-sm'
      }`}
      onClick={() => onSelect(route)}
    >
      {/* Header: Score and Safety */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <span className="text-lg font-bold text-blue-600">
            {route.overall_score.toFixed(0)}/100
          </span>
          <SafetyBadge safetyScore={route.safety_score} compact />
        </div>
        {hasTransfers && (
          <TransferIndicator 
            riskLevel={route.risk_level} 
            score={route.transfer_score}
            compact 
          />
        )}
      </div>

      {/* Journey Details */}
      <div className="flex items-center space-x-4">
        {/* Departure */}
        <div className="text-center">
          <div className="text-xl font-bold">{formatTime(journey.departure_time)}</div>
          <div className="text-sm text-gray-500">
            {journey.segments[0]?.from_station_code}
          </div>
        </div>

        {/* Duration and Stops */}
        <div className="flex-1 flex flex-col items-center">
          <div className="text-sm text-gray-500">
            {formatDuration(journey.total_duration_minutes)}
          </div>
          <div className="w-full flex items-center my-1">
            <div className="flex-1 h-0.5 bg-gray-300" />
            {hasTransfers && (
              <div className="px-2">
                <div className="w-3 h-3 rounded-full bg-blue-500" />
              </div>
            )}
            <div className="flex-1 h-0.5 bg-gray-300" />
          </div>
          <div className="text-xs text-gray-500">
            {hasTransfers 
              ? `${journey.transfers} transfer${journey.transfers > 1 ? 's' : ''}`
              : 'Direct'
            }
          </div>
        </div>

        {/* Arrival */}
        <div className="text-center">
          <div className="text-xl font-bold">{formatTime(journey.arrival_time)}</div>
          <div className="text-sm text-gray-500">
            {journey.segments[journey.segments.length - 1]?.to_station_code}
          </div>
        </div>
      </div>

      {/* Fare and Classes */}
      <div className="mt-3 flex items-center justify-between text-sm">
        <div className="text-gray-600">
          {formatCurrency(journey.total_fare)}
        </div>
        <div className="flex space-x-2">
          {journey.segments.slice(0, 2).map((segment, idx) => (
            <span 
              key={idx}
              className="px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600"
            >
              {segment.class_type}
            </span>
          ))}
        </div>
      </div>

      {/* Transfer Details (expanded view) */}
      {hasTransfers && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <div className="text-xs font-medium text-gray-500 mb-2">
            Transfer Details
          </div>
          {journey.segments.slice(0, -1).map((segment, idx) => (
            <div 
              key={idx}
              className="flex items-center justify-between text-sm py-1"
            >
              <span>
                {segment.to_station_code} - Transfer to {journey.segments[idx + 1]?.train_number}
              </span>
              <TransferIndicator 
                riskLevel={route.risk_level}
                compact
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * Route List Component
 */
const RouteList: React.FC<{
  routes: EnrichedRoute[];
  onSelect: (route: EnrichedRoute) => void;
  selectedRoute?: EnrichedRoute | null;
}> = ({ routes, onSelect, selectedRoute }) => {
  if (routes.length === 0) {
    return (
      <div className="p-8 text-center text-gray-500">
        <div className="text-4xl mb-2">🔍</div>
        <p>No routes found. Try a different search.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {routes.map((route) => (
        <RouteCard
          key={route.journey.journey_id}
          route={route}
          onSelect={onSelect}
          isSelected={selectedRoute?.journey.journey_id === route.journey.journey_id}
        />
      ))}
    </div>
  );
};

/**
 * Safety Status Component
 */
const SafetyStatus: React.FC<{
  source: string;
  destination: string;
}> = ({ source, destination }) => {
  const { status, isLoading, error } = useCorridorSafety(source, destination);

  if (isLoading || error || !status) return null;

  return (
    <div className="p-3 bg-gray-50 rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-lg">🛡️</span>
          <span className="font-medium">
            {source}-{destination} Corridor
          </span>
        </div>
        <SafetyBadge safetyScore={status.safety_score} />
      </div>
      
      {status.active_events > 0 && (
        <div className="mt-2 text-sm text-amber-600">
          ⚠️ {status.active_events} active safety event(s)
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

const RouteSearch: React.FC = () => {
  const [searchParams, setSearchParams] = useState<{
    source: string;
    destination: string;
    date: string;
  } | null>(null);
  
  const [selectedRoute, setSelectedRoute] = useState<EnrichedRoute | null>(null);

  const { 
    routes, 
    isLoading, 
    isConnected, 
    progress, 
    error, 
    search, 
    cancel 
  } = useRouteSearch({
    source: searchParams?.source || '',
    destination: searchParams?.destination || '',
    travelDate: searchParams?.date || '',
    maxRoutes: 10,
    autoConnect: false
  });

  const handleSearch = (source: string, destination: string, date: string) => {
    setSearchParams({ source, destination, date });
    setSelectedRoute(null);
    search();
  };

  return (
    <div className="max-w-4xl mx-auto p-4">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">
        🚂 Route Search
      </h1>

      {/* Search Form */}
      <SearchForm 
        onSearch={handleSearch}
        isLoading={isLoading}
      />

      {/* Error Message */}
      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <span className="text-red-600">❌</span>
            <span className="text-red-800">{error}</span>
          </div>
        </div>
      )}

      {/* Connection Status */}
      {isConnected && (
        <div className="mt-4 flex items-center space-x-2 text-sm text-green-600">
          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <span>Live connection active</span>
        </div>
      )}

      {/* Progress Indicator */}
      <div className="mt-4">
        <ProgressIndicator progress={progress} />
      </div>

      {/* Safety Status */}
      {searchParams && (
        <div className="mt-4">
          <SafetyStatus 
            source={searchParams.source}
            destination={searchParams.destination}
          />
        </div>
      )}

      {/* Cancel Button */}
      {isLoading && (
        <div className="mt-4">
          <button
            onClick={cancel}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
          >
            Cancel Search
          </button>
        </div>
      )}

      {/* Route List */}
      {(isLoading || routes.length > 0) && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-3">
            Available Routes
            {routes.length > 0 && (
              <span className="ml-2 text-sm font-normal text-gray-500">
                ({routes.length} found)
              </span>
            )}
          </h2>
          
          <RouteList
            routes={routes}
            onSelect={setSelectedRoute}
            selectedRoute={selectedRoute}
          />
        </div>
      )}

      {/* Selected Route Details */}
      {selectedRoute && (
        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h3 className="font-semibold text-blue-800 mb-2">
            Selected Route Details
          </h3>
          <pre className="text-xs text-blue-600 overflow-auto">
            {JSON.stringify(selectedRoute, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

export default RouteSearch;