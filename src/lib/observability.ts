/**
 * Observability & Error Logging Utility
 * Handles logging errors to the console in dev and can be extended 
 * for Sentry/LogRocket in production.
 */

export const logError = (error: Error, info?: { componentStack?: string }) => {
  console.error("Caught error:", error);
  if (info?.componentStack) {
    console.error("Component stack:", info.componentStack);
  }
  
  // Production: Add Sentry.captureException(error) here if needed
};

export const logEvent = (name: string, properties?: Record<string, any>) => {
  if (import.meta.env.DEV) {
    console.log(`[Event: ${name}]`, properties);
  }
  
  // Production: Add Analytics (PostHog/Mixpanel) here
};
