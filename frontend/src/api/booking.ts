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

// ==============================================================================
// BOOKING REQUEST API (Queue System)
// ==============================================================================

export interface BookingRequestPassenger {
  name: string;
  age: number;
  gender: "M" | "F" | "O";
  berth_preference?: "LOWER" | "MIDDLE" | "UPPER" | "SIDE_LOWER" | "SIDE_UPPER";
  id_proof_type?: "AADHAR" | "PAN" | "PASSPORT";
  id_proof_number?: string;
}

export interface BookingRequestCreate {
  source_station: string;
  destination_station: string;
  journey_date: string; // YYYY-MM-DD
  train_number: string;
  train_name?: string;
  class_type?: string;
  quota?: string;
  route_details?: Record<string, unknown>;
  passengers: BookingRequestPassenger[];
}

export interface BookingRequest {
  id: string;
  user_id: string;
  source_station: string;
  destination_station: string;
  journey_date: string;
  train_number: string;
  train_name?: string;
  class_type: string;
  quota: string;
  status: string;
  verification_status: string;
  payment_id?: string;
  created_at: string;
  updated_at: string;
  queue_status?: string;
}

export async function createBookingRequest(data: BookingRequestCreate): Promise<BookingRequest> {
  const res = await fetchWithAuth("/api/v1/booking/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error((error as { message?: string; detail?: string }).message || (error as { detail?: string }).detail || "Failed to create booking request");
  }
  return res.json();
}

export async function getBookingRequest(requestId: string): Promise<BookingRequest> {
  const res = await fetchWithAuth(`/api/v1/booking/request/${encodeURIComponent(requestId)}`, {
    method: "GET",
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error((error as { message?: string; detail?: string }).message || (error as { detail?: string }).detail || "Failed to fetch booking request");
  }
  return res.json();
}

export async function getMyBookingRequests(params?: { skip?: number; limit?: number }): Promise<BookingRequest[]> {
  let url = "/api/v1/booking/requests/my";
  if (params) {
    const qs: string[] = [];
    if (params.skip != null) qs.push(`skip=${params.skip}`);
    if (params.limit != null) qs.push(`limit=${params.limit}`);
    if (qs.length) url += `?${qs.join("&")}`;
  }
  const res = await fetchWithAuth(url);
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error((error as { message?: string; detail?: string }).message || (error as { detail?: string }).detail || "Failed to fetch booking requests");
  }
  return res.json();
}

// ==============================================================================
// REFUND API
// ==============================================================================

export interface Refund {
  id: string;
  booking_request_id: string;
  amount: number;
  currency: string;
  reason?: string;
  status: string;
  razorpay_refund_id?: string;
  created_at: string;
}

export async function createRefund(
  requestId: string,
  reason?: string
): Promise<Refund> {
  const res = await fetchWithAuth(`/api/v1/booking/request/${encodeURIComponent(requestId)}/refund`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error((error as { message?: string; detail?: string }).message || (error as { detail?: string }).detail || "Failed to create refund");
  }
  return res.json();
}

export async function getRefundStatus(requestId: string): Promise<Refund> {
  const res = await fetchWithAuth(`/api/v1/booking/request/${encodeURIComponent(requestId)}/refund`, {
    method: "GET",
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error((error as { message?: string; detail?: string }).message || (error as { detail?: string }).detail || "Failed to fetch refund status");
  }
  return res.json();
}

export async function getMyRefunds(params?: { skip?: number; limit?: number; status?: string }): Promise<Refund[]> {
  let url = "/api/v1/booking/refunds/my";
  if (params) {
    const qs: string[] = [];
    if (params.skip != null) qs.push(`skip=${params.skip}`);
    if (params.limit != null) qs.push(`limit=${params.limit}`);
    if (params.status) qs.push(`status=${encodeURIComponent(params.status)}`);
    if (qs.length) url += `?${qs.join("&")}`;
  }
  const res = await fetchWithAuth(url);
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error((error as { message?: string; detail?: string }).message || (error as { detail?: string }).detail || "Failed to fetch refunds");
  }
  return res.json();
}
