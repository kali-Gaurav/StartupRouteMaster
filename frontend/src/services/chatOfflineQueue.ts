/**
 * Simple IndexedDB wrapper for Chat Offline Queue (Task 7)
 */
const DB_NAME = 'RailAssistantOffline';
const STORE_NAME = 'messageQueue';
const DB_VERSION = 1;

export interface QueuedMessage {
  id: string;
  role: 'user';
  content: string;
  timestamp: string;
  sessionId: string;
}

export const initOfflineQueue = (): Promise<IDBDatabase> => {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
};

export const queueMessage = async (msg: QueuedMessage): Promise<void> => {
  const db = await initOfflineQueue();
  const tx = db.transaction(STORE_NAME, 'readwrite');
  const store = tx.objectStore(STORE_NAME);
  store.put(msg);
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
};

export const getQueuedMessages = async (): Promise<QueuedMessage[]> => {
  const db = await initOfflineQueue();
  const tx = db.transaction(STORE_NAME, 'readonly');
  const store = tx.objectStore(STORE_NAME);
  const request = store.getAll();
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
};

export const clearQueuedMessage = async (id: string): Promise<void> => {
  const db = await initOfflineQueue();
  const tx = db.transaction(STORE_NAME, 'readwrite');
  const store = tx.objectStore(STORE_NAME);
  store.delete(id);
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
};
