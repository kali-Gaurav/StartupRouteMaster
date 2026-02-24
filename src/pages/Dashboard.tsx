/**
 * Safe Journey Ops Dashboard
 * Shows SOS events in red zone (highest priority). Direct Google Maps links.
 * No login - prototype for investor demo.
 */
import { useState, useEffect } from "react";
import { MapPin, ExternalLink, Phone, Mail, User, AlertCircle, CheckCircle, RefreshCw, Train, Wifi, WifiOff, History, Star, CloudSync, Clock, ArrowRight } from "lucide-react";
import { getAllSOS, resolveSOS, type SOSEvent } from "@/services/sosApi";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import { storageService } from "@/services/storageService";

function StatCard({ title, value, icon: Icon, colorClass }: { title: string; value: string | number; icon: any; colorClass: string }) {
  return (
    <div className="bg-muted/30 border border-border rounded-xl p-4 flex items-center gap-4">
      <div className={`p-3 rounded-lg ${colorClass}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-sm text-muted-foreground">{title}</p>
        <p className="text-2xl font-bold">{value}</p>
      </div>
    </div>
  );
}

function DashboardStatGrid({ activeSOS, totalSaved, pendingSync }: { activeSOS: number; totalSaved: number; pendingSync: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      <StatCard title="Active SOS Reports" value={activeSOS} icon={AlertCircle} colorClass="bg-red-500" />
      <StatCard title="Saved Routes" value={totalSaved} icon={Star} colorClass="bg-yellow-500" />
      <StatCard title="Pending Sync" value={pendingSync} icon={CloudSync} colorClass="bg-blue-500" />
    </div>
  );
}

export default function Dashboard() {
  const isOnline = useBackendHealth();
  const [events, setEvents] = useState<SOSEvent[]>([]);
  const [recentSearches, setRecentSearches] = useState<any[]>([]);
  const [favorites, setFavorites] = useState<any[]>([]);
  const [pendingSyncCount, setPendingSyncCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string|null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      // 1. Fetch SOS Events
      try {
        const { events: list } = await getAllSOS();
        setEvents(list);
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
      setRecentSearches(history);
      setFavorites(favs);

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

  const activeCount = events.filter(e => e.status === "active").length;

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-full ${isOnline ? 'bg-green-500/10' : 'bg-orange-500/10'}`}>
              <Train className={`w-6 h-6 ${isOnline ? 'text-green-500' : 'text-orange-500'}`} />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">Personal Rail Dashboard</h1>
              <div className="flex items-center gap-2">
                {isOnline ? (
                   <span className="flex items-center gap-1 text-[10px] uppercase font-bold text-green-500">
                     <Wifi className="w-3 h-3" /> Live Control Center
                   </span>
                ) : (
                  <span className="flex items-center gap-1 text-[10px] uppercase font-bold text-orange-500">
                    <WifiOff className="w-3 h-3" /> Offline Workstation
                  </span>
                )}
              </div>
            </div>
          </div>
          
          <button 
            onClick={() => fetchData()}
            className="p-2 hover:bg-muted rounded-full transition-colors"
            title="Refresh dashboard"
          >
            <RefreshCw className={`w-5 h-5 text-muted-foreground ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <DashboardStatGrid 
          activeSOS={activeCount} 
          totalSaved={favorites.length} 
          pendingSync={pendingSyncCount} 
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Column: SOS Events */}
          <div className="lg:col-span-2 space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-red-500" />
                Live SOS Monitoring
              </h2>
            </div>
            
            {events.length === 0 ? (
               <div className="border border-dashed border-border rounded-xl p-12 text-center text-muted-foreground">
                  <CheckCircle className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p>All systems clear. No active SOS reports.</p>
               </div>
            ) : (
              <div className="grid gap-4">
                {events.map(e => (
                  <EventCard key={e.id} e={e} onResolve={() => {}} />
                ))}
              </div>
            )}
          </div>

          {/* Sidebar: Offline Insights */}
          <div className="space-y-8">
            {/* Favorites */}
            <section className="space-y-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                <Star className="w-4 h-4 text-yellow-500" />
                Favorite Routes
              </h3>
              <div className="bg-muted/30 border border-border rounded-xl divide-y divide-border">
                {favorites.length > 0 ? favorites.map((f, i) => (
                  <div key={i} className="p-3 flex items-center justify-between group cursor-pointer hover:bg-muted/50">
                    <div className="flex items-center gap-3">
                      <div className="font-bold">{f.source}</div>
                      <ArrowRight className="w-3 h-3 text-muted-foreground" />
                      <div className="font-bold">{f.destination}</div>
                    </div>
                  </div>
                )) : (
                  <p className="p-4 text-xs text-muted-foreground italic">No favorites saved yet.</p>
                )}
              </div>
            </section>

            {/* Recent Searches */}
            <section className="space-y-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                <History className="w-4 h-4 text-blue-500" />
                Recent History
              </h3>
              <div className="space-y-2">
                {recentSearches.map((s, i) => (
                  <div key={i} className="bg-muted/30 border border-border rounded-lg p-3 text-xs flex justify-between items-center">
                    <span>{s.query}</span>
                    <span className="text-muted-foreground">{new Date(s.timestamp).toLocaleTimeString()}</span>
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
            <div className={`p-2 rounded-xl ${isOnline ? "bg-red-500/10" : "bg-orange-500/10"}`}>
              {isOnline ? (
                <Wifi className="w-8 h-8 text-green-500" />
              ) : (
                <WifiOff className="w-8 h-8 text-orange-500" />
              )}
            </div>
            <div>
              <h1 className="text-xl font-bold">Safe Journey — Ops Dashboard</h1>
              <p className="text-sm text-muted-foreground">
                {isOnline ? "Live Monitoring (Prototype)" : "Offline - Cached Data"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {activeCount > 0 && (
              <div className="px-4 py-2 rounded-lg bg-red-500/20 text-red-600 font-bold">
                {activeCount} Active SOS
              </div>
            )}
            <button
              onClick={fetchEvents}
              disabled={loading}
              className="p-2 rounded-lg border border-border hover:bg-muted"
            >
              <RefreshCw className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-destructive/10 text-destructive">
            {error}
          </div>
        )}

        {loading && events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <RefreshCw className="w-12 h-12 animate-spin mb-4" />
            <p>Loading SOS events...</p>
          </div>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <CheckCircle className="w-16 h-16 text-green-500 mb-4" />
            <p className="font-medium">No SOS events yet</p>
            <p className="text-sm mt-1">Press SOS on the passenger page to test</p>
            <a href="/sos" className="mt-4 text-primary hover:underline">Go to SOS Page →</a>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                All Events ({events.length}) — Active first
              </h2>
            </div>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {events.map((e) => (
                <EventCard key={e.id} e={e} onResolve={() => handleResolve(e.id)} />
              ))}
            </div>
          </div>
        )}
      </main>

      <footer className="border-t border-border mt-12 py-6 text-center text-sm text-muted-foreground">
        <a href="/" className="hover:text-foreground">← Back to home</a>
        <span className="mx-2">|</span>
        <a href="/sos" className="hover:text-foreground">SOS Page (passenger)</a>
      </footer>
    </div>
  );
}
