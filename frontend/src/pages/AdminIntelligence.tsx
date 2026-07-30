import { useState, useEffect, useCallback } from "react";
import {
  BrainCircuit, Zap, ShieldCheck, TrendingUp, Activity,
  AlertTriangle, RefreshCw, Play, Square, Eye, Cpu,
  Database, BarChart3, Flame, Target, GitBranch,
  CheckCircle2, XCircle, Clock, ArrowUpRight, Layers
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { fetchWithAuth } from "@/lib/apiClient";

/* ─────────────────────────────── Types ─────────────────────────────── */
interface NISWeights  { availability: number; speed: number; comfort: number; safety: number; }
interface AriadneThread { booking_id: string; user_id: string; delay_mins: number; status: "SAFE"|"AT_RISK"|"RECOVERED"; hub: string; }
interface PricingSnapshot { route: string; base_fee: number; dynamic_fee: number; demand: number; scarcity: number; load: number; }
interface ForgeResult    { certification: string; chain_integrity: string; memory_leak_check: string; recovery_velocity_avg_ms: number; }
interface StreamStat     { ttfr_ms: number; chunks_served: number; cache_hit_rate: number; active_streams: number; }
interface ShardStat      { region: string; node_count: number; last_query_ms: number; status: "HOT"|"WARM"|"COLD"; }

/* Small helpers */
const pct = (v: number) => `${(v * 100).toFixed(0)}%`;
const pill = (ok: boolean) => ok
  ? <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-[9px] font-black uppercase">OK</Badge>
  : <Badge className="bg-rose-500/10 text-rose-400 border-rose-500/30 text-[9px] font-black uppercase animate-pulse">ALERT</Badge>;

/* ─────────────────────────────── Page ──────────────────────────────── */
export default function AdminIntelligence() {
  const [weights,    setWeights]    = useState<NISWeights | null>(null);
  const [threads,    setThreads]    = useState<AriadneThread[]>([]);
  const [pricing,    setPricing]    = useState<PricingSnapshot[]>([]);
  const [forge,      setForge]      = useState<ForgeResult | null>(null);
  const [stream,     setStream]     = useState<StreamStat | null>(null);
  const [shards,     setShards]     = useState<ShardStat[]>([]);
  const [drillRunning, setDrillRunning] = useState<string | null>(null);
  const [tuning, setTuning] = useState(false);
  const [loading, setLoading] = useState(true);

  /* Mock-safe fetch helper — returns parsed data or a fallback */
  const safe = async <T,>(url: string, fallback: T): Promise<T> => {
    try { const r = await fetchWithAuth(url); return await r.json(); }
    catch { return fallback; }
  };

  const refresh = useCallback(async () => {
    setLoading(true);
    const [w, thr, price, frg, st, sh] = await Promise.all([
      safe("/v3/intelligence/weights",    { availability: 0.4, speed: 0.25, comfort: 0.2, safety: 0.15 }),
      safe("/v3/ariadne/threads",         [] as AriadneThread[]),
      safe("/v3/yield/snapshot",          [] as PricingSnapshot[]),
      safe("/v3/aegis/audit",             { certification:"PENDING", chain_integrity:"UNKNOWN", memory_leak_check:"UNKNOWN", recovery_velocity_avg_ms:0 }),
      safe("/v3/stream/stats",            { ttfr_ms:0, chunks_served:0, cache_hit_rate:0, active_streams:0 }),
      safe("/v3/shard/status",            [] as ShardStat[]),
    ]);
    setWeights(w); setThreads(thr); setPricing(price); setForge(frg); setStream(st); setShards(sh);
    setLoading(false);
  }, []);

  // Auto tune weights via NIS
  const runAutoTune = async () => {
    setTuning(true);
    try {
      await fetchWithAuth("/v3/intelligence/tune", { method: "POST" });
      toast.success("🧠 NIS Auto-Tune complete — scoring weights updated.");
      await refresh();
    } catch { toast.error("Auto-tune failed"); }
    finally { setTuning(false); }
  };

  // Aegis chaos drill
  const runDrill = async (drill: string) => {
    setDrillRunning(drill);
    try {
      await fetchWithAuth(`/v3/aegis/drill/${drill}`, { method: "POST" });
      toast.warning(`🔨 Drill "${drill}" executed. Monitor recovery…`);
      setTimeout(refresh, 3000);
    } catch { toast.error("Drill command failed"); }
    finally { setTimeout(() => setDrillRunning(null), 3000); }
  };

  useEffect(() => { refresh(); const t = setInterval(refresh, 15000); return () => clearInterval(t); }, [refresh]);

  /* Derived */
  const atRisk  = threads.filter(t => t.status === "AT_RISK").length;
  const surging = pricing.filter(p => p.dynamic_fee > p.base_fee * 1.4).length;

  /* ──────────────────────────── UI ──────────────────────────── */
  return (
    <div className="space-y-8 animate-in fade-in duration-500 pb-16">

      {/* ── Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-violet-600 to-fuchsia-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
            <BrainCircuit className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-black tracking-tight text-white">Intelligence Command Centre</h2>
            <p className="text-[11px] text-slate-500 font-medium tracking-widest uppercase">NIS · Ariadne · Yield · Aegis · Neural Spine</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {atRisk > 0 && (
            <Badge className="bg-amber-500/10 text-amber-400 border-amber-500/30 gap-1.5 animate-pulse">
              <AlertTriangle className="w-3 h-3" /> {atRisk} Thread{atRisk > 1 ? "s" : ""} At Risk
            </Badge>
          )}
          {surging > 0 && (
            <Badge className="bg-rose-500/10 text-rose-400 border-rose-500/30 gap-1.5">
              <Flame className="w-3 h-3" /> {surging} Route{surging > 1 ? "s" : ""} Surging
            </Badge>
          )}
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading}
            className="h-9 text-[10px] font-black uppercase tracking-widest border-slate-700 hover:border-primary">
            <RefreshCw className={`w-3.5 h-3.5 mr-2 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>
      </div>

      {/* ── Row 1: 4 KPI cards ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
        {[
          { label: "NIS Weights Updated",   value: weights ? "ACTIVE" : "—",       icon: <BrainCircuit className="w-5 h-5" />,    color: "violet"  },
          { label: "Ariadne Threads Safe",  value: threads.length > 0 ? `${threads.filter(t=>t.status==="SAFE").length}/${threads.length}` : "0", icon: <GitBranch className="w-5 h-5" />, color: "emerald" },
          { label: "Yield Surge Routes",    value: surging.toString(),              icon: <TrendingUp className="w-5 h-5" />,      color: "amber"   },
          { label: "Aegis Certification",   value: forge?.certification ?? "—",     icon: <ShieldCheck className="w-5 h-5" />,    color: "sky"     },
        ].map(k => (
          <Card key={k.label} className="bg-slate-900 border-slate-800 shadow-xl overflow-hidden group">
            <CardContent className="p-5 flex items-center gap-4">
              <div className={`w-10 h-10 rounded-xl bg-${k.color}-500/10 text-${k.color}-400 flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform`}>
                {k.icon}
              </div>
              <div className="min-w-0">
                <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 truncate">{k.label}</p>
                <p className="text-xl font-black text-white">{k.value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-8">

        {/* ── Left: NIS Brain ── */}
        <div className="lg:col-span-1 space-y-6">

          {/* NIS Scoring Weights */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <BrainCircuit className="w-4 h-4 text-violet-400" /> NIS Auto-Weights
              </CardTitle>
              <Button size="sm" onClick={runAutoTune} disabled={tuning}
                className="h-7 px-3 text-[9px] font-black uppercase tracking-widest bg-violet-600 hover:bg-violet-500">
                {tuning ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3 mr-1" />}
                {tuning ? "Tuning…" : "Auto-Tune"}
              </Button>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              {weights && Object.entries(weights).map(([k, v]) => (
                <div key={k} className="space-y-1.5">
                  <div className="flex justify-between text-[9px] font-black uppercase tracking-widest text-slate-400">
                    <span>{k}</span>
                    <span className="text-violet-400">{pct(v)}</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-violet-600 to-fuchsia-500 rounded-full transition-all duration-700"
                      style={{ width: pct(v) }} />
                  </div>
                </div>
              ))}
              <p className="text-[9px] text-slate-600 italic pt-2">
                Weights dynamically recalibrated by real-world conversion signals.
              </p>
            </CardContent>
          </Card>

          {/* Zero-Block Stream Stats */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400" /> SSE Stream Engine
              </CardTitle>
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
            </CardHeader>
            <CardContent className="p-6 grid grid-cols-2 gap-4">
              {[
                { label: "TTFR",           value: stream ? `${stream.ttfr_ms}ms` : "—" },
                { label: "Active Streams", value: stream?.active_streams ?? 0 },
                { label: "Chunks Served",  value: stream?.chunks_served?.toLocaleString() ?? 0 },
                { label: "Cache Hit Rate", value: stream ? pct(stream.cache_hit_rate) : "—" },
              ].map(s => (
                <div key={s.label} className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
                  <p className="text-[8px] font-black uppercase text-slate-600 mb-1">{s.label}</p>
                  <p className="text-lg font-black text-white">{s.value}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Regional Shards */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Layers className="w-4 h-4 text-sky-400" /> Regional Shards
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-2">
              {shards.length === 0 ? (
                <p className="text-center text-[10px] text-slate-600 py-6 uppercase italic">No shard data</p>
              ) : shards.map(sh => (
                <div key={sh.region} className="flex items-center justify-between p-3 bg-slate-950 rounded-xl border border-slate-800">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${sh.status === "HOT" ? "bg-rose-500 animate-pulse" : sh.status === "WARM" ? "bg-amber-400" : "bg-slate-600"}`} />
                    <p className="text-[10px] font-black uppercase text-slate-300">{sh.region}</p>
                  </div>
                  <div className="flex items-center gap-3 text-[9px] text-slate-500 font-mono">
                    <span>{sh.node_count} nodes</span>
                    <span>{sh.last_query_ms}ms</span>
                    <Badge variant="outline" className={`h-4 text-[7px] font-black uppercase ${sh.status === "HOT" ? "text-rose-400 border-rose-500/30" : sh.status === "WARM" ? "text-amber-400 border-amber-500/30" : "text-slate-500 border-slate-700"}`}>
                      {sh.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* ── Centre: Ariadne + Yield ── */}
        <div className="lg:col-span-1 space-y-6">

          {/* Ariadne Thread Viewer */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-emerald-400" /> Ariadne Threads
              </CardTitle>
              {atRisk > 0 && <Badge className="bg-amber-500 text-white text-[9px] font-black animate-pulse">{atRisk} AT RISK</Badge>}
            </CardHeader>
            <CardContent className="p-0">
              {threads.length === 0 ? (
                <div className="p-10 text-center">
                  <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                  <p className="text-[10px] text-slate-600 uppercase font-black">All Threads Safe</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-800 max-h-72 overflow-y-auto">
                  {threads.map(t => (
                    <div key={t.booking_id} className={`p-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors ${t.status === "AT_RISK" ? "border-l-2 border-l-amber-500" : t.status === "RECOVERED" ? "border-l-2 border-l-emerald-500" : ""}`}>
                      <div>
                        <p className="text-[10px] font-black text-slate-200 font-mono">{t.booking_id.slice(0, 12)}…</p>
                        <p className="text-[9px] text-slate-500">Hub: <span className="text-slate-400">{t.hub}</span> · Delay: <span className={t.delay_mins > 60 ? "text-rose-400" : "text-amber-400"}>{t.delay_mins}m</span></p>
                      </div>
                      <Badge className={`text-[8px] font-black uppercase ${t.status === "SAFE" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : t.status === "AT_RISK" ? "bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse" : "bg-sky-500/10 text-sky-400 border-sky-500/20"}`}>
                        {t.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Yield / Surge Pricing */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Flame className="w-4 h-4 text-rose-400" /> Yield Surge Monitor
              </CardTitle>
              <p className="text-[9px] font-black text-slate-500 uppercase">Live ₹ Prices</p>
            </CardHeader>
            <CardContent className="p-0">
              {pricing.length === 0 ? (
                <p className="p-8 text-center text-[10px] text-slate-600 uppercase italic">No active surge routes</p>
              ) : (
                <div className="divide-y divide-slate-800 max-h-72 overflow-y-auto">
                  {pricing.map((p, i) => {
                    const multiplier = p.dynamic_fee / p.base_fee;
                    const isSurging = multiplier > 1.3;
                    return (
                      <div key={i} className="p-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors">
                        <div>
                          <p className="text-[10px] font-black text-slate-200 uppercase">{p.route}</p>
                          <div className="flex gap-2 mt-0.5 text-[9px] text-slate-500">
                            <span>D:{(p.demand*100).toFixed(0)}%</span>
                            <span>S:{(p.scarcity*100).toFixed(0)}%</span>
                            <span>L:{(p.load*100).toFixed(0)}%</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className={`text-base font-black ${isSurging ? "text-rose-400" : "text-white"}`}>₹{p.dynamic_fee}</p>
                          <p className="text-[8px] text-slate-600">Base ₹{p.base_fee} · <span className={isSurging ? "text-rose-400" : "text-emerald-400"}>{multiplier.toFixed(2)}x</span></p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ── Right: Aegis Forge ── */}
        <div className="lg:col-span-1 space-y-6">

          {/* Certification Badge */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-sky-400" /> Aegis Certification
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className={`rounded-2xl border p-6 text-center ${forge?.certification === "DIAMOND" ? "border-sky-500/30 bg-sky-500/5" : forge?.certification === "PLATINUM" ? "border-violet-500/30 bg-violet-500/5" : "border-slate-700 bg-slate-950"}`}>
                <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-2">Current Status</p>
                <p className={`text-4xl font-black ${forge?.certification === "DIAMOND" ? "text-sky-400" : forge?.certification === "PLATINUM" ? "text-violet-400" : "text-slate-500"}`}>
                  {forge?.certification ?? "—"}
                </p>
              </div>
              {forge && [
                { label: "Chain Integrity",    value: forge.chain_integrity,     ok: forge.chain_integrity === "STABLE"   },
                { label: "Memory Leak Check",  value: forge.memory_leak_check,   ok: forge.memory_leak_check === "CLEAN"  },
                { label: "Recovery Velocity",  value: `${forge.recovery_velocity_avg_ms}ms avg`, ok: forge.recovery_velocity_avg_ms < 500 },
              ].map(row => (
                <div key={row.label} className="flex items-center justify-between">
                  <p className="text-[9px] font-black uppercase text-slate-500">{row.label}</p>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-slate-300">{row.value}</span>
                    {pill(row.ok)}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Chaos Drill Console */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Activity className="w-4 h-4 text-rose-400" /> Aegis Forge Drills
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5 space-y-3">
              {[
                { id: "SHARD_REAPER",  label: "⚡ Shard Reaper",   desc: "Kill compute shard · verify auto-resurrection" },
                { id: "SHM_POISON",    label: "☣️ SHM Poison",     desc: "Corrupt shared memory · verify safe fallback"  },
                { id: "DB_POISON",     label: "💀 DB Poison",      desc: "Block ledger writes · verify SAGA rollback"    },
                { id: "RESOURCE_FLOOD",label: "🌊 Resource Flood", desc: "Spike CPU/RAM · verify governor shed logic"    },
              ].map(drill => (
                <button
                  key={drill.id}
                  onClick={() => runDrill(drill.id)}
                  disabled={drillRunning !== null}
                  className="w-full text-left bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-rose-500/30 rounded-xl p-4 transition-all group disabled:opacity-40"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-[10px] font-black uppercase text-slate-300 group-hover:text-white">{drill.label}</p>
                    {drillRunning === drill.id
                      ? <RefreshCw className="w-3.5 h-3.5 text-rose-400 animate-spin" />
                      : <Play className="w-3 h-3 text-slate-600 group-hover:text-rose-400" />
                    }
                  </div>
                  <p className="text-[9px] text-slate-600 mt-1 group-hover:text-slate-400">{drill.desc}</p>
                </button>
              ))}
              <Button variant="outline" size="sm" className="w-full h-9 text-[9px] font-black uppercase tracking-widest border-slate-700 hover:border-sky-500/50 mt-2"
                onClick={async () => { await fetchWithAuth("/v3/aegis/audit", { method: "GET" }); refresh(); toast.success("Resilience audit complete"); }}>
                <Eye className="w-3.5 h-3.5 mr-2" /> Run Full Resilience Audit
              </Button>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl">
            <CardContent className="p-5 space-y-3">
              <p className="text-[9px] font-black uppercase tracking-widest text-slate-500">Quick Actions</p>
              {[
                { label: "Flush CerebralCache",   action: () => { fetchWithAuth("/v3/synapse/flush", { method:"POST" }); toast.success("Cache flushed"); } },
                { label: "Force NIS Observation", action: () => { fetchWithAuth("/v3/intelligence/observe", { method:"POST" }); toast.success("Observation cycle triggered"); } },
                { label: "Stop All Chaos",         action: () => { fetchWithAuth("/v3/aegis/stop", { method:"POST" }); toast.success("All drills ceased"); } },
              ].map(a => (
                <Button key={a.label} variant="outline" size="sm" className="w-full h-9 text-[9px] font-black uppercase tracking-widest border-slate-800 hover:border-slate-600"
                  onClick={a.action}>
                  {a.label}
                </Button>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
