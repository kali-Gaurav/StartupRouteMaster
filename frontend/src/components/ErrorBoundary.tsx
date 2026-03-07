/**
 * Enhanced Error Boundary (Suggestion #25)
 * Catches component-level failures and provides a resilient fallback UI.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";
import { reportError } from "@/lib/observability";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "./ui/button";

interface Props {
  children: ReactNode;
  name?: string; // Component name for logging
}

interface State {
  hasError: boolean;
  error?: Error;
  componentStack?: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ componentStack: errorInfo.componentStack ?? undefined });
    reportError(error, {
      component: this.props.name || "Unknown",
      componentStack: errorInfo.componentStack ?? undefined,
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 border-2 border-dashed border-red-200 rounded-2xl bg-red-50 text-center space-y-4">
          <AlertTriangle className="h-10 w-10 text-red-500 mx-auto" />
          <div>
            <h3 className="font-bold text-red-900">Component Failure</h3>
            <p className="text-sm text-red-700">This part of the app failed to load.</p>
          </div>
          {this.state.error && (
            <details className="text-left text-xs text-red-700 bg-red-100 p-3 rounded">
              <summary className="cursor-pointer">Show error details</summary>
              <div className="whitespace-pre-wrap break-words">
                <strong>Error:</strong> {this.state.error.message}
                {this.state.componentStack && (
                  <>
                    <br />
                    <strong>Stack:</strong> {this.state.componentStack}
                  </>
                )}
              </div>
            </details>
          )}
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => this.setState({ hasError: false, error: undefined, componentStack: undefined })}
            className="border-red-300 text-red-700 hover:bg-red-100"
          >
            <RefreshCw className="h-3 w-3 mr-2" />
            Try Again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
