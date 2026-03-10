import { useState, useEffect } from "react";
import {
  TrendingUp,
  User as UserIcon,
  Zap,
  Users,
  Target,
  MessageSquare,
  Smartphone,
  Monitor,
  Layout,
  Briefcase,
  Wallet,
  Users as Group,
  Flame,
  ArrowUp,
  ArrowDown,
  Minus,
  Star,
  Award
} from "lucide-react";
import { fetchWithAuth } from "@/lib/apiClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";

interface UserStats {
  total_users: number;
  dau: number;
  active_now: number;
  retention_rate: number;
}

interface UserChartData {
  date: string;
  total: number;
  new: number;
}

interface UserFunnel {
  searches: number;
  unlocks: number;
  bookings: number;
  unlock_rate: number;
  booking_rate: number;
}

interface UserRetention {
  repeat_users: number;
  one_time_users: number;
  repeat_rate: number;
}

interface InteractionVelocity {
  messages_last_hour: number;
  mpm: number;
  peak_mpm_24h: number;
  is_spike: boolean;
}

interface PlatformDist {
  Mobile: number;
  Desktop: number;
  "Mini-App": number;
}

interface UserArchetype {
  persona: string;
  count: number;
  pct: number;
  trend: "UP" | "DOWN" | "STABLE";
}

interface KarmaLeader {
  name: string;
  karma: number;
  help_count: number;
  is_volunteer: boolean;
}

interface TopRoute {
  route: string;
  searches: number;
}

export default function AdminGrowth() {
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [userCharts, setUserCharts] = useState<UserChartData[]>([]);
  const [userFunnel, setUserFunnel] = useState<UserFunnel | null>(null);
  const [userRetention, setUserRetention] = useState<UserRetention | null>(null);
  const [velocity, setVelocity] = useState<InteractionVelocity | null>(null);
  const [platformDist, setPlatformDist] = useState<PlatformDist | null>(null);
  const [archetypes, setArchetypes] = useState<UserArchetype[]>([]);
  const [karmaLeaders, setKarmaLeaders] = useState<KarmaLeader[]>([]);
  const [topRoutes, setTopRoutes] = useState<TopRoute[]>([]);
  const [geoLoad, setGeoLoad] = useState<Record<string, number>>({});
  const [supportUserId, setSupportUserId] = useState("");
  const [supportMsg, setSupportMsg] = useState("");

  useEffect(() => {
    refreshGrowth();
    const interval = setInterval(refreshGrowth, 20000);
    return () => clearInterval(interval);
  }, []);

  const refreshGrowth = async () => {
    try {
      const [s, c, f, r, g, rt, v, p, arc, kl] = await Promise.all([
        fetchWithAuth("/admin/user/stats"),
        fetchWithAuth("/admin/user/charts"),
        fetchWithAuth("/admin/user/funnel"),
        fetchWithAuth("/admin/user/top-routes"),
        fetchWithAuth("/admin/user/geo-load"),
        fetchWithAuth("/admin/user/retention"),
        fetchWithAuth("/admin/user/interaction-velocity"),
        fetchWithAuth("/admin/user/platform-distribution"),
        fetchWithAuth("/admin/user/archetypes"),
        fetchWithAuth("/admin/user/karma-leaderboard")
      ]);
      setUserStats(await s.json());
      setUserCharts(await c.json());
      setUserFunnel(await f.json());
      setTopRoutes(await r.json());
      setGeoLoad(await g.json());
      setUserRetention(await rt.json());
      setVelocity(await v.json());
      setPlatformDist(await p.json());
      setArchetypes(await arc.json());
      setKarmaLeaders(await kl.json());
    } catch (e) { console.error("Growth refresh error"); }
  };

  const sendSupportMessage = async () => {
    if (!supportUserId || !supportMsg) {
      toast.error("User ID and Message required");
      return;
    }
    try {
      await fetchWithAuth("/admin/user/support/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: supportUserId, message: supportMsg })
      });
      toast.success("Intervention dispatched.");
      setSupportMsg("");
    } catch (e) { toast.error("Dispatch failed"); }
  };

  const getPersonaIcon = (p: string) => {
    if (p.includes("Business")) return <Briefcase className="w-4 h-4" />;
    if (p.includes("Budget")) return <Wallet className="w-4 h-4" />;
    if (p.includes("Family")) return <Group className="w-4 h-4" />;
    if (p.includes("Tatkal")) return <Flame className="w-4 h-4" />;
    return <UserIcon className="w-4 h-4" />;
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-primary" />
            Growth & Acquisition
          </h2>
          {velocity?.is_spike && (
            <Badge className="bg-amber-500 text-white animate-pulse px-3 py-1 gap-1.5 border-0 shadow-[0_0_15px_rgba(245,158,11,0.4)]">
              <Zap className="w-3 h-3" />
              INTERACTION SPIKE
            </Badge>
          )}
        </div>
        <div className="flex gap-2">
          <Badge variant="outline" className="font-mono bg-primary/5 border-primary/20 text-primary px-3 py-1">
            NETWORK RETENTION: {userRetention?.repeat_rate}%
          </Badge>
        </div>
      </div>

      {/* Acquisition & Retention KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-primary text-white border-0 shadow-lg overflow-hidden relative">
          <div className="absolute top-0 right-0 p-4 opacity-10"><Users className="w-16 h-16" /></div>
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] opacity-70">Total Platform Users</p>
            <p className="text-4xl font-black">{userStats?.total_users.toLocaleString()}</p>
            <div className="flex items-center gap-1 text-[10px] font-bold text-primary-foreground/80">
              <TrendingUp className="w-3 h-3" />
              +45 new today
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Loyalty Coefficient</p>
            <p className="text-3xl font-black italic tracking-tighter text-white">{userRetention?.repeat_rate}%</p>
            <p className="text-[10px] font-medium text-slate-500 italic">{userRetention?.repeat_users.toLocaleString()} repeat searchers</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Interaction Velocity</p>
            <p className={`text-3xl font-black italic tracking-tighter ${velocity?.is_spike ? 'text-amber-500' : 'text-emerald-500'}`}>
              {velocity?.mpm} <span className="text-sm">MPM</span>
            </p>
            <p className="text-[10px] font-medium text-slate-500 italic">Messages Per Minute</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Live Traffic Edge</p>
            <p className="text-3xl font-black italic tracking-tighter text-blue-500">{userStats?.active_now.toLocaleString()}</p>
            <p className="text-[10px] font-medium text-slate-500 italic">Sessions in flight</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-12 gap-8">
        {/* User Growth Chart */}
        <div className="lg:col-span-8 space-y-8">
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Network Acquisition Timeline (7D)
              </CardTitle>
              <Users className="w-4 h-4 text-primary" />
            </CardHeader>
            <CardContent className="p-8 h-[350px] flex items-end justify-between gap-2">
              {userCharts.map((d, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-3 group">
                  <div className="relative w-full flex flex-col-reverse gap-1">
                    <div 
                      className="w-full bg-slate-800 rounded-t-lg transition-all group-hover:bg-slate-700" 
                      style={{ height: `${(d.total / (Math.max(...userCharts.map(x => x.total)) || 1)) * 250}px` }} 
                    />
                    <div 
                      className="w-full bg-primary rounded-t-sm absolute bottom-0 left-0 transition-all group-hover:brightness-110 shadow-[0_0_15px_rgba(59,130,246,0.3)]" 
                      style={{ height: `${(d.new / (Math.max(...userCharts.map(x => x.total)) || 1)) * 250}px` }} 
                    />
                  </div>
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-tighter">{d.date}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* User Behavioral Persona Mix */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                User Behavioral Persona Mix
              </CardTitle>
              <Users className="w-4 h-4 text-emerald-500" />
            </CardHeader>
            <CardContent className="p-8 space-y-8">
              <div className="grid md:grid-cols-2 gap-12">
                {archetypes.map((arc) => (
                  <div key={arc.persona} className="space-y-3">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-slate-950 rounded-lg border border-slate-800 text-primary">
                          {getPersonaIcon(arc.persona)}
                        </div>
                        <div>
                          <p className="text-sm font-black text-slate-200 uppercase tracking-tight">{arc.persona}</p>
                          <p className="text-[8px] font-bold text-slate-500 uppercase tracking-widest">{arc.count} users</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-black text-white">{arc.pct}%</span>
                        {arc.trend === 'UP' ? <ArrowUp className="w-3 h-3 text-emerald-500" /> : arc.trend === 'DOWN' ? <ArrowDown className="w-3 h-3 text-rose-500" /> : <Minus className="w-3 h-3 text-slate-500" />}
                      </div>
                    </div>
                    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-primary shadow-[0_0_10px_rgba(59,130,246,0.5)]" style={{ width: `${arc.pct}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Platform & Device Mix */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Platform & Device Mix
              </CardTitle>
              <Smartphone className="w-4 h-4 text-primary" />
            </CardHeader>
            <CardContent className="p-8 space-y-10">
              <div className="grid grid-cols-3 gap-12">
                <div className="space-y-3">
                  <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest text-slate-500">
                    <span className="flex items-center gap-2"><Smartphone className="w-3.5 h-3.5" /> Mobile</span>
                    <span className="text-white">{platformDist?.Mobile || 0} users</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-primary shadow-[0_0_10px_rgba(59,130,246,0.5)]" style={{ width: `${(platformDist?.Mobile || 0) / (userStats?.active_now || 1) * 100}%` }} />
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest text-slate-500">
                    <span className="flex items-center gap-2"><Monitor className="w-3.5 h-3.5" /> Desktop</span>
                    <span className="text-white">{platformDist?.Desktop || 0} users</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]" style={{ width: `${(platformDist?.Desktop || 0) / (userStats?.active_now || 1) * 100}%` }} />
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest text-slate-500">
                    <span className="flex items-center gap-2"><Layout className="w-3.5 h-3.5" /> Mini-App</span>
                    <span className="text-white">{platformDist?.["Mini-App"] || 0} users</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]" style={{ width: `${(platformDist?.["Mini-App"] || 0) / (userStats?.active_now || 1) * 100}%` }} />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-4 space-y-8">
          {/* Task 32.2: Community Karma Leaderboard */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden border-t-4 border-t-emerald-500">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Award className="w-4 h-4 text-emerald-500" />
                Community Health Leaders
              </CardTitle>
              <Star className="w-4 h-4 text-amber-500 animate-pulse" />
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[400px]">
                <div className="divide-y divide-slate-800">
                  {karmaLeaders.map((leader, i) => (
                    <div key={i} className="p-5 space-y-3 hover:bg-slate-800/30 transition-colors">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-lg ${leader.is_volunteer ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-slate-950 text-slate-500'}`}>
                            <UserIcon className="w-4 h-4" />
                          </div>
                          <div>
                            <p className="text-sm font-black text-slate-200 uppercase tracking-tight">{leader.name}</p>
                            {leader.is_volunteer && <p className="text-[8px] font-black text-emerald-500 uppercase tracking-[0.2em]">Safety Volunteer</p>}
                          </div>
                        </div>
                        <Badge className="bg-primary/10 text-primary border-primary/20 font-black">{leader.karma} PTS</Badge>
                      </div>
                      <div className="flex justify-between items-center text-[9px] font-black uppercase tracking-widest text-slate-600">
                        <span>Total Interventions</span>
                        <span className="text-white">{leader.help_count}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Intervention Terminal */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl border-t-4 border-t-amber-500">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-amber-500" />
                Intervention Terminal
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="space-y-2">
                <label className="text-[8px] font-black uppercase text-slate-600 tracking-widest">Target User ID</label>
                <input 
                  type="text" 
                  value={supportUserId} 
                  onChange={(e) => setSupportUserId(e.target.value)}
                  placeholder="ID (e.g. user_...)"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2 text-[10px] font-bold text-white focus:outline-none focus:border-primary transition-all"
                />
              </div>
              <div className="space-y-2">
                <label className="text-[8px] font-black uppercase text-slate-600 tracking-widest">Manual Support Message</label>
                <textarea 
                  rows={4}
                  value={supportMsg} 
                  onChange={(e) => setSupportMsg(e.target.value)}
                  placeholder="Push message directly to chat session..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2 text-[10px] font-medium text-slate-300 focus:outline-none focus:border-primary transition-all resize-none"
                />
              </div>
              <Button 
                className="w-full h-12 bg-amber-600 hover:bg-amber-500 text-white font-black uppercase tracking-widest shadow-lg shadow-amber-600/20"
                onClick={sendSupportMessage}
              >
                DISPATCH MESSAGE
              </Button>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Conversion Funnel (30D)
              </CardTitle>
              <Target className="w-4 h-4 text-amber-500" />
            </CardHeader>
            <CardContent className="p-8 space-y-8">
              <div className="space-y-2">
                <div className="flex justify-between text-[10px] font-black uppercase text-slate-500">
                  <span>Searches</span>
                  <span>{userFunnel?.searches}</span>
                </div>
                <div className="h-10 w-full bg-slate-800/50 rounded-xl relative overflow-hidden border border-slate-800">
                  <div className="h-full bg-slate-700 opacity-20 w-full" />
                  <div className="absolute inset-0 flex items-center justify-center text-[10px] font-black tracking-[0.2em]">100% BASE</div>
                </div>
              </div>

              <div className="space-y-2 pl-6 relative">
                <div className="absolute left-0 top-0 bottom-0 w-px bg-slate-800" />
                <div className="flex justify-between text-[10px] font-black uppercase text-primary">
                  <span>Unlocks</span>
                  <span>{userFunnel?.unlocks} ({userFunnel?.unlock_rate}%)</span>
                </div>
                <div className="h-10 w-full bg-primary/10 rounded-xl relative overflow-hidden border border-primary/20">
                  <div className="h-full bg-primary shadow-[0_0_15px_rgba(59,130,246,0.4)]" style={{ width: `${userFunnel?.unlock_rate}%` }} />
                  <div className="absolute inset-0 flex items-center justify-center text-[10px] font-black tracking-[0.2em]">{userFunnel?.unlock_rate}%</div>
                </div>
              </div>

              <div className="space-y-2 pl-12 relative">
                <div className="absolute left-6 top-0 bottom-0 w-px bg-slate-800" />
                <div className="flex justify-between text-[10px] font-black uppercase text-emerald-500">
                  <span>Bookings</span>
                  <span>{userFunnel?.bookings} ({userFunnel?.booking_rate}%)</span>
                </div>
                <div className="h-10 w-full bg-emerald-500/10 rounded-xl relative overflow-hidden border border-emerald-500/20">
                  <div className="h-full bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.4)]" style={{ width: `${userFunnel?.booking_rate}%` }} />
                  <div className="absolute inset-0 flex items-center justify-center text-[10px] font-black tracking-[0.2em]">{userFunnel?.booking_rate}%</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
