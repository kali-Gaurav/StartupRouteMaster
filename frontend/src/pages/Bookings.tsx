/**
 * My Bookings – protected page showing booking history.
 * Uses useBookings (React Query) for cache, retry, and background refresh.
 * Also shows recent tickets from local store (viewable at /ticket/:id).
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useBookings } from "@/api/hooks/useBookings";
import { getAllTickets } from "@/lib/ticketStore";
import { HistorySkeleton } from "@/components/skeletons";
import { Ticket, AlertCircle, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { type Booking } from "@/api/booking";

function BookingsContent() {
  const [page, setPage] = useState(0);
  const limit = 20;
  const { data: bookingsData, isLoading: loading, error: queryError, refetch } = useBookings({ skip: page * limit, limit });
  
  // Handle various response shapes from useBookings hook
  const bookings: Booking[] = Array.isArray(bookingsData) 
    ? bookingsData 
    : (bookingsData as any)?.bookings || [];

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
          <>
            <ul className="space-y-4">
              {bookings.map((b: Booking) => (
                <li
                  key={b.id || b.pnr_number || Math.random()}
                  className="rounded-xl border border-border p-4 bg-card hover:border-primary/40 transition-colors"
                >
                  <div className="flex flex-wrap justify-between gap-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium">
                          {(b.booking_details as any)?.origin || (b.booking_details as any)?.source || "Unknown"} → {(b.booking_details as any)?.destination || (b.booking_details as any)?.dest || "Unknown"}
                        </span>
                        {b.booking_status && (
                          <span className={`text-xs px-2 py-0.5 rounded font-bold uppercase ${
                            b.booking_status === "confirmed" ? "bg-green-100 text-green-800" :
                            b.booking_status === "ticket_sent" ? "bg-blue-100 text-blue-800 border border-blue-200" :
                            b.booking_status === "pending_manual" ? "bg-purple-100 text-purple-800 animate-pulse" :
                            b.booking_status === "pending" ? "bg-yellow-100 text-yellow-800" :
                            b.booking_status === "cancelled" ? "bg-red-100 text-red-800" :
                            "bg-gray-100 text-gray-800"
                          }`}>
                            {b.booking_status.replace('_', ' ')}
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                        <span>Travel Date: {b.travel_date ? new Date(b.travel_date + "T12:00:00").toLocaleDateString("en-IN") : "—"}</span>
                        {b.pnr_number && <span className="font-mono">PNR: {b.pnr_number}</span>}
                        {b.amount_paid > 0 && <span>Amount: ₹{b.amount_paid.toFixed(2)}</span>}
                      </div>
                      {b.created_at && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Booked: {new Date(b.created_at).toLocaleDateString("en-IN", { dateStyle: "medium" })}
                        </p>
                      )}
                    </div>
                    {b.pnr_number && (
                      <Link
                        to={`/ticket/${encodeURIComponent(b.pnr_number)}`}
                        className="text-sm text-primary hover:underline"
                      >
                        View Ticket →
                      </Link>
                    )}
                  </div>
                </li>
              ))}
            </ul>
            {/* Pagination */}
            {bookings.length >= limit && (
              <div className="flex items-center justify-between mt-6 pt-4 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Page {page + 1}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={bookings.length < limit}
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            )}
          </>
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
