import { useState, useEffect } from "react";
import {
  Database,
  RefreshCw,
  Activity,
  PieChart,
  AlertCircle,
  CheckCircle2,
  Zap,
  Clock,
  Archive,
  Boxes,
  LayoutGrid
} from "lucide-react";
import { fetchWithAuth } from "@/lib/apiClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";

interface InventoryStats {
  average_age_minutes: number;
  total_cached_trains: number;
  oldest_samples: { train: string, age_mins: number }[];
}

interface SyncVelocity {
  run_id: string;
  trips: number;
  rps: number;
  timestamp: string;
}

interface StationFreshness {
  station: string;
  avg_age_mins: number;
}

export default function AdminInventory() {
  const [stats, setStats] = useState<InventoryStats | null>(null);
  const [velocity, setVelocity] = useState<SyncVelocity[]>([]);
  const [distribution, setDistribution] = useState<Record<string, number>>({});
  const [stationFreshness, setStationFreshness] = useState<StationFreshness[]>([]);
  const [syncStatus, setSyncStatus] = useState<any>(null);

  useEffect(() => {
    refreshInventory();
    const interval = setInterval(refreshInventory, 15000);
    return () => clearInterval(interval);
  }, []);

  const refreshInventory = async () => {
    try {
      const [s, v, d, st, sf] = await Promise.all([
        fetchWithAuth("/admin/inventory/freshness"),
        fetchWithAuth("/admin/inventory/velocity"),
        fetchWithAuth("/admin/inventory/distribution"),
        fetchWithAuth("/admin/inventory/status"),
        fetchWithAuth("/admin/inventory/station-freshness")
      ]);
      setStats(await s.json());
      setVelocity(await v.json());
      setDistribution(await d.json());
      setSyncStatus(await st.json());
      setStationFreshness(await sf.json());
    } catch (e) { console.error("Inventory refresh error"); }
  };

  const triggerGlobalSync = async () => {
    toast.info("Initializing global inventory sync...");
    try {
      const res = await fetchWithAuth("/admin/inventory/sync/trigger", { method: "POST" });
      const data = await res.json();
      toast.success(`Sync process started: ${data.run_id}`);
      refreshInventory();
    } catch (e) { toast.error("Sync trigger failed"); }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2">
          <Database className="w-6 h-6 text-primary" />
          Inventory Sentinel
        </h2>
        <div className="flex gap-2">
          <Badge variant="outline" className={`font-mono px-3 py-1 ${syncStatus?.is_healthy ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-rose-500/10 text-rose-500 border-rose-500/20'}`}>
            SYNC PIPELINE: {syncStatus?.is_healthy ? 'NOMINAL' : 'ANOMALY DETECTED'}
          </Badge>
        </div>
      </div>

      {/* Inventory KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl relative overflow-hidden">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Avg Data Age</p>
            <p className="text-3xl font-black italic tracking-tighter text-white">{stats?.average_age_minutes} <span className="text-sm">MINS</span></p>
            <p className="text-[10px] font-medium text-emerald-500 italic">Target: &lt; 30.0 mins</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Cached Availability</p>
            <p className="text-3xl font-black italic tracking-tighter text-white">{stats?.total_cached_trains.toLocaleString()}</p>
            <p className="text-[10px] font-medium text-slate-500 italic">Across active routes</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Sync Velocity</p>
            <p className="text-3xl font-black italic tracking-tighter text-blue-500">{velocity[0]?.rps || 0} <span className="text-sm">RPS</span></p>
            <p className="text-[10px] font-medium text-slate-500 italic">Records per second</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Provider Health</p>
            <p className="text-3xl font-black italic tracking-tighter text-emerald-500">100%</p>
            <p className="text-[10px] font-medium text-slate-500 italic">All uplinks active</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8 space-y-8">
          {/* Sync Pulse Chart */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                ETL Sync Pulse (Records Throughput)
              </CardTitle>
              <Activity className="w-4 h-4 text-primary animate-pulse" />
            </CardHeader>
            <CardContent className="p-8 h-[300px] flex items-end justify-between gap-3">
              {velocity.map((v, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-3 group relative h-full">
                  <div className="w-full bg-primary/20 rounded-t-lg transition-all group-hover:bg-primary/40 relative overflow-hidden" style={{ height: `${(v.trips / (Math.max(...velocity.map(x => x.trips)) || 1)) * 200}px` }}>
                    <div className="absolute bottom-0 left-0 w-full bg-primary shadow-[0_0_15px_rgba(59,130,246,0.4)]" style={{ height: `${(v.rps / 10) * 100}%` }} />
                  </div>
                  <span className="text-[8px] font-black text-slate-600 uppercase tracking-tighter">RUN {v.run_id.substring(7)}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Task 34.2: Regional Data Staleness Heatmap */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Regional Data Staleness (Station Level)
              </CardTitle>
              <LayoutGrid className="w-4 h-4 text-emerald-500" />
            </CardHeader>
            <CardContent className="p-6">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {stationFreshness.map((s) => (
                  <div key={s.station} className="bg-slate-950 border border-slate-800 rounded-xl p-4 text-center space-y-2 group hover:border-primary transition-all">
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{s.station}</p>
                    <p className={`text-xl font-black italic tracking-tighter ${s.avg_age_mins > 60 ? 'text-rose-500' : s.avg_age_mins > 30 ? 'text-amber-500' : 'text-emerald-500'}`}>
                      {s.avg_age_mins.toFixed(0)}m
                    </p>
                    <div className={`h-1 w-full rounded-full ${s.avg_age_mins > 60 ? 'bg-rose-500' : s.avg_age_mins > 30 ? 'bg-amber-500' : 'bg-emerald-500'} opacity-20`} />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Class Mix */}
            <Card className="bg-slate-900 border-slate-800 shadow-2xl">
              <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
                <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                  Inventory Class Mix
                </CardTitle>
                <PieChart className="w-4 h-4 text-primary" />
              </CardHeader>
              <CardContent className="p-6 space-y-4">
                {Object.entries(distribution).map(([cls, count]) => (
                  <div key={cls} className="space-y-1.5">
                    <div className="flex justify-between text-[10px] font-black uppercase tracking-widest text-slate-300">
                      <span>{cls}</span>
                      <span className="text-slate-500">{count.toLocaleString()}</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-primary" style={{ width: `${(count / (Math.max(...Object.values(distribution)) || 1)) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Stale Heatmap */}
            <Card className="bg-slate-900 border-slate-800 shadow-2xl">
              <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
                <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                  Stale Data Leaderboard
                </CardTitle>
                <AlertCircle className="w-4 h-4 text-rose-500" />
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-slate-800">
                  {stats?.oldest_samples.map((s, i) => (
                    <div key={i} className="p-4 flex justify-between items-center hover:bg-slate-800/30 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="bg-rose-500/10 p-1.5 rounded text-rose-500 border border-rose-500/20">
                          <Clock className="w-3 h-3" />
                        </div>
                        <p className="text-[10px] font-black text-slate-200">TRAIN #{s.train}</p>
                      </div>
                      <Badge variant="outline" className="bg-rose-500/10 text-rose-500 border-rose-500/20 h-5 font-black text-[8px] uppercase tracking-widest">
                        {s.age_mins.toFixed(0)}M AGO
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Sync Controls */}
        <div className="lg:col-span-4 space-y-8">
          <Card className="bg-slate-900 border-slate-800 shadow-2xl">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" />
                Control Commands
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <Button 
                className="w-full bg-primary hover:bg-primary/90 font-black uppercase text-[10px] tracking-widest h-12 shadow-[0_0_15px_rgba(59,130,246,0.3)]" 
                onClick={triggerGlobalSync}
              >
                <RefreshCw className="w-4 h-4 mr-3" />
                Trigger Global Refresh
              </Button>
              <Button variant="outline" className="w-full border-slate-700 text-slate-400 hover:bg-slate-800 font-black uppercase text-[10px] tracking-widest h-12">
                <Archive className="w-4 h-4 mr-3" />
                Clear Stale Cache
              </Button>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Pipeline Anomalies
              </CardTitle>
              <Boxes className="w-4 h-4 text-slate-500" />
            </CardHeader>
            <CardContent className="p-6">
              {syncStatus?.anomalies.length === 0 ? (
                <div className="flex items-center gap-3 text-emerald-500 bg-emerald-500/5 p-4 rounded-xl border border-emerald-500/10">
                  <CheckCircle2 className="w-4 h-4" />
                  <p className="text-[10px] font-black uppercase tracking-widest">No anomalies detected in last 5 runs</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {syncStatus?.anomalies.map((a: any, i: number) => (
                    <div key={i} className="bg-rose-500/10 border border-rose-500/20 p-4 rounded-xl space-y-1">
                      <p className="text-[10px] font-black text-rose-500 uppercase">{a.type}</p>
                      <p className="text-[9px] text-slate-400 leading-relaxed font-medium italic">"{a.message}"</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
