/**
 * Payment & Booking API — pure API calls. No UI.
 * Uses apiClient (Bearer token). Base: VITE_API_URL + /api.
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

export async function getBookingHistory(signal?: AbortSignal): Promise<{ success: boolean; data?: unknown[]; message?: string }> {
  const res = await fetchWithAuth("/payment/booking/history", { signal });
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
