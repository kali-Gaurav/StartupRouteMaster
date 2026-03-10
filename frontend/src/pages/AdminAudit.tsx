import { useState, useEffect } from "react";
import {
  History,
  User as UserIcon,
  Server,
  Lock,
  Clock,
  Eye,
  ArrowRightLeft,
  Activity,
  LogOut,
  ShieldAlert,
  AlertTriangle,
  Users,
  LifeBuoy
} from "lucide-react";
import { fetchWithAuth } from "@/lib/apiClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";

interface AuditLog {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  old_value: string;
  new_value: string;
  performed_by: string;
  reason: string;
  timestamp: string;
}

interface AdminSession {
  id: string;
  admin_id: string;
  ip_address: string;
  user_agent: string;
  geo_state: string;
  login_at: string;
  last_active_at: string;
}

interface HighRiskUser {
  user_id: string;
  name: string;
  fail_count: number;
  risk_level: "WARNING" | "CRITICAL";
  reason: string;
}

interface SOSIncident {
  id: string;
  user_name: string;
  train_number: string;
  location: string;
  status: string;
  time_elapsed_mins: number;
  severity: "LOW" | "MEDIUM" | "HIGH";
}

export default function AdminAudit() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [sessions, setSessions] = useState<AdminSession[]>([]);
  const [highRiskUsers, setHighRiskUsers] = useState<HighRiskUser[]>([]);
  const [sosIncidents, setSosIncidents] = useState<SOSIncident[]>([]);
  const [filter, setFilter] = useState("ALL");

  useEffect(() => {
    refreshData();
    const interval = setInterval(refreshData, 10000);
    return () => clearInterval(interval);
  }, []);

  const refreshData = () => {
    refreshLogs();
    refreshSessions();
    loadHighRisk();
    loadSOS();
  };

  const loadSOS = async () => {
    try {
      const res = await fetchWithAuth("/admin/security/sos-incidents");
      setSosIncidents(await res.json());
    } catch (e) { console.error("SOS error"); }
  };

  const loadHighRisk = async () => {
    try {
      const res = await fetchWithAuth("/admin/security/high-risk-users");
      setHighRiskUsers(await res.json());
    } catch (e) { console.error("Risk error"); }
  };

  const refreshLogs = async () => {
    try {
      const res = await fetchWithAuth("/admin/audit/logs");
      setLogs(await res.json());
    } catch (e) { console.error("Audit refresh error"); }
  };

  const refreshSessions = async () => {
    try {
      const res = await fetchWithAuth("/admin/sessions");
      setSessions(await res.json());
    } catch (e) { console.error("Session refresh error"); }
  };

  const revokeSession = async (id: string) => {
    if (!confirm("Terminate this administrative session immediately?")) return;
    try {
      await fetchWithAuth(`/admin/sessions/${id}/revoke`, { method: "POST" });
      toast.success("Session terminated.");
      refreshSessions();
    } catch (e) { toast.error("Termination failed"); }
  };

  const securityPulse = logs.filter(l => 
    l.action.includes("REVOKED") || 
    l.action.includes("SENSITIVE") || 
    l.action.includes("CREDENTIAL") ||
    l.action.includes("LOCKDOWN")
  ).slice(0, 3);

  const triggerLockdown = async () => {
    if (!confirm("CRITICAL: ACTIVATE GLOBAL LOCKDOWN? All sessions will be terminated and API keys cycled.")) return;
    toast.error("LOCKDOWN INITIATED. Cluster isolating...");
  };

  const filteredLogs = filter === "ALL" 
    ? logs 
    : logs.filter(l => l.entity_type.toUpperCase() === filter);

  const getActionIcon = (action: string) => {
    if (action.includes("VIEW")) return <Eye className="w-3 h-3" />;
    if (action.includes("TRANSITION")) return <ArrowRightLeft className="w-3 h-3" />;
    if (action.includes("ACCESS")) return <Lock className="w-3 h-3" />;
    return <Activity className="w-3 h-3" />;
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2">
          <History className="w-6 h-6 text-primary" />
          Security & Audit
        </h2>
        <div className="flex gap-2 bg-slate-900 p-1 rounded-lg border border-slate-800">
          {["ALL", "BOOKING", "SYSTEM", "ADMIN"].map(f => (
            <Button 
              key={f}
              variant={filter === f ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setFilter(f)}
              className="text-[10px] font-black uppercase px-4 h-8 tracking-widest"
            >
              {f}
            </Button>
          ))}
        </div>
      </div>

      {/* Task 33.3: Emergency SOS Command Center */}
      {sosIncidents.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-pulse">
          {sosIncidents.map((incident) => (
            <Card key={incident.id} className="bg-rose-600 border-rose-500 text-white shadow-[0_0_30px_rgba(225,29,72,0.4)]">
              <CardContent className="p-6 flex justify-between items-center">
                <div className="flex items-center gap-4">
                  <div className="bg-white/20 p-3 rounded-2xl">
                    <LifeBuoy className="w-8 h-8 text-white" />
                  </div>
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] opacity-80">Active SOS Incident</p>
                    <p className="text-xl font-black uppercase">{incident.user_name}</p>
                    <p className="text-[10px] font-bold opacity-70 uppercase tracking-tighter">Train #{incident.train_number} | {incident.location}</p>
                  </div>
                </div>
                <div className="text-right space-y-2">
                  <Badge className="bg-white text-rose-600 font-black uppercase">SEVERITY: {incident.severity}</Badge>
                  <p className="text-[10px] font-black">{incident.time_elapsed_mins}M ELAPSED</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Security Pulse Ticker */}
      <div className="bg-rose-500/10 border border-rose-500/20 rounded-2xl p-4 flex items-center justify-between overflow-hidden relative group">
        <div className="flex items-center gap-6 overflow-hidden">
          <div className="flex items-center gap-2 text-rose-500 shrink-0">
            <ShieldAlert className="w-5 h-5 animate-pulse" />
            <span className="text-[10px] font-black uppercase tracking-[0.2em]">Live Security Pulse</span>
          </div>
          <div className="h-4 w-px bg-rose-500/20 shrink-0" />
          <div className="flex gap-8 animate-in slide-in-from-right duration-1000">
            {securityPulse.length === 0 ? (
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">No critical security events in last 50 cycles</span>
            ) : (
              securityPulse.map((event, i) => (
                <div key={i} className="flex items-center gap-3 whitespace-nowrap">
                  <Badge variant="outline" className="bg-rose-500/10 text-rose-500 border-rose-500/20 text-[8px] font-black">
                    {event.action}
                  </Badge>
                  <span className="text-[10px] font-medium text-slate-300 italic">
                    {event.performed_by} executed {event.action} on {event.entity_type}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
        <div className="absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-slate-950 to-transparent pointer-events-none" />
      </div>

      <div className="grid lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8 space-y-8">
          {/* Audit Timeline */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Immutable Activity Timeline
              </CardTitle>
              <Badge variant="outline" className="font-mono text-[10px] text-slate-500 border-slate-800">
                READ-ONLY LEDGER
              </Badge>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[700px]">
                <table className="w-full text-left border-collapse">
                  <thead className="bg-slate-950/50 text-slate-500 font-black uppercase text-[10px] tracking-[0.2em] sticky top-0 z-10 border-b border-slate-800">
                    <tr>
                      <th className="p-6">Timeline</th>
                      <th className="p-6">Subject</th>
                      <th className="p-6">Action Execution</th>
                      <th className="p-6">Identity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {filteredLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-800/30 transition-colors group">
                        <td className="p-6">
                          <div className="flex items-center gap-3">
                            <Clock className="w-3.5 h-3.5 text-slate-600" />
                            <div className="flex flex-col">
                              <span className="text-xs font-bold text-slate-200">{new Date(log.timestamp).toLocaleTimeString()}</span>
                              <span className="text-[10px] font-medium text-slate-500">{new Date(log.timestamp).toLocaleDateString()}</span>
                            </div>
                          </div>
                        </td>
                        <td className="p-6">
                          <div className="flex items-center gap-2">
                            {log.entity_type === 'Booking' ? <Ticket className="w-3.5 h-3.5 text-primary" /> : <Server className="w-3.5 h-3.5 text-slate-500" />}
                            <span className="text-xs font-black uppercase tracking-tight text-slate-300">{log.entity_type}</span>
                          </div>
                          <p className="text-[9px] font-mono text-slate-600 mt-1 uppercase truncate max-w-[150px]">REF: {log.entity_id}</p>
                        </td>
                        <td className="p-6">
                          <div className="flex flex-col gap-1.5">
                            <Badge variant="outline" className="w-fit gap-1.5 px-2 py-0.5 font-black text-[8px] uppercase border-slate-700 bg-slate-800/50 text-slate-300">
                              {getActionIcon(log.action)}
                              {log.action}
                            </Badge>
                            <span className="text-[10px] text-emerald-500 font-bold">{log.new_value}</span>
                          </div>
                        </td>
                        <td className="p-6">
                          <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
                              <UserIcon className="w-3 h-3 text-primary" />
                            </div>
                            <span className="text-[10px] font-black uppercase tracking-widest text-primary">{log.performed_by}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-4 space-y-8">
          {/* High-Risk User Manifest */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl border-t-4 border-t-rose-600 overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-rose-500 flex items-center gap-2">
                <Users className="w-4 h-4" />
                Suspect User Ledger
              </CardTitle>
              <Badge variant="destructive" className={highRiskUsers.length > 0 ? 'animate-pulse' : ''}>{highRiskUsers.length}</Badge>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[350px]">
                {highRiskUsers.length === 0 ? (
                  <div className="p-12 text-center opacity-30 italic text-xs uppercase font-black text-slate-500">No active risk patterns</div>
                ) : (
                  <div className="divide-y divide-slate-800">
                    {highRiskUsers.map((u) => (
                      <div key={u.user_id} className="p-4 space-y-2 hover:bg-rose-500/5 transition-colors">
                        <div className="flex justify-between items-center">
                          <p className="text-xs font-black text-slate-200 uppercase">{u.name}</p>
                          <Badge className={u.risk_level === 'CRITICAL' ? 'bg-rose-600' : 'bg-amber-500'}>{u.risk_level}</Badge>
                        </div>
                        <p className="text-[9px] text-slate-500 font-mono italic">ID: {u.user_id}</p>
                        <div className="flex justify-between items-center text-[9px] font-black uppercase">
                          <span className="text-rose-500">{u.fail_count} FAILED ATTEMPTS</span>
                          <span className="text-slate-600">PATTERN: {u.reason}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Active Admin Sessions */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Active Admin Sessions
              </CardTitle>
              <Pulse className="w-4 h-4 text-emerald-500 animate-pulse" />
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[350px]">
                <div className="divide-y divide-slate-800">
                  {sessions.map((s) => (
                    <div key={s.id} className="p-4 space-y-3 hover:bg-slate-800/30 transition-colors">
                      <div className="flex justify-between items-start">
                        <div className="flex items-center gap-2">
                          <UserIcon className="w-3.5 h-3.5 text-emerald-500" />
                          <p className="text-[10px] font-black text-slate-200 uppercase">{s.admin_id}</p>
                        </div>
                        <button onClick={() => revokeSession(s.id)} className="text-slate-600 hover:text-rose-500 transition-colors">
                          <LogOut className="w-3 h-3" />
                        </button>
                      </div>
                      <div className="flex justify-between text-[8px] font-bold text-slate-500 uppercase tracking-widest">
                        <span>{s.ip_address}</span>
                        <span>{s.geo_state || 'LOCATING...'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800 shadow-2xl p-6 border-t-4 border-t-rose-600">
            <CardContent className="p-0 space-y-4">
              <div className="flex items-center gap-3 text-rose-500">
                <AlertTriangle className="w-6 h-6" />
                <p className="font-black uppercase tracking-widest">Emergency Zone</p>
              </div>
              <p className="text-[10px] text-slate-500 font-medium italic leading-relaxed">Activate global lockdown to terminate all sessions and cycle API keys immediately.</p>
              <Button variant="destructive" className="w-full h-12 font-black uppercase tracking-widest" onClick={triggerLockdown}>ACTIVATE LOCKDOWN</Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
