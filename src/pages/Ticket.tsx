/**
 * Dedicated ticket view: /ticket/:bookingId
 * Persistent, printable, shareable. Core trust infrastructure.
 */

import { useParams, Link } from "react-router-dom";
import { Printer, Share2, Download, ExternalLink, Ticket, ArrowLeft } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { getTicket, getTicketShareUrl, type StoredTicket, type TicketStatus } from "@/lib/ticketStore";
import { useState, useEffect } from "react";
import { logEvent } from "@/lib/observability";
import { formatCost } from "@/data/routes";
import { Button } from "@/components/ui/button";

function formatDisplayDate(isoDate: string): string {
  if (!isoDate) return "—";
  try {
    return new Date(isoDate + "T12:00:00").toLocaleDateString("en-IN", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return isoDate;
  }
}

function statusLabel(s: TicketStatus): string {
  switch (s) {
    case "confirmed":
      return "Confirmed";
    case "pending_irctc":
      return "Complete on IRCTC";
    case "completed":
      return "Completed";
    case "cancelled":
      return "Cancelled";
    default:
      return "Confirmed";
  }
}

function statusClass(s: TicketStatus): string {
  switch (s) {
    case "confirmed":
    case "pending_irctc":
      return "bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-500/30";
    case "completed":
      return "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-500/30";
    case "cancelled":
      return "bg-red-500/20 text-red-700 dark:text-red-300 border-red-500/30";
    default:
      return "bg-muted text-muted-foreground border-border";
  }
}

export default function TicketPage() {
  const { bookingId } = useParams<{ bookingId: string }>();
  const [ticket, setTicket] = useState<StoredTicket | null>(() =>
    bookingId ? getTicket(bookingId) : null
  );
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (ticket && bookingId) logEvent("ticket_viewed", { ticketId: bookingId });
  }, [ticket, bookingId]);

  const handlePrint = () => {
    window.print();
  };

  const handleShare = async () => {
    const url = bookingId ? getTicketShareUrl(bookingId) : "";
    try {
      if (navigator.share && ticket) {
        await navigator.share({
          title: `Ticket ${ticket.reference}`,
          text: `${ticket.originName} → ${ticket.destName} · ${ticket.travelDate}`,
          url,
        });
      } else {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch (e) {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!bookingId) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <main className="container mx-auto px-4 py-12 text-center">
          <p className="text-muted-foreground">Invalid ticket link.</p>
          <Link to="/bookings" className="text-primary hover:underline mt-2 inline-block">
            View My Bookings
          </Link>
        </main>
        <Footer />
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <main className="container mx-auto px-4 py-12">
          <div className="max-w-md mx-auto text-center">
            <Ticket className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-50" />
            <h1 className="text-xl font-bold text-foreground mb-2">Ticket not found</h1>
            <p className="text-muted-foreground mb-4">
              This ticket may have been opened on another device or the link is outdated.
            </p>
            <Link to="/bookings">
              <Button variant="outline">View My Bookings</Button>
            </Link>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  const shareUrl = getTicketShareUrl(ticket.id);

  return (
    <div className="min-h-screen bg-background">
      <div className="print:hidden">
        <Navbar />
      </div>

      {/* Screen-only actions */}
      <div className="print:hidden border-b border-border bg-card">
        <div className="container mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-2">
          <Link
            to="/bookings"
            className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="w-4 h-4" />
            My Bookings
          </Link>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={handlePrint}>
              <Printer className="w-4 h-4 mr-1.5" />
              Print
            </Button>
            <Button variant="outline" size="sm" onClick={handlePrint}>
              <Download className="w-4 h-4 mr-1.5" />
              Save as PDF
            </Button>
            <Button variant="outline" size="sm" onClick={handleShare}>
              <Share2 className="w-4 h-4 mr-1.5" />
              {copied ? "Copied!" : "Share link"}
            </Button>
          </div>
        </div>
      </div>

      <main className="container mx-auto px-4 py-8 print:py-4">
        <article
          className="max-w-2xl mx-auto bg-card border-2 border-border rounded-2xl overflow-hidden shadow-card print:shadow-none print:border-black"
          aria-label="Ticket"
        >
          {/* Header */}
          <div className="bg-primary/10 border-b border-border px-6 py-4 print:bg-gray-100">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <Ticket className="w-8 h-8 text-primary" />
                <h1 className="text-xl font-bold text-foreground">Travel Ticket</h1>
              </div>
              <span
                className={`inline-flex px-3 py-1 rounded-full text-sm font-semibold border ${statusClass(ticket.status)}`}
              >
                {statusLabel(ticket.status)}
              </span>
            </div>
          </div>

          {/* Reference / QR-style block */}
          <div className="px-6 py-4 border-b border-border bg-muted/30">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
              Booking reference
            </p>
            <p className="font-mono text-lg font-bold text-foreground tracking-wide break-all">
              {ticket.reference}
            </p>
            <p className="text-xs text-muted-foreground mt-2 break-all">{shareUrl}</p>
          </div>

          {/* Route */}
          <div className="px-6 py-5 space-y-4">
            <div>
              <p className="text-sm text-muted-foreground mb-1">Route</p>
              <p className="text-xl font-semibold text-foreground">
                {ticket.originName} → {ticket.destName}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-1">Travel date</p>
              <p className="font-medium text-foreground">{formatDisplayDate(ticket.travelDate)}</p>
            </div>
            {ticket.routeSummary && (
              <div>
                <p className="text-sm text-muted-foreground mb-1">Journey</p>
                <p className="text-sm text-foreground whitespace-pre-wrap">{ticket.routeSummary}</p>
              </div>
            )}
            {ticket.trainNumber && (
              <p className="text-sm text-muted-foreground">Train: {ticket.trainNumber}</p>
            )}
            <div className="pt-2">
              <p className="text-sm text-muted-foreground mb-1">Estimated fare</p>
              <p className="text-lg font-bold text-foreground">
                {ticket.totalCost > 0 ? formatCost(ticket.totalCost) : "—"}
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="print:hidden px-6 pb-6">
            {ticket.irctcUrl && (
              <Button
                className="w-full sm:w-auto"
                onClick={() => window.open(ticket.irctcUrl!, "_blank")}
              >
                <ExternalLink className="w-4 h-4 mr-2" />
                Open IRCTC to complete booking
              </Button>
            )}
          </div>
        </article>

        <p className="text-center text-sm text-muted-foreground mt-6 print:mt-4">
          Save this page or use the share link to open your ticket later.
        </p>
      </main>

      <div className="print:hidden">
        <Footer />
      </div>
    </div>
  );
}
