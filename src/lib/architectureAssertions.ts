/**
 * Living architecture: runtime checks that enforce documented contracts.
 * Run only in development to avoid cost; logs warnings or critical events.
 */

import { logEvent } from "@/lib/observability";
import type { BookingStep } from "@/context/BookingFlowContext";

const stepsOrder: BookingStep[] = ["review", "availability", "payment", "confirmation"];

/** Allowed direct transitions (from → to). confirmation is only reachable via setPaymentSuccess. */
const ALLOWED_TRANSITIONS: [BookingStep, BookingStep][] = [
  ["review", "availability"],
  ["availability", "review"],
  ["availability", "payment"],
  ["payment", "availability"],
  ["payment", "confirmation"],
];

function isAllowedTransition(from: BookingStep, to: BookingStep): boolean {
  if (to === "confirmation") return false;
  return ALLOWED_TRANSITIONS.some(([a, b]) => a === from && b === to);
}

/**
 * Pure transition check (for tests and callers). Returns true if transition is valid per state machine.
 */
export function isTransitionValid(
  from: BookingStep,
  to: BookingStep,
  via: "nextStep" | "goToStep"
): boolean {
  if (to === "confirmation") return via === "nextStep" && from === "payment";
  if (via === "nextStep") {
    const fromIdx = stepsOrder.indexOf(from);
    const toIdx = stepsOrder.indexOf(to);
    return toIdx === fromIdx + 1;
  }
  return isAllowedTransition(from, to);
}

/**
 * Call before applying a booking step transition (goToStep or nextStep).
 * In DEV, warns if transition is invalid per state machine doc.
 */
export function assertValidBookingTransition(
  from: BookingStep,
  to: BookingStep,
  via: "nextStep" | "goToStep"
): void {
  if (typeof import.meta.env === "undefined" || !import.meta.env.DEV) return;

  if (to === "confirmation") {
    logEvent(
      "architecture_assertion",
      {
        rule: "booking_state_machine",
        message: "confirmation must be set only via setPaymentSuccess",
        from,
        to,
        via,
      },
      "critical"
    );
    return;
  }

  if (via === "nextStep") {
    const fromIdx = stepsOrder.indexOf(from);
    const toIdx = stepsOrder.indexOf(to);
    if (toIdx !== fromIdx + 1) {
      logEvent(
        "architecture_assertion",
        {
          rule: "booking_state_machine",
          message: "nextStep must advance by one step",
          from,
          to,
        },
        "critical"
      );
    }
    return;
  }

  if (!isAllowedTransition(from, to)) {
    logEvent(
      "architecture_assertion",
      {
        rule: "booking_state_machine",
        message: "invalid goToStep transition",
        from,
        to,
      },
      "warn"
    );
  }
}

/**
 * Call when getRecoveryStrategy falls through to default (unexpected error type).
 */
export function assertKnownErrorType(error: unknown): void {
  if (typeof import.meta.env === "undefined" || !import.meta.env.DEV) return;
  logEvent(
    "architecture_assertion",
    {
      rule: "error_taxonomy",
      message: "unexpected error type in getRecoveryStrategy",
      errorName: error instanceof Error ? error.name : typeof error,
    },
    "critical"
  );
}
