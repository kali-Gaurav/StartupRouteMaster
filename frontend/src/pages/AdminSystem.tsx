import { useState, useEffect } from "react";
import {
  Server,
  Activity,
  HardDrive,
  Terminal,
  RefreshCw,
  ShieldCheck,
  Archive,
  BrainCircuit,
  LayoutGrid,
  ShieldAlert,
  Zap,
  Target,
  Users,
  Power
} from "lucide-react";
import { fetchWithAuth } from "@/lib/apiClient";
import { getRailwayWsUrl } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";

interface CircuitBreaker {
  name: string;
  state: "CLOSED" | "OPEN" | "HALF-OPEN";
  failures: number;
  threshold: number;
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

interface SnapshotRecord {
  timestamp: string;
  size_mb: number;
  status: string;
  files: { name: string, size: number }[];
}

interface ErrorTriage {
  category: string;
  count: number;
  status: "NOMINAL" | "CRITICAL";
}

interface FailurePattern {
  signature: string;
  affected_endpoint: string;
  occurrence_count: number;
  severity: "WARNING" | "CRITICAL";
  suggested_action: string;
}

interface InfrastructureDiagnostic {
  component: string;
  status: string;
  latency_ms?: number;
}

interface WorkerProcess {
  pid: number;
  name: string;
  cpu_pct: number;
  mem_mb: number;
  status: string;
  uptime: number;
}

interface SystemImpact {
  impact_score: number;
  active_users_at_risk: number;
  severity: "NOMINAL" | "WARNING" | "CRITICAL";
}

interface AdminProfile {
  route: string;
  p99_ms: number;
  avg_size_kb: number;
}

export default function AdminSystem() {
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [resourceHistory, setResourceHistory] = useState<any[]>([]);
  const [slowEndpoints, setSlowEndpoints] = useState<SlowEndpoint[]>([]);
  const [frictionLeaderboard, setFrictionLeaderboard] = useState<FrictionEndpoint[]>([]);
  const [circuitBreakers, setCircuitBreakers] = useState<CircuitBreaker[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotRecord[]>([]);
  const [errorTriage, setErrorTriage] = useState<ErrorTriage[]>([]);
  const [failurePatterns, setFailurePatterns] = useState<FailurePattern[]>([]);
  const [diagnostics, setDiagnostics] = useState<InfrastructureDiagnostic[]>([]);
  const [clusterMap, setClusterMap] = useState<WorkerProcess[]>([]);
  const [adminProfiling, setAdminProfiling] = useState<AdminProfile[]>([]);
  const [impactScore, setImpactScore] = useState<SystemImpact | null>(null);
  const [graphHealth, setGraphHealth] = useState<any>(null);
  const [cacheIntel, setCacheIntel] = useState<any[]>([]);
  const [metrics, setMetrics] = useState({ cpu: 0, mem: 0, p50: 0, p99: 0, alert: false });

  useEffect(() => {
    // WebSocket Metrics Feed
    const wsUrl = getRailwayWsUrl("/api/v2/admin/ws/metrics");
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (e) => setMetrics(JSON.parse(e.data));

    refreshSystem();
    const interval = setInterval(refreshSystem, 10000);
    return () => { clearInterval(interval); ws.close(); };
  }, []);

  const refreshSystem = async () => {
    try {
      const [h, hi, s, f, b, g, c, sn, et, fp, im, di, cl, ap] = await Promise.all([
        fetchWithAuth("/admin/system/health"),
        fetchWithAuth("/admin/system/resource-history"),
        fetchWithAuth("/admin/performance/slow-endpoints"),
        fetchWithAuth("/admin/performance/friction-leaderboard"),
        fetchWithAuth("/admin/performance/circuit-breakers"),
        fetchWithAuth("/admin/system/graph-health"),
        fetchWithAuth("/admin/system/cache-intelligence"),
        fetchWithAuth("/admin/system/snapshots"),
        fetchWithAuth("/admin/system/error-triage"),
        fetchWithAuth("/admin/system/failure-patterns"),
        fetchWithAuth("/admin/system/impact-score"),
        fetchWithAuth("/admin/system/diagnostics"),
        fetchWithAuth("/admin/system/cluster-map"),
        fetchWithAuth("/admin/performance/admin-profiling")
      ]);
      setSystemHealth(await h.json());
      setResourceHistory((await hi.json()).reverse());
      setSlowEndpoints(await s.json());
      setFrictionLeaderboard(await f.json());
      setCircuitBreakers(await b.json());
      setGraphHealth(await g.json());
      setCacheIntel(await c.json());
      setSnapshots((await sn.json()).reverse());
      setErrorTriage(await et.json());
      setFailurePatterns(await fp.json());
      setImpactScore(await im.json());
      setDiagnostics(await di.json());
      setClusterMap(await cl.json());
      setAdminProfiling(await ap.json());
    } catch (e) { console.error("System refresh error"); }
  };

  const resetBreaker = async (name: string) => {
    toast.info(`Force closing circuit: ${name}...`);
    try {
      await fetchWithAuth(`/admin/performance/circuit-breakers/${name}/reset`, { method: "POST" });
      toast.success(`${name} re-engaged.`);
      refreshSystem();
    } catch (e) { toast.error("Reset failed"); }
  };

  const restartWorker = async (pid: number) => {
    if (!confirm(`CRITICAL: Kill worker process ${pid}? Supervisor will auto-restart.`)) return;
    try {
      await fetchWithAuth(`/admin/system/cluster-map/${pid}/restart`, { method: "POST" });
      toast.success(`SIGTERM dispatched to PID ${pid}`);
      refreshSystem();
    } catch (e) { toast.error("Restart command failed"); }
  };

  const triggerSnapshot = async () => {
    toast.info("Initializing system snapshot...");
    try {
      const res = await fetchWithAuth("/admin/system/snapshot", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        toast.success(`Encrypted snapshot created: ${data.size_mb.toFixed(2)}MB`);
        refreshSystem();
      } else {
        toast.error("Snapshot failed");
      }
    } catch (e) { toast.error("Connection error"); }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2">
            <Server className="w-6 h-6 text-primary" />
            System Sentinel
          </h2>
          {impactScore && (
            <Badge className={`px-3 py-1 gap-1.5 border-0 shadow-lg ${impactScore.severity === 'CRITICAL' ? 'bg-rose-600 text-white animate-pulse' : impactScore.severity === 'WARNING' ? 'bg-amber-500 text-white' : 'bg-emerald-600 text-white'}`}>
              <Target className="w-3 h-3" />
              IMPACT: {impactScore.impact_score}% ({impactScore.severity})
            </Badge>
          )}
        </div>
        <div className="flex gap-3">
          {circuitBreakers.map(cb => (
            <button key={cb.name} onClick={() => resetBreaker(cb.name)} className="group">
              <Badge variant="outline" className={`gap-1.5 px-3 py-1 transition-all group-hover:border-primary ${cb.state === 'CLOSED' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-rose-500/10 text-rose-500 border-rose-500/20'}`}>
                <div className={`w-1.5 h-1.5 rounded-full ${cb.state === 'CLOSED' ? 'bg-emerald-500' : 'bg-rose-500 animate-ping'}`} />
                {cb.name.split(' ')[0]}: {cb.state}
                {cb.state !== 'CLOSED' && <RefreshCw className="w-2 h-2 ml-1 opacity-50 group-hover:animate-spin" />}
              </Badge>
            </button>
          ))}
        </div>
      </div>

      {/* Task 21.3: Error Triage Heatmap Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {errorTriage.map((t) => (
          <Card key={t.category} className={`bg-slate-900 border-slate-800 shadow-xl border-l-4 ${t.status === 'CRITICAL' ? 'border-l-rose-500 bg-rose-500/5' : 'border-l-emerald-500'}`}>
            <CardContent className="p-6 flex justify-between items-center">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">{t.category}</p>
                <p className={`text-2xl font-black italic ${t.status === 'CRITICAL' ? 'text-rose-500' : 'text-white'}`}>{t.count} Errors</p>
              </div>
              <LayoutGrid className={`w-8 h-8 ${t.status === 'CRITICAL' ? 'text-rose-500 animate-pulse' : 'text-slate-800'}`} />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8 space-y-8">
          {/* Resource Timeline */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Resource Saturation History (60M)
              </CardTitle>
              <Activity className="w-4 h-4 text-primary" />
            </CardHeader>
            <CardContent className="p-8 h-[350px] flex items-end justify-between gap-1">
              {resourceHistory.map((h, i) => (
                <div key={i} className="flex-1 flex flex-col-reverse gap-0.5 group relative h-full">
                  <div className="w-full bg-primary/20 rounded-t-sm" style={{ height: `${h.mem}%` }} />
                  <div className="w-full bg-primary rounded-t-sm" style={{ height: `${h.cpu}%` }} />
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Task 21.2 & 21.3: Failure Pattern Recognized List */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Recognized Failure Signatures (Auto-Patterns)
              </CardTitle>
              <ShieldAlert className="w-4 h-4 text-rose-500 animate-pulse" />
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[300px]">
                {failurePatterns.length === 0 ? (
                  <div className="p-12 text-center opacity-30 italic text-xs uppercase font-black">No failure bursts detected</div>
                ) : (
                  <div className="divide-y divide-slate-800">
                    {failurePatterns.map((p, i) => (
                      <div key={i} className="p-6 flex justify-between items-center hover:bg-slate-800/30 transition-colors group">
                        <div className="space-y-1">
                          <div className="flex items-center gap-3">
                            <Badge variant="outline" className={`h-5 text-[8px] font-black ${p.severity === 'CRITICAL' ? 'bg-rose-500 text-white border-0' : 'bg-amber-500/10 text-amber-500 border-amber-500/20'}`}>
                              {p.severity}
                            </Badge>
                            <p className="text-sm font-black text-slate-200 uppercase font-mono tracking-tighter">{p.signature}</p>
                          </div>
                          <p className="text-[10px] text-slate-500 font-medium">Affecting: <span className="text-slate-400">{p.affected_endpoint}</span></p>
                          <p className="text-[9px] text-emerald-500 font-black uppercase tracking-widest flex items-center gap-1">
                            <Zap className="w-2.5 h-2.5" /> Suggested Action: {p.suggested_action}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-xl font-black text-white">{p.occurrence_count}</p>
                          <p className="text-[8px] font-bold text-slate-600 uppercase tracking-widest">Occurrences</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Task 23.3: Cluster Process Map */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Backend Node Cluster Map (Worker PIDs)
              </CardTitle>
              <LayoutGrid className="w-4 h-4 text-primary animate-pulse" />
            </CardHeader>
            <CardContent className="p-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {clusterMap.map((worker) => (
                  <div key={worker.pid} className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3 relative group overflow-hidden">
                    <div className="absolute top-0 right-0 p-2 opacity-0 group-hover:opacity-10 transition-opacity">
                      <Zap className="w-8 h-8" />
                    </div>
                    <div className="flex justify-between items-center relative z-10">
                      <Badge variant="outline" className="text-[8px] font-mono text-primary border-primary/20 bg-primary/5">
                        PID: {worker.pid}
                      </Badge>
                      <button 
                        onClick={() => restartWorker(worker.pid)}
                        className="text-slate-600 hover:text-rose-500 transition-colors"
                        title="Force Restart Worker"
                      >
                        <Power className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="space-y-1">
                      <p className="text-[10px] font-black text-slate-200 uppercase truncate">{worker.name}</p>
                      <div className="flex justify-between text-[8px] font-bold text-slate-500 uppercase">
                        <span>CPU: {worker.cpu_pct}%</span>
                        <span>MEM: {worker.mem_mb}MB</span>
                      </div>
                    </div>
                    <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-primary shadow-[0_0_10px_rgba(59,130,246,0.5)]" style={{ width: `${Math.min(100, worker.cpu_pct * 2)}%` }} />
                    </div>
                    <div className="flex justify-between items-center text-[7px] font-black text-slate-600 uppercase tracking-tighter">
                      <span>UPTIME: {Math.floor(worker.uptime / 60)}M {worker.uptime % 60}S</span>
                      <span className="text-emerald-500 animate-pulse">{worker.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Task 21.10: Infrastructure Health Terminal */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Infrastructure Health Diagnostics
              </CardTitle>
              <LayoutGrid className="w-4 h-4 text-primary" />
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-slate-800">
                {diagnostics.map((d, i) => (
                  <div key={i} className="p-4 flex justify-between items-center hover:bg-slate-800/30 transition-colors group">
                    <div className="flex items-center gap-3">
                      <div className={`w-1.5 h-1.5 rounded-full ${d.status === 'REACHABLE' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-rose-500 animate-pulse'}`} />
                      <p className="text-xs font-black text-slate-200 uppercase tracking-tight">{d.component}</p>
                    </div>
                    <div className="flex items-center gap-4">
                      {d.latency_ms !== undefined && (
                        <span className="text-[10px] font-mono text-slate-500">{d.latency_ms}ms</span>
                      )}
                      <Badge variant="outline" className={`text-[8px] font-black uppercase ${d.status === 'REACHABLE' ? 'text-emerald-500 border-emerald-500/20' : 'text-rose-500 border-rose-500/20'}`}>
                        {d.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Backup Ledger */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Data Resilience Ledger
              </CardTitle>
              <ShieldCheck className="w-4 h-4 text-emerald-500" />
            </CardHeader>
            <CardContent className="p-0 text-[10px]">
              <ScrollArea className="h-[250px]">
                <div className="divide-y divide-slate-800">
                  {snapshots.map((s, i) => (
                    <div key={i} className="p-4 flex justify-between items-center hover:bg-slate-800/30 transition-colors group">
                      <div className="flex items-center gap-4">
                        <Archive className="w-4 h-4 text-slate-500" />
                        <div>
                          <p className="font-black text-slate-200 uppercase">{s.timestamp}</p>
                          <p className="text-slate-500 uppercase tracking-tighter">SIZE: {s.size_mb.toFixed(2)} MB</p>
                        </div>
                      </div>
                      <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-[8px] font-black">{s.status}</Badge>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* Engine Diagnostics Sidebar */}
        <div className="lg:col-span-4 space-y-8">
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                System Impact Stats
              </CardTitle>
              <Users className="w-4 h-4 text-slate-500" />
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-center">
                <p className="text-[8px] font-black uppercase text-slate-600">Users At Risk</p>
                <p className={`text-3xl font-black ${impactScore?.active_users_at_risk && impactScore.active_users_at_risk > 0 ? 'text-rose-500' : 'text-emerald-500'}`}>
                  {impactScore?.active_users_at_risk || 0}
                </p>
              </div>
              <p className="text-[9px] text-slate-500 leading-relaxed text-center italic">
                Impact score is calculated based on active user density vs. integration failure rates.
              </p>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800 shadow-2xl">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <BrainCircuit className="w-4 h-4 text-primary" />
                Engine Intelligence
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
                  <p className="text-[8px] font-black uppercase text-slate-600 mb-1">Graph Nodes</p>
                  <p className="text-lg font-black text-white">{graphHealth?.nodes?.toLocaleString() || 0}</p>
                </div>
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
                  <p className="text-[8px] font-black uppercase text-slate-600 mb-1">Graph Edges</p>
                  <p className="text-lg font-black text-white">{graphHealth?.edges?.toLocaleString() || 0}</p>
                </div>
              </div>

              <div className="space-y-4 pt-4 border-t border-slate-800">
                {cacheIntel.map(c => (
                  <div key={c.layer} className="space-y-1.5">
                    <div className="flex justify-between text-[9px] font-black uppercase tracking-widest text-slate-400">
                      <span>{c.layer} HIT RATIO</span>
                      <span className="text-primary">{c.hit_ratio}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-primary shadow-[0_0_10px_rgba(59,130,246,0.3)]" style={{ width: `${c.hit_ratio}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Terminal className="w-4 h-4 text-slate-500" />
                Control Commands
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <Button className="w-full bg-slate-800 hover:bg-slate-700 border-slate-700 font-black uppercase text-[10px] tracking-widest h-12" onClick={triggerSnapshot}>
                <HardDrive className="w-4 h-4 mr-3" />
                Force Backup Snapshot
              </Button>
              <Button variant="outline" className="w-full border-rose-500/20 text-rose-500 hover:bg-rose-500/10 font-black uppercase text-[10px] tracking-widest h-12">
                <RefreshCw className="w-4 h-4 mr-3" />
                Flush Global Cache
              </Button>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                High-Friction Nodes
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-slate-800 text-[10px]">
                {frictionLeaderboard.map((e, i) => (
                  <div key={i} className="p-4 flex justify-between items-center hover:bg-slate-800/30 transition-colors">
                    <span className="font-mono text-slate-400 truncate max-w-[150px]">{e.endpoint}</span>
                    <Badge variant="outline" className="bg-rose-500/10 text-rose-500 border-rose-500/20 h-5 font-black text-[8px]">
                      {e.friction_score}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
