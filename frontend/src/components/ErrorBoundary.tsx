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
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    reportError(error, { 
      component: this.props.name || "Unknown",
      stack: errorInfo.componentStack || undefined 
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
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => this.setState({ hasError: false })}
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
