/**
 * Global API error handling: 401 → logout, 429 → rate limit UI, 500 → retry + fallback.
 * Wire on401/on429 in AuthContext; use handleApiError in components or API layer.
 */

import {
  AuthError,
  RateLimitError,
  NetworkError,
  normalizeApiError,
  getRecoveryStrategy,
  type RecoveryStrategy,
} from "./errors";

export type On401 = () => void;
export type On429 = (retryAfter?: number) => void;
export type OnServerError = (message: string, retry: () => void) => void;

let on401: On401 = () => {};
let on429: On429 = () => {};
let onServerError: OnServerError = () => {};

export function configureApiErrorHandler(config: {
  on401?: On401;
  on429?: On429;
  onServerError?: OnServerError;
}) {
  if (config.on401) on401 = config.on401;
  if (config.on429) on429 = config.on429;
  if (config.onServerError) onServerError = config.onServerError;
}

/**
 * Handle a failed Response (e.g. after fetch). Dispatches to on401/on429/onServerError and returns a user message.
 */
export async function handleApiError(response: Response | null, cause?: unknown): Promise<{ message: string; strategy: RecoveryStrategy }> {
  const err = await normalizeApiError(response, cause);

  if (err instanceof AuthError) {
    on401();
    return { message: err.message, strategy: { userMessage: err.message, retry: false, fallback: "dismiss" } };
  }

  if (err instanceof RateLimitError) {
    on429(err.retryAfter);
    return {
      message: err.message,
      strategy: { userMessage: err.message, retry: true, fallback: "dismiss" },
    };
  }

  if (err instanceof NetworkError) {
    const strategy = getRecoveryStrategy(err);
    return { message: strategy.userMessage, strategy };
  }

  if (err.status && err.status >= 500) {
    onServerError(err.message, () => {
      // Caller can retry the request
      window.dispatchEvent(new CustomEvent("api:retry"));
    });
    return {
      message: "Server error. Please try again in a moment.",
      strategy: { userMessage: "Server error. Please try again.", retry: true, fallback: "refresh" },
    };
  }

  const strategy = getRecoveryStrategy(err);
  return { message: err.message, strategy };
}

/**
 * Handle an unknown error (e.g. from catch block). If it's an AuthError/RateLimitError, runs handlers.
 */
export function handleUnknownError(error: unknown): { message: string; strategy: RecoveryStrategy } {
  if (error instanceof AuthError) {
    on401();
    return { message: error.message, strategy: { userMessage: error.message, retry: false, fallback: "dismiss" } };
  }
  if (error instanceof RateLimitError) {
    on429(error.retryAfter);
    return { message: error.message, strategy: { userMessage: error.message, retry: true, fallback: "dismiss" } };
  }
  const strategy = getRecoveryStrategy(error);
  return { message: strategy.userMessage, strategy };
}
