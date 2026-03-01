/**
 * Payment & Booking API — pure API calls. No UI.
 * Uses apiClient (Bearer token). Base: RAILWAY_BACKEND_URL + /api.
 */

import { fetchWithAuth } from "@/lib/apiClient";

export interface CreateOrderRequest {
  route_origin: string;
  route_destination: string;
  train_no?: string;
  travel_date?: string;
}

export interface VerifyPaymentRequest {
  order_id: string;
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface BookingRedirectRequest {
  payment_order_id: string;
  origin: string;
  destination: string;
  train_no: string;
  travel_date: string;
  travel_class?: string;
}

export async function createOrder(data: CreateOrderRequest): Promise<unknown> {
  const res = await fetchWithAuth("/payment/create_order", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function verifyPayment(data: VerifyPaymentRequest): Promise<unknown> {
  const res = await fetchWithAuth("/payment/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function consumeRedirectToken(token: string): Promise<unknown> {
  const res = await fetchWithAuth("/payment/consume-redirect-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  return res.json();
}

export async function getBookingHistory(
  params?: { skip?: number; limit?: number },
  signal?: AbortSignal
): Promise<{ success: boolean; payments?: unknown[]; total?: number; skip?: number; limit?: number; message?: string }> {
  let url = "/payment/booking/history";
  if (params) {
    const qs: string[] = [];
    if (params.skip != null) qs.push(`skip=${params.skip}`);
    if (params.limit != null) qs.push(`limit=${params.limit}`);
    if (qs.length) url += `?${qs.join("&")}`;
  }
  const res = await fetchWithAuth(url, { signal });
  return res.json();
}

export async function createBookingRedirect(data: BookingRedirectRequest): Promise<unknown> {
  const res = await fetchWithAuth("/payment/booking/redirect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}
