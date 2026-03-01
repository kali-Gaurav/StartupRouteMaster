/**
 * Ops Center - Advanced Operational Control Center
 * Real-time monitoring of SOS events, System Health, and Route Trends.
 */
import { useState, useEffect } from "react";
import { 
  MapPin, ExternalLink, User, AlertCircle, CheckCircle, RefreshCw, 
  Train, Wifi, WifiOff, History, Star, Cloud, ArrowRight, Zap, ShieldAlert 
} from "lucide-react";
import { getAllSOS, resolveSOS, type SOSEvent } from "@/services/sosApi";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import { storageService } from "@/services/storageService";
import { useBookings } from "@/api/hooks/useBookings";

function StatCard({ title, value, icon: Icon, colorClass, subtitle }: { title: string; value: string | number; icon: any; colorClass: string; subtitle?: string }) {
  return (
    <div className="bg-card border border-border rounded-xl p-5 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow">
      <div className={`p-3 rounded-xl ${colorClass} bg-opacity-10`}>
        <Icon className={`w-6 h-6 ${colorClass.replace('bg-', 'text-')}`} />
      </div>
      <div>
        <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{title}</p>
        <p className="text-2xl font-black tabular-nums">{value}</p>
        {subtitle && <p className="text-[10px] text-muted-foreground mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

function SystemHealthIndicator({ label, status }: { label: string; status: "up" | "slow" | "down" }) {
  const colors = { up: "bg-green-500", slow: "bg-yellow-500", down: "bg-red-500" };
  return (
    <div className="flex items-center justify-between py-2.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-[9px] font-black uppercase tracking-tighter opacity-70">{status}</span>
        <div className={`w-2 h-2 rounded-full ${colors[status]} animate-pulse`} />
      </div>
    </div>
  );
}

function EventCard({ e, onResolve }: { e: SOSEvent; onResolve: () => void }) {
  const isRedZone = e.status === "active";
  
  return (
    <div className={cn(
      "p-5 rounded-2xl border-2 transition-all duration-300",
      isRedZone ? "border-red-500 bg-red-500/5 shadow-lg shadow-red-500/10" : "border-border bg-card opacity-60"
    )}>
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-2">
          <div className={cn("w-2.5 h-2.5 rounded-full animate-pulse", isRedZone ? "bg-red-500" : "bg-muted-foreground")} />
          <span className="text-[10px] font-black uppercase tracking-widest text-foreground/80">
            {e.priority || "Standard"} Incident
          </span>
        </div>
        <span className="text-[10px] font-mono text-muted-foreground">
          {new Date(e.triggered_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>
      </div>

      <div className="space-y-4">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-full bg-muted flex items-center justify-center shrink-0">
            <User className="w-5 h-5 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-black">{e.name}</p>
            <p className="text-xs text-muted-foreground font-medium">PNR: {e.trip?.vehicle_number || "Unknown"}</p>
          </div>
        </div>

        <div className="bg-background/50 border border-border rounded-xl p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-muted-foreground font-bold uppercase flex items-center gap-1">
              <MapPin className="w-3 h-3" /> GPS Telemetry
            </span>
            <a 
              href={e.google_maps_url || `https://www.google.com/maps?q=${e.lat},${e.lng}`} 
              target="_blank" 
              rel="noreferrer"
              className="text-[10px] font-black text-blue-500 flex items-center gap-1 hover:underline"
            >
              LOCATE <ExternalLink className="w-2.5 h-2.5" />
            </a>
          </div>
          <p className="text-[10px] font-mono tabular-nums bg-muted/50 p-1.5 rounded">{e.lat}, {e.lng}</p>
        </div>
      </div>

      {isRedZone && (
        <button 
          onClick={onResolve}
          className="w-full mt-5 py-2.5 bg-red-500 text-white rounded-xl text-xs font-black uppercase tracking-wider hover:bg-red-600 active:scale-95 transition-all shadow-md shadow-red-500/20"
        >
          Resolve Incident
        </button>
      )}
    </div>
  );
}

function cn(...inputs: any[]) {
  return inputs.filter(Boolean).join(" ");
}

export default function Dashboard() {
  const isOnline = useBackendHealth();
  const [events, setEvents] = useState<SOSEvent[]>([]);
  const [recentSearches, setRecentSearches] = useState<any[]>([]);
  const [favorites, setFavorites] = useState<any[]>([]);
  const [pendingSyncCount, setPendingSyncCount] = useState(0);
  const [loading, setLoading] = useState(true);

  // Manual Booking Integration
  const { data: bookingsData } = useBookings({ limit: 3 });
  const manualBookings = Array.isArray(bookingsData) ? bookingsData : [];

  // Stats Logic
  const activeCount = events.filter(e => e.status === "active").length;
  const resolvedToday = events.filter(e => e.status === "resolved").length;

  const handleResolve = async (id: string) => {
    try {
      await resolveSOS(id);
      fetchData();
    } catch (err) {
      console.error("Resolve failed", err);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      // 1. Fetch SOS Events
      try {
        const { events: list } = await getAllSOS();
        setEvents(list || []);
        localStorage.setItem("cached_sos_events", JSON.stringify(list));
      } catch {
        const cached = localStorage.getItem("cached_sos_events");
        if (cached) setEvents(JSON.parse(cached));
      }

      // 2. Local Storage Data
      const [history, favs] = await Promise.all([
        storageService.getRecentSearches(5),
        storageService.getFavorites()
      ]);
      setRecentSearches(history || []);
      setFavorites(favs || []);

      // 3. Sync Queue
      const queue = JSON.parse(localStorage.getItem('pending_rail_actions') || '[]');
      setPendingSyncCount(queue.length);
      
    } catch (err) {
      console.error("Dashboard data error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      if (isOnline) fetchData();
    }, 15000);
    return () => clearInterval(interval);
  }, [isOnline]);

  return (
    <div className="min-h-screen bg-[#f8fafc] dark:bg-background text-foreground">
      <header className="sticky top-0 z-10 border-b border-border bg-white/80 dark:bg-background/80 backdrop-blur-md">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl ${isOnline ? 'bg-primary/10' : 'bg-orange-500/10'}`}>
              <Train className={`w-6 h-6 ${isOnline ? 'text-primary' : 'text-orange-500'}`} />
            </div>
            <div>
              <h1 className="text-xl font-black tracking-tight flex items-center gap-2">
                Ops Center
                <span className="px-1.5 py-0.5 rounded bg-[#0f172a] text-[10px] text-white font-bold">V2.0</span>
              </h1>
              <div className="flex items-center gap-2">
                {isOnline ? (
                   <span className="flex items-center gap-1 text-[10px] uppercase font-bold text-green-600">
                     <Wifi className="w-3 h-3" /> Live Uplink
                   </span>
                ) : (
                  <span className="flex items-center gap-1 text-[10px] uppercase font-bold text-orange-500">
                    <WifiOff className="w-3 h-3" /> Offline Node
                  </span>
                )}
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <button 
              onClick={() => fetchData()}
              className="flex items-center gap-2 px-4 py-2 text-xs font-black uppercase tracking-wider border-2 border-border rounded-xl hover:bg-muted transition-all active:scale-95"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Sync Data
            </button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard title="Active SOS" value={activeCount} icon={AlertCircle} colorClass="bg-red-500" subtitle={`${resolvedToday} resolved today`} />
          <StatCard title="Monitored Routes" value={favorites.length} icon={Star} colorClass="bg-yellow-500" subtitle="Pinned itineraries" />
          <StatCard title="Pending Sync" value={pendingSyncCount} icon={Cloud} colorClass="bg-blue-500" subtitle="Edge queue size" />
          <StatCard title="Total Reach" value="12.4k" icon={User} colorClass="bg-emerald-500" subtitle="+18.2% monthly" />
        </div>

        {/* Manual Booking Requests Section (Wizard-of-Oz MVP) */}
        {manualBookings.length > 0 && (
          <section className="mb-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-black flex items-center gap-2 uppercase tracking-tight">
                <History className="w-6 h-6 text-purple-500" />
                Your Booking Status
              </h2>
              <Link to="/bookings" className="text-xs font-bold text-primary hover:underline">VIEW ALL HISTORY →</Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {manualBookings.map((b, i) => (
                <div key={i} className="bg-white dark:bg-card border-2 border-border rounded-2xl p-5 shadow-sm hover:shadow-md transition-all group">
                  <div className="flex justify-between items-start mb-3">
                    <span className="text-[10px] font-black bg-muted px-2 py-1 rounded-lg uppercase text-muted-foreground tracking-tighter">
                      PNR: {b.pnr_number || "TBD"}
                    </span>
                    <span className={cn(
                      "text-[10px] px-2.5 py-1 rounded-full font-black uppercase tracking-widest border",
                      b.booking_status === "ticket_sent" ? "bg-blue-500/10 text-blue-600 border-blue-200" :
                      b.booking_status === "confirmed" ? "bg-green-500/10 text-green-600 border-green-200" :
                      "bg-purple-500/10 text-purple-600 border-purple-200 animate-pulse"
                    )}>
                      {b.booking_status?.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-black group-hover:text-primary transition-colors">
                      {b.booking_details?.origin || "Route"} → {b.booking_details?.destination || "Manual"}
                    </p>
                    <p className="text-[10px] font-bold text-muted-foreground">
                      {new Date(b.travel_date).toLocaleDateString("en-IN", { dateStyle: 'medium' })} • {b.booking_details?.passengers?.length || 1} PAX
                    </p>
                  </div>
                  {b.booking_status === "pending_manual" && (
                    <div className="mt-4 pt-4 border-t border-dashed border-border">
                      <p className="text-[9px] font-medium text-muted-foreground leading-relaxed">
                        Our team is manually processing your ticket. You will receive it via Telegram/Email shortly.
                      </p>
                    </div>
                  )}
                  {b.pnr_number && (
                    <Link to={`/ticket/${b.pnr_number}`} className="mt-4 w-full py-2 bg-primary text-primary-foreground rounded-xl text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2 hover:opacity-90 active:scale-95 transition-all">
                      TRACK JOURNEY <Zap className="w-3 h-3 fill-current" />
                    </Link>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Manual Booking Requests Section (Wizard-of-Oz MVP) */}
        {manualBookings.length > 0 && (
          <section className="mb-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-black flex items-center gap-2 uppercase tracking-tight">
                <History className="w-6 h-6 text-purple-500" />
                Your Booking Status
              </h2>
              <Link to="/bookings" className="text-xs font-bold text-primary hover:underline">VIEW ALL HISTORY →</Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {manualBookings.map((b, i) => (
                <div key={i} className="bg-white dark:bg-card border-2 border-border rounded-2xl p-5 shadow-sm hover:shadow-md transition-all group">
                  <div className="flex justify-between items-start mb-3">
                    <span className="text-[10px] font-black bg-muted px-2 py-1 rounded-lg uppercase text-muted-foreground tracking-tighter">
                      PNR: {b.pnr_number || "TBD"}
                    </span>
                    <span className={cn(
                      "text-[10px] px-2.5 py-1 rounded-full font-black uppercase tracking-widest border",
                      b.booking_status === "ticket_sent" ? "bg-blue-500/10 text-blue-600 border-blue-200" :
                      b.booking_status === "confirmed" ? "bg-green-500/10 text-green-600 border-green-200" :
                      "bg-purple-500/10 text-purple-600 border-purple-200 animate-pulse"
                    )}>
                      {b.booking_status?.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-black group-hover:text-primary transition-colors">
                      {b.booking_details?.origin || "Route"} → {b.booking_details?.destination || "Manual"}
                    </p>
                    <p className="text-[10px] font-bold text-muted-foreground">
                      {new Date(b.travel_date).toLocaleDateString("en-IN", { dateStyle: 'medium' })} • {b.booking_details?.passengers?.length || 1} PAX
                    </p>
                  </div>
                  {b.booking_status === "pending_manual" && (
                    <div className="mt-4 pt-4 border-t border-dashed border-border">
                      <p className="text-[9px] font-medium text-muted-foreground leading-relaxed">
                        Our team is manually processing your ticket. You will receive it via Telegram/Email shortly.
                      </p>
                    </div>
                  )}
                  {b.pnr_number && (
                    <Link to={`/track/${b.pnr_number.slice(0, 5)}`} className="mt-4 w-full py-2 bg-primary text-primary-foreground rounded-xl text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2 hover:opacity-90 active:scale-95 transition-all">
                      TRACK JOURNEY <Zap className="w-3 h-3 fill-current" />
                    </Link>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Main Column: SOS Events + Live Tracker Quick Access */}
          <div className="lg:col-span-8 space-y-8">
            <section className="bg-indigo-600 rounded-3xl p-8 text-white relative overflow-hidden shadow-xl shadow-indigo-200">
              <div className="relative z-10">
                <h3 className="text-2xl font-black uppercase tracking-tighter mb-2">Live Train Tracker</h3>
                <p className="text-indigo-100 text-sm mb-6 max-w-sm">Enter your train number to see real-time position and delay status instantly.</p>
                <form 
                  onSubmit={(e) => {
                    e.preventDefault();
                    const num = (e.target as any).train_num.value;
                    if (num) window.location.href = `/track/${num}`;
                  }}
                  className="flex gap-2 max-w-md"
                >
                  <input 
                    name="train_num"
                    type="text" 
                    placeholder="e.g. 12002" 
                    className="flex-1 bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-sm font-bold placeholder:text-white/40 focus:outline-none focus:bg-white/20 transition-all"
                  />
                  <button type="submit" className="bg-white text-indigo-600 px-6 py-3 rounded-xl font-black text-xs uppercase tracking-widest hover:bg-indigo-50 active:scale-95 transition-all">
                    TRACK
                  </button>
                </form>
              </div>
              <Train className="absolute right-[-20px] bottom-[-20px] w-48 h-48 text-white/10 -rotate-12" />
            </section>
            <div className="flex items-center justify-between border-b-2 border-border pb-4">
              <h2 className="text-lg font-black flex items-center gap-2 uppercase tracking-tight">
                <ShieldAlert className="w-6 h-6 text-red-500" />
                Live Incident Response
              </h2>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
                <span className="text-[10px] font-black uppercase text-red-600">Real-time Stream</span>
              </div>
            </div>
            
            {events.length === 0 ? (
               <div className="border-2 border-dashed border-border rounded-3xl p-20 text-center bg-white dark:bg-card/50">
                  <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                    <CheckCircle className="w-10 h-10 text-green-600" />
                  </div>
                  <h3 className="font-black text-xl uppercase tracking-tight">All Systems Nominal</h3>
                  <p className="text-muted-foreground text-sm max-w-xs mx-auto mt-2">Zero active SOS reports across the network. Operational safety at 100%.</p>
               </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {events.map(e => (
                  <EventCard key={e.id} e={e} onResolve={() => handleResolve(e.id)} />
                ))}
              </div>
            )}
          </div>

          {/* Sidebar: System & Assets */}
          <div className="lg:col-span-4 space-y-8">
            <section className="bg-white dark:bg-card border-2 border-border rounded-3xl p-6 shadow-sm">
              <h3 className="text-xs font-black uppercase tracking-widest text-muted-foreground mb-5 flex items-center justify-between font-mono">
                SYS_INFRASTRUCTURE
                <Zap className="w-4 h-4 text-yellow-500" />
              </h3>
              <div className="divide-y divide-border">
                <SystemHealthIndicator label="Search Engine (RAPTOR)" status={isOnline ? "up" : "down"} />
                <SystemHealthIndicator label="Real-time Cache (Redis)" status={isOnline ? "up" : "down"} />
                <SystemHealthIndicator label="Delay Predictor (ML)" status="up" />
                <SystemHealthIndicator label="Position Estimator" status={isOnline ? "slow" : "down"} />
                <SystemHealthIndicator label="Supabase Auth" status="up" />
              </div>
            </section>

            <section className="space-y-4">
              <h3 className="text-xs font-black uppercase tracking-widest text-muted-foreground flex items-center gap-2 font-mono">
                <Star className="w-4 h-4 text-yellow-500" />
                WATCHLIST_ROUTES
              </h3>
              <div className="bg-white dark:bg-card border-2 border-border rounded-3xl divide-y divide-border overflow-hidden shadow-sm">
                {favorites.length > 0 ? favorites.map((f, i) => (
                  <div key={i} className="p-5 flex items-center justify-between group cursor-pointer hover:bg-muted/50 transition-all active:bg-muted">
                    <div className="flex items-center gap-5">
                      <div className="flex flex-col">
                        <span className="text-sm font-black tracking-tight">{f.source}</span>
                        <span className="text-[9px] font-bold text-muted-foreground uppercase opacity-60">Origin</span>
                      </div>
                      <ArrowRight className="w-4 h-4 text-primary animate-in slide-in-from-left-2" />
                      <div className="flex flex-col">
                        <span className="text-sm font-black tracking-tight">{f.destination}</span>
                        <span className="text-[9px] font-bold text-muted-foreground uppercase opacity-60">Dest</span>
                      </div>
                    </div>
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity translate-x-2 group-hover:translate-x-0">
                      <ExternalLink className="w-4 h-4 text-primary" />
                    </div>
                  </div>
                )) : (
                  <p className="p-8 text-xs text-muted-foreground italic text-center font-medium">No monitor routes in watchlist.</p>
                )}
              </div>
            </section>

            <section className="space-y-4">
              <h3 className="text-xs font-black uppercase tracking-widest text-muted-foreground flex items-center gap-2 font-mono">
                <History className="w-4 h-4 text-blue-500" />
                SEARCH_TELEMETRY
              </h3>
              <div className="space-y-3">
                {recentSearches.map((s, i) => (
                  <div key={i} className="bg-white dark:bg-card border border-border rounded-2xl p-4 text-xs flex justify-between items-center shadow-sm hover:border-primary/30 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-blue-500/20 flex items-center justify-center">
                        <div className="w-1 h-1 rounded-full bg-blue-500" />
                      </div>
                      <span className="font-black">{s.origin?.code || s.query}</span>
                      <span className="text-muted-foreground opacity-30">→</span>
                      <span className="font-black">{s.destination?.code || 'ANY'}</span>
                    </div>
                    <span className="text-[10px] font-black text-muted-foreground tabular-nums bg-muted px-2 py-1 rounded-lg">
                      {new Date(s.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
