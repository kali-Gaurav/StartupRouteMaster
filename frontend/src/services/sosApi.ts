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
  train_no?: string;
  passenger_name?: string;
  emergency_contacts?: string[];
  message?: string;
  trip?: SOSTrip;
}

export interface SOSEvent {
  id: string;
  lat: number;
  lng: number;
  name: string;
  phone?: string;
  email?: string;
  extra?: string;
  train_no?: string;
  passenger_name?: string;
  trip?: SOSTrip;
  status: "active" | "resolved" | "trip_ended";
  priority?: string;
  triggered_at?: string;
  created_at?: string;
  google_maps_url?: string;
  resolved_at?: string;
}

// All calls go to /api/v1/sos/*
const SOS_BASE = "/api/v1/sos";

export async function triggerSOS(
  payload: SOSPayload,
  token?: string | null
): Promise<{ ok?: boolean; success?: boolean; event_id?: string; id?: string; tracking_url?: string }> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const body = {
    lat: payload.lat,
    lng: payload.lng,
    train_no: payload.train_no || payload.trip?.vehicle_number || "",
    passenger_name: payload.passenger_name || payload.name || "Passenger",
    emergency_contacts: payload.emergency_contacts || [],
    message: payload.message || payload.extra || "",
  };

  const res = await fetch(getRailwayApiUrl(`${SOS_BASE}/trigger`), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to send SOS");
  return res.json();
}

export async function getActiveSOS(token?: string | null): Promise<{ events: SOSEvent[] }> {
  const headers: HeadersInit = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(getRailwayApiUrl(`${SOS_BASE}`), { headers });
  if (!res.ok) throw new Error("Failed to fetch SOS events");
  const data = await res.json();
  // Backend returns {active_events: [...]} — normalize to {events: [...]}
  return { events: data.active_events || data.events || [] };
}

export async function getAllSOS(token?: string | null): Promise<{ events: SOSEvent[] }> {
  const headers: HeadersInit = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(getRailwayApiUrl(`${SOS_BASE}/all`), { headers });
  if (!res.ok) throw new Error("Failed to fetch SOS events");
  return res.json();
}

export async function resolveSOS(eventId: string, token?: string | null): Promise<void> {
  const headers: HeadersInit = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(getRailwayApiUrl(`${SOS_BASE}/${eventId}/resolve`), {
    method: "POST",
    headers,
  });
  if (!res.ok) throw new Error("Failed to resolve SOS");
}

export async function sendLocationUpdate(
  eventId: string,
  lat: number,
  lng: number,
  token?: string | null
): Promise<void> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(getRailwayApiUrl(`${SOS_BASE}/${eventId}/location`), {
    method: "POST",
    headers,
    body: JSON.stringify({ lat, lng }),
  });
  if (!res.ok) throw new Error("Failed to send location");
}

export async function sendTelemetry(
  eventId: string,
  data: {
    lat: number;
    lng: number;
    battery_level?: number;
    speed_kmh?: number;
    accuracy_m?: number;
    timestamp?: string;
  },
  token?: string | null
): Promise<void> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(getRailwayApiUrl(`${SOS_BASE}/${eventId}/telemetry`), {
    method: "POST",
    headers,
    body: JSON.stringify(data),
  });
  // Non-critical — don't throw
  if (!res.ok) console.warn("Telemetry update failed (non-critical)");
}

export async function endTrip(eventId: string, token?: string | null): Promise<void> {
  const headers: HeadersInit = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(getRailwayApiUrl(`${SOS_BASE}/${eventId}/end`), {
    method: "POST",
    headers,
  });
  if (!res.ok) throw new Error("Failed to end trip");
}

/** Helpers for building Google Maps URL */
export function getGoogleMapsUrl(lat: number, lng: number): string {
  return `https://maps.google.com/?q=${lat},${lng}`;
}

export function getSOSShareText(event: Partial<SOSEvent>, trackingUrl: string): string {
  const name = event.passenger_name || event.name || "Someone";
  const train = event.train_no ? ` on train ${event.train_no}` : "";
  const mapsUrl = event.lat && event.lng ? getGoogleMapsUrl(event.lat, event.lng) : "";
  return `🚨 SOS ALERT: ${name} needs help${train}!\nLocation: ${mapsUrl}\nLive tracking: ${trackingUrl}\nPlease call them immediately.`;
}
