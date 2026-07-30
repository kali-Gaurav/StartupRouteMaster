import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
interface Props {
  children?: ReactNode;
  /** Optional component name shown in the fallback UI */
  name?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Task 18: Telemetry Integration Placeholder
    console.error("Uncaught error:", error, errorInfo);
    
    // Example: Sentry.captureException(error);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
          <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center border border-slate-100">
            <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-6">
              <AlertTriangle className="w-8 h-8 text-red-500" />
            </div>
            
            <h1 className="text-2xl font-bold text-slate-900 mb-2">
              Something went wrong{this.props.name ? ` in ${this.props.name}` : ''}
            </h1>
            
            <p className="text-slate-600 mb-8">
              We've encountered an unexpected error. Our team has been notified and we're working to fix it.
            </p>

            <div className="space-y-3">
              <Button 
                onClick={() => window.location.reload()}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white py-6 rounded-xl text-lg font-semibold"
              >
                <RefreshCw className="w-5 h-5 mr-2" />
                Reload Page
              </Button>
              
              <Button 
                variant="ghost"
                onClick={() => this.setState({ hasError: false, error: null })}
                className="w-full text-slate-500"
              >
                Try to Recover
              </Button>
            </div>

            {process.env.NODE_ENV === 'development' && (
              <div className="mt-8 text-left p-4 bg-slate-900 rounded-lg overflow-auto max-h-40">
                <pre className="text-xs text-red-400 font-mono">
                  {this.state.error?.toString()}
                </pre>
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
