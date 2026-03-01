/**
 * Living architecture: tests that enforce the booking state machine and error taxonomy.
 */

import { describe, expect, it, vi } from "vitest";
import {
  isTransitionValid,
  assertValidBookingTransition,
  assertKnownErrorType,
} from "@/lib/architectureAssertions";

vi.mock("@/lib/observability", () => ({
  logEvent: vi.fn(),
}));

describe("isTransitionValid (state machine contract)", () => {
  it("allows nextStep: review → availability", () => {
    expect(isTransitionValid("review", "availability", "nextStep")).toBe(true);
  });

  it("allows nextStep: availability → payment", () => {
    expect(isTransitionValid("availability", "payment", "nextStep")).toBe(true);
  });

  it("allows nextStep: payment → confirmation (only way to confirmation)", () => {
    expect(isTransitionValid("payment", "confirmation", "nextStep")).toBe(true);
  });

  it("disallows nextStep skip: review → confirmation", () => {
    expect(isTransitionValid("review", "confirmation", "nextStep")).toBe(false);
  });

  it("disallows nextStep skip: review → payment", () => {
    expect(isTransitionValid("review", "payment", "nextStep")).toBe(false);
  });

  it("disallows goToStep to confirmation from any step", () => {
    expect(isTransitionValid("review", "confirmation", "goToStep")).toBe(false);
    expect(isTransitionValid("availability", "confirmation", "goToStep")).toBe(false);
    expect(isTransitionValid("payment", "confirmation", "goToStep")).toBe(false);
  });

  it("allows goToStep back: payment → availability", () => {
    expect(isTransitionValid("payment", "availability", "goToStep")).toBe(true);
  });

  it("allows goToStep back: availability → review", () => {
    expect(isTransitionValid("availability", "review", "goToStep")).toBe(true);
  });

  it("disallows goToStep skip: review → payment", () => {
    expect(isTransitionValid("review", "payment", "goToStep")).toBe(false);
  });
});

describe("assertValidBookingTransition", () => {
  it("does not throw for valid transitions", () => {
    expect(() => assertValidBookingTransition("review", "availability", "nextStep")).not.toThrow();
    expect(() => assertValidBookingTransition("payment", "availability", "goToStep")).not.toThrow();
  });

  it("does not throw for invalid transitions (logs in DEV only)", () => {
    expect(() => assertValidBookingTransition("review", "confirmation", "goToStep")).not.toThrow();
    expect(() => assertValidBookingTransition("review", "payment", "goToStep")).not.toThrow();
  });
});

describe("assertKnownErrorType", () => {
  it("does not throw", () => {
    expect(() => assertKnownErrorType(new Error("test"))).not.toThrow();
    expect(() => assertKnownErrorType({ unknown: true })).not.toThrow();
  });
});
