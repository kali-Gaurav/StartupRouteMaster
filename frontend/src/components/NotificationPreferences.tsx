/**
 * Notification Preferences Component
 * Allows users to manage notification settings by channel and type
 */

import React, { useEffect, useState } from 'react';
import { Bell, Mail, MessageSquare, Save, X } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';

interface PreferencesState {
  sms_enabled: boolean;
  email_enabled: boolean;
  push_enabled: boolean;
  booking_confirmed: boolean;
  payment_received: boolean;
  pnr_status: boolean;
  delay_alerts: boolean;
  safety_alerts: boolean;
  marketing: boolean;
}

const CHANNEL_ICONS = {
  sms: MessageSquare,
  email: Mail,
  push: Bell,
};

const NOTIFICATION_TYPES = [
  { id: 'booking_confirmed', label: 'Booking Confirmed', icon: '🎫' },
  { id: 'payment_received', label: 'Payment Received', icon: '💳' },
  { id: 'pnr_status', label: 'PNR Status Updates', icon: '📋' },
  { id: 'delay_alerts', label: 'Train Delays', icon: '⚠️' },
  { id: 'safety_alerts', label: 'Safety Alerts', icon: '🛡️' },
  { id: 'marketing', label: 'Marketing Offers', icon: '🎁' },
];

interface NotificationPreferencesProps {
  onClose?: () => void;
}

export function NotificationPreferences({ onClose }: NotificationPreferencesProps) {
  const { token } = useAuth();
  const [preferences, setPreferences] = useState<PreferencesState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchPreferences();
  }, [token]);

  const fetchPreferences = async () => {
    if (!token) {
      setError('Authentication required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/notifications/preferences`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch preferences');
      const data = await response.json();
      setPreferences(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load preferences');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = (key: keyof PreferencesState) => {
    if (preferences) {
      setPreferences({ ...preferences, [key]: !preferences[key] });
      setSaved(false);
    }
  };

  const handleSave = async () => {
    if (!token || !preferences) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/notifications/preferences`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(preferences),
      });

      if (!response.ok) throw new Error('Failed to save preferences');
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save preferences');
    }
  };

  if (loading) {
    return (
      <div className="p-6 bg-white dark:bg-slate-900 rounded-lg">
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-12 bg-gray-200 dark:bg-slate-700 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!preferences) {
    return (
      <div className="p-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900 rounded-lg text-red-700 dark:text-red-400">
        {error || 'Failed to load preferences'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <Bell className="w-5 h-5" />
          Notification Preferences
        </h2>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-slate-800 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Channel Toggles */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
          Channels
        </h3>
        <div className="space-y-2">
          {[
            { key: 'sms_enabled' as const, label: 'SMS', icon: MessageSquare },
            { key: 'email_enabled' as const, label: 'Email', icon: Mail },
            { key: 'push_enabled' as const, label: 'Push Notifications', icon: Bell },
          ].map(({ key, label, icon: Icon }) => (
            <label key={key} className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-slate-800 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors">
              <input
                type="checkbox"
                checked={preferences[key]}
                onChange={() => handleToggle(key)}
                className="w-4 h-4 rounded border-gray-300 text-blue-600"
              />
              <Icon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              <span className="flex-1 font-medium text-gray-700 dark:text-gray-300">{label}</span>
              <span className={`text-xs font-semibold px-2 py-1 rounded ${
                preferences[key]
                  ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                  : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
              }`}>
                {preferences[key] ? 'On' : 'Off'}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Notification Types */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
          Notification Types
        </h3>
        <div className="space-y-2">
          {NOTIFICATION_TYPES.map(({ id, label, icon }) => (
            <label
              key={id}
              className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-slate-800 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
            >
              <input
                type="checkbox"
                checked={preferences[id as keyof PreferencesState] !== false}
                onChange={() => handleToggle(id as keyof PreferencesState)}
                className="w-4 h-4 rounded border-gray-300 text-blue-600"
              />
              <span className="text-lg">{icon}</span>
              <span className="flex-1 font-medium text-gray-700 dark:text-gray-300">{label}</span>
              <span className={`text-xs font-semibold px-2 py-1 rounded ${
                preferences[id as keyof PreferencesState]
                  ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                  : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
              }`}>
                {preferences[id as keyof PreferencesState] ? 'On' : 'Off'}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Status Message */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900 rounded-lg text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {saved && (
        <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-900 rounded-lg text-green-700 dark:text-green-400">
          ✓ Preferences saved successfully
        </div>
      )}

      {/* Save Button */}
      <button
        onClick={handleSave}
        className="w-full flex items-center justify-center gap-2 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
      >
        <Save className="w-4 h-4" />
        Save Preferences
      </button>
    </div>
  );
}
