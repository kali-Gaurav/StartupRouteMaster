/**
 * Auth API — pure API calls. No UI.
 * Uses apiClient (Bearer token, 401 → logout). Base: RAILWAY_BACKEND_URL + /api.
 */

import { fetchWithAuth } from "@/lib/apiClient";

export interface AuthResponse {
  success: boolean;
  message: string;
  token?: string;
  refresh_token?: string;
  user?: Record<string, unknown>;
  is_new_user?: boolean;
}

export interface SendOTPRequest {
  phone?: string;
  email?: string;
}

export interface VerifyOTPRequest {
  phone?: string;
  email?: string;
  otp: string;
}

export async function sendOTP(data: SendOTPRequest): Promise<AuthResponse> {
  const res = await fetchWithAuth("/auth/send-otp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function verifyOTP(data: VerifyOTPRequest): Promise<AuthResponse> {
  const res = await fetchWithAuth("/auth/verify-otp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function googleAuth(idToken: string): Promise<AuthResponse> {
  const res = await fetchWithAuth("/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  return res.json();
}

export async function telegramAuth(initData: string, user: Record<string, unknown>): Promise<AuthResponse> {
  const res = await fetchWithAuth("/auth/telegram", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: initData, user }),
  });
  return res.json();
}

export async function getCurrentUser(): Promise<{ success: boolean; user?: Record<string, unknown> }> {
  const res = await fetchWithAuth("/auth/me");
  if (!res.ok) throw new Error("Failed to get current user");
  return res.json();
}

export async function updateProfile(data: Record<string, unknown>): Promise<{ success: boolean; user?: Record<string, unknown> }> {
  const res = await fetchWithAuth("/user/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function updateLocation(latitude: number, longitude: number): Promise<{ success: boolean; message?: string }> {
  const res = await fetchWithAuth("/user/location", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ latitude, longitude }),
  });
  return res.json();
}

export async function logout(): Promise<void> {
  await fetchWithAuth("/auth/logout", { method: "POST" });
}
