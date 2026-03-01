import { getRailwayApiUrl } from '@/lib/utils';

export interface PendingAction {
  id?: number;
  type: 'search' | 'booking_intent' | 'log_event';
  payload: any;
  timestamp: number;
}

// Extend DB for pending actions
export async function addPendingAction(type: PendingAction['type'], payload: any) {
  try {
    // Note: We can add an 'actions' table to Dexie if needed, 
    // but for now we'll use a simple localStorage queue or just handle searches
    const queue = JSON.parse(localStorage.getItem('pending_rail_actions') || '[]');
    queue.push({ type, payload, timestamp: Date.now() });
    localStorage.setItem('pending_rail_actions', JSON.stringify(queue));
  } catch (err) {
    console.warn("Failed to queue action", err);
  }
}

export async function processSyncQueue() {
  const queue: PendingAction[] = JSON.parse(localStorage.getItem('pending_rail_actions') || '[]');
  if (queue.length === 0) return;

  console.log(`[SyncEngine] Processing ${queue.length} pending actions...`);
  
  const remaining: PendingAction[] = [];
  
  for (const action of queue) {
    try {
      // Example: Sync searches to backend for analytics
      if (action.type === 'search') {
        await fetch(getRailwayApiUrl('/analytics/search'), {
          method: 'POST',
          body: JSON.stringify(action.payload)
        });
      }
      // Add other sync types here
    } catch (err) {
      remaining.push(action);
    }
  }

  localStorage.setItem('pending_rail_actions', JSON.stringify(remaining));
}

// Auto-sync when coming back online
window.addEventListener('online', processSyncQueue);
