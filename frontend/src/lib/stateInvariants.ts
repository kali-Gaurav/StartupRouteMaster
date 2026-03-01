/**
 * Global state integrity layer.
 * Run on app load to enforce invariants and recover from corrupted local data.
 * - No duplicate ticket IDs; valid ticket shape; trim to max size.
 * - Expired booking sessions purged.
 * - Corrupted data reset safely (no throw).
 */

import { logEvent } from "@/lib/observability";

const TICKET_STORAGE_KEY = "route-master-tickets";
const SESSION_STORAGE_KEY = "route-master-booking-session";
const MAX_TICKETS = 50;
const SESSION_TTL_MS = 30 * 60 * 1000;

const VALID_TICKET_STATUS = new Set(["confirmed", "pending_irctc", "completed", "cancelled"]);

function isTicketShape(t: unknown): t is { id: string } & Record<string, unknown> {
  return t != null && typeof t === "object" && "id" in t && typeof (t as Record<string, unknown>).id === "string";
}

/** Keep only entries that have the minimal shape the app expects (Ticket page, list). */
function sanitizeTicket(t: unknown): Record<string, unknown> | null {
  if (!isTicketShape(t)) return null;
  const o = t as Record<string, unknown>;
  if (
    typeof o.reference !== "string" ||
    typeof o.originName !== "string" ||
    typeof o.destName !== "string" ||
    typeof o.travelDate !== "string" ||
    typeof o.routeSummary !== "string" ||
    typeof o.totalCost !== "number"
  )
    return null;
  if (!VALID_TICKET_STATUS.has(o.status as string)) o.status = "pending_irctc";
  return o;
}

/**
 * Validate and repair ticket store. Removes duplicates (keep newest), invalid entries, and trims to MAX_TICKETS.
 */
function enforceTicketInvariants(): void {
  try {
    const raw = localStorage.getItem(TICKET_STORAGE_KEY);
    if (!raw) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      localStorage.removeItem(TICKET_STORAGE_KEY);
      logEvent("state_invariants", { store: "tickets", action: "reset_parse_error" }, "warn");
      return;
    }
    if (!Array.isArray(parsed)) {
      localStorage.removeItem(TICKET_STORAGE_KEY);
      logEvent("state_invariants", { store: "tickets", action: "reset_not_array" }, "warn");
      return;
    }
    const seen = new Set<string>();
    const repaired: Record<string, unknown>[] = [];
    for (const item of parsed) {
      const sane = sanitizeTicket(item);
      if (!sane) continue;
      const id = sane.id as string;
      if (seen.has(id)) continue;
      seen.add(id);
      repaired.push({ ...sane, createdAt: typeof sane.createdAt === "number" ? sane.createdAt : Date.now() });
    }
    const trimmed = repaired.slice(0, MAX_TICKETS);
    localStorage.setItem(TICKET_STORAGE_KEY, JSON.stringify(trimmed));
    if (repaired.length !== parsed.length || trimmed.length !== repaired.length) {
      logEvent("state_invariants", {
        store: "tickets",
        action: "repaired",
        before: parsed.length,
        after: trimmed.length,
      }, "info");
    }
  } catch (e) {
    try {
      localStorage.removeItem(TICKET_STORAGE_KEY);
    } catch {
      /* ignore */
    }
    logEvent("state_invariants", { store: "tickets", action: "reset_error", error: String(e) }, "error");
  }
}

/**
 * Purge expired booking session. Session store uses TTL; remove if updatedAt is missing or too old.
 */
function enforceSessionInvariants(): void {
  try {
    const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return;
    let parsed: { updatedAt?: number; [k: string]: unknown };
    try {
      parsed = JSON.parse(raw) as { updatedAt?: number };
    } catch {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
      logEvent("state_invariants", { store: "session", action: "reset_parse_error" }, "warn");
      return;
    }
    const updatedAt = parsed?.updatedAt;
    if (typeof updatedAt !== "number" || Date.now() - updatedAt > SESSION_TTL_MS) {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
      logEvent("state_invariants", { store: "session", action: "purged_expired" }, "info");
    }
  } catch (e) {
    try {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      /* ignore */
    }
    logEvent("state_invariants", { store: "session", action: "reset_error", error: String(e) }, "error");
  }
}

/**
 * Run all state invariant checks. Call once at app bootstrap (e.g. main.tsx or root layout).
 * Safe to call from any environment; no-op if storage is unavailable.
 */
export function runStateInvariants(): void {
  if (typeof localStorage === "undefined" || typeof sessionStorage === "undefined") return;
  enforceTicketInvariants();
  enforceSessionInvariants();
}
