import { useState, useEffect, useCallback } from "react";
import {
  BrainCircuit,
  Play,
  Pause,
  RotateCcw,
  Activity,
  Zap,
  CircleDot,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  ArrowUpRight,
  Sparkles,
  Shield,
  TrendingUp,
  Server,
  HeadphonesIcon,
  BarChart3,
  Scale,
  AlertTriangle,
  RefreshCw,
  Bot,
  Cpu,
} from "lucide-react";
import { fetchWithAuth } from "@/lib/apiClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";

// ─── Types ───

interface AgentMetrics {
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  avg_duration_ms: number;
  last_execution: string | null;
  last_error: string | null;
}

interface Agent {
  name: string;
  description: string;
  category: string;
  priority: string;
  icon: string;
  color: string;
  version: string;
  status: string;
  enabled: boolean;
  auto_schedule_interval: number | null;
  metrics: AgentMetrics;
}

interface SwarmStatus {
  total_agents: number;
  enabled: number;
  running: number;
  idle: number;
  failed: number;
  paused: number;
  categories: Record<string, number>;
  total_executions: number;
  success_rate: number;
  uptime_seconds: number;
  is_running: boolean;
}

interface ExecutionRecord {
  agent: string;
  timestamp: string;
  status: string;
  duration_ms: number;
  summary: string;
}

// ─── Helpers ───

const categoryConfig: Record<string, { icon: any; label: string; gradient: string }> = {
  finance: { icon: TrendingUp, label: "Finance", gradient: "from-emerald-500/20 to-emerald-600/5" },
  operations: { icon: Zap, label: "Operations", gradient: "from-amber-500/20 to-amber-600/5" },
  growth: { icon: ArrowUpRight, label: "Growth", gradient: "from-violet-500/20 to-violet-600/5" },
  infrastructure: { icon: Server, label: "Infrastructure", gradient: "from-blue-500/20 to-blue-600/5" },
  support: { icon: HeadphonesIcon, label: "Support", gradient: "from-cyan-500/20 to-cyan-600/5" },
  analytics: { icon: BarChart3, label: "Analytics", gradient: "from-purple-500/20 to-purple-600/5" },
  intelligence: { icon: BrainCircuit, label: "Intelligence", gradient: "from-blue-500/20 to-blue-600/5" },
  routing: { icon: Zap, label: "Routing", gradient: "from-amber-500/20 to-amber-600/5" },
  compliance: { icon: Scale, label: "Compliance", gradient: "from-slate-500/20 to-slate-600/5" },
};

const statusColors: Record<string, string> = {
  idle: "text-slate-400 bg-slate-400/10 border-slate-400/20",
  running: "text-blue-400 bg-blue-400/10 border-blue-400/20",
  success: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  failed: "text-rose-400 bg-rose-400/10 border-rose-400/20",
  degraded: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  paused: "text-slate-500 bg-slate-500/10 border-slate-500/20",
};

const priorityColors: Record<string, string> = {
  critical: "text-rose-400 border-rose-400/30",
  high: "text-amber-400 border-amber-400/30",
  normal: "text-blue-400 border-blue-400/30",
  low: "text-slate-400 border-slate-400/30",
  background: "text-slate-500 border-slate-500/30",
};

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

function formatTimeAgo(isoString: string | null): string {
  if (!isoString) return "Never";
  const diff = (Date.now() - new Date(isoString).getTime()) / 1000;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  return `${Math.round(diff / 3600)}h ago`;
}

// ─── Component ───

export default function AdminAgents() {
  const [swarmStatus, setSwarmStatus] = useState<SwarmStatus | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [history, setHistory] = useState<ExecutionRecord[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [agentEvents, setAgentEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningAgent, setRunningAgent] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [statusRes, agentsRes, historyRes] = await Promise.all([
        fetchWithAuth("/v2/agents/swarm/status"),
        fetchWithAuth("/v2/agents/swarm/agents"),
        fetchWithAuth("/v2/agents/swarm/history?limit=30"),
      ]);
      setSwarmStatus(await statusRes.json());
      setAgents(await agentsRes.json());
      setHistory(await historyRes.json());
    } catch (err) {
      console.error("Swarm refresh error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 10000);
    return () => clearInterval(interval);
  }, [refresh]);

  const loadAgentDetail = async (agent: Agent) => {
    setSelectedAgent(agent);
    try {
      const res = await fetchWithAuth(`/v2/agents/agent/${agent.name}/events?limit=20`);
      setAgentEvents(await res.json());
    } catch {
      setAgentEvents([]);
    }
  };

  const runAgent = async (agentName: string) => {
    setRunningAgent(agentName);
    try {
      const res = await fetchWithAuth(`/v2/agents/agent/${agentName}/run`, { method: "POST" });
      const result = await res.json();
      toast.success(`${agentName}: ${result.summary || "Executed"}`, {
        description: `${result.duration_ms}ms | Attempt ${result.attempt || 1}`,
      });
      await refresh();
      if (selectedAgent?.name === agentName) {
        await loadAgentDetail({ ...selectedAgent, status: result.status || "success" });
      }
    } catch (err: any) {
      toast.error(`${agentName} failed`, { description: err.message });
    } finally {
      setRunningAgent(null);
    }
  };

  const toggleAgent = async (agentName: string, currentlyEnabled: boolean) => {
    const action = currentlyEnabled ? "pause" : "resume";
    try {
      await fetchWithAuth(`/v2/agents/agent/${agentName}/${action}`, { method: "POST" });
      toast.success(`${agentName} ${action}d`);
      await refresh();
    } catch (err: any) {
      toast.error(`Failed to ${action} ${agentName}`);
    }
  };

  const resetAgent = async (agentName: string) => {
    try {
      await fetchWithAuth(`/v2/agents/agent/${agentName}/reset`, { method: "POST" });
      toast.success(`${agentName} metrics reset`);
      await refresh();
    } catch {
      toast.error("Reset failed");
    }
  };

  const runAll = async () => {
    try {
      toast.info("Running all agents...");
      await fetchWithAuth("/v2/agents/swarm/run-all", { method: "POST" });
      toast.success("All agents executed");
      await refresh();
    } catch {
      toast.error("Swarm execution failed");
    }
  };

  const runCategory = async (category: string) => {
    try {
      toast.info(`Running ${category} agents...`);
      await fetchWithAuth(`/v2/agents/category/${category}/run`, { method: "POST" });
      toast.success(`All ${category} agents executed`);
      await refresh();
    } catch {
      toast.error(`${category} execution failed`);
    }
  };

  const filteredAgents = selectedCategory
    ? agents.filter((a) => a.category === selectedCategory)
    : agents;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="w-16 h-16 rounded-full border-4 border-primary/20 border-t-primary animate-spin" />
            <Bot className="w-6 h-6 text-primary absolute inset-0 m-auto animate-pulse" />
          </div>
          <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-500">
            Connecting to Agent Swarm...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* ─── Header ─── */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-black uppercase tracking-tight flex items-center gap-3">
            <div className="relative">
              <BrainCircuit className="w-7 h-7 text-primary" />
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-emerald-500 rounded-full border-2 border-slate-950 animate-pulse" />
            </div>
            Agent Command Center
          </h2>
          <p className="text-xs text-slate-500 mt-1 uppercase tracking-widest font-bold">
            {swarmStatus?.total_agents} autonomous agents managing your business
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refresh}
            className="h-8 text-[10px] font-black uppercase border-slate-700 text-slate-400 hover:text-white hover:border-primary/50"
          >
            <RefreshCw className="w-3 h-3 mr-1" />
            Refresh
          </Button>
          <Button
            onClick={runAll}
            size="sm"
            className="h-8 text-[10px] font-black uppercase bg-primary hover:bg-primary/90 shadow-[0_0_15px_rgba(59,130,246,0.3)]"
          >
            <Sparkles className="w-3 h-3 mr-1" />
            Execute All
          </Button>
        </div>
      </div>

      {/* ─── Swarm Vitals ─── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <VitalCard label="Total Agents" value={swarmStatus?.total_agents ?? 0} icon={Bot} color="text-primary" />
        <VitalCard label="Active" value={swarmStatus?.enabled ?? 0} icon={CheckCircle2} color="text-emerald-500" />
        <VitalCard label="Running" value={swarmStatus?.running ?? 0} icon={Loader2} color="text-blue-400" spinning />
        <VitalCard label="Failed" value={swarmStatus?.failed ?? 0} icon={XCircle} color="text-rose-500" />
        <VitalCard label="Success Rate" value={`${swarmStatus?.success_rate ?? 100}%`} icon={Activity} color="text-emerald-400" />
        <VitalCard label="Uptime" value={formatDuration(swarmStatus?.uptime_seconds ?? 0)} icon={Clock} color="text-amber-400" />
      </div>

      {/* ─── Category Navigation ─── */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setSelectedCategory(null)}
          className={`px-4 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${
            !selectedCategory
              ? "bg-primary text-white shadow-[0_0_15px_rgba(59,130,246,0.3)]"
              : "bg-slate-800/50 text-slate-400 hover:text-white hover:bg-slate-800"
          }`}
        >
          All ({agents.length})
        </button>
        {Object.entries(categoryConfig).map(([key, cfg]) => {
          const count = swarmStatus?.categories[key] ?? 0;
          if (count === 0) return null;
          const Icon = cfg.icon;
          return (
            <button
              key={key}
              onClick={() => setSelectedCategory(key)}
              className={`px-4 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all flex items-center gap-2 ${
                selectedCategory === key
                  ? "bg-primary text-white shadow-[0_0_15px_rgba(59,130,246,0.3)]"
                  : "bg-slate-800/50 text-slate-400 hover:text-white hover:bg-slate-800"
              }`}
            >
              <Icon className="w-3 h-3" />
              {cfg.label} ({count})
            </button>
          );
        })}
      </div>

      {/* ─── Main Grid ─── */}
      <div className="grid lg:grid-cols-12 gap-6">
        {/* Agent List */}
        <div className="lg:col-span-7 space-y-3">
          {selectedCategory && (
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                {categoryConfig[selectedCategory]?.label} Agents
              </h3>
              <Button
                variant="outline"
                size="sm"
                onClick={() => runCategory(selectedCategory)}
                className="h-7 text-[9px] font-black uppercase border-slate-700 text-primary hover:bg-primary/10"
              >
                <Play className="w-3 h-3 mr-1" />
                Run Category
              </Button>
            </div>
          )}

          {filteredAgents.map((agent) => (
            <AgentCard
              key={agent.name}
              agent={agent}
              isSelected={selectedAgent?.name === agent.name}
              isRunning={runningAgent === agent.name}
              onSelect={() => loadAgentDetail(agent)}
              onRun={() => runAgent(agent.name)}
              onToggle={() => toggleAgent(agent.name, agent.enabled)}
              onReset={() => resetAgent(agent.name)}
            />
          ))}
        </div>

        {/* Detail Panel */}
        <div className="lg:col-span-5 space-y-4">
          {selectedAgent ? (
            <AgentDetailPanel agent={selectedAgent} events={agentEvents} />
          ) : (
            <Card className="bg-slate-900 border-slate-800 shadow-2xl">
              <CardContent className="p-12 flex flex-col items-center gap-4 text-center">
                <div className="w-16 h-16 rounded-2xl bg-slate-800/50 flex items-center justify-center border border-slate-700/50">
                  <Cpu className="w-8 h-8 text-slate-600" />
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-400">Select an Agent</p>
                  <p className="text-xs text-slate-600 mt-1">
                    Click on any agent card to view its detailed telemetry, event log, and execution history.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Execution Feed */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl">
            <CardHeader className="border-b border-slate-800 py-3 bg-slate-900/50">
              <CardTitle className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-primary" />
                Live Execution Feed
              </CardTitle>
            </CardHeader>
            <ScrollArea className="h-72">
              <CardContent className="p-0">
                {history.length === 0 ? (
                  <p className="p-8 text-center text-xs text-slate-600 italic">
                    No executions yet. Run an agent to see activity here.
                  </p>
                ) : (
                  <div className="divide-y divide-slate-800/50">
                    {history.map((record, i) => (
                      <div
                        key={i}
                        className="px-4 py-3 hover:bg-slate-800/20 transition-colors flex items-start gap-3"
                      >
                        <div className="mt-0.5">
                          {record.status === "success" ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                          ) : (
                            <XCircle className="w-3.5 h-3.5 text-rose-500" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-black text-slate-300 uppercase">
                              {record.agent}
                            </span>
                            <span className="text-[9px] text-slate-600 font-mono">
                              {record.duration_ms}ms
                            </span>
                          </div>
                          <p className="text-[10px] text-slate-500 truncate mt-0.5">
                            {record.summary}
                          </p>
                        </div>
                        <span className="text-[9px] text-slate-600 font-mono whitespace-nowrap">
                          {formatTimeAgo(record.timestamp)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </ScrollArea>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-Components ───

function VitalCard({
  label,
  value,
  icon: Icon,
  color,
  spinning,
}: {
  label: string;
  value: string | number;
  icon: any;
  color: string;
  spinning?: boolean;
}) {
  return (
    <Card className="bg-slate-900 border-slate-800 shadow-xl relative overflow-hidden group hover:border-slate-700 transition-all">
      <CardContent className="p-4 space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-[9px] font-black uppercase tracking-[0.15em] text-slate-500">{label}</p>
          <Icon
            className={`w-4 h-4 ${color} ${spinning ? "animate-spin" : ""} group-hover:scale-110 transition-transform`}
          />
        </div>
        <p className={`text-2xl font-black tracking-tighter ${color}`}>{value}</p>
      </CardContent>
      <div className={`absolute inset-0 bg-gradient-to-br ${color.replace("text-", "from-")}/5 to-transparent pointer-events-none`} />
    </Card>
  );
}

function AgentCard({
  agent,
  isSelected,
  isRunning,
  onSelect,
  onRun,
  onToggle,
  onReset,
}: {
  agent: Agent;
  isSelected: boolean;
  isRunning: boolean;
  onSelect: () => void;
  onRun: () => void;
  onToggle: () => void;
  onReset: () => void;
}) {
  const successRate =
    agent.metrics.total_executions > 0
      ? Math.round((agent.metrics.successful_executions / agent.metrics.total_executions) * 100)
      : 100;

  return (
    <div
      onClick={onSelect}
      className={`
        group cursor-pointer rounded-xl border transition-all duration-200
        ${
          isSelected
            ? "bg-slate-800/60 border-primary/40 shadow-[0_0_20px_rgba(59,130,246,0.15)]"
            : "bg-slate-900 border-slate-800 hover:border-slate-700 hover:bg-slate-800/30"
        }
        ${!agent.enabled ? "opacity-50" : ""}
      `}
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center text-lg border border-slate-700/50 shrink-0"
            style={{ backgroundColor: agent.color + "15" }}
          >
            {agent.icon}
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-black text-white truncate">{agent.name}</span>
              <Badge
                variant="outline"
                className={`text-[8px] px-1.5 py-0 h-4 font-mono ${statusColors[agent.status] ?? statusColors.idle}`}
              >
                {agent.status.toUpperCase()}
              </Badge>
              <Badge
                variant="outline"
                className={`text-[8px] px-1.5 py-0 h-4 font-mono ${priorityColors[agent.priority] ?? ""}`}
              >
                {agent.priority.toUpperCase()}
              </Badge>
            </div>
            <p className="text-[10px] text-slate-500 mt-0.5 truncate">{agent.description}</p>

            {/* Mini Stats */}
            <div className="flex items-center gap-4 mt-2">
              <span className="text-[9px] text-slate-600 font-mono">
                {agent.metrics.total_executions} runs
              </span>
              <span className="text-[9px] text-slate-600 font-mono">
                {successRate}% ok
              </span>
              <span className="text-[9px] text-slate-600 font-mono">
                ~{agent.metrics.avg_duration_ms}ms
              </span>
              <span className="text-[9px] text-slate-600 font-mono">
                {formatTimeAgo(agent.metrics.last_execution)}
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRun();
              }}
              disabled={isRunning || !agent.enabled}
              className="w-7 h-7 rounded-lg bg-primary/10 hover:bg-primary/20 flex items-center justify-center text-primary transition-colors disabled:opacity-30"
              title="Run"
            >
              {isRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggle();
              }}
              className={`w-7 h-7 rounded-lg flex items-center justify-center transition-colors ${
                agent.enabled
                  ? "bg-amber-500/10 hover:bg-amber-500/20 text-amber-500"
                  : "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-500"
              }`}
              title={agent.enabled ? "Pause" : "Resume"}
            >
              {agent.enabled ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onReset();
              }}
              className="w-7 h-7 rounded-lg bg-slate-700/30 hover:bg-slate-700/50 flex items-center justify-center text-slate-400 transition-colors"
              title="Reset"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Progress bar */}
      {agent.metrics.total_executions > 0 && (
        <div className="h-0.5 bg-slate-800 rounded-b-xl overflow-hidden">
          <div
            className={`h-full transition-all duration-1000 ${successRate >= 90 ? "bg-emerald-500" : successRate >= 70 ? "bg-amber-500" : "bg-rose-500"}`}
            style={{ width: `${successRate}%` }}
          />
        </div>
      )}
    </div>
  );
}

function AgentDetailPanel({ agent, events }: { agent: Agent; events: any[] }) {
  const successRate =
    agent.metrics.total_executions > 0
      ? Math.round((agent.metrics.successful_executions / agent.metrics.total_executions) * 100)
      : 100;

  return (
    <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
      {/* Header */}
      <div
        className="p-5 border-b border-slate-800"
        style={{
          background: `linear-gradient(135deg, ${agent.color}10, transparent)`,
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center text-xl border border-slate-700/50"
            style={{ backgroundColor: agent.color + "20" }}
          >
            {agent.icon}
          </div>
          <div>
            <h3 className="text-base font-black text-white">{agent.name}</h3>
            <p className="text-[10px] text-slate-500 mt-0.5">
              v{agent.version} • {agent.category} • {agent.priority} priority
            </p>
          </div>
        </div>
        <p className="text-xs text-slate-400 mt-3">{agent.description}</p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-3 divide-x divide-slate-800 border-b border-slate-800">
        <MetricBlock label="Executions" value={agent.metrics.total_executions} />
        <MetricBlock label="Success" value={`${successRate}%`} color={successRate >= 90 ? "text-emerald-400" : "text-amber-400"} />
        <MetricBlock label="Avg Time" value={`${agent.metrics.avg_duration_ms}ms`} />
      </div>

      {/* Auto Schedule */}
      {agent.auto_schedule_interval && (
        <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">
            Auto Schedule
          </span>
          <Badge variant="outline" className="text-[9px] font-mono border-slate-700 text-slate-400">
            Every {formatDuration(agent.auto_schedule_interval)}
          </Badge>
        </div>
      )}

      {/* Event Log */}
      <CardHeader className="border-b border-slate-800 py-3 bg-slate-900/50">
        <CardTitle className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
          Event Log
        </CardTitle>
      </CardHeader>
      <ScrollArea className="h-48">
        <CardContent className="p-0">
          {events.length === 0 ? (
            <p className="p-6 text-center text-[10px] text-slate-600 italic">
              No events recorded yet. Run this agent to generate events.
            </p>
          ) : (
            <div className="divide-y divide-slate-800/30">
              {events.map((evt: any, i: number) => (
                <div key={i} className="px-4 py-2.5 flex items-center gap-2.5">
                  {evt.status === "success" ? (
                    <CheckCircle2 className="w-3 h-3 text-emerald-500 shrink-0" />
                  ) : evt.status === "error" ? (
                    <XCircle className="w-3 h-3 text-rose-500 shrink-0" />
                  ) : evt.status === "warning" ? (
                    <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" />
                  ) : (
                    <CircleDot className="w-3 h-3 text-slate-500 shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] text-slate-400 truncate">{evt.message}</p>
                  </div>
                  {evt.duration_ms > 0 && (
                    <span className="text-[9px] font-mono text-slate-600">{evt.duration_ms}ms</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </ScrollArea>

      {/* Last Error */}
      {agent.metrics.last_error && (
        <div className="px-5 py-3 bg-rose-500/5 border-t border-rose-500/20">
          <p className="text-[10px] font-bold text-rose-400 flex items-center gap-1.5">
            <AlertTriangle className="w-3 h-3" />
            Last Error
          </p>
          <p className="text-[10px] text-rose-300/70 mt-1 font-mono">{agent.metrics.last_error}</p>
        </div>
      )}
    </Card>
  );
}

function MetricBlock({
  label,
  value,
  color = "text-white",
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="p-4 text-center">
      <p className="text-[9px] font-black uppercase tracking-widest text-slate-600">{label}</p>
      <p className={`text-lg font-black tracking-tight mt-1 ${color}`}>{value}</p>
    </div>
  );
}
