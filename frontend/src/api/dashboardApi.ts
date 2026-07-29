/**
 * Dashboard API Client
 * Handles all dashboard and user profile API calls
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface DashboardSummary {
  total_bookings: number;
  total_spent: number;
  upcoming_bookings: number;
  cancelled_bookings: number;
  recent_activity: any[];
}

export interface Booking {
  booking_id: string;
  pnr_number: string;
  status: string;
  total_amount: number;
  travel_date: string;
  train_number: string;
  from_station: string;
  to_station: string;
  class_type: string;
  created_at: string;
}

export interface BookingsResponse {
  bookings: Booking[];
  total: number;
  limit: number;
  offset: number;
}

export interface Payment {
  payment_id: string;
  booking_id: string;
  amount: number;
  status: string;
  payment_method: string;
  created_at: string;
  transaction_id: string;
}

export interface PaymentsResponse {
  payments: Payment[];
  total: number;
  limit: number;
  offset: number;
}

export interface Ticket {
  ticket_id: string;
  booking_id: string;
  pnr_number: string;
  passenger_name: string;
  train_number: string;
  from_station: string;
  to_station: string;
  travel_date: string;
  seat_number: string;
  class: string;
  coach: string;
  status: string;
}

export interface TicketsResponse {
  tickets: Ticket[];
  total: number;
}

export interface UserProfile {
  user_id: string;
  email: string;
  full_name: string;
  phone_number: string;
  profile_picture_url: string;
  role: string;
  verified: boolean;
  verified_at: string;
  created_at: string;
  last_active_at: string;
  preferences: Record<string, boolean>;
}

export interface SavedRoute {
  id: string;
  name: string;
  from_station: string;
  to_station: string;
  created_at: string;
}

export interface SavedRoutesResponse {
  routes: SavedRoute[];
  total: number;
}

/**
 * Get dashboard summary statistics
 */
export async function getDashboardSummary(token: string): Promise<DashboardSummary> {
  const response = await fetch(`${API_BASE}/api/v1/user/dashboard`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard summary: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get user bookings with optional filtering and pagination
 */
export async function getUserBookings(
  token: string,
  limit: number = 50,
  offset: number = 0,
  statusFilter?: string
): Promise<BookingsResponse> {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });

  if (statusFilter) {
    params.append('status_filter', statusFilter);
  }

  const response = await fetch(`${API_BASE}/api/v1/user/bookings?${params}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch bookings: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get user payment history
 */
export async function getUserPayments(
  token: string,
  limit: number = 50,
  offset: number = 0
): Promise<PaymentsResponse> {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });

  const response = await fetch(`${API_BASE}/api/v1/user/payments?${params}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch payments: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get user tickets
 */
export async function getUserTickets(token: string): Promise<TicketsResponse> {
  const response = await fetch(`${API_BASE}/api/v1/user/tickets`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch tickets: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get user profile
 */
export async function getUserProfile(token: string): Promise<UserProfile> {
  const response = await fetch(`${API_BASE}/api/v1/user/profile`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch user profile: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get saved routes
 */
export async function getSavedRoutes(token: string): Promise<SavedRoutesResponse> {
  const response = await fetch(`${API_BASE}/api/v1/user/saved-routes`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch saved routes: ${response.statusText}`);
  }

  return response.json();
}
