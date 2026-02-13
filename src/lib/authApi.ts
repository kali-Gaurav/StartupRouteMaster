/**
 * Authentication API
 * Uses shared apiClient for base URL, auth header, and 401 → logout.
 */

import { fetchWithAuth } from './apiClient';

export interface AuthResponse {
  success: boolean;
  message: string;
  token?: string;
  refresh_token?: string;
  user?: any;
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

export const telegramAuth = async (initData: string, user: any): Promise<AuthResponse> => {
  const response = await fetchWithAuth('/auth/telegram', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ init_data: initData, user }),
  });
  return await response.json();
};

/** Uses token from apiClient config (set by AuthProvider). */
export const getCurrentUser = async (): Promise<any> => {
  const response = await fetchWithAuth('/auth/me');
  if (!response.ok) throw new Error('Failed to get current user');
  return await response.json();
};

/** Uses token from apiClient config. */
export const updateProfile = async (data: any): Promise<any> => {
  const response = await fetchWithAuth('/user/profile', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json();
};

/** Uses token from apiClient config. */
export const updateLocation = async (latitude: number, longitude: number): Promise<any> => {
  const response = await fetchWithAuth('/user/location', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ latitude, longitude }),
  });
  return await response.json();
};
