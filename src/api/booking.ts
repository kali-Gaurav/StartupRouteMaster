/**
 * Booking API
 * Interacts with /api/v1/booking endpoints.
 */

import { fetchWithAuth } from "@/lib/apiClient";

export interface AvailabilityCheckRequest {
  trip_id: number;
  from_stop_id: number;
  to_stop_id: number;
  travel_date: string;
  quota_type: string;
  passengers?: number;
}

export interface AvailabilityCheckResponse {
  available: boolean;
  available_seats: number;
  total_seats: number;
  waitlist_position?: number;
  confirmation_probability?: number;
  message: string;
}

export async function checkAvailability(data: AvailabilityCheckRequest): Promise<AvailabilityCheckResponse> {
  const res = await fetchWithAuth("/v1/booking/availability", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}
