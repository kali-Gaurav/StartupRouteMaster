import { v3Fetch } from "@/lib/apiClient";

export interface AuthResponse {
  token: string;
  user: Record<string, unknown>;
  is_new_user: boolean;
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

export async function sendOTP(data: SendOTPRequest): Promise<{ cooldown_seconds: number }> {
  return v3Fetch("/auth/send-otp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function verifyOTP(data: VerifyOTPRequest): Promise<AuthResponse> {
  return v3Fetch("/auth/verify-otp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function googleAuth(idToken: string): Promise<AuthResponse> {
  return v3Fetch("/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
}

export async function telegramAuth(initData: string, user: Record<string, unknown>): Promise<AuthResponse> {
  return v3Fetch("/auth/telegram", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: initData, user }),
  });
}

export async function getCurrentUser(): Promise<Record<string, unknown>> {
  return v3Fetch("/auth/me");
}

export async function updateProfile(data: Record<string, unknown>): Promise<Record<string, unknown>> {
  return v3Fetch("/user/profile", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateLocation(latitude: number, longitude: number): Promise<{ latitude: number; longitude: number; safety?: any }> {
  return v3Fetch("/user/location", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ latitude, longitude }),
  });
}

export async function logout(): Promise<void> {
  try {
    await v3Fetch("/auth/logout", { method: "POST" });
  } catch {
    // Non-fatal
  }
}
