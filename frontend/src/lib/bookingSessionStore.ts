/**
 * Booking flow session persistence (sessionStorage).
 * Enables "Resume?" after refresh or return. TTL 30 minutes.
 */

const STORAGE_KEY = "route-master-booking-session";
const TTL_MS = 30 * 60 * 1000;

export interface BookingSessionSnapshot {
  step: string;
  travelDate: string;
  originName: string;
  destName: string;
  updatedAt?: number;
  /** Serialized route (Route from data/routes) */
  route: string;
}

export function saveBookingSession(snapshot: BookingSessionSnapshot): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ ...snapshot, updatedAt: Date.now() }));
  } catch (e) {
    console.warn("bookingSession save failed", e);
  }
}

export function loadBookingSession(): BookingSessionSnapshot | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as BookingSessionSnapshot & { updatedAt: number };
    if (!parsed.updatedAt || Date.now() - parsed.updatedAt > TTL_MS) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearBookingSession(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function hasRecoverableSession(): boolean {
  return loadBookingSession() != null;
}
