/**
 * Shared error banner: consistent styling, optional retry and dismiss.
 * Use for API errors and validation messages.
 */

import { AlertCircle, X } from "lucide-react";
import { isNetworkError, isRateLimitError } from "@/lib/errors";

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
  onDismiss?: () => void;
  /** If true, show a "Retry" button (e.g. for network/rate limit). */
  showRetry?: boolean;
  className?: string;
}

export function ErrorBanner({
  message,
  onRetry,
  onDismiss,
  showRetry = !!onRetry,
  className,
}: ErrorBannerProps) {
  return (
    <div
      className={`flex flex-wrap items-center gap-3 p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive ${className ?? ""}`}
      role="alert"
    >
      <AlertCircle className="w-5 h-5 shrink-0" />
      <p className="flex-1 text-sm font-medium">{message}</p>
      {showRetry && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 px-3 py-1.5 rounded-lg bg-destructive/20 text-destructive text-sm font-medium hover:bg-destructive/30"
        >
          Retry
        </button>
      )}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 p-1 rounded hover:bg-destructive/20"
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

/**
 * Derive user-facing message and whether to show retry from normalized error.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

export function shouldShowRetry(error: unknown): boolean {
  return isNetworkError(error) || isRateLimitError(error);
}
