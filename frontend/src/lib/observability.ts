/**
 * Observability & Error Logging Utility
 */

type ErrorReporter = (error: any, info?: { componentStack?: string }) => void;
type EventLogger = (name: string, properties?: Record<string, any>, extra?: any) => void;

let currentErrorReporter: ErrorReporter = (error, info) => {
  console.error("Caught error:", error);
  if (info?.componentStack) {
    console.error("Component stack:", info.componentStack);
  }
};

let currentEventLogger: EventLogger = (name, properties, extra) => {
  if (import.meta.env.DEV) {
    console.log(`[Event: ${name}]`, properties, extra || "");
  }
};

export const logError = (error: any, info?: { componentStack?: string }) => {
  currentErrorReporter(error, info);
};

export const reportError = logError;

export const logEvent = (name: string, properties?: Record<string, any>, extra?: any) => {
  currentEventLogger(name, properties, extra);
};

export const logPerf = (metric: string, value: number, tags?: Record<string, string>) => {
  if (import.meta.env.DEV) {
    console.log(`[Perf: ${metric}] ${value}ms`, tags || "");
  }
};

export const setErrorReporter = (reporter: ErrorReporter) => {
  currentErrorReporter = reporter;
};

export const setEventLogger = (logger: EventLogger) => {
  currentEventLogger = logger;
};
