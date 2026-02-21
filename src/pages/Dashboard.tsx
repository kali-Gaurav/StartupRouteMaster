/**
 * Safe Journey Ops Dashboard
 * Shows SOS events in red zone (highest priority). Direct Google Maps links.
 * No login - prototype for investor demo.
 */
import { useState, useEffect } from "react";
import { MapPin, ExternalLink, Phone, Mail, User, AlertCircle, CheckCircle, RefreshCw, Train } from "lucide-react";
import { getAllSOS, resolveSOS, type SOSEvent } from "@/services/sosApi";

function EventCard({ e, onResolve }: { e: SOSEvent; onResolve: () => void }) {
  const isActive = e.status === "active";
  const isTripEnded = e.status === "trip_ended";
  return (
    <div
      className={`
        rounded-xl border-2 p-5 space-y-4
        ${isActive ? "border-red-500 bg-red-500/5" : "border-muted bg-muted/30"}
      `}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          {isActive ? (
            <AlertCircle className="w-5 h-5 text-red-500 shrink-0" />
          ) : (
            <CheckCircle className="w-5 h-5 text-green-500 shrink-0" />
          )}
          <span className={`font-bold ${isActive ? "text-red-600" : isTripEnded ? "text-green-600" : "text-muted-foreground"}`}>
            {isActive ? "RED ZONE — LIVE" : isTripEnded ? "Trip ended safely" : "Resolved"}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">
          {new Date(e.triggered_at).toLocaleString()}
        </span>
      </div>

      <div className="grid gap-2 text-sm">
        <div className="flex items-center gap-2">
          <User className="w-4 h-4 text-muted-foreground" />
          <span className="font-medium">{e.name}</span>
        </div>
        <div className="flex items-center gap-2">
          <Phone className="w-4 h-4 text-muted-foreground" />
          <a href={`tel:${e.phone}`} className="text-primary hover:underline">{e.phone}</a>
        </div>
        <div className="flex items-center gap-2">
          <Mail className="w-4 h-4 text-muted-foreground" />
          <a href={`mailto:${e.email}`} className="text-primary hover:underline">{e.email}</a>
        </div>
        <div className="flex items-center gap-2">
          <MapPin className="w-4 h-4 text-muted-foreground" />
          <span className="text-muted-foreground">
            {e.lat.toFixed(5)}, {e.lng.toFixed(5)}
          </span>
        </div>
      </div>

      {e.trip && [e.trip.origin, e.trip.destination, e.trip.mode, e.trip.vehicle_number, e.trip.driver_name, e.trip.boarding_time, e.trip.eta].some(Boolean) && (
        <div className="rounded-lg bg-muted/50 p-3 space-y-1">
          <div className="flex items-center gap-2 font-medium text-sm mb-2">
            <Train className="w-4 h-4 text-primary" />
            Trip Details
          </div>
          <div className="grid gap-1 text-xs text-muted-foreground">
            {e.trip.origin && <span><b>From:</b> {e.trip.origin}</span>}
            {e.trip.destination && <span><b>To:</b> {e.trip.destination}</span>}
            {e.trip.mode && <span><b>Mode:</b> {e.trip.mode}</span>}
            {e.trip.vehicle_number && <span><b>Vehicle:</b> {e.trip.vehicle_number}</span>}
            {e.trip.driver_name && <span><b>Driver:</b> {e.trip.driver_name}</span>}
            {e.trip.boarding_time && <span><b>Boarded:</b> {e.trip.boarding_time}</span>}
            {e.trip.eta && <span><b>ETA:</b> {e.trip.eta}</span>}
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <a
          href={e.google_maps_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90"
        >
          <ExternalLink className="w-4 h-4" />
          Open in Google Maps
        </a>
        {isActive && (
          <button
            onClick={onResolve}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-green-500 text-green-600 text-sm font-medium hover:bg-green-500/10"
          >
            <CheckCircle className="w-4 h-4" />
            Mark Resolved
          </button>
        )}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [events, setEvents] = useState<SOSEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      const { events: list } = await getAllSOS();
      setEvents(list);
    } catch {
      setError("Failed to load. Is the backend running?");
      setEvents([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
    const interval = setInterval(fetchEvents, 5000); // Poll every 5s for demo
    return () => clearInterval(interval);
  }, []);

  const handleResolve = async (id: string) => {
    try {
      await resolveSOS(id);
      fetchEvents();
    } catch {
      setError("Failed to resolve.");
    }
  };

  const activeCount = events.filter((e) => e.status === "active").length;

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-8 h-8 text-red-500" />
            <div>
              <h1 className="text-xl font-bold">Safe Journey — Ops Dashboard</h1>
              <p className="text-sm text-muted-foreground">Live SOS monitoring (prototype)</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {activeCount > 0 && (
              <div className="px-4 py-2 rounded-lg bg-red-500/20 text-red-600 font-bold">
                {activeCount} Active SOS
              </div>
            )}
            <button
              onClick={fetchEvents}
              disabled={loading}
              className="p-2 rounded-lg border border-border hover:bg-muted"
            >
              <RefreshCw className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-destructive/10 text-destructive">
            {error}
          </div>
        )}

        {loading && events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <RefreshCw className="w-12 h-12 animate-spin mb-4" />
            <p>Loading SOS events...</p>
          </div>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <CheckCircle className="w-16 h-16 text-green-500 mb-4" />
            <p className="font-medium">No SOS events yet</p>
            <p className="text-sm mt-1">Press SOS on the passenger page to test</p>
            <a href="/sos" className="mt-4 text-primary hover:underline">Go to SOS Page →</a>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                All Events ({events.length}) — Active first
              </h2>
            </div>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {events.map((e) => (
                <EventCard key={e.id} e={e} onResolve={() => handleResolve(e.id)} />
              ))}
            </div>
          </div>
        )}
      </main>

      <footer className="border-t border-border mt-12 py-6 text-center text-sm text-muted-foreground">
        <a href="/" className="hover:text-foreground">← Back to home</a>
        <span className="mx-2">|</span>
        <a href="/sos" className="hover:text-foreground">SOS Page (passenger)</a>
      </footer>
    </div>
  );
}
