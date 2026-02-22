/**
 * Booking API
 * Interacts with /api/v1/booking endpoints.
 */

import { fetchWithAuth } from "@/lib/apiClient";

export interface AvailabilityCheckRequest {
  trip_id: number | string; // Support both string and number
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
  // additional compatibility fields
  availability_status?: string;
  fare?: number;
  quota?: string;
  class?: string;
  probability?: number;
}

export interface Booking {
  id: string;
  pnr_number: string;
  user_id: string;
  travel_date: string;
  booking_status: string;
  amount_paid: number;
  booking_details: Record<string, unknown>;
  passenger_details?: PassengerDetail[];
  created_at: string;
  payment_status?: string;
}

export interface PassengerDetail {
  full_name: string;
  age: number;
  gender: string;
  phone_number?: string;
  email?: string;
  document_type?: string;
  document_number?: string;
  concession_type?: string;
  concession_discount?: number;
  meal_preference?: string;
}

export interface BookingListResponse {
  bookings: Booking[];
  total: number;
  skip: number;
  limit: number;
}

export async function checkAvailability(data: AvailabilityCheckRequest): Promise<AvailabilityCheckResponse> {
  const res = await fetchWithAuth("/api/v1/booking/availability", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error((error as { message?: string; detail?: string }).message || (error as { detail?: string }).detail || "Availability check failed");
  }
  return res.json();
}

export async function getBookingByPnr(pnr: string): Promise<Booking> {
  const res = await fetchWithAuth(`/api/v1/booking/${encodeURIComponent(pnr)}`, {
    method: "GET",
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error((error as { message?: string; detail?: string }).message || (error as { detail?: string }).detail || "Failed to fetch booking");
  }
  return res.json();
}

export async function getBookings(params?: { skip?: number; limit?: number }, signal?: AbortSignal): Promise<BookingListResponse> {
  let url = "/api/v1/booking/";
  if (params) {
    const qs: string[] = [];
    if (params.skip != null) qs.push(`skip=${params.skip}`);
    if (params.limit != null) qs.push(`limit=${params.limit}`);
    if (qs.length) url += `?${qs.join("&")}`;
  }
  const res = await fetchWithAuth(url, { signal });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error((error as { message?: string; detail?: string }).message || (error as { detail?: string }).detail || "Failed to fetch bookings");
  }
  return res.json();
}
