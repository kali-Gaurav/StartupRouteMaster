import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type BookingStatus =
  | 'initiated'
  | 'validating'
  | 'seat_allocating'
  | 'pricing'
  | 'payment_pending'
  | 'payment_processing'
  | 'confirmed'
  | 'cancelled'
  | 'failed'
  | 'waitlist';

export interface PassengerDetails {
  full_name: string;
  age: number;
  gender: 'M' | 'F' | 'O';
  phone_number?: string;
  email?: string;
  berth_preference?: string;
  meal_preference?: string;
  concession_type?: string;
}

export interface TrainInfo {
  train_number: string;
  train_name?: string;
  from_station: string;
  to_station: string;
  travel_date: string;
  class_type: string;
  departure_time?: string;
  arrival_time?: string;
  duration?: string;
}

export interface BookingData {
  id?: string;
  status: BookingStatus;
  pnr_number?: string;
  passengers: PassengerDetails[];
  trainInfo: TrainInfo;
  totalAmount: number;
  seatsAllocated?: string[];
  waitlistPosition?: number | null;
}

export interface PaymentData {
  razorpayOrderId?: string;
  status: 'pending' | 'processing' | 'success' | 'failed';
  error?: string;
  paymentMethod?: string;
}

interface BookingState {
  current: BookingData;
  payment: PaymentData;
  loading: boolean;
  error?: string;

  // Actions
  initializeBooking: (trainInfo: TrainInfo) => void;
  addPassenger: (passenger: PassengerDetails) => void;
  removePassenger: (index: number) => void;
  updatePassenger: (index: number, passenger: PassengerDetails) => void;
  setTotalAmount: (amount: number) => void;

  // Booking actions
  setBookingStatus: (status: BookingStatus) => void;
  setBookingData: (data: Partial<BookingData>) => void;
  setBookingId: (id: string, pnr?: string) => void;

  // Payment actions
  setPaymentOrderId: (orderId: string) => void;
  setPaymentStatus: (status: PaymentData['status']) => void;
  setPaymentError: (error: string) => void;
  setPaymentMethod: (method: string) => void;

  // Loading and error
  setLoading: (loading: boolean) => void;
  setError: (error?: string) => void;

  // Reset
  reset: () => void;
  resetPayment: () => void;
}

const initialBookingData: BookingData = {
  status: 'initiated',
  passengers: [],
  trainInfo: {
    train_number: '',
    from_station: '',
    to_station: '',
    travel_date: '',
    class_type: '',
  },
  totalAmount: 0,
};

const initialPaymentData: PaymentData = {
  status: 'pending',
};

export const useBookingStore = create<BookingState>()(
  persist(
    (set) => ({
      current: initialBookingData,
      payment: initialPaymentData,
      loading: false,
      error: undefined,

      initializeBooking: (trainInfo) =>
        set((state) => ({
          current: {
            ...initialBookingData,
            trainInfo,
          },
          payment: initialPaymentData,
        })),

      addPassenger: (passenger) =>
        set((state) => ({
          current: {
            ...state.current,
            passengers: [...state.current.passengers, passenger],
          },
        })),

      removePassenger: (index) =>
        set((state) => ({
          current: {
            ...state.current,
            passengers: state.current.passengers.filter((_, i) => i !== index),
          },
        })),

      updatePassenger: (index, passenger) =>
        set((state) => ({
          current: {
            ...state.current,
            passengers: state.current.passengers.map((p, i) => (i === index ? passenger : p)),
          },
        })),

      setTotalAmount: (amount) =>
        set((state) => ({
          current: {
            ...state.current,
            totalAmount: amount,
          },
        })),

      setBookingStatus: (status) =>
        set((state) => ({
          current: {
            ...state.current,
            status,
          },
        })),

      setBookingData: (data) =>
        set((state) => ({
          current: {
            ...state.current,
            ...data,
          },
        })),

      setBookingId: (id, pnr) =>
        set((state) => ({
          current: {
            ...state.current,
            id,
            pnr_number: pnr,
          },
        })),

      setPaymentOrderId: (orderId) =>
        set((state) => ({
          payment: {
            ...state.payment,
            razorpayOrderId: orderId,
          },
        })),

      setPaymentStatus: (status) =>
        set((state) => ({
          payment: {
            ...state.payment,
            status,
            error: undefined,
          },
        })),

      setPaymentError: (error) =>
        set((state) => ({
          payment: {
            ...state.payment,
            error,
            status: 'failed',
          },
        })),

      setPaymentMethod: (method) =>
        set((state) => ({
          payment: {
            ...state.payment,
            paymentMethod: method,
          },
        })),

      setLoading: (loading) => set({ loading }),

      setError: (error) => set({ error }),

      reset: () =>
        set({
          current: initialBookingData,
          payment: initialPaymentData,
          loading: false,
          error: undefined,
        }),

      resetPayment: () =>
        set({
          payment: initialPaymentData,
        }),
    }),
    {
      name: 'routemaster-booking-storage',
      partialize: (state) => ({
        current: state.current,
        payment: state.payment,
      }),
    }
  )
);
