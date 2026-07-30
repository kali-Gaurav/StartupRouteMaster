/**
 * Train Schedule Page — /trains/:trainNumber/schedule
 * Shows full timetable for any Indian Railways train.
 * Links from RouteCard train segments.
 */
import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import {
  Train, MapPin, Clock, Search, ArrowLeft, Share2,
  ChevronRight, Loader2, AlertCircle, Navigation, ExternalLink, Calendar
} from "lucide-react";
import { getRailwayApiUrl } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface ScheduleStop {
  station_code: string;
  station_name: string;
  city: string;
  sequence: number;
  arrival: string;
  departure: string;
}

interface TrainSchedule {
  train_number: string;
  train_name: string;
  stops: ScheduleStop[];
  total_stops: number;
}

function TimeCell({ time, label }: { time: string; label: string }) {
  const t = time || "--:--";
  const isSource = label === "Source" || t === "--:--";
  return (
    <div className="text-center min-w-[60px]">
      <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">{label}</p>
      <p className={cn("font-mono font-black text-sm", isSource && "text-muted-foreground italic text-xs")}>
        {isSource ? "—" : t.slice(0, 5)}
      </p>
    </div>
  );
}

export default function TrainSchedulePage() {
  const { trainNumber } = useParams<{ trainNumber: string }>();
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState(trainNumber || "");
  const [schedule, setSchedule] = useState<TrainSchedule | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSchedule = async (tno: string) => {
    const num = tno.trim();
    if (!num) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(getRailwayApiUrl(`/api/v1/stations/schedule/${num}`), {
        signal: AbortSignal.timeout(10000),
      });
      if (!res.ok) {
        setError(`Train ${num} schedule not found. Check the train number and try again.`);
        return;
      }
      const data: TrainSchedule = await res.json();
      if (!data.stops || data.stops.length === 0) {
        setError(`No schedule data available for train ${num}.`);
        return;
      }
      setSchedule(data);
      navigate(`/trains/${num}/schedule`, { replace: true });
    } catch (e: any) {
      setError("Could not load schedule. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (trainNumber) fetchSchedule(trainNumber);
  }, [trainNumber]);

  const handleShare = () => {
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(() => toast.success("Link copied!"));
  };

  const source = schedule?.stops[0];
  const dest = schedule?.stops[schedule.stops.length - 1];

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="flex-1 container mx-auto px-4 pt-24 pb-12 max-w-2xl">

        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-sm font-bold text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          {schedule && (
            <button onClick={handleShare} className="flex items-center gap-2 text-sm font-bold text-muted-foreground hover:text-primary transition-colors">
              <Share2 className="w-4 h-4" /> Share
            </button>
          )}
        </div>

        {/* Search */}
        <div className="bg-card border-2 border-border rounded-2xl p-5 mb-6 shadow-sm">
          <label className="block text-xs font-black uppercase tracking-widest text-muted-foreground mb-3">
            Enter Train Number
          </label>
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Train className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value.replace(/\D/g, "").slice(0, 6))}
                onKeyDown={(e) => e.key === "Enter" && fetchSchedule(searchInput)}
                placeholder="e.g. 12951"
                className="w-full pl-12 pr-4 py-4 rounded-xl border-2 border-border bg-background font-mono text-lg font-black tracking-[0.2em] focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
            <button
              onClick={() => fetchSchedule(searchInput)}
              disabled={loading || !searchInput}
              className="px-6 py-4 rounded-xl bg-primary text-primary-foreground font-black text-sm uppercase tracking-widest hover:opacity-90 disabled:opacity-50 transition-all flex items-center gap-2 shadow-lg shadow-primary/20"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
              {loading ? "Loading..." : "Search"}
            </button>
          </div>
          {error && (
            <div className="mt-4 p-3 rounded-xl bg-destructive/10 border border-destructive/20 flex items-center gap-3">
              <AlertCircle className="w-4 h-4 text-destructive shrink-0" />
              <p className="text-sm font-bold text-destructive">{error}</p>
            </div>
          )}
        </div>

        {/* Schedule result */}
        {schedule && (
          <div className="animate-in slide-in-from-bottom-4 duration-500">
            {/* Train header */}
            <div className="bg-card border-2 border-border rounded-2xl overflow-hidden shadow-sm mb-4">
              <div className="bg-gradient-to-r from-primary/20 to-primary/5 border-b border-border p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                        <Train className="w-5 h-5 text-primary" />
                      </div>
                      <div>
                        <p className="font-mono font-black text-2xl tracking-widest">{schedule.train_number}</p>
                        <p className="text-sm font-bold text-muted-foreground">{schedule.train_name}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-3 text-sm">
                      <span className="flex items-center gap-1.5 font-bold">
                        <MapPin className="w-4 h-4 text-primary" />
                        {source?.station_name || source?.station_code}
                      </span>
                      <ChevronRight className="w-4 h-4 text-muted-foreground self-center" />
                      <span className="flex items-center gap-1.5 font-bold">
                        <MapPin className="w-4 h-4 text-accent" />
                        {dest?.station_name || dest?.station_code}
                      </span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="text-xs font-black uppercase tracking-widest text-muted-foreground">
                      {schedule.total_stops} stops
                    </span>
                    <div className="flex gap-2 mt-2">
                      <Link
                        to={`/track/${schedule.train_number}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-xs font-black border border-primary/20 hover:bg-primary/20 transition-colors"
                      >
                        <Navigation className="w-3 h-3" /> Live Status
                      </Link>
                    </div>
                  </div>
                </div>
              </div>

              {/* Column headers */}
              <div className="grid grid-cols-[auto_1fr_auto_auto] gap-4 px-5 py-3 bg-secondary/50 border-b border-border">
                <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">#</span>
                <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Station</span>
                <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground text-center">Arrives</span>
                <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground text-center">Departs</span>
              </div>

              {/* Stops */}
              <div className="divide-y divide-border">
                {schedule.stops.map((stop, idx) => {
                  const isFirst = idx === 0;
                  const isLast = idx === schedule.stops.length - 1;
                  return (
                    <div
                      key={stop.sequence || idx}
                      className={cn(
                        "grid grid-cols-[auto_1fr_auto_auto] gap-4 px-5 py-4 items-center transition-colors",
                        "hover:bg-secondary/30",
                        isFirst && "bg-primary/5",
                        isLast && "bg-accent/5",
                      )}
                    >
                      {/* Sequence number with dot indicator */}
                      <div className="flex flex-col items-center gap-1 min-w-[20px]">
                        <div className={cn(
                          "w-3 h-3 rounded-full border-2",
                          isFirst ? "bg-primary border-primary" :
                          isLast ? "bg-accent border-accent" :
                          "bg-background border-muted-foreground/40"
                        )} />
                        <span className="text-[10px] font-bold text-muted-foreground">{idx + 1}</span>
                      </div>

                      {/* Station info */}
                      <div>
                        <p className={cn(
                          "font-black text-sm",
                          (isFirst || isLast) && "text-primary"
                        )}>
                          {stop.station_name || stop.station_code}
                        </p>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-muted-foreground font-bold">{stop.station_code}</span>
                          {stop.city && stop.city !== stop.station_name && (
                            <span className="text-xs text-muted-foreground">{stop.city}</span>
                          )}
                          {isFirst && <span className="text-[10px] font-black text-primary uppercase tracking-wider">Source</span>}
                          {isLast && <span className="text-[10px] font-black text-accent uppercase tracking-wider">Destination</span>}
                        </div>
                      </div>

                      {/* Times */}
                      <TimeCell time={isFirst ? "—" : stop.arrival} label="Arr" />
                      <TimeCell time={isLast ? "—" : stop.departure} label="Dep" />
                    </div>
                  );
                })}
              </div>
            </div>

            {/* IRCTC booking link */}
            <a
              href={`https://www.irctc.co.in/nget/train-search?trainNo=${schedule.train_number}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between p-4 rounded-xl border-2 border-dashed border-border hover:border-primary/40 hover:bg-primary/5 transition-all group"
            >
              <div>
                <p className="text-sm font-black group-hover:text-primary transition-colors">Book on IRCTC</p>
                <p className="text-xs text-muted-foreground">Opens IRCTC booking for train {schedule.train_number}</p>
              </div>
              <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </a>
          </div>
        )}

        {/* Empty state */}
        {!schedule && !loading && !error && (
          <div className="text-center py-12 bg-secondary/30 rounded-2xl border border-dashed border-border">
            <Calendar className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
            <p className="text-muted-foreground font-bold">Enter a train number to see its full timetable</p>
            <p className="text-xs text-muted-foreground mt-2">Example: 12951, 12301, 12628</p>
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
