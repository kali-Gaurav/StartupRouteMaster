/**
 * My Bookings – protected page showing booking history.
 * Uses useBookings (React Query) for cache, retry, and background refresh.
 * Also shows recent tickets from local store (viewable at /ticket/:id).
 */

import { Link } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useBookings } from "@/api/hooks/useBookings";
import { getAllTickets } from "@/lib/ticketStore";
import { HistorySkeleton } from "@/components/skeletons";
import { Ticket, AlertCircle } from "lucide-react";

interface Booking {
  booking_id?: string;
  id?: string;
  origin: string;
  destination: string;
  travel_date?: string;
  created_at?: string;
  train_no?: string;
}

function BookingsContent() {
  const { data: bookings = [], isLoading: loading, error: queryError, refetch } = useBookings() as { data: Booking[], isLoading: boolean, error: unknown, refetch: () => void };
  const error = queryError ? (queryError instanceof Error ? queryError.message : "Failed to load bookings") : null;
  const localTickets = getAllTickets();

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="container mx-auto px-4 py-8 flex-1">
        <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
          <Ticket className="w-7 h-7" />
          My Bookings
        </h1>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-destructive/10 text-destructive flex items-center gap-2">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span>{error}</span>
            <button
              type="button"
              onClick={() => refetch()}
              className="ml-auto text-sm underline hover:no-underline"
            >
              Retry
            </button>
          </div>
        )}

        {localTickets.length > 0 && (
          <section className="mb-8">
            <h2 className="text-lg font-semibold text-foreground mb-3">Recent tickets (this device)</h2>
            <p className="text-sm text-muted-foreground mb-3">
              Open or share your ticket anytime. Stored on this device.
            </p>
            <ul className="space-y-3">
              {localTickets.slice(0, 10).map((t) => (
                <li key={t.id}>
                  <Link
                    to={`/ticket/${encodeURIComponent(t.id)}`}
                    className="block rounded-xl border border-border p-4 bg-card hover:border-primary/40 transition-colors"
                  >
                    <div className="flex flex-wrap justify-between gap-2">
                      <span className="font-medium">{t.originName} → {t.destName}</span>
                      <span className="text-sm text-muted-foreground">
                        {t.travelDate ? new Date(t.travelDate + "T12:00:00").toLocaleDateString("en-IN") : "—"}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 font-mono">{t.reference}</p>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        <h2 className="text-lg font-semibold text-foreground mb-3">Booking history</h2>
        {loading ? (
          <HistorySkeleton count={5} />
        ) : bookings.length === 0 ? (
          <div className="rounded-xl border border-border bg-muted/30 p-6 text-center text-muted-foreground">
            <p className="font-medium">No server bookings yet</p>
            <p className="text-sm mt-1">Bookings from this account will appear here.</p>
            <a href="/" className="inline-block mt-3 text-primary hover:underline">Search routes →</a>
          </div>
        ) : (
          <ul className="space-y-4">
            {bookings.map((b: Booking) => (
              <li
                key={b.booking_id || b.id || Math.random()}
                className="rounded-xl border border-border p-4 bg-card"
              >
                <div className="flex flex-wrap justify-between gap-2">
                  <span className="font-medium">{b.origin} → {b.destination}</span>
                  <span className="text-sm text-muted-foreground">{b.travel_date || b.created_at}</span>
                </div>
                {b.train_no && <p className="text-sm text-muted-foreground mt-1">Train: {b.train_no}</p>}
              </li>
            ))}
          </ul>
        )}
      </main>
      <Footer />
    </div>
  );
}

export default function Bookings() {
  return (
    <ProtectedRoute>
      <BookingsContent />
    </ProtectedRoute>
  );
}
