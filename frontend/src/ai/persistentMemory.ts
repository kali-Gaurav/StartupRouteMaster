/**
 * Diksha Persistent Memory - Cross-session context retention.
 */

export interface MemoryState {
  lastIntent?: string;
  lastQuery?: string;
  guardianActive?: boolean;
  journeyActive?: boolean;
  emotionalRisk?: number;
  lastInteraction?: string;
}

const STORAGE_KEY = "diksha_memory_v1";

export function loadMemory(): MemoryState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function saveMemory(state: MemoryState) {
  try {
    const currentState = loadMemory();
    const updatedState = { ...currentState, ...state, lastInteraction: new Date().toISOString() };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updatedState));
  } catch (err) {
    console.error("Failed to save AI memory:", err);
  }
}

export function clearMemory() {
  localStorage.removeItem(STORAGE_KEY);
}
