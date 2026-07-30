/**
 * Route Sorter Web Worker (Suggestion #5)
 * Offloads heavy sorting/filtering from the main thread.
 */

self.onmessage = (e: MessageEvent) => {
  const { routes, sortBy, order } = e.data;

  if (!routes || !Array.isArray(routes)) return;

  const sorted = [...routes].sort((a, b) => {
    let valA, valB;

    switch (sortBy) {
      case 'fare':
        valA = a.fare || 999999;
        valB = b.fare || 999999;
        break;
      case 'duration_min':
        // Assuming duration is a string like "12h 30m", we might need a numeric fallback
        valA = a.time_minutes || 9999;
        valB = b.time_minutes || 9999;
        break;
      case 'departure':
        valA = a.departure;
        valB = b.departure;
        break;
      default:
        return 0;
    }

    if (valA < valB) return order === 'asc' ? -1 : 1;
    if (valA > valB) return order === 'asc' ? 1 : -1;
    return 0;
  });

  self.postMessage({ sorted });
};
