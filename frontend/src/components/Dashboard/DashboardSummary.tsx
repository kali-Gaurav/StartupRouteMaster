/**
 * Dashboard Summary Component
 * Displays key statistics cards
 */

import { Ticket, CreditCard, TrendingUp, CheckCircle } from "lucide-react";

interface DashboardSummaryProps {
  bookingsCount: number;
  totalSpent: number;
  upcomingCount: number;
  completedCount: number;
}

export function DashboardSummary({
  bookingsCount,
  totalSpent,
  upcomingCount,
  completedCount,
}: DashboardSummaryProps) {
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
            <Ticket className="w-6 h-6 text-blue-600" />
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

export default DashboardSummary;
