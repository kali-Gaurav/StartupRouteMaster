/**
 * Authentication API
 * Uses shared apiClient for base URL, auth header, and 401 → logout.
 */

import { fetchWithAuth } from './apiClient';

export interface User {
  user_id: number;
  id?: string; // Keep id as optional string just in case
  phone?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  telegram_id?: number;
}

export interface AuthResponse {
  success: boolean;
  message: string;
  token?: string;
  refresh_token?: string;
  user?: User;
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

export const sendOTP = async (data: SendOTPRequest): Promise<AuthResponse> => {
  const response = await fetchWithAuth('/auth/send-otp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json();
};

export const verifyOTP = async (data: VerifyOTPRequest): Promise<AuthResponse> => {
  const response = await fetchWithAuth('/auth/verify-otp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json();
};

export const googleAuth = async (idToken: string): Promise<AuthResponse> => {
  const response = await fetchWithAuth('/auth/google', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_token: idToken }),
  });
  return await response.json();
};

export const telegramAuth = async (initData: string, user: unknown): Promise<AuthResponse> => {
  const response = await fetchWithAuth('/auth/telegram', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ init_data: initData, user }),
  });
  return await response.json();
};

/** Uses token from apiClient config (set by AuthProvider). */
export const getCurrentUser = async (): Promise<User> => {
  const response = await fetchWithAuth('/auth/me');
  if (!response.ok) throw new Error('Failed to get current user');
  return await response.json();
};

/** Uses token from apiClient config. */
export const updateProfile = async (data: Partial<User>): Promise<{ success: boolean }> => {
  const response = await fetchWithAuth('/user/profile', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json();
};

/** Uses token from apiClient config. */
export const updateLocation = async (latitude: number, longitude: number): Promise<{ success: boolean }> => {
  const response = await fetchWithAuth('/user/location', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ latitude, longitude }),
  });
  return await response.json();
};

// Refreshes tokens using the stored refresh token. Returns new auth response or throws on failure.
export const refreshToken = async (): Promise<AuthResponse> => {
  // Direct fetch; this should not call fetchWithAuth to avoid recursion
  const base = API_BASE.replace(/\/$/, '');
  const url = base + '/api/auth/refresh';
  const refresh_token = localStorage.getItem('refresh_token');
  if (!refresh_token) throw new Error('No refresh token available');
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token }),
  });
  if (!res.ok) {
    throw new Error('Failed to refresh token');
  }
  return await res.json();
};
