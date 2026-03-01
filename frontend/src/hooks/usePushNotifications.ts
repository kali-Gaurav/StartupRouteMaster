/**
 * Push Notifications Hook - Registration & Subscription
 * Integrates with Service Worker for real-time safety alerts.
 */
import { useEffect, useState, useCallback } from 'react';
import { logEvent, reportError } from '@/lib/observability';

export function usePushNotifications() {
  const [permission, setPermission] = useState<NotificationPermission>(
    typeof Notification !== 'undefined' ? Notification.permission : 'default'
  );
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [subscription, setSubscription] = useState<PushSubscription | null>(null);

  const registerServiceWorker = useCallback(async () => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      try {
        const registration = await navigator.serviceWorker.register('/sw.js');
        const existingSub = await registration.pushManager.getSubscription();
        setSubscription(existingSub);
        setIsSubscribed(!!existingSub);
        return registration;
      } catch (err) {
        reportError(new Error('Service Worker registration failed'), { error: err });
      }
    }
    return null;
  }, []);

  const subscribeUser = async () => {
    if (permission !== 'granted') {
      const result = await Notification.requestPermission();
      setPermission(result);
      if (result !== 'granted') return;
    }

    const registration = await registerServiceWorker();
    if (!registration) return;

    try {
      // Note: VAPID_PUBLIC_KEY should be fetched from backend or env
      const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY;
      
      if (!VAPID_PUBLIC_KEY) {
        console.warn('VITE_VAPID_PUBLIC_KEY missing. Push subscription skipped.');
        return;
      }

      const sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: VAPID_PUBLIC_KEY
      });

      setSubscription(sub);
      setIsSubscribed(true);
      
      // Sync with backend
      // await syncPushSubscription(sub);
      logEvent('push_subscribed', { endpoint: sub.endpoint });
      
    } catch (err) {
      reportError(new Error('Push subscription failed'), { error: err });
    }
  };

  const unsubscribeUser = async () => {
    if (subscription) {
      await subscription.unsubscribe();
      setSubscription(null);
      setIsSubscribed(false);
      logEvent('push_unsubscribed');
    }
  };

  useEffect(() => {
    registerServiceWorker();
  }, [registerServiceWorker]);

  return {
    permission,
    isSubscribed,
    subscribeUser,
    unsubscribeUser
  };
}
