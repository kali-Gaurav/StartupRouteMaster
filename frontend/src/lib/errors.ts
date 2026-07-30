/**
 * Normalized API errors so UI can respond by type:
 * - AuthError → redirect to login
 * - RateLimitError → retry UI / back off
 * - ValidationError → show field errors
 * - NetworkError → offline / retry banner
 */

import { assertKnownErrorType } from "@/lib/architectureAssertions";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly code?: string,
    public readonly details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

export class AuthError extends ApiError {
  constructor(message = "Authentication required", status = 401, details?: unknown) {
    super(message, status, "AUTH_ERROR", details);
    this.name = "AuthError";
    Object.setPrototypeOf(this, AuthError.prototype);
  }
}

export class ValidationError extends ApiError {
  constructor(message: string, status = 400, details?: unknown) {
    super(message, status, "VALIDATION_ERROR", details);
    this.name = "ValidationError";
    Object.setPrototypeOf(this, ValidationError.prototype);
  }
}

export class RateLimitError extends ApiError {
  constructor(
    message = "Too many requests. Please try again later.",
    public readonly retryAfter?: number
  ) {
    super(message, 429, "RATE_LIMIT", { retryAfter: retryAfter });
    this.name = "RateLimitError";
    Object.setPrototypeOf(this, RateLimitError.prototype);
  }
}

export class NetworkError extends ApiError {
  constructor(message = "Network error. Please check your connection.", cause?: unknown) {
    super(message, undefined, "NETWORK_ERROR", cause);
    this.name = "NetworkError";
    Object.setPrototypeOf(this, NetworkError.prototype);
  }
}

/** Booking flow: availability, redirect, or flow state. */
export class BookingError extends Error {
  constructor(
    message: string,
    public readonly code: "AVAILABILITY" | "REDIRECT" | "FLOW" | "UNKNOWN" = "UNKNOWN",
    public readonly details?: unknown
  ) {
    super(message);
    this.name = "BookingError";
    Object.setPrototypeOf(this, BookingError.prototype);
  }
}

/** Payment: order creation, verification, or gateway. */
export class PaymentError extends Error {
  constructor(
    message: string,
    public readonly code: "ORDER" | "VERIFY" | "GATEWAY" | "UNKNOWN" = "UNKNOWN",
    public readonly details?: unknown
  ) {
    super(message);
    this.name = "PaymentError";
    Object.setPrototypeOf(this, PaymentError.prototype);
  }
}

/** Local persistence: ticket store or session store. */
export class PersistenceError extends Error {
  constructor(
    message: string,
    public readonly store: "tickets" | "session" = "tickets",
    public readonly details?: unknown
  ) {
    super(message);
    this.name = "PersistenceError";
    Object.setPrototypeOf(this, PersistenceError.prototype);
  }
}

export type RecoverableError = NetworkError | RateLimitError | PaymentError | BookingError;

export interface RecoveryStrategy {
  userMessage: string;
  retry: boolean;
  fallback: "dismiss" | "back" | "refresh" | "none";
}

const DEFAULT_RECOVERY: RecoveryStrategy = {
  userMessage: "Something went wrong. Please try again.",
  retry: true,
  fallback: "dismiss",
};

/**
 * Map error type to user-facing message and recovery behavior.
 */
export function getRecoveryStrategy(error: unknown): RecoveryStrategy {
  if (error instanceof NetworkError) {
    return {
      userMessage: "Check your connection and try again.",
      retry: true,
      fallback: "refresh",
    };
  }
  if (error instanceof RateLimitError) {
    return {
      userMessage: error.message,
      retry: true,
      fallback: "dismiss",
    };
  }
  if (error instanceof PaymentError) {
    return {
      userMessage: error.message || "Payment could not be completed.",
      retry: true,
      fallback: "back",
    };
  }
  if (error instanceof BookingError) {
    return {
      userMessage: error.message || "Booking step failed.",
      retry: true,
      fallback: "back",
    };
  }
  if (error instanceof PersistenceError) {
    return {
      userMessage: "Local data issue. Your ticket list may have been reset.",
      retry: false,
      fallback: "dismiss",
    };
  }
  if (error instanceof Error) return { ...DEFAULT_RECOVERY, userMessage: error.message };
  assertKnownErrorType(error);
  return DEFAULT_RECOVERY;
}

/**
 * Normalize a failed fetch or Response into a typed error.
 * Call after fetch when !res.ok or when fetch throws.
 */
export async function normalizeApiError(response: Response | null, cause?: unknown): Promise<ApiError> {
  if (!response) {
    if (cause instanceof TypeError && cause.message?.includes("fetch")) {
      return new NetworkError("Network error. Please check your connection.", cause);
    }
    return new NetworkError(cause instanceof Error ? cause.message : "Request failed", cause);
  }

  const status = response.status;
  let body: { message?: string; detail?: string | unknown; msg?: string } = {};
  try {
    const text = await response.text();
    if (text) body = JSON.parse(text) as typeof body;
  } catch {
    // ignore
  }

  const msg =
    body?.message ??
    (typeof body?.detail === "string" ? body.detail : Array.isArray(body?.detail) ? (body.detail[0] as { msg?: string })?.msg : body?.msg) ??
    `Request failed (${status})`;

  if (status === 401) return new AuthError(msg, status, body);
  if (status === 429) {
    const retryAfter = response.headers.get("Retry-After");
    return new RateLimitError(
      retryAfter ? `Too many requests. Please try again after ${retryAfter} seconds.` : msg,
      retryAfter ? parseInt(retryAfter, 10) : undefined
    );
  }
  if (status >= 400 && status < 500) return new ValidationError(msg, status, body);
  return new ApiError(msg, status, "API_ERROR", body);
}

/** Type guard for UI branching */
export function isAuthError(e: unknown): e is AuthError {
  return e instanceof AuthError;
}
export function isRateLimitError(e: unknown): e is RateLimitError {
  return e instanceof RateLimitError;
}
export function isValidationError(e: unknown): e is ValidationError {
  return e instanceof ValidationError;
}
export function isNetworkError(e: unknown): e is NetworkError {
  return e instanceof NetworkError;
}
export function isBookingError(e: unknown): e is BookingError {
  return e instanceof BookingError;
}
export function isPaymentError(e: unknown): e is PaymentError {
  return e instanceof PaymentError;
}
export function isPersistenceError(e: unknown): e is PersistenceError {
  return e instanceof PersistenceError;
}
