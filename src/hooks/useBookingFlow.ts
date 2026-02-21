/**
 * Booking Flow Hook
 * Manages the complete booking flow: Auth → Payment → IRCTC Redirect
 */

import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { createBookingRedirect } from '@/lib/paymentApi';
import { invalidateBookingsCache } from '@/lib/queryInvalidation';
import { logEvent } from '@/lib/observability';

export interface BookingData {
  origin: string;
  destination: string;
  trainNo: string;
  travelDate: string;
  travelClass?: string;
}

export const useBookingFlow = () => {
  const { isAuthenticated, token } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [bookingData, setBookingData] = useState<BookingData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  /**
   * Start booking flow
   * Checks auth → Shows payment → Redirects to IRCTC
   */
  const startBooking = (data: BookingData) => {
    setBookingData(data);
    setError('');
    logEvent('booking_started', { origin: data.origin, destination: data.destination });

    if (!isAuthenticated) {
      setShowAuthModal(true);
      return;
    }

    setShowPaymentModal(true);
  };

  /**
   * Handle successful authentication
   */
  const handleAuthSuccess = () => {
    setShowAuthModal(false);
    if (bookingData) {
      setShowPaymentModal(true);
    }
  };

  /**
   * Handle successful payment
   */
  const handlePaymentSuccess = async (paymentOrderId: string) => {
    if (!bookingData || !token) return;

    setLoading(true);
    setError('');

    try {
      const response = await createBookingRedirect({
        payment_order_id: paymentOrderId,
        origin: bookingData.origin,
        destination: bookingData.destination,
        train_no: bookingData.trainNo,
        travel_date: bookingData.travelDate,
        travel_class: bookingData.travelClass || 'SL',
      });

      if (response.success && response.irctc_url) {
        logEvent('booking_redirect_success', { origin: bookingData.origin, destination: bookingData.destination });
        await invalidateBookingsCache();
        window.open(response.irctc_url, '_blank');
        setShowPaymentModal(false);
        return true;
      } else {
        throw new Error('Failed to create booking');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to redirect to IRCTC');
      return false;
    } finally {
      setLoading(false);
    }
  };

  /**
   * Reset flow
   */
  const reset = () => {
    setShowAuthModal(false);
    setShowPaymentModal(false);
    setBookingData(null);
    setError('');
    setLoading(false);
  };

  return {
    isAuthenticated,
    showAuthModal,
    showPaymentModal,
    bookingData,
    loading,
    error,
    startBooking,
    handleAuthSuccess,
    handlePaymentSuccess,
    setShowAuthModal,
    setShowPaymentModal,
    reset,
  };
};
