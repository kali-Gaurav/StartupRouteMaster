import { v3Fetch } from "@/lib/apiClient";

export interface AvailabilityCheckRequest {
  trip_id: number | string; 
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
}

export interface BookingListResponse {
  bookings: Booking[];
  total: number;
  skip: number;
  limit: number;
}

export async function checkAvailability(data: AvailabilityCheckRequest): Promise<AvailabilityCheckResponse> {
  return v3Fetch("/api/v1/booking/availability", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getBookingByPnr(pnr: string): Promise<Booking> {
  return v3Fetch(`/api/v1/booking/${encodeURIComponent(pnr)}`);
}

export async function getBookings(params?: { skip?: number; limit?: number }, signal?: AbortSignal): Promise<BookingListResponse> {
  let url = "/api/v1/booking/";
  if (params) {
    const qs: string[] = [];
    if (params.skip != null) qs.push(`skip=${params.skip}`);
    if (params.limit != null) qs.push(`limit=${params.limit}`);
    if (qs.length) url += `?${qs.join("&")}`;
  }
  return v3Fetch(url, { signal });
}

export interface BookingRequestPassenger {
  name: string;
  age: number;
  gender: "M" | "F" | "O";
}

export interface BookingRequestCreate {
  source_station: string;
  destination_station: string;
  journey_date: string; 
  train_number: string;
  passengers: BookingRequestPassenger[];
}

export interface BookingRequest {
  id: string;
  user_id: string;
  status: string;
  created_at: string;
}

export async function createBookingRequest(data: BookingRequestCreate): Promise<BookingRequest> {
  return v3Fetch("/api/v1/booking/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export interface SegmentPNR {
  id: string;
  pnr: string;
  status: string;
}

export async function getSegmentPnrs(journeyId: string): Promise<SegmentPNR[]> {
  return v3Fetch(`/api/v1/booking/segment-pnrs/${encodeURIComponent(journeyId)}`);
}

export async function getBookingRequest(requestId: string): Promise<BookingRequest> {
  return v3Fetch(`/api/v1/booking/request/${encodeURIComponent(requestId)}`);
}

export async function getMyBookingRequests(params?: { skip?: number; limit?: number }): Promise<BookingRequest[]> {
  let url = "/api/v1/booking/requests/my";
  if (params) {
    const qs: string[] = [];
    if (params.skip != null) qs.push(`skip=${params.skip}`);
    if (params.limit != null) qs.push(`limit=${params.limit}`);
    if (qs.length) url += `?${qs.join("&")}`;
  }
  return v3Fetch(url);
}

export interface Refund {
  id: string;
  status: string;
}

export async function createRefund(requestId: string, reason?: string): Promise<Refund> {
  return v3Fetch(`/api/v1/booking/request/${encodeURIComponent(requestId)}/refund`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
}

export async function getRefundStatus(requestId: string): Promise<Refund> {
  return v3Fetch(`/api/v1/booking/request/${encodeURIComponent(requestId)}/refund`);
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
  return v3Fetch(url);
}
