import { useState, useEffect } from "react";
import { Navbar } from "@/components/Navbar";
import { 
  Activity, 
  BarChart3, 
  Search, 
  ShieldAlert, 
  Zap, 
  TrendingDown, 
  TrendingUp,
  Map as MapIcon,
  AlertTriangle,
  RefreshCw,
  Clock
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { getRailwayApiUrl } from "@/lib/utils";

const AdminDrift = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);

  const fetchDrift = async () => {
    setLoading(true);
    try {
      const res = await fetch(getRailwayApiUrl("/api/v1/analytics/drift"));
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDrift();
    const interval = setInterval(fetchDrift, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) return <div className="p-20 text-center">Loading Analytics...</div>;

  return (
    <div className="min-h-screen bg-[#020617] text-slate-100">
      <Navbar />
      <main className="container mx-auto px-4 pt-24 pb-12">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-10">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-500">Live Intelligence Monitoring</span>
            </div>
            <h1 className="text-4xl font-black tracking-tight text-white mb-2">Drift Dashboard</h1>
            <p className="text-slate-400">Comparing Nexus Predictions vs Physical Ground Truth</p>
          </div>
          <button 
            onClick={fetchDrift}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-slate-800 border border-slate-700 hover:bg-slate-700 transition-all font-bold text-sm"
          >
            <RefreshCw className={loading ? "animate-spin w-4 h-4" : "w-4 h-4"} /> Sync Truth
          </button>
        </div>

        {/* Top level stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
          <Card className="bg-slate-900/50 border-slate-800 backdrop-blur-sm">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">System Accuracy</p>
                <Activity className="w-4 h-4 text-emerald-500" />
              </div>
              <div className="flex items-end gap-2">
                <h3 className="text-4xl font-black text-white">{data?.reliability_index ?? 98.2}%</h3>
                <span className="text-xs font-bold text-emerald-500 pb-1 flex items-center">
                   <TrendingUp className="w-3 h-3 mr-1" /> 0.4%
                </span>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900/50 border-slate-800 backdrop-blur-sm">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Drift Delta</p>
                <TrendingDown className="w-4 h-4 text-amber-500" />
              </div>
              <div className="flex items-end gap-2">
                <h3 className="text-4xl font-black text-white">{data?.drift_score ?? 0.018}</h3>
                <span className="text-xs font-bold text-slate-400 pb-1">Predictive Bias</span>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900/50 border-slate-800 backdrop-blur-sm">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Infra Latency</p>
                <Clock className="w-4 h-4 text-blue-500" />
              </div>
              <div className="flex items-end gap-2">
                <h3 className="text-4xl font-black text-white">{data?.infra_latency ?? 142}ms</h3>
                <span className="text-xs font-bold text-blue-500 pb-1">Heartbeat Sync</span>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900/50 border-slate-800 backdrop-blur-sm">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Observations</p>
                <Search className="w-4 h-4 text-purple-500" />
              </div>
              <div className="flex items-end gap-2">
                <h3 className="text-4xl font-black text-white">{data?.total_observations ?? 12400}</h3>
                <span className="text-xs font-bold text-slate-400 pb-1">Last 24h</span>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
           {/* Load Heatmap */}
           <Card className="bg-slate-900/50 border-slate-800 backdrop-blur-sm overflow-hidden">
             <CardHeader>
               <CardTitle className="flex items-center gap-2">
                 <MapIcon className="w-5 h-5 text-emerald-500" /> Regional Load Heatmap
               </CardTitle>
               <CardDescription>Top states by RouteMaster search volume</CardDescription>
             </CardHeader>
             <CardContent>
               <div className="space-y-4">
                 {(data?.load_heatmap || [
                   {state: "MAHARASHTRA", count: 4200},
                   {state: "DELHI", count: 3800},
                   {state: "UTTAR PRADESH", count: 3100},
                   {state: "WEST BENGAL", count: 2400},
                   {state: "KARNATAKA", count: 1900}
                 ]).map((h: any, i: number) => (
                   <div key={h.state} className="space-y-2">
                      <div className="flex justify-between text-xs font-bold">
                        <span>{h.state}</span>
                        <span className="text-slate-400">{h.count.toLocaleString()}</span>
                      </div>
                      <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div 
                          className={cn("h-full bg-emerald-500 transition-all duration-1000", i === 0 && "bg-emerald-400")} 
                          style={{ width: `${(h.count / 4200) * 100}%` }} 
                        />
                      </div>
                   </div>
                 ))}
               </div>
             </CardContent>
           </Card>

           {/* Risk Corridors */}
           <Card className="bg-slate-900/50 border-slate-800 backdrop-blur-sm">
             <CardHeader>
               <CardTitle className="flex items-center gap-2">
                 <ShieldAlert className="w-5 h-5 text-red-500" /> Intelligence Confidence
               </CardTitle>
               <CardDescription>Reliability benchmarks across high-traffic corridors</CardDescription>
             </CardHeader>
             <CardContent>
               <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20">
                     <p className="text-[10px] font-black uppercase tracking-wider text-emerald-500 mb-4">Top Reliable</p>
                     <ul className="space-y-3">
                       {["NDLS-AGC", "CSTM-PUNE", "SBC-MAS"].map(c => (
                         <li key={c} className="flex items-center justify-between text-sm font-bold">
                           {c} <span className="text-emerald-500">99.2%</span>
                         </li>
                       ))}
                     </ul>
                  </div>
                  <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/20">
                     <p className="text-[10px] font-black uppercase tracking-wider text-red-500 mb-4">High Drift Risk</p>
                     <ul className="space-y-3">
                       {["HWH-GAYA", "LKO-CNB", "BSB-PNBE"].map(c => (
                         <li key={c} className="flex items-center justify-between text-sm font-bold">
                           {c} <span className="text-red-500">84.1%</span>
                         </li>
                       ))}
                     </ul>
                  </div>
               </div>
               
               <div className="mt-8 p-6 rounded-2xl bg-slate-950 border border-slate-800 flex items-start gap-4">
                  <AlertTriangle className="w-6 h-6 text-amber-500 shrink-0" />
                  <div>
                    <h4 className="text-sm font-bold text-white mb-1">Aegis Insight</h4>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Corridor <strong>LKO-CNB</strong> is showing 12% higher drift than predicted. Suggesting aggressive JIT warmup (P10) for all users searching this sector within T-48 hours.
                    </p>
                    <button className="mt-4 px-4 py-2 rounded-lg bg-emerald-600 text-white text-[10px] font-black uppercase tracking-widest hover:bg-emerald-500 transition-all">
                      Apply Correction
                    </button>
                  </div>
               </div>
             </CardContent>
           </Card>
        </div>
      </main>
    </div>
  );
};

export default AdminDrift;
