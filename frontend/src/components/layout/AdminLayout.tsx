import React, { useState, useEffect } from "react";
import { Link, useLocation, Outlet, useNavigate } from "react-router-dom";
import { 
  Shield, 
  LayoutDashboard, 
  Ticket, 
  CreditCard, 
  TrendingUp, 
  BrainCircuit, 
  Server, 
  History, 
  LogOut,
  Bell,
  ChevronRight,
  Search,
  Activity,
  Database,
  Settings,
  Cpu,
  Zap
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { fetchWithAuth } from "@/lib/apiClient";

/**
 * Task 10.1 & 26.3: High-Tech Admin Command Shell.
 * Provides specialized sidebar navigation and real-time cluster health badges.
 */
export default function AdminLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    loadHealth();
    const interval = setInterval(loadHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadHealth = async () => {
    try {
      const res = await fetchWithAuth("/admin/system/health");
      setHealth(await res.json());
    } catch (e) { console.error("Health poll error"); }
  };

  const navItems = [
    { name: "Command Center", path: "/ops/admin", icon: LayoutDashboard },
    { name: "Operations Hub", path: "/ops/admin/operations", icon: Ticket, badge: "Pending" },
    { name: "Financial Suite", path: "/ops/admin/finance", icon: CreditCard },
    { name: "User & Growth", path: "/ops/admin/growth", icon: TrendingUp },
    { name: "AI Intelligence", path: "/ops/admin/ai", icon: BrainCircuit },
    { name: "Inventory Sentinel", path: "/ops/admin/inventory", icon: Database },
    { name: "System Sentinel", path: "/ops/admin/system", icon: Server },
    { name: "Platform Settings", path: "/ops/admin/settings", icon: Settings },
    { name: "Security Audit", path: "/ops/admin/audit", icon: History },
  ];

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    toast.success("Disconnected from Command Center.");
    navigate("/admin/auth");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex font-sans selection:bg-primary/30">
      {/* Sidebar Navigation */}
      <aside 
        className={`${isSidebarCollapsed ? 'w-20' : 'w-72'} border-r border-slate-800 bg-slate-900/50 backdrop-blur-xl transition-all duration-300 flex flex-col z-50`}
      >
        <div className="p-6 flex items-center gap-3 border-b border-slate-800">
          <div className="bg-primary/20 p-2 rounded-xl border border-primary/30 shadow-[0_0_15px_rgba(59,130,246,0.3)]">
            <Shield className="w-6 h-6 text-primary animate-pulse" />
          </div>
          {!isSidebarCollapsed && (
            <div className="flex flex-col">
              <span className="font-black tracking-tighter text-lg uppercase leading-none">RouteMaster</span>
              <span className="text-[10px] text-primary font-black uppercase tracking-[0.2em]">Ops Portal</span>
            </div>
          )}
        </div>

        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`
                  flex items-center gap-3 px-4 py-3 rounded-lg transition-all group
                  ${isActive 
                    ? 'bg-primary text-white shadow-[0_0_20px_rgba(59,130,246,0.4)]' 
                    : 'hover:bg-slate-800 text-slate-400 hover:text-white'}
                `}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'scale-110' : 'group-hover:scale-110'} transition-transform`} />
                {!isSidebarCollapsed && (
                  <span className="text-sm font-bold flex-1">{item.name}</span>
                )}
                {!isSidebarCollapsed && isActive && <ChevronRight className="w-4 h-4 opacity-50" />}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800 space-y-4">
          <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-[10px] font-black uppercase tracking-widest text-emerald-500">Uplink Active</span>
              </div>
              {health && <Badge variant="outline" className="text-[8px] h-4 px-1 border-slate-700 font-mono text-slate-500">PID:{health.process_id}</Badge>}
            </div>
            {!isSidebarCollapsed && <p className="text-[10px] text-slate-500 font-medium italic">Latency: 42ms | Node: AP-SOUTH-1</p>}
          </div>
          <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-rose-500 hover:bg-rose-500/10 transition-colors"
          >
            <LogOut className="w-5 h-5" />
            {!isSidebarCollapsed && <span className="text-sm font-bold uppercase tracking-widest">Terminate Session</span>}
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col relative overflow-hidden">
        {/* Global Action Bar */}
        <header className="h-20 border-b border-slate-800 bg-slate-900/30 backdrop-blur-md flex items-center justify-between px-8 z-40">
          <div className="flex items-center gap-4 flex-1 max-w-xl">
            <div className="relative w-full group">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-primary transition-colors" />
              <input 
                type="text" 
                placeholder="EXECUTE GLOBAL QUERY (ID, PNR, VPA...)"
                className="w-full bg-slate-800/50 border border-slate-700 rounded-none px-10 py-2.5 text-[10px] font-bold tracking-[0.1em] focus:outline-none focus:border-primary transition-all uppercase placeholder:text-slate-600"
              />
            </div>
          </div>

          <div className="flex items-center gap-6">
            {/* Task 26.3: Global Uptime Indicator */}
            {health && (
              <div className="hidden md:flex items-center gap-3 px-4 py-2 bg-slate-900/50 rounded-xl border border-slate-800 animate-in fade-in zoom-in duration-500">
                <div className="flex flex-col text-right">
                  <span className="text-[8px] font-black uppercase text-slate-500 tracking-tighter leading-none mb-1">Fleet Uptime</span>
                  <span className="text-xs font-black text-emerald-500 font-mono tracking-tight leading-none">{health.uptime_human}</span>
                </div>
                <div className="w-px h-6 bg-slate-800" />
                <Zap className="w-4 h-4 text-amber-500" />
              </div>
            )}

            <div className="flex flex-col text-right">
              <span className="text-[10px] font-black uppercase text-slate-500 tracking-tighter">System Health</span>
              <span className="text-xs font-bold text-emerald-500 uppercase">{health?.cpu_usage_percent < 80 ? '99.98% OPTIMAL' : 'DEGRADED'}</span>
            </div>
            <div className="w-px h-8 bg-slate-800" />
            <Button variant="ghost" size="icon" className="relative text-slate-400 hover:text-white">
              <Bell className="w-5 h-5" />
              <span className="absolute top-2 right-2 w-2 h-2 bg-rose-500 rounded-full border-2 border-slate-950" />
            </Button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top_right,_var(--tw-gradient-stops))] from-slate-900/50 via-transparent to-transparent">
          <div className="p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
