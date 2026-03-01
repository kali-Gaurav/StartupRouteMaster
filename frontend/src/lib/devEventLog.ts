/**
 * Dev-only in-memory event log for DevDebugPanel (ring buffer).
 * Bounded to MAX_EVENTS to avoid memory growth in long dev sessions.
 */

const MAX_EVENTS = 200;

export type EventLevel = "info" | "warn" | "error" | "critical";

export interface DevEventEntry {
  event: string;
  level?: EventLevel;
  payload?: Record<string, unknown>;
  ts: number;
}

const log: DevEventEntry[] = [];

export function getDevEventLog(): DevEventEntry[] {
  return [...log];
}

export function pushDevEvent(
  event: string,
  payload?: Record<string, unknown>,
  level?: EventLevel
): void {
  if (!import.meta.env.DEV) return;
  log.unshift({ event, level: level ?? "info", payload, ts: Date.now() });
  if (log.length > MAX_EVENTS) log.pop();
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("dev-event-log-update"));
}

export function getLastDevError(): Error | null {
  return lastError;
}

let lastError: Error | null = null;
export function setLastDevError(e: Error | null): void {
  lastError = e;
}
