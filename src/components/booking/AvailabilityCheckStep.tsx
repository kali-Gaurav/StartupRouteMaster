import { Loader2, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import { useBookingFlowContext } from "@/context/BookingFlowContext";
import { Button } from "@/components/ui/button";
import { BookingStepSkeleton } from "@/components/skeletons";
import { cn } from "@/lib/utils";
import { useEffect, useRef, useState } from "react";

export function AvailabilityCheckStep() {
  const {
    availabilityPhase,
    nextStep,
    goToStep,
    close,
    error,
    setError,
    runAvailabilityCheck,
    retryAvailability,
  } = useBookingFlowContext();

  const hasStartedCheck = useRef(false);
  useEffect(() => {
    if (availabilityPhase === "idle" && !hasStartedCheck.current) {
      hasStartedCheck.current = true;
      runAvailabilityCheck();
    }
  }, [availabilityPhase, runAvailabilityCheck]);
  useEffect(() => {
    if (availabilityPhase === "failed" || availabilityPhase === "confirmed") {
      hasStartedCheck.current = false;
    }
  }, [availabilityPhase]);

  const [slowWarning, setSlowWarning] = useState(false);
  useEffect(() => {
    if (availabilityPhase !== "checking" && availabilityPhase !== "locking") {
      setSlowWarning(false);
      return;
    }
    const t = setTimeout(() => setSlowWarning(true), 8000);
    return () => clearTimeout(t);
  }, [availabilityPhase]);

  useEffect(() => {
    if (availabilityPhase === "confirmed") {
      const t = setTimeout(() => nextStep(), 800);
      return () => clearTimeout(t);
    }
  }, [availabilityPhase, nextStep]);

  const isChecking = availabilityPhase === "checking" || availabilityPhase === "locking";
  const isConfirmed = availabilityPhase === "confirmed";

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground">Seat availability</h3>

      <div className="rounded-xl border border-border bg-muted/20 p-6 min-h-[140px] flex flex-col items-center justify-center">
        {availabilityPhase === "checking" && (
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <BookingStepSkeleton />
            <p className="font-medium text-foreground">Checking seat availability…</p>
            <p className="text-sm">Please wait</p>
            {slowWarning && (
              <p className="text-amber-600 dark:text-amber-400 text-xs">
                Taking longer than usual. You can go back and try again.
              </p>
            )}
          </div>
        )}
        {availabilityPhase === "locking" && (
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="font-medium text-foreground">Locking seats…</p>
            <p className="text-sm">Almost there</p>
            {slowWarning && (
              <p className="text-amber-600 dark:text-amber-400 text-xs">
                Taking longer than usual. You can go back and try again.
              </p>
            )}
          </div>
        )}
        {availabilityPhase === "confirmed" && (
          <div className="flex flex-col items-center gap-3 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="h-12 w-12" />
            <p className="font-semibold text-foreground">Seats confirmed</p>
            <p className="text-sm text-muted-foreground">Proceeding to payment…</p>
          </div>
        )}
        {availabilityPhase === "failed" && (
          <div className="flex flex-col items-center gap-3 text-destructive">
            <AlertCircle className="h-10 w-10" />
            <p className="font-medium">Availability check failed</p>
            <p className="text-sm text-muted-foreground text-center">
              Seats may have changed. Try again or choose another route.
            </p>
            <Button variant="outline" size="sm" onClick={retryAvailability} className="mt-2">
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="flex flex-wrap gap-3 pt-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => goToStep("review")}
          disabled={isChecking}
        >
          Back
        </Button>
        {isConfirmed && (
          <Button type="button" onClick={nextStep}>
            Continue to payment
          </Button>
        )}
        {availabilityPhase === "failed" && (
          <Button type="button" onClick={() => close()}>
            Choose another route
          </Button>
        )}
      </div>
    </div>
  );
}
