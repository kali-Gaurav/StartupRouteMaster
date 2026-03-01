/**
 * State machine tests: booking flow transitions match docs/architecture/booking-flow-state-machine.md.
 */

import React from "react";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, beforeEach, vi } from "vitest";
import {
  BookingFlowProvider,
  useBookingFlowContext,
  bookingStepIndex,
  bookingStepsForProgress,
} from "@/context/BookingFlowContext";
import type { Route } from "@/data/routes";

vi.mock("@/lib/observability", () => ({ logEvent: vi.fn() }));

function minimalRoute(): Route {
  return {
    id: "r1",
    category: "FAST",
    segments: [],
    totalTime: 120,
    totalCost: 500,
    totalTransfers: 0,
    totalDistance: 100,
    liveFareTotal: 500,
    seatProbability: 0.9,
    safetyScore: 80,
  };
}

function wrapper({ children }: { children: React.ReactNode }) {
  return <BookingFlowProvider>{children}</BookingFlowProvider>;
}

describe("booking flow state machine", () => {
  describe("stepsOrder and progress", () => {
    it("stepsOrder is review, availability, payment, confirmation", () => {
      const steps = bookingStepsForProgress().map((s) => s.id);
      expect(steps).toEqual(["review", "availability", "payment", "confirmation"]);
    });

    it("bookingStepIndex returns correct indices", () => {
      expect(bookingStepIndex("review")).toBe(0);
      expect(bookingStepIndex("availability")).toBe(1);
      expect(bookingStepIndex("payment")).toBe(2);
      expect(bookingStepIndex("confirmation")).toBe(3);
    });
  });

  describe("nextStep advances by one only", () => {
    it("review → availability → payment → confirmation", () => {
      const { result } = renderHook(() => useBookingFlowContext(), { wrapper });
      const route = minimalRoute();

      act(() => {
        result.current.openReview({
          route,
          travelDate: "2025-06-15",
          originName: "A",
          destName: "B",
        });
      });
      expect(result.current.step).toBe("review");

      act(() => result.current.nextStep());
      expect(result.current.step).toBe("availability");

      act(() => result.current.nextStep());
      expect(result.current.step).toBe("payment");

      act(() => result.current.nextStep());
      expect(result.current.step).toBe("confirmation");
    });

    it("nextStep from confirmation stays at confirmation", () => {
      const { result } = renderHook(() => useBookingFlowContext(), { wrapper });
      const route = minimalRoute();
      act(() => {
        result.current.openReview({
          route,
          travelDate: "2025-06-15",
          originName: "A",
          destName: "B",
        });
      });
      act(() => result.current.nextStep());
      act(() => result.current.nextStep());
      act(() => result.current.nextStep());
      expect(result.current.step).toBe("confirmation");
      act(() => result.current.nextStep());
      expect(result.current.step).toBe("confirmation");
    });
  });

  describe("goToStep allows only documented back transitions", () => {
    it("payment → availability via goToStep", () => {
      const { result } = renderHook(() => useBookingFlowContext(), { wrapper });
      const route = minimalRoute();
      act(() => {
        result.current.openReview({
          route,
          travelDate: "2025-06-15",
          originName: "A",
          destName: "B",
        });
      });
      act(() => result.current.nextStep());
      act(() => result.current.nextStep());
      expect(result.current.step).toBe("payment");
      act(() => result.current.goToStep("availability"));
      expect(result.current.step).toBe("availability");
    });

    it("availability → review via goToStep", () => {
      const { result } = renderHook(() => useBookingFlowContext(), { wrapper });
      const route = minimalRoute();
      act(() => {
        result.current.openReview({
          route,
          travelDate: "2025-06-15",
          originName: "A",
          destName: "B",
        });
      });
      act(() => result.current.nextStep());
      expect(result.current.step).toBe("availability");
      act(() => result.current.goToStep("review"));
      expect(result.current.step).toBe("review");
    });
  });

  describe("confirmation only via setPaymentSuccess", () => {
    it("setPaymentSuccess moves to confirmation and clears session", () => {
      const { result } = renderHook(() => useBookingFlowContext(), { wrapper });
      const route = minimalRoute();
      act(() => {
        result.current.openReview({
          route,
          travelDate: "2025-06-15",
          originName: "A",
          destName: "B",
        });
      });
      act(() => result.current.nextStep());
      act(() => result.current.nextStep());
      expect(result.current.step).toBe("payment");
      act(() => result.current.setPaymentSuccess("ord-1", "https://irctc.example"));
      expect(result.current.step).toBe("confirmation");
      expect(result.current.bookingId).toBe("ord-1");
      expect(result.current.irctcUrl).toBe("https://irctc.example");
    });
  });

  describe("resumeSession restores from sessionStorage", () => {
    beforeEach(() => {
      sessionStorage.clear();
    });

    it("resumeSession hydrates step and route from stored session", () => {
      const route = minimalRoute();
      sessionStorage.setItem(
        "route-master-booking-session",
        JSON.stringify({
          step: "availability",
          travelDate: "2025-06-15",
          originName: "A",
          destName: "B",
          route: JSON.stringify(route),
          updatedAt: Date.now(),
        })
      );

      const { result } = renderHook(() => useBookingFlowContext(), { wrapper });
      expect(result.current.recoverableSession).not.toBeNull();
      act(() => result.current.resumeSession());
      expect(result.current.open).toBe(true);
      expect(result.current.step).toBe("availability");
      expect(result.current.originName).toBe("A");
      expect(result.current.destName).toBe("B");
      expect(result.current.route).toEqual(route);
    });
  });

  describe("close resets to idle", () => {
    it("close clears state and session", () => {
      const { result } = renderHook(() => useBookingFlowContext(), { wrapper });
      const route = minimalRoute();
      act(() => {
        result.current.openReview({
          route,
          travelDate: "2025-06-15",
          originName: "A",
          destName: "B",
        });
      });
      act(() => result.current.nextStep());
      expect(result.current.open).toBe(true);
      act(() => result.current.close());
      expect(result.current.open).toBe(false);
      expect(result.current.step).toBe("review");
      expect(result.current.route).toBeNull();
    });
  });
});
