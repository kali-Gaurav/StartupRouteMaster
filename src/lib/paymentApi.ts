/**
 * Payment API
 * Uses shared apiClient for base URL, auth header, and 401 → logout.
 */

import { fetchWithAuth } from './apiClient';

declare global {
  interface Window {
    Razorpay: unknown;
  }
}

export interface PaymentOrder {
  order_id: string;
  razorpay_order_id: string;
  amount: number;
  currency: string;
  key_id: string;
}

export interface CreateOrderRequest {
  route_origin?: string; // Made optional for unlock flow
  route_destination?: string; // Made optional for unlock flow
  train_no?: string;
  travel_date: string; // Made required for both unlock and booking
  route_id: string; // Add route_id for unlock flow
  is_unlock_payment?: boolean;
  // NEW: Route details for verification (optional, speeds up verification)
  train_number?: string; // Train number (e.g., "12951")
  from_station_code?: string; // Source station code (e.g., "NDLS")
  to_station_code?: string; // Destination station code (e.g., "MMCT")
  source_station_name?: string; // Source station name (fallback)
  destination_station_name?: string; // Destination station name (fallback)
}

export interface VerifyPaymentRequest {
  payment_id: string; // Changed from order_id to our internal payment_id
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

/** Uses token from apiClient config. */
export const createPaymentOrder = async (data: CreateOrderRequest): Promise<{ 
  success: boolean; 
  message?: string; 
  already_paid?: boolean; 
  order: PaymentOrder; 
  payment_id: string;
  // NEW: Verification results (for unlock flow)
  verification?: {
    sl_availability?: any;
    ac3_availability?: any;
    sl_fare?: any;
    ac3_fare?: any;
  };
  route_info?: {
    train_number?: string;
    from_station_code?: string;
    to_station_code?: string;
  };
  warnings?: string[];
  api_calls_made?: number;
}> => {
  const response = await fetchWithAuth('/payments/create_order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json();
};

/** Uses token from apiClient config. Returns redirect_token on success; frontend must consume it before showing success. */
export const verifyPayment = async (data: VerifyPaymentRequest): Promise<{ success: boolean; redirect_token?: string }> => {
  const response = await fetchWithAuth('/payments/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json();
};

/** Consume signed redirect token (one-time). Call after verify success; only then trust payment success. */
export const consumeRedirectToken = async (token: string): Promise<{ success: boolean; data?: unknown }> => {
  const response = await fetchWithAuth('/payments/consume-redirect-token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  return await response.json();
};

/** Uses token from apiClient config. */
export const checkPaymentStatus = async (routeId: string, travelDate: string): Promise<{ paid: boolean; already_paid_booking?: boolean }> => {
  const response = await fetchWithAuth(`/payments/check_payment_status?route_id=${routeId}&travel_date=${travelDate}`);
  return await response.json();
};

/**
 * Poll payment status after Razorpay redirect
 * Returns when payment is completed, failed, or timeout
 */
export async function pollPaymentStatus(
  orderId: string,
  options?: {
    maxAttempts?: number;
    intervalMs?: number;
    onStatusChange?: (status: string) => void;
  }
): Promise<{ status: "completed" | "failed" | "timeout"; orderId: string }> {
  const maxAttempts = options?.maxAttempts ?? 30; // 30 attempts
  const intervalMs = options?.intervalMs ?? 1000; // 1 second
  let attempts = 0;

  return new Promise((resolve) => {
    const poll = async () => {
      attempts++;
      try {
        const response = await fetchWithAuth(`/api/payments/order_status/${encodeURIComponent(orderId)}`);
        if (!response.ok) {
          if (attempts >= maxAttempts) {
            resolve({ status: "timeout", orderId });
            return;
          }
          setTimeout(poll, intervalMs);
          return;
        }

        const data = (await response.json()) as { status?: string; payment_status?: string };
        const status = data.status || data.payment_status || "pending";
        
        if (options?.onStatusChange) {
          options.onStatusChange(status);
        }

        if (status === "completed" || status === "success") {
          resolve({ status: "completed", orderId });
        } else if (status === "failed" || status === "failure") {
          resolve({ status: "failed", orderId });
        } else if (attempts >= maxAttempts) {
          resolve({ status: "timeout", orderId });
        } else {
          setTimeout(poll, intervalMs);
        }
      } catch (error) {
        console.error("Payment status poll error:", error);
        if (attempts >= maxAttempts) {
          resolve({ status: "timeout", orderId });
        } else {
          setTimeout(poll, intervalMs);
        }
      }
    };

    poll();
  });
}

/** Uses token from apiClient config. */
export const createBookingRedirect = async (data: BookingRedirectRequest): Promise<{ redirect_url: string; irctc_url?: string }> => {
  const response = await fetchWithAuth('/payments/booking/redirect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json();
};

/** Uses token from apiClient config. Pass signal for request cancellation (e.g. from TanStack Query). */
export const getBookingHistory = async (
  params?: { skip?: number; limit?: number },
  signal?: AbortSignal
): Promise<{ success: boolean; message?: string; payments?: unknown[]; total?: number; skip?: number; limit?: number }> => {
  let url = '/payments/booking/history';
  if (params) {
    const qs = [];
    if (params.skip != null) qs.push(`skip=${params.skip}`);
    if (params.limit != null) qs.push(`limit=${params.limit}`);
    if (qs.length) url += `?${qs.join('&')}`;
  }
  const response = await fetchWithAuth(url, { signal });
  return await response.json();
};


/**
 * Bulk: get all unlocked route IDs for the current authenticated user.
 */
export const getUnlockedRoutes = async (): Promise<{ routes: string[] }> => {
  const response = await fetchWithAuth('/payments/unlocked-routes');
  return await response.json();
};

export const openRazorpayCheckout = (
  order: PaymentOrder,
  user: unknown,
  onSuccess: (response: unknown) => void,
  onFailure: (error: Error) => void
) => {
  const u = user as Record<string, string | undefined>;
  const options = {
    key: order.key_id,
    amount: order.amount,
    currency: order.currency,
    name: 'Railway Manager',
    description: 'Service Fee - ₹49',
    order_id: order.razorpay_order_id,
    prefill: {
      name: `${u?.first_name || ''} ${u?.last_name || ''}`.trim() || 'User',
      email: u?.email || '',
      contact: u?.phone || '',
    },
    theme: {
      color: '#3b82f6',
    },
    handler: function (response: unknown) {
      const r = response as Record<string, string>;
      onSuccess({
        order_id: order.order_id,
        razorpay_order_id: r.razorpay_order_id,
        razorpay_payment_id: r.razorpay_payment_id,
        razorpay_signature: r.razorpay_signature,
      });
    },
    modal: {
      ondismiss: function () {
        onFailure(new Error('Payment cancelled'));
      },
    },
  };

  // @ts-expect-error - Razorpay SDK is loaded via script tag
  const rzp = new window.Razorpay(options);
  rzp.open();
};
