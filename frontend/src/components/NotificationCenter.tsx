/**
 * Notification Center Component
 * Displays user's notification history
 */

import React, { useEffect, useState } from 'react';
import { Bell, Trash2, CheckCircle, AlertCircle, Clock } from 'lucide-react';

interface Notification {
  id: string;
  type: string;
  message: string;
  status: 'sent' | 'delivered' | 'failed';
  channel: string;
  created_at: string;
  read: boolean;
}

interface NotificationCenterProps {
  onClose?: () => void;
}

export function NotificationCenter({ onClose }: NotificationCenterProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'unread'>('all');

  useEffect(() => {
    loadNotifications();
  }, []);

  const loadNotifications = async () => {
    // Mock notifications for now
    setNotifications([
      {
        id: '1',
        type: 'booking_confirmed',
        message: 'Your booking PNR123456 has been confirmed',
        status: 'delivered',
        channel: 'sms',
        created_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
        read: false,
      },
      {
        id: '2',
        type: 'payment_received',
        message: 'Payment of ₹2,500 received for booking PNR123456',
        status: 'delivered',
        channel: 'email',
        created_at: new Date(Date.now() - 1000 * 60 * 10).toISOString(),
        read: false,
      },
      {
        id: '3',
        type: 'delay_alert',
        message: 'Train 12456 is delayed by 15 minutes',
        status: 'delivered',
        channel: 'push',
        created_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
        read: true,
      },
    ]);
    setLoading(false);
  };

  const handleDelete = (id: string) => {
    setNotifications(notifications.filter(n => n.id !== id));
  };

  const handleMarkAsRead = (id: string) => {
    setNotifications(notifications.map(n =>
      n.id === id ? { ...n, read: true } : n
    ));
  };

  const filteredNotifications = filter === 'unread'
    ? notifications.filter(n => !n.read)
    : notifications;

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'delivered':
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-600" />;
      default:
        return <Clock className="w-4 h-4 text-yellow-600" />;
    }
  };

  const getChannelBadge = (channel: string) => {
    const colors: Record<string, string> = {
      sms: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
      email: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
      push: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
    };
    return colors[channel] || 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400';
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;

    return date.toLocaleDateString();
  };

  return (
    <div className="flex flex-col h-full max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-slate-700">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <Bell className="w-5 h-5" />
          Notification Center
        </h2>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 p-4 border-b border-gray-200 dark:border-slate-700">
        <button
          onClick={() => setFilter('all')}
          className={`px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
            filter === 'all'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 dark:bg-slate-800 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-slate-700'
          }`}
        >
          All Notifications ({notifications.length})
        </button>
        <button
          onClick={() => setFilter('unread')}
          className={`px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
            filter === 'unread'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 dark:bg-slate-800 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-slate-700'
          }`}
        >
          Unread ({notifications.filter(n => !n.read).length})
        </button>
      </div>

      {/* Notifications List */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-200 dark:bg-slate-700 rounded animate-pulse" />
            ))}
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full py-12 text-center">
            <Bell className="w-12 h-12 text-gray-300 dark:text-slate-600 mb-3" />
            <p className="text-gray-600 dark:text-gray-400 font-medium">No notifications</p>
            <p className="text-sm text-gray-500 dark:text-gray-500">
              {filter === 'unread' ? 'You\'re all caught up!' : 'Your notification history is empty'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-slate-700">
            {filteredNotifications.map(notification => (
              <div
                key={notification.id}
                className={`p-4 hover:bg-gray-50 dark:hover:bg-slate-800/50 transition-colors ${
                  !notification.read ? 'bg-blue-50 dark:bg-blue-900/10' : ''
                }`}
              >
                <div className="flex gap-3">
                  <div className="flex-shrink-0 mt-1">
                    {getStatusIcon(notification.status)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className={`text-sm font-medium ${
                          !notification.read
                            ? 'text-gray-900 dark:text-white font-semibold'
                            : 'text-gray-700 dark:text-gray-300'
                        }`}>
                          {notification.type.replace(/_/g, ' ').toUpperCase()}
                        </p>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                          {notification.message}
                        </p>
                      </div>

                      <button
                        onClick={() => handleDelete(notification.id)}
                        className="text-gray-400 hover:text-red-600 dark:hover:text-red-400 flex-shrink-0"
                        title="Delete notification"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="flex items-center gap-2 mt-2">
                      <span className={`text-xs font-semibold px-2 py-1 rounded ${getChannelBadge(notification.channel)}`}>
                        {notification.channel.toUpperCase()}
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-500">
                        {formatTime(notification.created_at)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
