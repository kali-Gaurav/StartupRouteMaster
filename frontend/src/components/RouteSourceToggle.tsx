/**
 * Route Source Toggle Component
 * Allows users to switch between live (database) and cached (precomputed) routes
 */

import { useState, useEffect } from "react";
import { Database, FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { isBackendAvailable } from "@/services/railwayBackApi";

export type RouteSource = "live" | "cached";

interface RouteSourceToggleProps {
  value: RouteSource;
  onChange: (source: RouteSource) => void;
  className?: string;
  showStatus?: boolean;
}

const STORAGE_KEY = "railway_route_source_preference";

export function RouteSourceToggle({
  value,
  onChange,
  className,
  showStatus = true,
}: RouteSourceToggleProps) {
  const [backendAvailable, setBackendAvailable] = useState<boolean | null>(null);
  const [checkingBackend, setCheckingBackend] = useState(false);

  // Load preference from localStorage
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "live" || saved === "cached") {
      onChange(saved);
    }
  }, [onChange]);

  // Check backend availability
  useEffect(() => {
    if (showStatus) {
      setCheckingBackend(true);
      isBackendAvailable()
        .then((available) => {
          setBackendAvailable(available);
          // Auto-switch to cached if backend unavailable and currently on live
          if (!available && value === "live") {
            onChange("cached");
          }
        })
        .catch(() => setBackendAvailable(false))
        .finally(() => setCheckingBackend(false));
    }
  }, [showStatus, value, onChange]);

  const handleChange = (newSource: RouteSource) => {
    onChange(newSource);
    localStorage.setItem(STORAGE_KEY, newSource);
  };

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="flex items-center gap-1 rounded-lg border bg-background p-1">
        <Button
          variant={value === "live" ? "default" : "ghost"}
          size="sm"
          onClick={() => handleChange("live")}
          disabled={backendAvailable === false && !checkingBackend}
          className={cn(
            "h-8 gap-1.5 px-3",
            value === "live" && "bg-primary text-primary-foreground"
          )}
        >
          <Database className="h-3.5 w-3.5" />
          <span className="text-xs font-medium">Live</span>
        </Button>
        <Button
          variant={value === "cached" ? "default" : "ghost"}
          size="sm"
          onClick={() => handleChange("cached")}
          className={cn(
            "h-8 gap-1.5 px-3",
            value === "cached" && "bg-primary text-primary-foreground"
          )}
        >
          <FileText className="h-3.5 w-3.5" />
          <span className="text-xs font-medium">Cached</span>
        </Button>
      </div>
      {showStatus && (
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {checkingBackend ? (
            <>
              <Loader2 className="h-3 w-3 animate-spin" />
              <span>Checking...</span>
            </>
          ) : backendAvailable === false ? (
            <>
              <div className="h-2 w-2 rounded-full bg-amber-500" />
              <span>Backend offline</span>
            </>
          ) : backendAvailable === true ? (
            <>
              <div className="h-2 w-2 rounded-full bg-green-500" />
              <span>Backend online</span>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
