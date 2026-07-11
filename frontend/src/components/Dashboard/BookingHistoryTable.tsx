/**
 * Booking History Table Component
 * Sortable, filterable table for booking history
 */

import { Link } from "react-router-dom";
import { Calendar, Users, ChevronLeft, ChevronRight, Ticket } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { HistorySkeleton } from "@/components/skeletons";

interface BookingHistoryTableProps {
  bookings: any[];
  isLoading: boolean;
  currentPage: number;
  pageSize: number;
  sortBy?: string;
  filterStatus?: string;
  onSortChange?: (field: string) => void;
  onStatusFilterChange?: (status: string) => void;
  onPageChange: (page: number) => void;
}

export function BookingHistoryTable({
  bookings,
  isLoading,
  currentPage,
  pageSize,
  sortBy = "date-desc",
  filterStatus = "",
  onSortChange = () => {},
  onStatusFilterChange = () => {},
  onPageChange,
}: BookingHistoryTableProps) {
  const filteredBookings = filterStatus
    ? bookings.filter(b => b.booking_status === filterStatus)
    : bookings;

  const sortedBookings = [...filteredBookings].sort((a, b) => {
    switch (sortBy) {
      case "date-asc":
        return new Date(a.travel_date).getTime() - new Date(b.travel_date).getTime();
      case "date-desc":
        return new Date(b.travel_date).getTime() - new Date(a.travel_date).getTime();
      case "amount-asc":
        return (a.amount_paid || 0) - (b.amount_paid || 0);
      case "amount-desc":
        return (b.amount_paid || 0) - (a.amount_paid || 0);
      default:
        return 0;
    }
  });

  const paginatedBookings = sortedBookings.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  const totalPages = Math.ceil(sortedBookings.length / pageSize);

  if (isLoading) {
    return <HistorySkeleton count={3} />;
  }

  if (filteredBookings.length === 0) {
    return (
      <div className="rounded-2xl border-2 border-dashed border-border bg-muted/30 p-8 text-center">
        <Ticket className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
        <p className="font-medium text-muted-foreground">No bookings found</p>
        <p className="text-sm text-muted-foreground/70 mt-1">Start by searching for a route</p>
        <Link to="/" className="inline-block mt-4 text-primary font-bold text-sm hover:underline">
          Search Routes →
        </Link>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-3">
        {paginatedBookings.map((booking) => (
          <div
            key={booking.id}
            className="bg-card border border-border rounded-xl p-4 hover:border-primary/40 transition-all hover:shadow-md"
          >
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-bold text-sm md:text-base">
                    {(booking.booking_details as any)?.origin || "Unknown"} → {(booking.booking_details as any)?.destination || "Unknown"}
                  </span>
                  <span className={cn(
                    "text-[10px] px-2 py-1 rounded-full font-black uppercase tracking-tighter",
                    booking.booking_status === "confirmed" ? "bg-green-100 text-green-800" :
                    booking.booking_status === "pending" ? "bg-yellow-100 text-yellow-800" :
                    booking.booking_status === "cancelled" ? "bg-red-100 text-red-800" :
                    "bg-gray-100 text-gray-800"
                  )}>
                    {booking.booking_status?.replace('_', ' ') || "pending"}
                  </span>
                </div>
                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground font-medium">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    {booking.travel_date ? new Date(booking.travel_date + "T12:00:00").toLocaleDateString("en-IN") : "—"}
                  </span>
                  <span className="flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    {(booking.booking_details as any)?.passengers?.length || 1} passenger{(booking.booking_details as any)?.passengers?.length !== 1 ? 's' : ''}
                  </span>
                  {booking.pnr_number && (
                    <span className="font-mono bg-muted/50 px-2 py-0.5 rounded">
                      PNR: {booking.pnr_number}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  {booking.amount_paid > 0 && (
                    <p className="font-black text-lg">₹{booking.amount_paid.toFixed(0)}</p>
                  )}
                  <p className="text-xs text-muted-foreground font-medium">
                    {booking.created_at ? new Date(booking.created_at).toLocaleDateString("en-IN") : "—"}
                  </p>
                </div>
                {booking.pnr_number && (
                  <Link
                    to={`/ticket/${encodeURIComponent(booking.pnr_number)}`}
                    className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-black uppercase tracking-wider hover:opacity-90 transition-opacity whitespace-nowrap"
                  >
                    View
                  </Link>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(Math.max(0, currentPage - 1))}
            disabled={currentPage === 0}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Previous
          </Button>
          <span className="text-xs text-muted-foreground font-medium">
            Page {currentPage + 1} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages - 1}
          >
            Next
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      )}
    </>
  );
}

export default BookingHistoryTable;
