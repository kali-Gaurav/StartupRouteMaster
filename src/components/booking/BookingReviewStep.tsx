import { Clock, MapPin, Train, AlertCircle } from "lucide-react";
import { useBookingFlowContext } from "@/context/BookingFlowContext";
import { getStationByCode } from "@/data/stations";
import { formatDuration, formatCost } from "@/data/routes";
import { Button } from "@/components/ui/button";

export function BookingReviewStep() {
  const { route, travelDate, originName, destName, nextStep, close, error, setError } =
    useBookingFlowContext();

  if (!route) return null;

  const first = route.segments[0];
  const last = route.segments[route.segments.length - 1];
  const fromName = getStationByCode(first?.from)?.name ?? originName ?? first?.from;
  const toName = getStationByCode(last?.to)?.name ?? destName ?? last?.to;
  const displayDate = travelDate
    ? new Date(travelDate + "T12:00:00").toLocaleDateString("en-IN", {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "—";

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground">Booking summary</h3>

      <div className="rounded-xl border border-border bg-muted/30 p-4 space-y-3">
        <div className="flex items-center gap-2 text-foreground font-medium">
          <MapPin className="h-4 w-4 text-primary shrink-0" />
          <span>{fromName}</span>
          <span className="text-muted-foreground">→</span>
          <span>{toName}</span>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Clock className="h-4 w-4" />
            {first?.departure} – {last?.arrival} · {formatDuration(route.totalTime)}
          </span>
          <span className="flex items-center gap-1.5">
            <Train className="h-4 w-4" />
            {route.segments.length} leg{route.segments.length > 1 ? "s" : ""}
            {route.totalTransfers > 0 && ` · ${route.totalTransfers} transfer${route.totalTransfers > 1 ? "s" : ""}`}
          </span>
        </div>
        <div className="pt-2 border-t border-border">
          <span className="text-sm text-muted-foreground">Travel date: </span>
          <span className="font-medium text-foreground">{displayDate}</span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-sm text-muted-foreground">Estimated fare</span>
          <span className="text-xl font-bold text-foreground">
            {route.totalCost > 0 ? formatCost(route.totalCost) : "N/A"}
          </span>
        </div>
      </div>

      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-800 dark:text-amber-200">
        <p className="font-medium">Cancellation</p>
        <p className="text-muted-foreground mt-0.5">
          IRCTC cancellation rules apply. Check fare rules before payment.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="flex flex-wrap gap-3 pt-2">
        <Button type="button" variant="outline" onClick={close}>
          Back
        </Button>
        <Button
          type="button"
          onClick={() => {
            setError(null);
            nextStep();
          }}
        >
          Continue to confirm seats
        </Button>
      </div>
    </div>
  );
}
