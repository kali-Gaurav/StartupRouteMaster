/**
 * Persistent ticket store (localStorage).
 * Used for /ticket/:id and ticket history. Survives refresh and return visits.
 */

const STORAGE_KEY = "route-master-tickets";
const MAX_TICKETS = 50;

export type TicketStatus = "confirmed" | "pending_irctc" | "completed" | "cancelled";

export interface StoredTicket {
  id: string;
  reference: string;
  originName: string;
  destName: string;
  travelDate: string;
  routeSummary: string;
  totalCost: number;
  irctcUrl: string | null;
  status: TicketStatus;
  createdAt: number;
  /** First segment train number for display */
  trainNumber?: string;
}

function loadAll(): StoredTicket[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as StoredTicket[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveAll(tickets: StoredTicket[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets));
  } catch (e) {
    console.warn("ticketStore save failed", e);
  }
}

export function saveTicket(ticket: Omit<StoredTicket, "createdAt">): void {
  const all = loadAll();
  const withDate: StoredTicket = { ...ticket, createdAt: Date.now() };
  const filtered = all.filter((t) => t.id !== ticket.id);
  filtered.unshift(withDate);
  saveAll(filtered.slice(0, MAX_TICKETS));
}

export function getTicket(id: string): StoredTicket | null {
  const all = loadAll();
  return all.find((t) => t.id === id) ?? null;
}

export function getAllTickets(): StoredTicket[] {
  return loadAll();
}

export function getTicketShareUrl(id: string): string {
  const base = typeof window !== "undefined" ? window.location.origin : "";
  return `${base}/ticket/${encodeURIComponent(id)}`;
}
