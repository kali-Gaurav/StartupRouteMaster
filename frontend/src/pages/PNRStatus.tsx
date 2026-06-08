/**
 * PNR Status Page — /pnr
 * Lets users check their Indian Railways booking status.
 * Calls GET /api/v1/pnr/{pnr_number}
 */
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import {
  Search, Train, MapPin, User, Clock, CheckCircle2, AlertCircle,
  XCircle, Ticket, RefreshCcw, Share2, ExternalLink, ChevronRight,
  Loader2, Hash
} from "lucide-react";
import { getRailwayApiUrl } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface Passenger {
  number: string | number;
  booking_status: string;
  current_status: string;
  coach: string;
  berth: string;
  berth_type: string;
}

interface PNRResult {
  pnr: string;
  status: string;
  train_number: string;
  train_name: string;
  from_station: string;
  to_station: string;
  travel_date: string;
  class: string;
  quota: string;
  chart_status: string;
  passengers: Passenger[];
  cached?: boolean;
}

function StatusBadge({ status }: { status: string }) {
  const s = (status || "").toUpperCase();
  if (s.startsWith("CNF") || s === "CONFIRMED") {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-sm font-black border border-emerald-500/30">
        <CheckCircle2 className="w-4 h-4" /> Confirmed
      </span>
    );
  }
  if (s.startsWith("RAC")) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-sm font-black border border-amber-500/30">
        <AlertCircle className="w-4 h-4" /> RAC — {status}
      </span>
    );
  }
  if (s.startsWith("WL") || s.startsWith("GNWL") || s.startsWith("PQWL") || s.startsWith("RLWL")) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-red-500/15 text-red-600 dark:text-red-400 text-sm font-black border border-red-500/30">
        <XCircle className="w-4 h-4" /> Waitlist — {status}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-secondary text-muted-foreground text-sm font-black border border-border">
      {status || "Unknown"}
    </span>
  );
}

function PassengerRow({ p, index }: { p: Passenger; index: number }) {
  const isConfirmed = (p.current_status || "").toUpperCase().startsWith("CNF");
  return (
    <div className={cn(
      "flex items-center justify-between p-4 rounded-xl border transition-all",
      isConfirmed ? "border-emerald-500/20 bg-emerald-500/5" : "border-border bg-card"
    )}>
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <User className="w-4 h-4 text-primary" />
        </div>
        <div>
          <p className="text-sm font-black">Passenger {p.number || index + 1}</p>
          <p className="text-xs text-muted-foreground font-medium">
            Booked: <span className="text-foreground">{p.booking_status || "—"}</span>
          </p>
        </div>
      </div>
      <div className="text-right">
        <StatusBadge status={p.current_status || p.booking_status || "Unknown"} />
        {p.coach && (
          <p className="text-xs text-muted-foreground mt-1 font-bold">
            Coach <span className="text-foreground font-black">{p.coach}</span>
            {p.berth && <> · Berth <span className="text-foreground font-black">{p.berth}</span></>}
            {p.berth_type && <span className="ml-1 text-primary">({p.berth_type})</span>}
          </p>
        )}
      </div>
    </div>
  );
}

// Inject HowTo schema for PNR page — helps Google understand the page
const PNR_SCHEMA = {
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "How to Check PNR Status",
  "description": "Check your Indian Railways PNR booking status including berth allocation, coach, and chart status.",
  "step": [
    { "@type": "HowToStep", "name": "Find your PNR", "text": "Find the 10-digit PNR number on your IRCTC booking confirmation email or SMS." },
    { "@type": "HowToStep", "name": "Enter PNR", "text": "Type or paste your 10-digit PNR number in the field above." },
    { "@type": "HowToStep", "name": "Check status", "text": "Click 'Check' to see your booking status, coach, berth allocation, and chart preparation status." }
  ]
};

export default function PNRStatusPage() {
  // Inject schema on mount
  useEffect(() => {
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.setAttribute('data-rm-schema', 'pnr-howto');
    script.textContent = JSON.stringify(PNR_SCHEMA);
    document.head.appendChild(script);
    document.title = 'PNR Status Check — Indian Railways | Route Master';
    return () => { document.querySelectorAll('script[data-rm-schema]').forEach(el => el.remove()); };
  }, []);
  const { pnr: urlPnr } = useParams<{ pnr: string }>();
  const navigate = useNavigate();

  const [pnrInput, setPnrInput] = useState(urlPnr || "");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PNRResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCheck = async (pnrToCheck?: string) => {
    const pnr = (pnrToCheck || pnrInput).trim().replace(/\s/g, "");
    if (pnr.length !== 10 || !/^\d+$/.test(pnr)) {
      setError("PNR must be exactly 10 digits.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(getRailwayApiUrl(`/api/v1/pnr/${pnr}`), {
        signal: AbortSignal.timeout(15000),
      });

      if (res.status === 503) {
        setError("PNR check requires RAPIDAPI_KEY configuration. Please try again later or check directly on IRCTC.");
        return;
      }
      if (res.status === 404) {
        setError("PNR not found. Please check the number and try again.");
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || `Failed to check PNR (${res.status}). Try again.`);
        return;
      }

      const data: PNRResult = await res.json();
      setResult(data);
      navigate(`/pnr/${pnr}`, { replace: true });
    } catch (e: any) {
      if (e.name === "TimeoutError") {
        setError("Request timed out. The server took too long to respond.");
      } else {
        setError("Could not connect to PNR service. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  // Auto-check if PNR in URL
  useState(() => {
    if (urlPnr && urlPnr.length === 10) {
      handleCheck(urlPnr);
    }
  });

  const handleShare = () => {
    if (!result) return;
    const url = `${window.location.origin}/pnr/${result.pnr}`;
    navigator.clipboard.writeText(url).then(() => toast.success("Link copied!"));
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 pt-24 pb-12 max-w-2xl">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 mb-4">
            <Ticket className="w-8 h-8 text-primary" />
          </div>
          <h1 className="text-3xl font-black tracking-tighter text-foreground">PNR Status</h1>
          <p className="text-muted-foreground mt-2">Check your Indian Railways booking status instantly</p>
        </div>

        {/* Search Box */}
        <div className="bg-card border-2 border-border rounded-2xl p-6 mb-6 shadow-sm">
          <label className="block text-xs font-black uppercase tracking-widest text-muted-foreground mb-3">
            Enter 10-digit PNR Number
          </label>
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Hash className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                value={pnrInput}
                onChange={(e) => {
                  const v = e.target.value.replace(/\D/g, "").slice(0, 10);
                  setPnrInput(v);
                  if (error) setError(null);
                }}
                onKeyDown={(e) => e.key === "Enter" && handleCheck()}
                placeholder="e.g. 4215678901"
                className={cn(
                  "w-full pl-12 pr-4 py-4 rounded-xl border-2 bg-background",
                  "font-mono text-lg tracking-[0.2em] font-bold",
                  "focus:outline-none focus:ring-2 focus:ring-primary/30",
                  error ? "border-destructive" : "border-border focus:border-primary",
                  "transition-all"
                )}
                maxLength={10}
              />
              {pnrInput.length > 0 && (
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-muted-foreground font-bold">
                  {pnrInput.length}/10
                </span>
              )}
            </div>
            <button
              onClick={() => handleCheck()}
              disabled={loading || pnrInput.length !== 10}
              className={cn(
                "px-6 py-4 rounded-xl font-black text-sm uppercase tracking-widest",
                "bg-primary text-primary-foreground",
                "hover:opacity-90 active:scale-[0.98] transition-all",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "flex items-center gap-2 shadow-lg shadow-primary/20"
              )}
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
              {loading ? "Checking..." : "Check"}
            </button>
          </div>

          {error && (
            <div className="mt-4 p-4 rounded-xl bg-destructive/10 border border-destructive/20 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-destructive shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-bold text-destructive">{error}</p>
                <a
                  href={`https://www.irctc.co.in/nget/pnr-status`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline mt-1 inline-flex items-center gap-1"
                >
                  Check on IRCTC directly <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          )}
        </div>

        {/* Result */}
        {result && (
          <div className="space-y-4 animate-in slide-in-from-bottom-4 duration-500">
            {/* Journey Summary Card */}
            <div className="bg-card border-2 border-border rounded-2xl overflow-hidden shadow-sm">
              {/* Status header */}
              <div className={cn(
                "p-4 flex items-center justify-between",
                result.status?.toUpperCase().startsWith("CNF")
                  ? "bg-emerald-500/10 border-b border-emerald-500/20"
                  : result.status?.toUpperCase().startsWith("WL") || result.status?.toUpperCase().startsWith("GNWL")
                    ? "bg-red-500/10 border-b border-red-500/20"
                    : "bg-secondary border-b border-border"
              )}>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-black uppercase tracking-widest text-muted-foreground">PNR</span>
                  <span className="font-mono font-black text-xl tracking-[0.15em]">{result.pnr}</span>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={result.status} />
                  <button
                    onClick={handleShare}
                    className="p-2 rounded-lg hover:bg-background/50 transition-colors"
                    title="Share PNR status link"
                  >
                    <Share2 className="w-4 h-4 text-muted-foreground" />
                  </button>
                  <button
                    onClick={() => handleCheck()}
                    className="p-2 rounded-lg hover:bg-background/50 transition-colors"
                    title="Refresh"
                  >
                    <RefreshCcw className="w-4 h-4 text-muted-foreground" />
                  </button>
                </div>
              </div>

              {/* Journey details */}
              <div className="p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Train className="w-5 h-5 text-primary" />
                    <div>
                      <p className="font-black text-lg">
                        {result.train_number} — {result.train_name || "Express"}
                      </p>
                      <p className="text-xs text-muted-foreground font-bold uppercase">
                        {result.class} · {result.quota} Quota
                      </p>
                    </div>
                  </div>
                  <a
                    href={`/track/${result.train_number}`}
                    className="text-xs text-primary font-black hover:underline flex items-center gap-1"
                  >
                    Live Status <ChevronRight className="w-3 h-3" />
                  </a>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-secondary/50 rounded-xl p-3 text-center">
                    <MapPin className="w-4 h-4 text-primary mx-auto mb-1" />
                    <p className="text-[10px] text-muted-foreground font-black uppercase tracking-wider">From</p>
                    <p className="font-black text-sm">{result.from_station || "—"}</p>
                  </div>
                  <div className="bg-secondary/50 rounded-xl p-3 text-center">
                    <Clock className="w-4 h-4 text-amber-500 mx-auto mb-1" />
                    <p className="text-[10px] text-muted-foreground font-black uppercase tracking-wider">Date</p>
                    <p className="font-black text-sm">{result.travel_date || "—"}</p>
                  </div>
                  <div className="bg-secondary/50 rounded-xl p-3 text-center">
                    <MapPin className="w-4 h-4 text-accent mx-auto mb-1" />
                    <p className="text-[10px] text-muted-foreground font-black uppercase tracking-wider">To</p>
                    <p className="font-black text-sm">{result.to_station || "—"}</p>
                  </div>
                </div>

                <div className="flex items-center justify-between px-1">
                  <span className="text-xs text-muted-foreground font-bold">
                    Chart: <span className={cn(
                      "font-black",
                      result.chart_status?.toLowerCase().includes("prepared") ? "text-emerald-500" : "text-amber-500"
                    )}>
                      {result.chart_status || "Not Prepared"}
                    </span>
                  </span>
                  {result.cached && (
                    <span className="text-[10px] text-muted-foreground font-bold bg-secondary px-2 py-0.5 rounded">
                      Cached
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Passengers */}
            {result.passengers && result.passengers.length > 0 && (
              <div className="bg-card border-2 border-border rounded-2xl p-5 shadow-sm">
                <h3 className="text-sm font-black uppercase tracking-widest text-muted-foreground mb-4 flex items-center gap-2">
                  <User className="w-4 h-4" /> Passengers ({result.passengers.length})
                </h3>
                <div className="space-y-3">
                  {result.passengers.map((p, i) => (
                    <PassengerRow key={i} p={p} index={i} />
                  ))}
                </div>
              </div>
            )}

            {/* IRCTC Link */}
            <a
              href="https://www.irctc.co.in/nget/pnr-status"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between p-4 rounded-xl border-2 border-dashed border-border hover:border-primary/40 hover:bg-primary/5 transition-all group"
            >
              <span className="text-sm font-bold text-muted-foreground group-hover:text-foreground">
                Check on official IRCTC website
              </span>
              <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </a>
          </div>
        )}

        {/* Empty state / How to find PNR */}
        {!result && !loading && !error && (
          <div className="bg-secondary/30 rounded-2xl p-6 border border-dashed border-border">
            <h3 className="font-black text-sm uppercase tracking-widest text-muted-foreground mb-4">
              How to find your PNR
            </h3>
            <div className="space-y-3">
              {[
                "Check your IRCTC booking confirmation email",
                "Look at the top of your printed train ticket",
                "Find it in the IRCTC app under 'My Bookings'",
                "Check the SMS you received after booking",
              ].map((tip, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                    <span className="text-xs font-black text-primary">{i + 1}</span>
                  </div>
                  <p className="text-sm text-muted-foreground font-medium">{tip}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}
