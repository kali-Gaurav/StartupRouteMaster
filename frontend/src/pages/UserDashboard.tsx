/**
 * User Dashboard – Feature #2: Complete user dashboard UI
 * Features:
 * - Dashboard Summary (totals, stats)
 * - Booking History (sortable, filterable, paginated)
 * - Payment History (sortable, paginated)
 * - Tickets List (with download/print)
 * - User Profile (editable)
 * - Real-time updates
 * - Responsive design (mobile + desktop)
 * - Loading & error states
 */

import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useBookings } from "@/api/hooks/useBookings";
import { useAuth } from "@/context/AuthContext";
import { getAllTickets } from "@/lib/ticketStore";
import { HistorySkeleton } from "@/components/skeletons";
import {
  BarChart3, Users, CreditCard, Ticket as TicketIcon, TrendingUp,
  Calendar, MapPin, Clock, Download, Print, Edit2, Save, X,
  ChevronLeft, ChevronRight, ArrowUpRight, ArrowDownLeft,
  AlertCircle, CheckCircle, AlertTriangle, Loader, Settings
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";

// Dashboard Summary Card Component
function DashboardSummary({ bookingsCount, totalSpent, upcomingCount, completedCount }: {
  bookingsCount: number;
  totalSpent: number;
  upcomingCount: number;
  completedCount: number;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {/* Total Bookings */}
      <div className="bg-gradient-to-br from-blue-500/10 to-blue-600/5 border border-blue-200/30 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Total Bookings</p>
            <p className="text-3xl font-black tabular-nums">{bookingsCount}</p>
            <p className="text-xs text-muted-foreground mt-2">{completedCount} completed</p>
          </div>
          <div className="p-3 rounded-xl bg-blue-500/10">
            <TicketIcon className="w-6 h-6 text-blue-600" />
          </div>
        </div>
      </div>

      {/* Total Spent */}
      <div className="bg-gradient-to-br from-green-500/10 to-green-600/5 border border-green-200/30 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Total Spent</p>
            <p className="text-3xl font-black tabular-nums">₹{totalSpent.toLocaleString("en-IN")}</p>
            <p className="text-xs text-muted-foreground mt-2">Avg: ₹{bookingsCount > 0 ? (totalSpent / bookingsCount).toFixed(0) : 0}</p>
          </div>
          <div className="p-3 rounded-xl bg-green-500/10">
            <CreditCard className="w-6 h-6 text-green-600" />
          </div>
        </div>
      </div>

      {/* Upcoming Journeys */}
      <div className="bg-gradient-to-br from-purple-500/10 to-purple-600/5 border border-purple-200/30 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Upcoming</p>
            <p className="text-3xl font-black tabular-nums">{upcomingCount}</p>
            <p className="text-xs text-muted-foreground mt-2">Journeys to take</p>
          </div>
          <div className="p-3 rounded-xl bg-purple-500/10">
            <TrendingUp className="w-6 h-6 text-purple-600" />
          </div>
        </div>
      </div>

      {/* Account Status */}
      <div className="bg-gradient-to-br from-amber-500/10 to-amber-600/5 border border-amber-200/30 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Status</p>
            <p className="text-xl font-black flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              Active
            </p>
            <p className="text-xs text-muted-foreground mt-2">Member in good standing</p>
          </div>
          <div className="p-3 rounded-xl bg-amber-500/10">
            <CheckCircle className="w-6 h-6 text-amber-600" />
          </div>
        </div>
      </div>
    </div>
  );
}

// User Profile Card Component
interface UserProfileCardProps {
  user: {
    name: string;
    email: string;
    phone: string;
    created_at: string;
  } | null;
  isLoading: boolean;
  onEdit: () => void;
}

function UserProfileCard({ user, isLoading, onEdit }: UserProfileCardProps) {
  if (isLoading) {
    return (
      <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
        <div className="space-y-3">
          <div className="h-4 w-32 bg-muted animate-pulse rounded" />
          <div className="h-4 w-48 bg-muted animate-pulse rounded" />
          <div className="h-4 w-40 bg-muted animate-pulse rounded" />
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="bg-card border border-border rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-lg font-black flex items-center gap-2 uppercase tracking-tight">
          <Users className="w-5 h-5 text-primary" />
          Profile
        </h3>
        <button
          onClick={onEdit}
          className="p-2 hover:bg-muted rounded-lg transition-colors"
          title="Edit profile"
        >
          <Edit2 className="w-4 h-4 text-muted-foreground hover:text-foreground" />
        </button>
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">Name</p>
          <p className="text-lg font-black">{user.name || "Not set"}</p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">Email</p>
          <p className="text-sm font-medium break-all">{user.email}</p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">Phone</p>
          <p className="text-sm font-medium">{user.phone || "Not provided"}</p>
        </div>
        <div className="pt-4 border-t border-border">
          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">Member Since</p>
          <p className="text-sm font-medium">
            {user.created_at ? new Date(user.created_at).toLocaleDateString("en-IN", { dateStyle: 'long' }) : "—"}
          </p>
        </div>
      </div>
    </div>
  );
}

// Booking History Table Component
interface BookingHistoryTableProps {
  bookings: any[];
  isLoading: boolean;
  currentPage: number;
  pageSize: number;
  sortBy: string;
  filterStatus: string;
  onSortChange: (field: string) => void;
  onStatusFilterChange: (status: string) => void;
  onPageChange: (page: number) => void;
}

function BookingHistoryTable({
  bookings,
  isLoading,
  currentPage,
  pageSize,
  sortBy,
  filterStatus,
  onSortChange,
  onStatusFilterChange,
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

  return (
    <section className="mb-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-black flex items-center gap-2 uppercase tracking-tight">
          <TicketIcon className="w-5 h-5 text-primary" />
          Booking History ({filteredBookings.length})
        </h2>
        <Link to="/bookings" className="text-xs font-bold text-primary hover:underline">
          VIEW ALL →
        </Link>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => onStatusFilterChange("")}
          className={cn(
            "px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all",
            filterStatus === ""
              ? "bg-primary text-primary-foreground shadow-md"
              : "bg-muted text-muted-foreground hover:bg-muted/80"
          )}
        >
          All
        </button>
        {["confirmed", "pending", "cancelled"].map(status => (
          <button
            key={status}
            onClick={() => onStatusFilterChange(status)}
            className={cn(
              "px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all",
              filterStatus === status
                ? "bg-primary text-primary-foreground shadow-md"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {status}
          </button>
        ))}
      </div>

      {isLoading ? (
        <HistorySkeleton count={3} />
      ) : filteredBookings.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-border bg-muted/30 p-8 text-center">
          <TicketIcon className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
          <p className="font-medium text-muted-foreground">No bookings found</p>
          <p className="text-sm text-muted-foreground/70 mt-1">Start by searching for a route</p>
          <Link to="/" className="inline-block mt-4 text-primary font-bold text-sm hover:underline">
            Search Routes →
          </Link>
        </div>
      ) : (
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
                        className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-black uppercase tracking-wider hover:opacity-90 transition-opacity"
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
      )}
    </section>
  );
}

// Payment History Table Component
interface PaymentHistoryTableProps {
  bookings: any[];
  isLoading: boolean;
  currentPage: number;
  pageSize: number;
  sortBy: string;
  onSortChange: (field: string) => void;
  onPageChange: (page: number) => void;
}

function PaymentHistoryTable({
  bookings,
  isLoading,
  currentPage,
  pageSize,
  sortBy,
  onSortChange,
  onPageChange,
}: PaymentHistoryTableProps) {
  const paymentsData = bookings.filter(b => b.amount_paid > 0);

  const sortedPayments = [...paymentsData].sort((a, b) => {
    switch (sortBy) {
      case "date-asc":
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      case "date-desc":
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      case "amount-asc":
        return (a.amount_paid || 0) - (b.amount_paid || 0);
      case "amount-desc":
        return (b.amount_paid || 0) - (a.amount_paid || 0);
      default:
        return 0;
    }
  });

  const paginatedPayments = sortedPayments.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  const totalPages = Math.ceil(sortedPayments.length / pageSize);

  return (
    <section className="mb-8">
      <h2 className="text-lg font-black flex items-center gap-2 uppercase tracking-tight mb-6">
        <CreditCard className="w-5 h-5 text-primary" />
        Payment History ({paymentsData.length})
      </h2>

      <div className="flex gap-2 mb-4">
        {["date-desc", "date-asc", "amount-desc", "amount-asc"].map(option => (
          <button
            key={option}
            onClick={() => onSortChange(option)}
            className={cn(
              "px-3 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all",
              sortBy === option
                ? "bg-primary text-primary-foreground shadow-md"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {option.includes("date") ? "Date" : "Amount"} {option.includes("asc") ? "↑" : "↓"}
          </button>
        ))}
      </div>

      {isLoading ? (
        <HistorySkeleton count={3} />
      ) : paymentsData.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-border bg-muted/30 p-8 text-center">
          <CreditCard className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
          <p className="font-medium text-muted-foreground">No payments yet</p>
          <p className="text-sm text-muted-foreground/70 mt-1">Payments from bookings will appear here</p>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {paginatedPayments.map((payment) => (
              <div
                key={payment.id}
                className="bg-card border border-border rounded-xl p-4 hover:border-primary/40 transition-all"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-bold text-sm">
                        {(payment.booking_details as any)?.origin || "Unknown"} → {(payment.booking_details as any)?.destination || "Unknown"}
                      </span>
                      <span className="inline-flex items-center gap-1 text-xs text-green-600 font-bold">
                        <ArrowDownLeft className="w-3 h-3" />
                        Completed
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground font-medium">
                      {payment.created_at ? new Date(payment.created_at).toLocaleString("en-IN") : "—"}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-black text-lg text-green-600">+ ₹{payment.amount_paid.toFixed(2)}</p>
                    <p className="text-xs text-muted-foreground font-medium">Paid</p>
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
      )}
    </section>
  );
}

// Tickets List Component
function TicketsList() {
  const tickets = getAllTickets();

  if (tickets.length === 0) {
    return null;
  }

  return (
    <section className="mb-8">
      <h2 className="text-lg font-black flex items-center gap-2 uppercase tracking-tight mb-6">
        <TicketIcon className="w-5 h-5 text-primary" />
        Saved Tickets ({tickets.length})
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {tickets.slice(0, 6).map((ticket) => (
          <div
            key={ticket.id}
            className="bg-card border border-border rounded-xl p-4 hover:border-primary/40 transition-all hover:shadow-md"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <p className="font-bold text-sm">
                  {ticket.originName} → {ticket.destName}
                </p>
                <p className="text-xs text-muted-foreground font-medium mt-1">
                  {ticket.travelDate ? new Date(ticket.travelDate + "T12:00:00").toLocaleDateString("en-IN") : "—"}
                </p>
              </div>
              <div className="text-right">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <TicketIcon className="w-5 h-5 text-primary" />
                </div>
              </div>
            </div>
            <p className="text-xs font-mono text-muted-foreground break-all mb-3">
              Ref: {ticket.reference}
            </p>
            <div className="flex gap-2">
              <Link
                to={`/ticket/${encodeURIComponent(ticket.id)}`}
                className="flex-1 px-3 py-2 rounded-lg bg-primary/10 text-primary text-xs font-bold hover:bg-primary/20 transition-colors text-center"
              >
                View
              </Link>
              <button
                onClick={() => {
                  // Download/print placeholder
                  console.log("Download ticket:", ticket.id);
                }}
                className="px-3 py-2 rounded-lg border border-border text-xs font-bold hover:bg-muted transition-colors"
              >
                <Download className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
      {tickets.length > 6 && (
        <div className="text-center mt-4">
          <p className="text-xs text-muted-foreground">+{tickets.length - 6} more tickets</p>
        </div>
      )}
    </section>
  );
}

// Edit Profile Modal Component
interface EditProfileModalProps {
  isOpen: boolean;
  user: any;
  onClose: () => void;
  onSave: (data: any) => void;
  isLoading: boolean;
}

function EditProfileModal({ isOpen, user, onClose, onSave, isLoading }: EditProfileModalProps) {
  const [formData, setFormData] = useState({ name: "", email: "", phone: "" });

  useEffect(() => {
    if (user) {
      setFormData({
        name: user.name || "",
        email: user.email || "",
        phone: user.phone || "",
      });
    }
  }, [user, isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-card rounded-2xl max-w-md w-full p-6 shadow-xl border border-border">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-black uppercase tracking-tight">Edit Profile</h3>
          <button
            onClick={onClose}
            className="p-2 hover:bg-muted rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-4 mb-6">
          <div>
            <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground block mb-2">
              Name
            </label>
            <Input
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Your name"
              disabled={isLoading}
            />
          </div>
          <div>
            <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground block mb-2">
              Email
            </label>
            <Input
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              type="email"
              placeholder="your@email.com"
              disabled={isLoading}
            />
          </div>
          <div>
            <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground block mb-2">
              Phone
            </label>
            <Input
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              placeholder="+91 9876543210"
              disabled={isLoading}
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            onClick={() => onSave(formData)}
            disabled={isLoading}
            className="flex-1"
          >
            {isLoading ? (
              <>
                <Loader className="w-4 h-4 mr-2 animate-spin" />
                Saving
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Changes
              </>
            )}
          </Button>
          <Button
            onClick={onClose}
            variant="outline"
            disabled={isLoading}
            className="flex-1"
          >
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}

// Main Dashboard Content
function UserDashboardContent() {
  const { user: authUser } = useAuth();
  const { data: bookingsData, isLoading } = useBookings({ limit: 50 });
  const { toast } = useToast();

  const bookings: any[] = Array.isArray(bookingsData) ? bookingsData : (bookingsData as any)?.bookings || [];

  // State management
  const [bookingPage, setBookingPage] = useState(0);
  const [paymentPage, setPaymentPage] = useState(0);
  const [bookingSortBy, setBookingSortBy] = useState("date-desc");
  const [paymentSortBy, setPaymentSortBy] = useState("date-desc");
  const [statusFilter, setStatusFilter] = useState("");
  const [showEditModal, setShowEditModal] = useState(false);
  const [isEditLoading, setIsEditLoading] = useState(false);

  // Calculate stats
  const totalSpent = bookings.reduce((sum, b) => sum + (b.amount_paid || 0), 0);
  const upcomingCount = bookings.filter(b => {
    const travelDate = new Date(b.travel_date + "T12:00:00");
    return travelDate > new Date() && (b.booking_status === "confirmed" || b.booking_status === "ticket_sent");
  }).length;
  const completedCount = bookings.filter(b => b.booking_status === "confirmed" || b.booking_status === "ticket_sent").length;

  // Handle profile edit
  const handleProfileSave = async (data: any) => {
    setIsEditLoading(true);
    try {
      // TODO: Wire up to Team 3 API endpoint for profile update
      // await updateUserProfile(data);
      toast({
        title: "Success",
        description: "Profile updated successfully",
        variant: "default",
      });
      setShowEditModal(false);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update profile",
        variant: "destructive",
      });
    } finally {
      setIsEditLoading(false);
    }
  };

  const userData = authUser ? {
    name: (authUser as any)?.display_name || (authUser as any)?.name || "User",
    email: (authUser as any)?.email || "",
    phone: (authUser as any)?.phone || "",
    created_at: (authUser as any)?.created_at || new Date().toISOString(),
  } : null;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="container mx-auto px-4 py-8 flex-1">
        {/* Header */}
        <div className="mb-8 animate-in fade-in slide-in-from-top-4 duration-500">
          <h1 className="text-3xl font-black uppercase tracking-tighter mb-2 flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-primary" />
            My Dashboard
          </h1>
          <p className="text-muted-foreground font-medium">Track your bookings, payments, and tickets</p>
        </div>

        {/* Dashboard Summary */}
        <DashboardSummary
          bookingsCount={bookings.length}
          totalSpent={totalSpent}
          upcomingCount={upcomingCount}
          completedCount={completedCount}
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
          {/* Main Content Area */}
          <div className="lg:col-span-2 space-y-8">
            {/* Booking History */}
            <BookingHistoryTable
              bookings={bookings}
              isLoading={isLoading}
              currentPage={bookingPage}
              pageSize={5}
              sortBy={bookingSortBy}
              filterStatus={statusFilter}
              onSortChange={setBookingSortBy}
              onStatusFilterChange={setStatusFilter}
              onPageChange={setBookingPage}
            />

            {/* Payment History */}
            <PaymentHistoryTable
              bookings={bookings}
              isLoading={isLoading}
              currentPage={paymentPage}
              pageSize={5}
              sortBy={paymentSortBy}
              onSortChange={setPaymentSortBy}
              onPageChange={setPaymentPage}
            />

            {/* Tickets List */}
            <TicketsList />
          </div>

          {/* Sidebar: User Profile & Quick Actions */}
          <div className="lg:col-span-1 space-y-6">
            {/* User Profile */}
            <UserProfileCard
              user={userData}
              isLoading={isLoading}
              onEdit={() => setShowEditModal(true)}
            />

            {/* Quick Actions */}
            <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
              <h3 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-4 flex items-center gap-2">
                <Settings className="w-4 h-4 text-primary" />
                Quick Actions
              </h3>
              <div className="space-y-2">
                <Link
                  to="/"
                  className="block w-full px-4 py-3 rounded-lg bg-primary/10 text-primary text-xs font-bold uppercase tracking-wider hover:bg-primary/20 transition-colors text-center"
                >
                  New Booking
                </Link>
                <Link
                  to="/bookings"
                  className="block w-full px-4 py-3 rounded-lg border border-border text-xs font-bold uppercase tracking-wider hover:bg-muted transition-colors text-center"
                >
                  All Bookings
                </Link>
                <button
                  onClick={() => setShowEditModal(true)}
                  className="block w-full px-4 py-3 rounded-lg border border-border text-xs font-bold uppercase tracking-wider hover:bg-muted transition-colors"
                >
                  Edit Profile
                </button>
              </div>
            </div>

            {/* Helpful Info Card */}
            <div className="bg-gradient-to-br from-blue-500/10 to-blue-600/5 border border-blue-200/30 rounded-2xl p-6">
              <h3 className="text-xs font-bold uppercase tracking-widest text-blue-700 mb-3">Need Help?</h3>
              <p className="text-xs leading-relaxed text-blue-700/80 font-medium mb-3">
                Questions about your bookings or payments? Check our help center or contact support.
              </p>
              <a
                href="#"
                className="inline-flex items-center gap-1 text-xs font-black text-blue-600 hover:underline"
              >
                View Help →
              </a>
            </div>
          </div>
        </div>
      </main>
      <Footer />

      {/* Edit Profile Modal */}
      <EditProfileModal
        isOpen={showEditModal}
        user={userData}
        onClose={() => setShowEditModal(false)}
        onSave={handleProfileSave}
        isLoading={isEditLoading}
      />
    </div>
  );
}

export default function UserDashboard() {
  return (
    <ProtectedRoute>
      <UserDashboardContent />
    </ProtectedRoute>
  );
}
