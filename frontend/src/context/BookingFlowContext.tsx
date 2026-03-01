/**
 * Booking Confidence Flow: Review → Availability → Payment → Confirmation
 * Single source of truth for step, route, and availability state.
 * Persists session to sessionStorage for resume-after-refresh.
 */

import {
  createContext,
  useCallback,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";
import type { Route } from "@/data/routes";
import { assertValidBookingTransition } from "@/lib/architectureAssertions";
import {
  saveBookingSession,
  loadBookingSession,
  clearBookingSession,
} from "@/lib/bookingSessionStore";
import { logEvent } from "@/lib/observability";
import { checkAvailability } from "@/api/booking"; // backend availability API

export type BookingStep = "review" | "availability" | "payment" | "confirmation";
export type AvailabilityPhase = "idle" | "checking" | "locking" | "confirmed" | "failed";

export interface BookingFlowState {
  open: boolean;
  step: BookingStep;
  route: Route | null;
  travelDate: string;
  originName: string;
  destName: string;
  availabilityPhase: AvailabilityPhase;
  availabilityInfo?: any | null; // store response from availability API
  bookingId: string | null;
  irctcUrl: string | null;
  error: string | null;
  isUnlockFlow?: boolean; // New field
  lastUnlockedRouteId: string | null; // New field for communicating unlocked routes
}

const stepsOrder: BookingStep[] = ["review", "availability", "payment", "confirmation"];

export interface RecoverableSessionInfo {
  originName: string;
  destName: string;
  step: string;
}

type BookingFlowContextValue = BookingFlowState & {
  openReview: (params: {
    route: Route;
    travelDate: string;
    originName: string;
    destName: string;
  }) => void;
  openUnlockPayment: (params: {
    route: Route;
    travelDate: string;
    originName: string;
    destName: string;
  }) => void;
  goToStep: (step: BookingStep) => void;
  nextStep: () => void;
  close: () => void;
  setError: (err: string | null) => void;
  runAvailabilityCheck: () => Promise<boolean>;
  setPaymentSuccess: (orderId: string, irctcUrl: string | null) => void;
  setUnlockSuccess: (routeId: string) => void;
  retryAvailability: () => void;
  /** Set when a persisted session exists on load (e.g. after refresh). */
  recoverableSession: RecoverableSessionInfo | null;
  resumeSession: () => void;
  dismissRecoverableSession: () => void;
};

const initialState: BookingFlowState = {
  open: false,
  step: "review",
  route: null,
  travelDate: "",
  originName: "",
  destName: "",
  availabilityPhase: "idle",
  bookingId: null,
  irctcUrl: null,
  error: null,
  isUnlockFlow: false,
  lastUnlockedRouteId: null, // Initialize new field
};

const BookingFlowContext = createContext<BookingFlowContextValue | null>(null);

// availability / locking constants were part of an earlier polling implementation
// now handled directly by runAvailabilityCheck and backend responses.

export function BookingFlowProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<BookingFlowState>(initialState);
  const [recoverableSession, setRecoverableSession] = useState<RecoverableSessionInfo | null>(null);

  useEffect(() => {
    const stored = loadBookingSession();
    if (stored?.originName && stored?.destName) {
      setRecoverableSession({
        originName: stored.originName,
        destName: stored.destName,
        step: stored.step || "review",
      });
    }
  }, []);

  useEffect(() => {
    if (!state.open || !state.route) return;
    saveBookingSession({
      step: state.step,
      travelDate: state.travelDate,
      originName: state.originName,
      destName: state.destName,
      updatedAt: Date.now(),
      route: JSON.stringify(state.route),
    });
  }, [state.open, state.step, state.travelDate, state.originName, state.destName, state.route]);

  const openReview = useCallback(
    (params: { route: Route; travelDate: string; originName: string; destName: string }) => {
      logEvent("booking_started", {
        step: "review",
        hasDate: !!params.travelDate,
      });
      setState({
        ...initialState,
        open: true,
        step: "review",
        route: params.route,
        travelDate: params.travelDate,
        originName: params.originName,
        destName: params.destName,
        isUnlockFlow: false,
      });
    },
    []
  );

  const openUnlockPayment = useCallback(
    (params: { route: Route; travelDate: string; originName: string; destName: string }) => {
      logEvent("unlock_flow_started", {
        routeId: params.route.id,
      });
      setState({
        ...initialState,
        open: true,
        step: "payment",
        route: params.route,
        travelDate: params.travelDate,
        originName: params.originName,
        destName: params.destName,
        isUnlockFlow: true,
      });
    },
    []
  );

  const goToStep = useCallback((step: BookingStep) => {
    setState((s) => {
      assertValidBookingTransition(s.step, step, "goToStep");
      return { ...s, step, error: null };
    });
  }, []);

  const nextStep = useCallback(() => {
    setState((s) => {
      const idx = stepsOrder.indexOf(s.step);
      const next = idx < stepsOrder.length - 1 ? stepsOrder[idx + 1] : s.step;
      assertValidBookingTransition(s.step, next, "nextStep");
      return { ...s, step: next, error: null };
    });
  }, []);

  const close = useCallback(() => {
    clearBookingSession();
    setState((prev) => {
      if (prev.step !== "confirmation" && !prev.isUnlockFlow) { // Only log abandoned if not confirmation and not unlock flow
        logEvent("booking_abandoned", { step: prev.step }, "info");
      }
      return { ...initialState, lastUnlockedRouteId: null }; // Clear lastUnlockedRouteId on close
    });
  }, []);

  const setError = useCallback((error: string | null) => {
    setState((s) => ({ ...s, error }));
  }, []);

  const runAvailabilityCheck = useCallback((): Promise<boolean> => {
    const { route, travelDate } = state;
    if (!route || !travelDate) {
      setState((s) => ({ ...s, error: "Missing route or travel date" }));
      return Promise.resolve(false);
    }

    return new Promise(async (resolve) => {
      setState((s) => ({ ...s, availabilityPhase: "checking", error: null }));

      try {
        const segs = (route.segments as any[]) || [];
        const resp = await checkAvailability({
          trip_id: route.id as unknown as any, // backend will resolve string or number
          from_stop_id: segs[0]?.from_stop_id || 0,
          to_stop_id: segs[segs.length - 1]?.to_stop_id || 0,
          travel_date: travelDate,
          quota_type: (route as any).quota_type || "GENERAL",
          passengers: (state as any).passengers || 1,
        });

        // store the raw response for UI
        setState((s) => ({ ...s, availabilityInfo: resp }));

        // determine next state based on response
        if (resp.available) {
          setState((s) => ({ ...s, availabilityPhase: "confirmed" }));
          resolve(true);
        } else {
          setState((s) => ({ ...s, availabilityPhase: "failed", error: resp.message || "Unavailable" }));
          resolve(false);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Availability check failed";
        setState((s) => ({ ...s, availabilityPhase: "failed", error: msg }));
        resolve(false);
      }
    });
  }, [state]);

  const setPaymentSuccess = useCallback((orderId: string, irctcUrl: string | null) => {
    logEvent("booking_confirmed", { hasIrctcUrl: !!irctcUrl });
    clearBookingSession();
    setState((s) => ({
      ...s,
      step: "confirmation",
      bookingId: orderId,
      irctcUrl,
      error: null,
    }));
  }, []);

  const setUnlockSuccess = useCallback((routeId: string) => {
    logEvent("route_unlocked", { routeId });
    clearBookingSession(); // Clear any partial booking session
    setState({ // Update state to include lastUnlockedRouteId
      ...initialState, // Reset other modal state
      lastUnlockedRouteId: routeId,
    });
  }, []);

  const retryAvailability = useCallback(() => {
    setState((s) => ({ ...s, availabilityPhase: "idle", error: null }));
  }, []);

  const resumeSession = useCallback(() => {
    const stored = loadBookingSession();
    if (!stored) return;
    let route: Route | null = null;
    try {
      route = JSON.parse(stored.route) as Route;
    } catch {
      /* ignore */
    }
    if (!route) return;
    clearBookingSession();
    setRecoverableSession(null);
    setState({
      open: true,
      step: stored.step as BookingStep,
      route,
      travelDate: stored.travelDate,
      originName: stored.originName,
      destName: stored.destName,
      availabilityPhase: "idle",
      bookingId: null,
      irctcUrl: null,
      error: null,
      isUnlockFlow: false, // Assume false for resumed sessions unless explicitly stored
      lastUnlockedRouteId: null, // Ensure this is reset or handled
    });
  }, []);

  const dismissRecoverableSession = useCallback(() => {
    clearBookingSession();
    setRecoverableSession(null);
  }, []);

  const value: BookingFlowContextValue = {
    ...state,
    openReview,
    openUnlockPayment,
    goToStep,
    nextStep,
    close,
    setError,
    runAvailabilityCheck,
    setPaymentSuccess,
    setUnlockSuccess,
    retryAvailability,
    recoverableSession,
    resumeSession,
    dismissRecoverableSession,
  };

  return (
    <BookingFlowContext.Provider value={value}>{children}</BookingFlowContext.Provider>
  );
}

export function useBookingFlowContext(): BookingFlowContextValue {
  const ctx = useContext(BookingFlowContext);
  if (!ctx) throw new Error("useBookingFlowContext must be used within BookingFlowProvider");
  return ctx;
}

export function bookingStepIndex(step: BookingStep): number {
  return stepsOrder.indexOf(step);
}

export function bookingStepsForProgress(): { id: BookingStep; label: string }[] {
  return [
    { id: "review", label: "Review" },
    { id: "availability", label: "Confirm seats" },
    { id: "payment", label: "Payment" },
    { id: "confirmation", label: "Ticket" },
  ];
}
