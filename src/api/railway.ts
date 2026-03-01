/**
 * Railway API — routes, stations, health, stats. No UI.
 * Uses getRailwayApiUrl (root paths: /routes, /stations/search, /health).
 */

import { getRailwayApiUrl } from "@/lib/utils";

export interface Station {
  code: string;
  name: string;
  city?: string;
  state?: string;
}

export interface BackendRoutesResponse {
  source: string;
  destination: string;
  routes: {
    direct: unknown[];
    one_transfer: unknown[];
    two_transfer: unknown[];
    three_transfer: unknown[];
  };
  stations?: Record<string, Station>;
  journey_message?: string;
  booking_tips?: string[];
  message?: string;
}

export async function searchStations(q: string): Promise<Station[]> {
  if (!q || q.trim().length < 2) return [];
  const url = getRailwayApiUrl("/stations/search?q=" + encodeURIComponent(q.trim())); // Fixed path
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Stations search failed: " + res.status);
  }
  const data = (await res.json()) as { stations?: Array<Record<string, unknown>> };
  const list = data.stations ?? [];
  return list.map((s: Record<string, unknown>) => ({
    code: (s.station_code ?? s.code ?? "") as string,
    name: String(s.station_name ?? s.name ?? s.station_code ?? s.code ?? "").trim(),
    city: String(s.city ?? "").trim(),
    state: String(s.state ?? "").trim(),
  }));
}

export async function searchRoutes(
  source: string,
  destination: string,
  params?: { date?: string; max_transfers?: number; max_results?: number; sort_by?: string; correlationId?: string; budget?: string }
): Promise<BackendRoutesResponse> {
  const src = String(source ?? "").trim().toUpperCase();
  const dest = String(destination ?? "").trim().toUpperCase();
  const date = params?.date?.trim() || new Date().toISOString().slice(0, 10);
  
  const body = {
    source: src,
    destination: dest,
    date: date,
    max_transfers: params?.max_transfers ?? 2,
    max_results: params?.max_results ?? 50,
    sort_by: params?.sort_by,
    budget: params?.budget,
  };

  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (params?.correlationId) headers["X-Correlation-Id"] = params.correlationId;

  const res = await fetch(getRailwayApiUrl("/search/"), { // Fixed: added trailing slash
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { message?: string; detail?: string | unknown[] };
    const msg = typeof err.message === "string" ? err.message : (Array.isArray(err.detail) ? (err.detail[0] as { msg?: string })?.msg : err.detail);
    throw new Error((msg as string) ?? "Routes search failed: " + res.status);
  }
  return res.json();
}

export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(getRailwayApiUrl("/health"));
    return res.ok;
  } catch {
    return false;
  }
}

export async function healthLive(): Promise<boolean> {
  try {
    const res = await fetch(getRailwayApiUrl("/health/live"));
    return res.ok;
  } catch {
    return false;
  }
}

export async function healthReady(): Promise<boolean> {
  try {
    const res = await fetch(getRailwayApiUrl("/health/ready"));
    return res.ok;
  } catch {
    return false;
  }
}

export async function getStats(): Promise<{ total_stations?: number; total_trains?: number; total_routes?: number }> {
  const res = await fetch(getRailwayApiUrl("/stats"));
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}
