/**
 * RouteMaster Background Location Service Worker
 * Handles background sync and location persistence when the app is backgrounded.
 */

const CACHE_NAME = 'routemaster-location-v1';
const SYNC_TAG = 'location-update';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

// Listen for messages from the main thread
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'START_TRACKING') {
    console.log('[SW] Background tracking started');
    // We can't use navigator.geolocation in SW, but we can 
    // keep the SW alive to receive location data from the main thread
    // even when the page is backgrounded, using periodic sync if supported.
  }
});

// Background Sync API
self.addEventListener('sync', (event) => {
  if (event.tag === SYNC_TAG) {
    event.waitUntil(sendLastKnownLocation());
  }
});

// Periodic Background Sync (Modern Browsers)
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'location-ping') {
    event.waitUntil(sendLastKnownLocation());
  }
});

async function sendLastKnownLocation() {
  // Retrieve queued location updates from IndexedDB
  // and send them to the backend /api/v2/live/location
  console.log('[SW] Sending background location update...');
  // Implementation details for DB retrieval would go here
}

// Handle push notifications that might trigger location checks
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  if (data.type === 'LOCATION_CHECK') {
    // Show a silent notification to keep process alive
    self.registration.showNotification('RouteMaster Guardian', {
      body: 'Active journey tracking in progress...',
      icon: '/icon-192x192.png',
      tag: 'guardian-mode',
      silent: true
    });
  }
});
