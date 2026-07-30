/**
 * Station Departures Board — /station/:code
 * Like an airport FIDS — shows all trains departing today.
 * High daily user intent: travelers check before leaving home.
 */
import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import {
  Train, MapPin, Clock, Search, RefreshCcw, ArrowRight,
  Loader2, AlertCircle, ChevronRight, Navigation, Calendar,
  Zap, Hash
} from "lucide-react";
import { getRailwayApiUrl, cn } from "@/lib/utils";
import { toast } from "sonner";

interface Departure {
  train_number: string;
  train_name: string;
  departure_time: string;
  destination: string;
  platform: string;
}

interface BoardData {
  station_code: string;
  station_name: string;
  city: string;
  state: string;
  date: string;
  departures: Departure[];
  total: number;
}

// Popular stations for quick access
const POPULAR_STATIONS = [
  { code: "NDLS", name: "New Delhi" },
  { code: "BCT",  name: "Mumbai Central" },
  { code: "HWH",  name: "Howrah" },
  { code: "MAS",  name: "Chennai Central" },
  { code: "SBC",  name: "Bengaluru City" },
  { code: "SC",   name: "Secunderabad" },
  { code: "PUNE", name: "Pune Jn" },
  { code: "JP",   name: "Jaipur Jn" },
  { code: "PNBE", name: "Patna Jn" },
  { code: "LKO",  name: "Lucknow" },
];

function isSoon(time: string): boolean {
  try {
    const now = new Date();
    const [h, m] = time.split(":").map(Number);
    const dep = new Date();
    dep.setHours(h, m, 0);
    const diff = (dep.getTime() - now.getTime()) / 60000; // minutes
    return diff >= 0 && diff <= 30;
  } catch { return false; }
}

function isDeparted(time: string): boolean {
  try {
    const now = new Date();
    const [h, m] = time.split(":").map(Number);
    const dep = new Date();
    dep.setHours(h, m, 0);
    return dep.getTime() < now.getTime();
  } catch { return false; }
}

export default function StationBoardPage() {
  const { code: urlCode } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState(urlCode?.toUpperCase() || "");
  const [board, setBoard] = useState<BoardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().slice(0, 10));

  const fetchBoard = useCallback(async (code: string, date?: string) => {
    const c = code.trim().toUpperCase();
    if (!c) return;
    setLoading(true);
    setError(null);
    try {
      const d = date || selectedDate;
      const res = await fetch(
        getRailwayApiUrl(`/api/v1/stations/${c}/departures?date=${d}&limit=60`),
        { signal: AbortSignal.timeout(10000) }
      );
      if (res.status === 404) { setError(`Station '${c}' not found. Try a valid station code like NDLS, BCT, HWH.`); return; }
      if (!res.ok) { setError("Failed to load departures. Please try again."); return; }
      const data: BoardData = await res.json();
      setBoard(data);
      setLastRefresh(new Date());
      navigate(`/station/${c}`, { replace: true });
    } catch (e: any) {
      setError(e.name === "TimeoutError" ? "Request timed out." : "Could not connect. Check your connection.");
    } finally {
      setLoading(false);
    }
  }, [selectedDate, navigate]);

  useEffect(() => {
    if (urlCode) fetchBoard(urlCode, selectedDate);
  }, [urlCode, selectedDate]);

  // Auto-refresh every 2 minutes
  useEffect(() => {
    if (!board) return;
    const interval = setInterval(() => fetchBoard(board.station_code, selectedDate), 120000);
    return () => clearInterval(interval);
  }, [board, selectedDate, fetchBoard]);

  const now = new Date();
  const upcomingDeps = board?.departures.filter(d => !isDeparted(d.departure_time)) || [];
  const pastDeps = board?.departures.filter(d => isDeparted(d.departure_time)) || [];

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="flex-1 container mx-auto px-4 pt-24 pb-12 max-w-3xl">

        {/* Page header */}
        <div className="mb-6">
          <h1 className="text-3xl font-black tracking-tighter flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Navigation className="w-5 h-5 text-primary" />
            </div>
            Station Board
          </h1>
          <p className="text-muted-foreground mt-1">Live departure board for any Indian Railways station</p>
        </div>

        {/* Search row */}
        <div className="bg-card border-2 border-border rounded-2xl p-5 mb-6 shadow-sm">
          <div className="flex gap-3 mb-4">
            <div className="relative flex-1">
              <Hash className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                value={searchInput}
                onChange={e => setSearchInput(e.target.value.toUpperCase().slice(0, 6))}
                onKeyDown={e => e.key === "Enter" && fetchBoard(searchInput, selectedDate)}
                placeholder="Station code e.g. NDLS"
                className="w-full pl-12 pr-4 py-4 rounded-xl border-2 border-border bg-background font-mono text-lg font-black tracking-widest focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all uppercase"
              />
            </div>
            <input
              type="date"
              value={selectedDate}
              min={new Date().toISOString().slice(0, 10)}
              onChange={e => setSelectedDate(e.target.value)}
              className="px-4 py-4 rounded-xl border-2 border-border bg-background font-bold text-sm focus:outline-none focus:border-primary transition-all hidden sm:block"
            />
            <button
              onClick={() => fetchBoard(searchInput, selectedDate)}
              disabled={loading || !searchInput}
              className="px-6 py-4 rounded-xl bg-primary text-primary-foreground font-black text-sm uppercase tracking-widest hover:opacity-90 disabled:opacity-50 transition-all flex items-center gap-2 shadow-lg shadow-primary/20 shrink-0"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
              {loading ? "Loading..." : "View"}
            </button>
          </div>

          {/* Popular station chips */}
          <div className="flex flex-wrap gap-2">
            <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground self-center mr-1">Popular:</span>
            {POPULAR_STATIONS.map(s => (
              <button
                key={s.code}
                onClick={() => { setSearchInput(s.code); fetchBoard(s.code, selectedDate); }}
                className={cn(
                  "px-3 py-1.5 rounded-full text-xs font-black border-2 transition-all",
                  board?.station_code === s.code
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-secondary text-muted-foreground hover:border-primary/40 hover:text-foreground"
                )}
              >
                {s.code}
              </button>
            ))}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/20 flex items-center gap-3 mb-6">
            <AlertCircle className="w-5 h-5 text-destructive shrink-0" />
            <p className="text-sm font-bold text-destructive">{error}</p>
          </div>
        )}

        {/* Departures board */}
        {board && (
          <div className="animate-in slide-in-from-bottom-4 duration-500">
            {/* Station header */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-2xl font-black tracking-tighter flex items-center gap-2">
                  <MapPin className="w-5 h-5 text-primary" />
                  {board.station_name}
                  <span className="font-mono text-muted-foreground text-lg">({board.station_code})</span>
                </h2>
                <p className="text-sm text-muted-foreground font-bold">{board.city}, {board.state} · {board.total} trains · {board.date}</p>
              </div>
              <div className="text-right">
                <button
                  onClick={() => fetchBoard(board.station_code, selectedDate)}
                  disabled={loading}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border hover:border-primary/40 text-xs font-black text-muted-foreground hover:text-foreground transition-all"
                >
                  <RefreshCcw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
                  Refresh
                </button>
                {lastRefresh && (
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Updated {lastRefresh.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </p>
                )}
              </div>
            </div>

            {/* Live clock */}
            <div className="flex items-center gap-2 mb-4 px-1">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-black text-emerald-600 dark:text-emerald-400 uppercase tracking-widest">
                Live — {now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
              </span>
              <span className="text-xs text-muted-foreground ml-auto font-bold">
                {upcomingDeps.length} upcoming
              </span>
            </div>

            {/* Column headers */}
            <div className="grid grid-cols-[80px_1fr_auto_auto] gap-3 px-4 py-2 bg-secondary/50 rounded-xl border border-border mb-2 text-[10px] font-black uppercase tracking-widest text-muted-foreground">
              <span>Train No.</span>
              <span>Train Name → Destination</span>
              <span className="text-center">Departs</span>
              <span className="text-right hidden sm:block">Action</span>
            </div>

            {/* Upcoming departures */}
            <div className="space-y-1.5">
              {upcomingDeps.length === 0 && (
                <div className="text-center py-8 text-muted-foreground font-bold">
                  No more departures today for this station.
                </div>
              )}
              {upcomingDeps.map((dep, i) => {
                const soon = isSoon(dep.departure_time);
                return (
                  <div
                    key={`${dep.train_number}-${i}`}
                    className={cn(
                      "grid grid-cols-[80px_1fr_auto_auto] gap-3 px-4 py-3 rounded-xl border-2 items-center transition-all hover:shadow-sm",
                      soon
                        ? "border-amber-500/30 bg-amber-500/5 animate-pulse-subtle"
                        : "border-border bg-card hover:border-primary/20"
                    )}
                  >
                    <div>
                      <p className="font-mono font-black text-sm">{dep.train_number}</p>
                      {soon && (
                        <span className="text-[9px] font-black text-amber-500 uppercase tracking-wider flex items-center gap-0.5">
                          <Zap className="w-2.5 h-2.5 fill-amber-500" /> Soon
                        </span>
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="font-bold text-sm truncate">{dep.train_name}</p>
                      {dep.destination && (
                        <p className="text-xs text-muted-foreground flex items-center gap-1 truncate">
                          <ArrowRight className="w-3 h-3 shrink-0" />
                          {dep.destination}
                        </p>
                      )}
                    </div>
                    <div className="text-center">
                      <p className={cn(
                        "font-mono font-black text-base",
                        soon ? "text-amber-500" : "text-foreground"
                      )}>
                        {dep.departure_time}
                      </p>
                      {dep.platform && (
                        <p className="text-[10px] text-muted-foreground font-bold">Pf {dep.platform}</p>
                      )}
                    </div>
                    <div className="hidden sm:flex flex-col gap-1">
                      <Link
                        to={`/track/${dep.train_number}`}
                        className="text-[10px] font-black text-primary hover:underline flex items-center gap-0.5"
                      >
                        <Navigation className="w-3 h-3" /> Live
                      </Link>
                      <Link
                        to={`/trains/${dep.train_number}/schedule`}
                        className="text-[10px] font-black text-muted-foreground hover:text-foreground flex items-center gap-0.5"
                      >
                        <Clock className="w-3 h-3" /> Schedule
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Past departures (collapsed) */}
            {pastDeps.length > 0 && (
              <details className="mt-4 group">
                <summary className="flex items-center gap-2 cursor-pointer text-xs font-black text-muted-foreground hover:text-foreground transition-colors py-2 px-1">
                  <ChevronRight className="w-4 h-4 group-open:rotate-90 transition-transform" />
                  {pastDeps.length} departed trains (tap to show)
                </summary>
                <div className="mt-2 space-y-1.5 opacity-50">
                  {pastDeps.slice(-20).map((dep, i) => (
                    <div key={`past-${dep.train_number}-${i}`} className="grid grid-cols-[80px_1fr_auto] gap-3 px-4 py-2.5 rounded-xl border border-dashed border-border items-center">
                      <span className="font-mono font-bold text-sm text-muted-foreground">{dep.train_number}</span>
                      <div className="min-w-0">
                        <p className="font-bold text-sm text-muted-foreground truncate">{dep.train_name}</p>
                        {dep.destination && <p className="text-xs text-muted-foreground truncate">→ {dep.destination}</p>}
                      </div>
                      <p className="font-mono font-bold text-sm text-muted-foreground line-through">{dep.departure_time}</p>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}

        {/* Empty state */}
        {!board && !loading && !error && (
          <div className="text-center py-16 bg-secondary/30 rounded-2xl border border-dashed border-border">
            <Train className="w-14 h-14 text-muted-foreground/30 mx-auto mb-4" />
            <p className="font-black text-lg text-muted-foreground">Select a station above</p>
            <p className="text-sm text-muted-foreground mt-1">See all trains departing today, in real time</p>
          </div>
        )}

      </main>
      <Footer />
    </div>
  );
}
