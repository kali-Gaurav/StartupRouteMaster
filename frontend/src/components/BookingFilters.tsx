/**
 * BookingFilters Component
 * Provides filtering and sorting controls for bookings
 */

import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';

interface BookingFiltersProps {
  onStatusChange?: (status: string | undefined) => void;
  onSortChange?: (sortBy: string) => void;
  loading?: boolean;
}

export function BookingFilters({
  onStatusChange,
  onSortChange,
  loading = false,
}: BookingFiltersProps) {
  const [status, setStatus] = useState<string | undefined>(undefined);
  const [sortBy, setSortBy] = useState('date');

  const handleStatusChange = (value: string) => {
    const newStatus = value === 'all' ? undefined : value;
    setStatus(newStatus);
    onStatusChange?.(newStatus);
  };

  const handleSortChange = (value: string) => {
    setSortBy(value);
    onSortChange?.(value);
  };

  return (
    <div className="flex flex-col gap-4 p-4 bg-white rounded-lg border border-gray-200 dark:bg-slate-900 dark:border-slate-700">
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Status Filter */}
        <div className="flex-1">
          <label htmlFor="status-filter" className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">
            Status
          </label>
          <div className="relative">
            <select
              id="status-filter"
              value={status || 'all'}
              onChange={(e) => handleStatusChange(e.target.value)}
              disabled={loading}
              className="w-full px-3 py-2 border border-gray-300 rounded-md appearance-none bg-white dark:bg-slate-800 dark:border-slate-600 dark:text-white text-sm font-medium cursor-pointer disabled:opacity-50"
            >
              <option value="all">All Bookings</option>
              <option value="initiated">Initiated</option>
              <option value="payment_pending">Pending Payment</option>
              <option value="confirmed">Confirmed</option>
              <option value="cancelled">Cancelled</option>
              <option value="failed">Failed</option>
              <option value="waitlist">Waitlist</option>
            </select>
            <ChevronDown className="absolute right-3 top-3 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        {/* Sort Filter */}
        <div className="flex-1">
          <label htmlFor="sort-filter" className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">
            Sort By
          </label>
          <div className="relative">
            <select
              id="sort-filter"
              value={sortBy}
              onChange={(e) => handleSortChange(e.target.value)}
              disabled={loading}
              className="w-full px-3 py-2 border border-gray-300 rounded-md appearance-none bg-white dark:bg-slate-800 dark:border-slate-600 dark:text-white text-sm font-medium cursor-pointer disabled:opacity-50"
            >
              <option value="date">Latest First</option>
              <option value="date-asc">Oldest First</option>
              <option value="amount">Amount (High to Low)</option>
              <option value="amount-asc">Amount (Low to High)</option>
            </select>
            <ChevronDown className="absolute right-3 top-3 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>
      </div>
    </div>
  );
}
