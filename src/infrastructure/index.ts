/**
 * Infrastructure – query client, error boundary, observability.
 */

export { queryClient } from "./queryClient";
export { ErrorBoundary } from "@/components/ErrorBoundary";
export { reportError, setErrorReporter } from "@/lib/observability";
