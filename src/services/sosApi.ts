import { getRailwayApiUrl } from "@/lib/utils";

export interface SOSTrip {
  origin?: string;
  destination?: string;
  mode?: string;
  vehicle_number?: string;
  driver_name?: string;
  boarding_time?: string;
  eta?: string;
}

export interface SOSPayload {
  lat: number;
  lng: number;
  name?: string;
  phone?: string;
  email?: string;
  extra?: string;
  trip?: SOSTrip;
}

export interface SOSEvent {
  id: string;
  lat: number;
  lng: number;
  name: string;
  phone: string;
  email: string;
  extra: string;
  trip?: SOSTrip;
  status: "active" | "resolved" | "trip_ended";
  priority: string;
  triggered_at: string;
  google_maps_url: string;
  resolved_at?: string;
}

export async function triggerSOS(payload: SOSPayload): Promise<{ ok: boolean; id: string }> {
  const res = await fetch(getRailwayApiUrl("/sos"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to send SOS");
  return res.json();
}

export async function getActiveSOS(): Promise<{ events: SOSEvent[] }> {
  const res = await fetch(getRailwayApiUrl("/sos/active"));
  if (!res.ok) throw new Error("Failed to fetch SOS events");
  return res.json();
}

export async function getAllSOS(): Promise<{ events: SOSEvent[] }> {
  const res = await fetch(getRailwayApiUrl("/sos/all"));
  if (!res.ok) throw new Error("Failed to fetch SOS events");
  return res.json();
}

export async function resolveSOS(eventId: string): Promise<void> {
  const res = await fetch(getRailwayApiUrl(`/sos/${eventId}/resolve`), { method: "POST" });
  if (!res.ok) throw new Error("Failed to resolve");
}

export async function sendLocationUpdate(eventId: string, lat: number, lng: number): Promise<void> {
  const res = await fetch(getRailwayApiUrl(`/sos/${eventId}/location`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lng }),
  });
  if (!res.ok) throw new Error("Failed to send location");
}

export async function endTrip(eventId: string): Promise<void> {
  const res = await fetch(getRailwayApiUrl(`/sos/${eventId}/end`), { method: "POST" });
  if (!res.ok) throw new Error("Failed to end trip");
}
