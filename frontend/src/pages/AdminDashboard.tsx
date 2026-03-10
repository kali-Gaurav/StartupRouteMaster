import { useState, useEffect, useCallback, useRef } from "react";
import {
  Shield,
  CreditCard,
  Activity,
  LayoutDashboard,
  TrendingUp,
  Zap,
  BrainCircuit,
  Activity as Pulse,
  Zap as Power
} from "lucide-react";
import { fetchWithAuth } from "@/lib/apiClient";
import { getRailwayWsUrl } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// --- Interfaces ---

interface PortalHealth {
  portal: string;
  status: "ONLINE" | "DEGRADED" | "OFFLINE";
  latency: number;
}

interface VPAStat {
  vpa: string;
  name: string;
  utilization_pct: number;
  volume: number;
  limit: number;
  is_active: boolean;
  history: any[];
}

interface PendingBooking {
  id: string;
  user_id: string;
  train_number: string;
  amount_paid: number;
  escrow_status: string;
  created_at: string;
  merchant_vpa: string;
  utr_number: string;
}

interface BookingDetails {
  id: string;
  train_number: string;
  travel_date: string;
  passengers: { name: string; age: number; gender: string }[];
  berth_preference: string;
  amount_paid: number;
  irctc_creds: any;
}

interface ProviderHealth {
  provider: string;
  success_rate: number;
  total_calls: number;
  estimated_cost: number;
  status: "UP" | "SLOW" | "DOWN";
}

interface CircuitBreaker {
  name: string;
  state: "CLOSED" | "OPEN" | "HALF-OPEN";
  failures: number;
  threshold: number;
}

interface FinanceOverview {
  gross_revenue: number;
  net_profit: number;
  active_escrow: number;
  total_transactions: number;
  success_rate: number;
  daily_target_pct: number;
}

interface SlowEndpoint {
  endpoint: string;
  p99_latency: number;
  total_calls: number;
}

interface FrictionEndpoint {
  endpoint: string;
  friction_score: number;
  avg_latency: number;
  error_rate: number;
}

interface UserStats {
  total_users: number;
  dau: number;
  active_now: number;
  retention_rate: number;
}

interface UserFunnel {
  searches: number;
  unlocks: number;
  bookings: number;
  unlock_rate: number;
  booking_rate: number;
}

interface InventoryStats {
  average_age_minutes: number;
  total_cached_trains: number;
  oldest_samples: { train: string, age_mins: number }[];
}

interface AISentiment {
  sentiment_score: number;
  label: "POSITIVE" | "NEUTRAL" | "FRUSTRATED";
  sample_count: number;
}

interface AIIntentAnalytics {
  total_responses: number;
  fallback_count: number;
  fallback_rate: number;
  intent_accuracy: number;
}

interface RefundRequest {
  id: string;
  booking_id: string;
  amount: number;
  vpa: string;
  status: "PENDING" | "PROCESSED" | "FAILED";
  reason: string;
  created_at: string;
}

export default function AdminDashboard() {
  const [vpaStats, setVpaStats] = useState<VPAStat[]>([]);
  const [pendingBookings, setPendingBookings] = useState<PendingBooking[]>([]);
  const [selectedBooking, setSelectedBooking] = useState<BookingDetails | null>(null);
  const [refunds, setRefunds] = useState<RefundRequest[]>([]);
  const [providerHealth, setProviderHealth] = useState<ProviderHealth[]>([]);
  const [financeOverview, setFinanceOverview] = useState<FinanceOverview | null>(null);
  const [slowEndpoints, setSlowEndpoints] = useState<SlowEndpoint[]>([]);
  const [frictionLeaderboard, setFrictionLeaderboard] = useState<FrictionEndpoint[]>([]);
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [userFunnel, setUserFunnel] = useState<UserFunnel | null>(null);
  const [inventoryStats, setInventoryStats] = useState<InventoryStats | null>(null);
  const [aiSentiment, setAiSentiment] = useState<AISentiment | null>(null);
  const [aiIntent, setAiIntent] = useState<AIIntentAnalytics | null>(null);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [topRoutes, setTopRoutes] = useState<TopRoute[]>([]);
  const [geoLoad, setGeoLoad] = useState<Record<string, number>>({});
  const [resourceHistory, setResourceHistory] = useState<{ cpu: number, mem: number, timestamp: string }[]>([]);
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [metrics, setMetrics] = useState({ cpu: 0, mem: 0, p50: 0, p99: 0, alert: false });
  const [loading, setLoading] = useState(false);

  const portalMatrix: PortalHealth[] = [
    { portal: "Operations Hub", status: "ONLINE", latency: 42 },
    { portal: "Financial Suite", status: "ONLINE", latency: 18 },
    { portal: "Inventory Sentinel", status: "ONLINE", latency: 125 },
    { portal: "AI Intelligence", status: metrics.alert ? "DEGRADED" : "ONLINE", latency: 1400 },
    { portal: "Security & Audit", status: "ONLINE", latency: 12 },
  ];

  useEffect(() => {
    // WebSocket Metrics Feed
    const wsUrl = getRailwayWsUrl("/api/v2/admin/ws/metrics");
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (e) => setMetrics(JSON.parse(e.data));

    refreshAll();
    const interval = setInterval(refreshAll, 10000);
    return () => { clearInterval(interval); ws.close(); };
  }, []);

  const refreshAll = () => {
    loadStats();
    loadPending();
    loadPerformance();
    loadFinance();
    loadSlowEndpoints();
    loadFrictionLeaderboard();
    loadUserAnalytics();
    loadGeoLoad();
    loadResourceHistory();
    loadSystemHealth();
    loadAuditLogs();
    loadInventory();
    loadAIAnalytics();
  };

  const loadAIAnalytics = async () => {
    try {
      const [s, i] = await Promise.all([
        fetchWithAuth("/admin/ai/sentiment"),
        fetchWithAuth("/admin/ai/intent-analytics")
      ]);
      setAiSentiment(await s.json());
      setAiIntent(await i.json());
    } catch (e) { console.error("AI Analytics error"); }
  };

  const loadInventory = async () => {
    try {
      const [f] = await Promise.all([
        fetchWithAuth("/admin/inventory/freshness")
      ]);
      setInventoryStats(await f.json());
    } catch (e) { console.error("Inventory data error"); }
  };

  const loadAuditLogs = async () => {
    try {
      const res = await fetchWithAuth("/admin/audit/logs");
      setAuditLogs(await res.json());
    } catch (e) { console.error("Audit logs error"); }
  };

  const loadSystemHealth = async () => {
    try {
      const res = await fetchWithAuth("/admin/system/health");
      setSystemHealth(await res.json());
    } catch (e) { console.error("System health error"); }
  };

  const loadResourceHistory = async () => {
    try {
      const res = await fetchWithAuth("/admin/system/resource-history");
      const data = await res.json();
      setResourceHistory(data.reverse());
    } catch (e) { console.error("Resource history error"); }
  };

  const loadGeoLoad = async () => {
    try {
      const res = await fetchWithAuth("/admin/user/geo-load");
      setGeoLoad(await res.json());
    } catch (e) { console.error("Geo load error"); }
  };

  const loadUserAnalytics = async () => {
    try {
      const [s, r, f] = await Promise.all([
        fetchWithAuth("/admin/user/stats"),
        fetchWithAuth("/admin/user/top-routes"),
        fetchWithAuth("/admin/user/funnel")
      ]);
      setUserStats(await s.json());
      setTopRoutes(await r.json());
      setUserFunnel(await f.json());
    } catch (e) { console.error("User analytics error"); }
  };

  const loadSlowEndpoints = async () => {
    try {
      const res = await fetchWithAuth("/admin/performance/slow-endpoints");
      setSlowEndpoints(await res.json());
    } catch (e) { console.error("Slow endpoints error"); }
  };

  const loadFrictionLeaderboard = async () => {
    try {
      const res = await fetchWithAuth("/admin/performance/friction-leaderboard");
      setFrictionLeaderboard(await res.json());
    } catch (e) { console.error("Friction error"); }
  };

  const loadPerformance = async () => {
    try {
      const res = await fetchWithAuth("/admin/performance/status");
      setProviderHealth(await res.json());
    } catch (e) { console.error("Performance stats error"); }
  };

  const loadFinance = async () => {
    try {
      const [o, r] = await Promise.all([
        fetchWithAuth("/admin/finance/overview"),
        fetchWithAuth("/admin/finance/refunds")
      ]);
      setFinanceOverview(await o.json());
      setRefunds(await r.json());
    } catch (e) { console.error("Finance data error"); }
  };

  const loadStats = async () => {
    try {
      const res = await fetchWithAuth("/admin/vpa/stats");
      setVpaStats(await res.json());
    } catch (e) { console.error("VPA stats error"); }
  };

  const loadPending = async () => {
    try {
      const res = await fetchWithAuth("/admin/bookings/pending");
      setPendingBookings(await res.json());
    } catch (e) { console.error("Pending bookings error"); }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight flex items-center gap-2">
            <LayoutDashboard className="w-8 h-8 text-primary" />
            Command <span className="text-primary">Center</span>
          </h1>
          <p className="text-muted-foreground mt-1 font-medium italic">High-Tech Fleet Overview</p>
        </div>
        <div className="flex gap-3">
          <Badge variant="outline" className="font-mono gap-2 px-3 py-1 bg-slate-900 border-slate-800">
            <span className="text-[10px] opacity-50 font-black">UPTIME</span>
            <span className="text-emerald-500">99.98%</span>
          </Badge>
          <Badge variant="outline" className="font-mono gap-2 px-3 py-1 bg-slate-900 border-slate-800">
            <Power className="w-3 h-3 text-amber-500" />
            IST: {new Date().toLocaleTimeString('en-IN')}
          </Badge>
        </div>
      </div>

      {/* Task 20.3: Portal Health Matrix */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-6">
        {portalMatrix.map((p) => (
          <Card key={p.portal} className="bg-slate-900 border-slate-800 shadow-xl hover:ring-1 hover:ring-primary/30 transition-all cursor-pointer group">
            <CardContent className="p-6 space-y-4 text-center">
              <div className="flex flex-col items-center gap-2">
                <div className={`w-2 h-2 rounded-full shadow-[0_0_10px_rgba(16,185,129,0.5)] ${p.status === 'ONLINE' ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 group-hover:text-slate-300 transition-colors">{p.portal}</p>
              </div>
              <div className="space-y-1">
                <p className={`text-xl font-black italic tracking-tighter ${p.status === 'ONLINE' ? 'text-white' : 'text-rose-500'}`}>{p.status}</p>
                <p className="text-[8px] font-bold text-slate-600 uppercase tracking-widest">{p.latency}ms Latency</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-12 gap-8">
        {/* Platform Core Telemetry */}
        <div className="lg:col-span-8 space-y-8">
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Platform Core Telemetry (Sync Timeline)
              </CardTitle>
              <Activity className="w-4 h-4 text-primary animate-pulse" />
            </CardHeader>
            <CardContent className="p-8 h-[300px] flex items-end justify-between gap-1">
              {resourceHistory.map((h, i) => (
                <div key={i} className="flex-1 flex flex-col-reverse gap-0.5">
                  <div className="w-full bg-primary/20 rounded-t-sm" style={{ height: `${h.mem}%` }} />
                  <div className="w-full bg-primary rounded-t-sm" style={{ height: `${h.cpu}%` }} />
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Growth Pulse */}
            <Card className="bg-slate-900 border-slate-800 shadow-2xl">
              <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
                <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                  Growth Pulse
                </CardTitle>
                <TrendingUp className="w-4 h-4 text-emerald-500" />
              </CardHeader>
              <CardContent className="p-6 space-y-6">
                <div className="grid grid-cols-2 gap-4 text-center">
                  <div className="space-y-1"><p className="text-[10px] font-black uppercase text-slate-500">Live Users</p><p className="text-2xl font-black text-emerald-500">{userStats?.active_now || 0}</p></div>
                  <div className="space-y-1"><p className="text-[10px] font-black uppercase text-slate-500">Conversion</p><p className="text-2xl font-black text-white">{userFunnel?.booking_rate || 0}%</p></div>
                </div>
                <div className="space-y-2">
                  {topRoutes.map((r, i) => (
                    <div key={i} className="flex justify-between items-center text-[10px]">
                      <span className="font-bold text-slate-400">{r.route}</span>
                      <Badge variant="outline" className="h-5 text-[8px] font-black">{r.searches} HITS</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Financial Status */}
            <Card className="bg-slate-900 border-slate-800 shadow-2xl">
              <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
                <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                  Financial Status
                </CardTitle>
                <CreditCard className="w-4 h-4 text-primary" />
              </CardHeader>
              <CardContent className="p-6 space-y-6">
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1">
                  <p className="text-[10px] font-black uppercase text-slate-500">Net Profit Velocity</p>
                  <p className="text-3xl font-black italic tracking-tighter text-emerald-500">₹{financeOverview?.net_profit.toLocaleString()}</p>
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between items-center text-[10px]">
                    <span className="font-black text-slate-500 uppercase">Escrow Buffer</span>
                    <span className="font-bold text-amber-500">₹{financeOverview?.active_escrow.toLocaleString()}</span>
                  </div>
                  <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-primary" style={{ width: `${financeOverview?.daily_target_pct}%` }} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Intelligence Sidebar */}
        <div className="lg:col-span-4 space-y-8">
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                AI Intent Accuracy
              </CardTitle>
              <BrainCircuit className="w-4 h-4 text-primary" />
            </CardHeader>
            <CardContent className="p-8 text-center space-y-6">
              <div className="relative inline-flex items-center justify-center">
                <svg className="w-32 h-32 transform -rotate-90">
                  <circle cx="64" cy="64" r="58" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-slate-800" />
                  <circle cx="64" cy="64" r="58" stroke="currentColor" strokeWidth="8" fill="transparent" strokeDasharray={364.4} strokeDashoffset={364.4 - (364.4 * (aiIntent?.intent_accuracy || 0) / 100)} className="text-primary shadow-[0_0_15px_rgba(59,130,246,0.5)]" />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-black text-white">{aiIntent?.intent_accuracy}%</span>
                  <span className="text-[8px] font-black uppercase text-slate-500 tracking-widest">Confidence</span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-800">
                <div className="text-center"><p className="text-[8px] font-black uppercase text-slate-500">Sentiment</p><p className="text-sm font-bold text-emerald-500">{aiSentiment?.label}</p></div>
                <div className="text-center"><p className="text-[8px] font-black uppercase text-slate-500">Fallbacks</p><p className="text-sm font-bold text-rose-500">{aiIntent?.fallback_count}</p></div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Shield className="w-4 h-4 text-emerald-500" />
                Security Audit Pulse
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[250px]">
                <div className="divide-y divide-slate-800">
                  {auditLogs.slice(0, 5).map((l, i) => (
                    <div key={i} className="p-4 space-y-1 hover:bg-slate-800/30 transition-colors">
                      <div className="flex justify-between items-center">
                        <span className="text-[9px] font-black uppercase text-slate-200">{l.action}</span>
                        <span className="text-[8px] font-bold text-slate-600">{new Date(l.timestamp).toLocaleTimeString()}</span>
                      </div>
                      <p className="text-[8px] text-slate-500 font-medium italic truncate">By {l.performed_by}: {l.new_value}</p>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          <Card className="bg-primary text-white border-0 shadow-2xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:scale-110 transition-transform"><Power className="w-16 h-16" /></div>
            <CardContent className="p-6 space-y-4">
              <div className="space-y-1">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] opacity-70 text-primary-foreground">System Load</p>
                <p className="text-4xl font-black italic tracking-tighter">{metrics.cpu}%</p>
              </div>
              <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest bg-white/10 p-2 rounded-lg">
                <div className="w-2 h-2 rounded-full bg-white animate-ping" />
                Real-Time Node Monitoring Active
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
