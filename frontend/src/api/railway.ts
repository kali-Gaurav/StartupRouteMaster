import { getRailwayApiUrl } from "@/lib/utils";
import { v3Fetch } from "@/lib/apiClient";

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
  const url = getRailwayApiUrl("/stations/search?q=" + encodeURIComponent(q.trim()));
  const data = await v3Fetch<{ stations?: Array<Record<string, unknown>> }>(url);
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
  params?: { date?: string; max_transfers?: number; max_results?: number; sort_by?: string; correlationId?: string; budget?: string; discovery_only?: boolean }
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
    discovery_only: params?.discovery_only ?? false,
  };

  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (params?.correlationId) headers["X-Correlation-Id"] = params.correlationId;

  return v3Fetch<BackendRoutesResponse>(getRailwayApiUrl("/search/"), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
}

export async function healthCheck(): Promise<boolean> {
  try {
    await v3Fetch(getRailwayApiUrl("/health"));
    return true;
  } catch {
    return false;
  }
}

export async function healthLive(): Promise<boolean> {
  try {
    await v3Fetch(getRailwayApiUrl("/health/live"));
    return true;
  } catch {
    return false;
  }
}

export async function healthReady(): Promise<boolean> {
  try {
    await v3Fetch(getRailwayApiUrl("/health/ready"));
    return true;
  } catch {
    return false;
  }
}

export async function getStats(): Promise<{ total_stations?: number; total_trains?: number; total_routes?: number }> {
  return v3Fetch(getRailwayApiUrl("/stats"));
}
