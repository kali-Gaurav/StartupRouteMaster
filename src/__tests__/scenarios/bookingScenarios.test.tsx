/**
 * Scenario tests: scripted flows that simulate real users under stress.
 * Run regularly to guard against regressions in booking, payment, and recovery.
 */

import React from "react";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, beforeEach, vi } from "vitest";
import {
  BookingFlowProvider,
  useBookingFlowContext,
} from "@/context/BookingFlowContext";
import { getRecoveryStrategy, PaymentError, NetworkError } from "@/lib/errors";
import type { Route } from "@/data/routes";

vi.mock("@/lib/observability", () => ({ logEvent: vi.fn() }));
// mock the booking API so availability checks can be faked in scenarios
vi.mock("@/api/booking", () => ({
  checkAvailability: vi.fn(),
}));

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

describe("scenario: interrupted booking", () => {
  beforeEach(() => sessionStorage.clear());

  it("user opens flow, advances to availability, then closes → flow closed and session cleared", () => {
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
    expect(result.current.open).toBe(true);

    act(() => result.current.close());
    expect(result.current.open).toBe(false);
    expect(result.current.route).toBeNull();
    expect(result.current.recoverableSession).toBeNull();
    expect(sessionStorage.getItem("route-master-booking-session")).toBeNull();
  });
});

describe("scenario: payment retry", () => {
  it("payment error leaves user on payment step with error set; clearing error keeps them on payment", () => {
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

    act(() => result.current.setError("Payment gateway timeout"));
    expect(result.current.step).toBe("payment");
    expect(result.current.error).toBe("Payment gateway timeout");

    act(() => result.current.setError(null));
    expect(result.current.step).toBe("payment");
    expect(result.current.error).toBeNull();
  });
});

describe("scenario: slow availability", () => {
  it("invokes the availability API and moves to confirmed when seats are available", async () => {
    const { checkAvailability } = await import("@/api/booking");
    (checkAvailability as unknown as vi.Mock).mockResolvedValue({
      available: true,
      available_seats: 5,
      total_seats: 100,
      message: "ok",
    });

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

    await act(async () => {
      const ok = await result.current.runAvailabilityCheck();
      expect(ok).toBe(true);
    });

    expect((checkAvailability as unknown as vi.Mock).mock.calls.length).toBe(1);
    expect(result.current.availabilityPhase).toBe("confirmed");
    expect(result.current.availabilityInfo).not.toBeNull();
  });
});

describe("scenario: offline recovery", () => {
  it("NetworkError maps to refresh + retry recovery strategy", () => {
    const err = new NetworkError("Network error. Please check your connection.");
    const strategy = getRecoveryStrategy(err);
    expect(strategy.retry).toBe(true);
    expect(strategy.fallback).toBe("refresh");
    expect(strategy.userMessage).toMatch(/connection|try again/i);
  });

  it("PaymentError maps to back + retry so user can fix and retry", () => {
    const err = new PaymentError("Card declined");
    const strategy = getRecoveryStrategy(err);
    expect(strategy.retry).toBe(true);
    expect(strategy.fallback).toBe("back");
    expect(strategy.userMessage).toMatch(/payment|declined/i);
  });
});
