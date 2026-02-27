/**
 * Frontend observability - errors and product analytics.
 * Ready for Sentry and PostHog by replacing the no-op implementation.
 */

export interface ErrorContext {
  componentStack?: string;
  [key: string]: unknown;
}

/** 
 * ERROR TRACKING (e.g. Sentry)
 */
let reportFn: (error: Error, context?: ErrorContext) => void = (error, context) => {
  if (import.meta.env.DEV) {
    console.error("[Observability:Error]", error, context);
  }
};

export function setErrorReporter(fn: (error: Error, context?: ErrorContext) => void) {
  reportFn = fn;
}

export function reportError(error: Error | string, context?: ErrorContext): void {
  const err = error instanceof Error ? error : new Error(String(error));
  reportFn(err, context);
}

/** 
 * EVENT ANALYTICS (e.g. PostHog)
 */
export type EventPayload = Record<string, string | number | boolean | undefined | null>;
export type EventLevel = "info" | "warn" | "error" | "critical";

type EventLoggerFn = (event: string, payload?: EventPayload, level?: EventLevel) => void;

let eventLogFn: EventLoggerFn = (event, payload, level = "info") => {
  if (import.meta.env.DEV) {
    console.debug(`[Observability:Event:${level}]`, event, payload);
  }
};

export function setEventLogger(fn: EventLoggerFn) {
  eventLogFn = fn;
}

export function logEvent(event: string, payload?: EventPayload, level: EventLevel = "info"): void {
  eventLogFn(event, payload, level);
}

/**
 * PERFORMANCE MONITORING
 */
export function logPerf(name: string, data: EventPayload): void {
  logEvent("perf", { name, ...data }, "info");
}

/**
 * TRACKING CORE EVENTS
 */
export const track = {
  loginSuccess: (userId: string, method: string) => logEvent("login_success", { userId, method }),
  loginFailure: (reason: string) => logEvent("login_failure", { reason }, "error"),
  sosTriggered: (mode: 'EMERGENCY' | 'SHIELD', location: { lat: number, lng: number }) => 
    logEvent("sos_triggered", { mode, ...location }, "critical"),
  searchPerformed: (origin: string, destination: string, count: number) => 
    logEvent("search_performed", { origin, destination, count }),
  paymentStarted: (routeId: string, amount: number) => 
    logEvent("payment_started", { routeId, amount }),
  paymentSuccess: (routeId: string, transactionId: string) => 
    logEvent("payment_success", { routeId, transactionId }),
};
