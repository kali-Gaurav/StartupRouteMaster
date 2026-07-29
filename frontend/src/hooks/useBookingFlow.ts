/**
 * Booking Flow Hook
 * Manages the complete booking flow: Create → Payment → Confirmation
 */

import { useCallback } from 'react';
import { useBookingStore } from '@/store/useBookingStore';
import type { PassengerDetails, TrainInfo, BookingData as BookingStateData } from '@/store/useBookingStore';
import { logEvent } from '@/lib/observability';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

export interface BookingRequest {
  journey_id: string;
  train_number: string;
  from_station: string;
  to_station: string;
  travel_date: string;
  passengers: PassengerDetails[];
  class_type: string;
  berth_preference?: string;
  meal_preference?: string;
  payment_method: string;
}

export interface PaymentInitiateRequest {
  booking_id: string;
}

export interface PaymentVerifyRequest {
  booking_id: string;
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface BookingResponse {
  booking_id: string;
  pnr_number: string;
  status: string;
  total_amount: number;
  payment_url?: string;
  expires_at?: string;
  seats_allocated: string[];
}

export interface PaymentInitiateResponse {
  razorpay_order_id: string;
  amount_paise: number;
  currency: string;
  booking_id: string;
}

export interface PaymentVerifyResponse {
  booking_id: string;
  status: string;
  pnr_number: string;
  message: string;
}

export const useBookingFlow = () => {
  const bookingStore = useBookingStore();

  const createBooking = useCallback(
    async (request: BookingRequest): Promise<BookingResponse | null> => {
      try {
        bookingStore.setLoading(true);
        bookingStore.setError(undefined);
        bookingStore.setBookingStatus('validating');

        const response = await fetch(`${API_BASE}/api/v1/bookings`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(request),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to create booking');
        }

        const data: BookingResponse = await response.json();
        bookingStore.setBookingId(data.booking_id, data.pnr_number);
        bookingStore.setBookingStatus('payment_pending');
        logEvent('booking_created', { booking_id: data.booking_id });

        return data;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to create booking';
        bookingStore.setError(errorMsg);
        bookingStore.setBookingStatus('failed');
        return null;
      } finally {
        bookingStore.setLoading(false);
      }
    },
    [bookingStore]
  );

  const initiatePayment = useCallback(
    async (bookingId: string): Promise<PaymentInitiateResponse | null> => {
      try {
        bookingStore.setLoading(true);
        bookingStore.setError(undefined);
        bookingStore.setPaymentStatus('processing');

        const response = await fetch(`${API_BASE}/api/v1/bookings/${bookingId}/payment/initiate`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to initiate payment');
        }

        const data: PaymentInitiateResponse = await response.json();
        bookingStore.setPaymentOrderId(data.razorpay_order_id);
        logEvent('payment_initiated', { booking_id: bookingId });

        return data;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to initiate payment';
        bookingStore.setPaymentError(errorMsg);
        return null;
      } finally {
        bookingStore.setLoading(false);
      }
    },
    [bookingStore]
  );

  const verifyPayment = useCallback(
    async (request: PaymentVerifyRequest): Promise<PaymentVerifyResponse | null> => {
      try {
        bookingStore.setLoading(true);
        bookingStore.setError(undefined);
        bookingStore.setPaymentStatus('processing');

        const response = await fetch(`${API_BASE}/api/v1/bookings/${request.booking_id}/payment/verify`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            razorpay_order_id: request.razorpay_order_id,
            razorpay_payment_id: request.razorpay_payment_id,
            razorpay_signature: request.razorpay_signature,
          }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to verify payment');
        }

        const data: PaymentVerifyResponse = await response.json();
        bookingStore.setPaymentStatus('success');
        bookingStore.setBookingStatus('confirmed');
        logEvent('payment_verified', { booking_id: request.booking_id });

        return data;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to verify payment';
        bookingStore.setPaymentError(errorMsg);
        bookingStore.setBookingStatus('failed');
        return null;
      } finally {
        bookingStore.setLoading(false);
      }
    },
    [bookingStore]
  );

  const cancelBooking = useCallback(
    async (bookingId: string, reason: string): Promise<boolean> => {
      try {
        bookingStore.setLoading(true);
        bookingStore.setError(undefined);

        const response = await fetch(`${API_BASE}/api/v1/bookings/${bookingId}/cancel`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ reason }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to cancel booking');
        }

        bookingStore.setBookingStatus('cancelled');
        logEvent('booking_cancelled', { booking_id: bookingId });
        return true;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to cancel booking';
        bookingStore.setError(errorMsg);
        return false;
      } finally {
        bookingStore.setLoading(false);
      }
    },
    [bookingStore]
  );

  return {
    bookingStore,
    createBooking,
    initiatePayment,
    verifyPayment,
    cancelBooking,
    isLoading: bookingStore.loading,
    error: bookingStore.error,
  };
};
