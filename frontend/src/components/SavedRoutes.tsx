/**
 * SavedRoutes Component
 * Displays and manages user's saved train routes
 */

import React from 'react';
import { MapPin, Trash2, ArrowRight, Plus } from 'lucide-react';
import { useSavedRoutes } from '@/hooks/useSavedRoutes';

interface SavedRoutesProps {
  onSelectRoute?: (from: string, to: string) => void;
}

export function SavedRoutes({ onSelectRoute }: SavedRoutesProps) {
  const { routes, loading, error, removeRoute } = useSavedRoutes();

  if (error && routes.length === 0) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900 rounded-lg text-sm text-red-700 dark:text-red-400">
        {error}
      </div>
    );
  }

  if (loading && routes.length === 0) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-12 bg-gray-200 dark:bg-slate-700 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (routes.length === 0) {
    return (
      <div className="text-center py-8 px-4 border border-dashed border-gray-300 dark:border-slate-700 rounded-lg bg-gray-50 dark:bg-slate-900">
        <MapPin className="w-12 h-12 text-gray-300 dark:text-slate-600 mx-auto mb-3" />
        <p className="text-gray-600 dark:text-gray-400 font-medium">No saved routes yet</p>
        <p className="text-sm text-gray-500 dark:text-gray-500 mt-1">
          Your frequently used routes will appear here
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-lg text-gray-900 dark:text-white">Saved Routes</h3>
        <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-2 py-1 rounded">
          {routes.length}
        </span>
      </div>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {routes.map((route) => (
          <div
            key={route.id}
            className="flex items-center justify-between p-3 border border-gray-200 dark:border-slate-700 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors group"
          >
            <div
              className="flex-1 cursor-pointer flex items-center gap-3"
              onClick={() => onSelectRoute?.(route.from_station, route.to_station)}
            >
              <MapPin className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                  {route.name || `${route.from_station} - ${route.to_station}`}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
                  <span className="truncate">{route.from_station}</span>
                  <ArrowRight className="w-3 h-3 flex-shrink-0" />
                  <span className="truncate">{route.to_station}</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => removeRoute(route.id)}
              className="p-1.5 text-gray-400 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
              title="Remove route"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
