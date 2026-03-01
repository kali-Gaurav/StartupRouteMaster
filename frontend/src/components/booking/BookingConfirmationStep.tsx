import { useEffect } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, ExternalLink, Ticket } from "lucide-react";
import { useBookingFlowContext } from "@/context/BookingFlowContext";
import { Button } from "@/components/ui/button";
import { formatCost } from "@/data/routes";
import { getStationByCode } from "@/data/stations";
import { saveTicket } from "@/lib/ticketStore";

function buildRouteSummary(route: { segments: { from: string; to: string; departure: string; arrival: string; trainNumber?: string }[] }): string {
  return route.segments
    .map((s, i) => {
      const from = getStationByCode(s.from)?.name ?? s.from;
      const to = getStationByCode(s.to)?.name ?? s.to;
      return `${i + 1}. ${from} ${s.departure} → ${to} ${s.arrival}${s.trainNumber ? ` (${s.trainNumber})` : ""}`;
    })
    .join("\n");
}

export function BookingConfirmationStep() {
  const { route, travelDate, originName, destName, bookingId, irctcUrl, close } =
    useBookingFlowContext();

  useEffect(() => {
    if (!bookingId || !route) return;
    saveTicket({
      id: bookingId,
      reference: bookingId,
      originName,
      destName,
      travelDate,
      routeSummary: buildRouteSummary(route),
      totalCost: route.totalCost ?? 0,
      irctcUrl,
      status: "pending_irctc",
      trainNumber: route.segments[0]?.trainNumber,
    });
  }, [bookingId, route, originName, destName, travelDate, irctcUrl]);

  const displayDate = travelDate
    ? new Date(travelDate + "T12:00:00").toLocaleDateString("en-IN", {
        weekday: "short",
        day: "numeric",
        month: "short",
      })
    : "—";

  const openIRCTC = () => {
    if (irctcUrl) window.open(irctcUrl, "_blank");
  };

  return (
    <div className="space-y-6">
      <div className="text-center py-4">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 mb-4">
          <CheckCircle2 className="h-10 w-10" />
        </div>
        <h3 className="text-xl font-bold text-foreground">Booking confirmed</h3>
        <p className="text-muted-foreground mt-1">Complete your ticket on IRCTC to get your PNR.</p>
      </div>

      {bookingId && (
        <div className="rounded-lg bg-muted/50 px-4 py-3 text-center">
          <span className="text-sm text-muted-foreground">Reference </span>
          <span className="font-mono font-semibold text-foreground">{bookingId}</span>
        </div>
      )}

      {route && (
        <div className="rounded-xl border border-border p-4 space-y-2">
          <p className="font-medium text-foreground">
            {originName} → {destName}
          </p>
          <p className="text-sm text-muted-foreground">{displayDate}</p>
          {route.totalCost > 0 && (
            <p className="text-sm font-semibold text-foreground">{formatCost(route.totalCost)}</p>
          )}
        </div>
      )}

      <div className="space-y-2">
        <p className="text-sm font-semibold text-foreground">Next steps</p>
        <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
          <li>Open IRCTC and complete the booking with your passenger details.</li>
          <li>Your payment for our service fee is confirmed.</li>
          <li>Train fare will be charged on IRCTC checkout.</li>
        </ul>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 pt-2">
        {irctcUrl ? (
          <Button className="flex-1" onClick={openIRCTC}>
            <ExternalLink className="h-4 w-4 mr-2" />
            Open IRCTC to complete ticket
          </Button>
        ) : (
          <p className="text-sm text-muted-foreground">
            Open IRCTC from your account or My Bookings when ready.
          </p>
        )}
        <Link to={bookingId ? `/ticket/${encodeURIComponent(bookingId)}` : "/bookings"}>
          <Button variant="outline">
            <Ticket className="h-4 w-4 mr-2" />
            View ticket
          </Button>
        </Link>
        <Link to="/bookings">
          <Button variant="outline">My Bookings</Button>
        </Link>
        <Button variant="ghost" onClick={close}>
          Close
        </Button>
      </div>

      <p className="text-xs text-center text-muted-foreground pt-2">
        Need help? Contact support from My Bookings or the app footer.
      </p>
    </div>
  );
}
