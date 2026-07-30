/**
 * Payment History Table Component
 * Sortable table for payment history
 */

import { ChevronLeft, ChevronRight, CreditCard, ArrowDownLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { HistorySkeleton } from "@/components/skeletons";

interface PaymentHistoryTableProps {
  bookings: any[];
  isLoading: boolean;
  currentPage: number;
  pageSize: number;
  sortBy?: string;
  onSortChange?: (field: string) => void;
  onPageChange: (page: number) => void;
}

export function PaymentHistoryTable({
  bookings,
  isLoading,
  currentPage,
  pageSize,
  sortBy = "date-desc",
  onSortChange = () => {},
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

  if (isLoading) {
    return <HistorySkeleton count={3} />;
  }

  if (paymentsData.length === 0) {
    return (
      <div className="rounded-2xl border-2 border-dashed border-border bg-muted/30 p-8 text-center">
        <CreditCard className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
        <p className="font-medium text-muted-foreground">No payments yet</p>
        <p className="text-sm text-muted-foreground/70 mt-1">Payments from bookings will appear here</p>
      </div>
    );
  }

  return (
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
  );
}

export default PaymentHistoryTable;
