/**
 * Payment API
 * Uses shared apiClient for base URL, auth header, and 401 → logout.
 */

import { fetchWithAuth } from './apiClient';

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
export const createPaymentOrder = async (data: CreateOrderRequest): Promise<any> => {
  const response = await fetchWithAuth('/payments/create_order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json();
};

/** Uses token from apiClient config. Returns redirect_token on success; frontend must consume it before showing success. */
export const verifyPayment = async (data: VerifyPaymentRequest): Promise<any> => {
  const response = await fetchWithAuth('/payments/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json();
};

/** Consume signed redirect token (one-time). Call after verify success; only then trust payment success. */
export const consumeRedirectToken = async (token: string): Promise<any> => {
  const response = await fetchWithAuth('/payments/consume-redirect-token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  return await response.json();
};

/** Uses token from apiClient config. */
export const checkPaymentStatus = async (routeId: string, travelDate: string): Promise<any> => {
  const response = await fetchWithAuth(`/payments/check_payment_status?route_id=${routeId}&travel_date=${travelDate}`);
  return await response.json();
};

/** Uses token from apiClient config. */
export const createBookingRedirect = async (data: BookingRedirectRequest): Promise<any> => {
  const response = await fetchWithAuth('/payments/booking/redirect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json();
};

/** Uses token from apiClient config. Pass signal for request cancellation (e.g. from TanStack Query). */
export const getBookingHistory = async (signal?: AbortSignal): Promise<any> => {
  const response = await fetchWithAuth('/payments/booking/history', { signal });
  return await response.json();
};

export const isRouteUnlocked = async (routeId: string): Promise<{ is_unlocked: boolean }> => {
  const response = await fetchWithAuth(`/payments/is_route_unlocked?route_id=${routeId}`);
  return await response.json();
};

export const openRazorpayCheckout = (
  order: PaymentOrder,
  user: any,
  onSuccess: (response: any) => void,
  onFailure: (error: any) => void
) => {
  const options = {
    key: order.key_id,
    amount: order.amount,
    currency: order.currency,
    name: 'Railway Manager',
    description: 'Service Fee - ₹49',
    order_id: order.razorpay_order_id,
    prefill: {
      name: `${user?.first_name || ''} ${user?.last_name || ''}`.trim() || 'User',
      email: user?.email || '',
      contact: user?.phone || '',
    },
    theme: {
      color: '#3b82f6',
    },
    handler: function (response: any) {
      onSuccess({
        order_id: order.order_id,
        razorpay_order_id: response.razorpay_order_id,
        razorpay_payment_id: response.razorpay_payment_id,
        razorpay_signature: response.razorpay_signature,
      });
    },
    modal: {
      ondismiss: function () {
        onFailure(new Error('Payment cancelled'));
      },
    },
  };

  // @ts-ignore - Razorpay SDK is loaded via script tag
  const rzp = new window.Razorpay(options);
  rzp.open();
};
