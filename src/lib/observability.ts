/**
 * Frontend observability – errors and optional RUM.
 * Wire to Sentry/LogRocket later by replacing the no-op implementation.
 */

export interface ErrorContext {
  componentStack?: string;
  [key: string]: unknown;
}

let reportFn: (error: Error, context?: ErrorContext) => void = (error, context) => {
  console.error("[reportError]", error, context);
};

/**
 * Configure error reporting (e.g. Sentry.captureException).
 * Call once at app init if using a service.
 */
export function setErrorReporter(fn: (error: Error, context?: ErrorContext) => void) {
  reportFn = fn;
}

/**
 * Report an error to the configured reporter (and console).
 * Use in ErrorBoundary and after caught API errors if needed.
 */
export function reportError(error: Error, context?: ErrorContext): void {
  reportFn(error, context);
}

/** Event payload for analytics/debugging. No PII in production logs. */
export type EventPayload = Record<string, string | number | boolean | undefined>;

export type EventLevel = "info" | "warn" | "error" | "critical";

type EventLoggerFn = (event: string, payload?: EventPayload, level?: EventLevel) => void;

let eventLogFn: EventLoggerFn = (event, payload, level = "info") => {
  if (import.meta.env.DEV) {
    console.debug(`[logEvent:${level}]`, event, payload);
  }
};

/**
 * Configure event logging (e.g. analytics, Datadog RUM).
 * Call once at app init if using a service.
 */
export function setEventLogger(fn: EventLoggerFn) {
  eventLogFn = fn;
}

/**
 * Log a named event for debugging and product analytics.
 * Optional level: info | warn | error | critical (default info). Keeps payload small; avoid PII.
 */
export function logEvent(event: string, payload?: EventPayload, level?: EventLevel): void {
  eventLogFn(event, payload, level ?? "info");
}

/**
 * Log a performance timing event. Use for route load time, API latency, flow duration.
 * Example: logPerf("search_latency", { ms: 120, origin, destination })
 */
export function logPerf(name: string, data: EventPayload): void {
  eventLogFn("perf", { name, ...data }, "info");
}
