import { useState, useEffect } from "react";
import {
  Ticket,
  ExternalLink,
  CheckCircle2,
  User as UserIcon,
  Search,
  Lock,
  LayoutDashboard,
  Activity as Pulse,
  Flame,
  ShieldAlert
} from "lucide-react";
import { fetchWithAuth } from "@/lib/apiClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";

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

interface RefundRequest {
  id: string;
  booking_id: string;
  amount: number;
  vpa: string;
  status: "PENDING" | "PROCESSED" | "FAILED";
  reason: string;
  created_at: string;
}

interface OpsProductivity {
  avg_fulfillment_minutes: number;
  total_completed: number;
  performance_status: "OPTIMAL" | "DEGRADED";
}

interface OpsTrend {
  hour: string;
  avg_mins: number;
}

interface SurgeStatus {
  is_surge: boolean;
  surge_intensity: string;
  action_taken: string;
  current_session_velocity: number;
}

export default function AdminOperations() {
  const [pendingBookings, setPendingBookings] = useState<PendingBooking[]>([]);
  const [selectedBooking, setSelectedBooking] = useState<BookingDetails | null>(null);
  const [refunds, setRefunds] = useState<RefundRequest[]>([]);
  const [productivity, setProductivity] = useState<OpsProductivity | null>(null);
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [surgeStatus, setSurgeStatus] = useState<SurgeStatus | null>(null);
  const [trends, setTrends] = useState<OpsTrend[]>([]);
  const [pnrInput, setPnrInput] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    refreshData();
    const interval = setInterval(refreshData, 10000);
    return () => clearInterval(interval);
  }, []);

  const refreshData = () => {
    loadPending();
    loadRefunds();
    loadProductivity();
    loadTrends();
    loadSystemHealth();
    loadSurge();
  };

  const loadSurge = async () => {
    try {
      const res = await fetchWithAuth("/v2/admin/system/surge-detection");
      setSurgeStatus(await res.json());
    } catch (e) { console.error("Surge check error"); }
  };

  const loadSystemHealth = async () => {
    try {
      const res = await fetchWithAuth("/v2/admin/system/health");
      setSystemHealth(await res.json());
    } catch (e) { console.error("Health error"); }
  };

  const loadProductivity = async () => {
    try {
      const res = await fetchWithAuth("/v2/admin/operations/productivity");
      setProductivity(await res.json());
    } catch (e) { console.error("Ops stats error"); }
  };

  const loadTrends = async () => {
    try {
      const res = await fetchWithAuth("/v2/admin/operations/trends");
      setTrends(await res.json());
    } catch (e) { console.error("Ops trends error"); }
  };

  const loadPending = async () => {
    try {
      const res = await fetchWithAuth("/v2/admin/bookings/pending");
      setPendingBookings(await res.json());
    } catch (e) { console.error("Pending bookings error"); }
  };

  const loadRefunds = async () => {
    try {
      const res = await fetchWithAuth("/v2/admin/finance/refunds");
      setRefunds(await res.json());
    } catch (e) { console.error("Refunds error"); }
  };

  const fetchDetails = async (id: string) => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`/v2/admin/bookings/${id}/details`);
      setSelectedBooking(await res.json());
      setPnrInput("");
    } catch (e) { toast.error("Failed to load details"); }
    finally { setLoading(false); }
  };

  const completeBooking = async (id: string) => {
    if (!pnrInput || pnrInput.length < 10) {
      toast.error("10-digit PNR required");
      return;
    }
    try {
      await fetchWithAuth(`/v2/admin/bookings/${id}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pnr_number: pnrInput })
      });
      toast.success("Booking confirmed!");
      setSelectedBooking(null);
      loadPending();
      loadProductivity();
    } catch (e) { toast.error("Completion failed"); }
  };

  const isTatkal = systemHealth?.is_tatkal_window;
  const isSurge = surgeStatus?.is_surge;

  return (
    <div className={`space-y-8 animate-in fade-in duration-500 ${(isTatkal || isSurge) ? 'selection:bg-rose-500/30' : ''}`}>
      {/* Task 27.3: Surge Protection Banner */}
      {isSurge && (
        <div className="bg-rose-600 border border-rose-500 text-white rounded-2xl p-4 flex items-center justify-between shadow-[0_0_30px_rgba(225,29,72,0.4)] animate-pulse">
          <div className="flex items-center gap-4">
            <ShieldAlert className="w-8 h-8" />
            <div>
              <p className="text-sm font-black uppercase tracking-widest">Traffic Surge Detected</p>
              <p className="text-xs font-bold opacity-80 uppercase tracking-tighter">Velocity: {surgeStatus?.current_session_velocity} sessions/5m | Action: {surgeStatus?.action_taken}</p>
            </div>
          </div>
          <Badge className="bg-white text-rose-600 font-black px-4 py-1 h-fit">SURGE LEVEL: {surgeStatus?.surge_intensity}</Badge>
        </div>
      )}

      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2">
            <Ticket className={`w-6 h-6 ${(isTatkal || isSurge) ? 'text-rose-500 animate-pulse' : 'text-primary'}`} />
            Operations Hub
          </h2>
          {isTatkal && (
            <Badge className="bg-rose-600 text-white animate-bounce px-3 py-1 gap-1.5 border-0 shadow-[0_0_15px_rgba(225,29,72,0.5)]">
              <Flame className="w-3 h-3" />
              TATKAL ACTIVE
            </Badge>
          )}
        </div>
        <div className="flex gap-2">
          <Badge variant="outline" className={`font-mono px-3 py-1 ${productivity?.performance_status === 'OPTIMAL' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-rose-500/10 text-rose-500 border-rose-500/20'}`}>
            EFFICIENCY: {productivity?.performance_status}
          </Badge>
        </div>
      </div>

      {/* Task 12.5: Agent Daily KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className={`bg-slate-900 border-slate-800 text-white shadow-xl relative overflow-hidden ${(isTatkal || isSurge) ? 'ring-1 ring-rose-500/20' : ''}`}>
          <div className="absolute top-0 right-0 p-4 opacity-10"><CheckCircle2 className="w-16 h-16" /></div>
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Manual Fullfillments</p>
            <p className="text-3xl font-black italic tracking-tighter text-white">{productivity?.total_completed.toLocaleString()}</p>
            <p className="text-[10px] font-medium text-emerald-500 italic">Across all shifts</p>
          </CardContent>
        </Card>

        <Card className={`bg-slate-900 border-slate-800 text-white shadow-xl ${(isTatkal || isSurge) ? 'ring-1 ring-rose-500/20' : ''}`}>
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Avg Response Time</p>
            <p className={`text-3xl font-black italic tracking-tighter ${productivity?.avg_fulfillment_minutes && productivity.avg_fulfillment_minutes > 5 ? 'text-rose-500' : 'text-emerald-500'}`}>
              {productivity?.avg_fulfillment_minutes} <span className="text-sm">MINS</span>
            </p>
            <p className="text-[10px] font-medium text-slate-500 italic">Target: &lt; 5.0 mins</p>
          </CardContent>
        </Card>

        <Card className={`bg-slate-900 border-slate-800 text-white shadow-xl overflow-hidden group ${(isTatkal || isSurge) ? 'ring-1 ring-rose-500/20' : ''}`}>
          <CardContent className="p-6 space-y-3">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Fulfillment Trend</p>
            <div className="h-10 flex items-end gap-1">
              {trends.map((t, i) => (
                <div 
                  key={i} 
                  className={`flex-1 rounded-t-sm transition-all group-hover:opacity-100 ${t.avg_mins > 5 ? 'bg-rose-500 opacity-50' : 'bg-emerald-500 opacity-30'}`}
                  style={{ height: `${Math.min(100, (t.avg_mins / 10) * 100)}%` }}
                  title={`${t.hour}: ${t.avg_mins}m`}
                />
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className={`bg-slate-900 border-slate-800 text-white shadow-xl ${(isTatkal || isSurge) ? 'border-rose-500 shadow-[0_0_20px_rgba(225,29,72,0.2)] animate-pulse' : ''}`}>
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Queue Health</p>
            <p className={`text-3xl font-black italic tracking-tighter ${(isTatkal || isSurge) ? 'text-rose-500' : 'text-blue-500'}`}>{pendingBookings.length}</p>
            <p className="text-[10px] font-medium text-slate-500 italic">Awaiting manual entry</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-12 gap-8">
        {/* Left: Processing Queue */}
        <div className="lg:col-span-4 space-y-6">
          <Card className={`bg-slate-900 border-slate-800 shadow-xl overflow-hidden ${(isTatkal || isSurge) ? 'ring-1 ring-rose-500/20' : ''}`}>
            <CardHeader className={`border-b border-slate-800 py-4 flex flex-row items-center justify-between ${(isTatkal || isSurge) ? 'bg-rose-950/20' : 'bg-slate-900/50'}`}>
              <CardTitle className={`text-xs font-black uppercase tracking-[0.2em] ${(isTatkal || isSurge) ? 'text-rose-400' : 'text-slate-400'}`}>
                {(isTatkal || isSurge) ? 'HIGH PRIORITY MANIFEST' : 'Incoming Requests'}
              </CardTitle>
              <Pulse className={`w-4 h-4 ${(isTatkal || isSurge) ? 'text-rose-500 animate-ping' : 'text-primary animate-pulse'}`} />
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[600px]">
                {pendingBookings.length === 0 ? (
                  <div className="p-12 text-center space-y-2 opacity-30">
                    <CheckCircle2 className="w-8 h-8 mx-auto" />
                    <p className="text-[10px] font-bold uppercase">All Clean</p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-800">
                    {pendingBookings.map(b => (
                      <button 
                        key={b.id} 
                        onClick={() => fetchDetails(b.id)} 
                        className={`w-full p-5 text-left transition-all hover:bg-slate-800/50 group ${selectedBooking?.id === b.id ? ((isTatkal || isSurge) ? 'bg-rose-500/10 border-l-4 border-l-rose-500' : 'bg-primary/10 border-l-4 border-l-primary') : ''}`}
                      >
                        <div className="flex justify-between items-start mb-1">
                          <p className="font-black text-sm text-slate-100 uppercase tracking-tight">Train #{b.train_number}</p>
                          <span className={`text-[8px] font-black px-1.5 py-0.5 rounded uppercase ${(isTatkal || isSurge) ? 'bg-rose-500 text-white' : 'bg-slate-800 text-slate-500'}`}>
                            {(isTatkal || isSurge) ? 'HIGH PRIORITY' : 'NEW'}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono uppercase">
                          <span>ID: {b.id.substring(0,8)}</span>
                          <span className="opacity-20">|</span>
                          <span className={`${(isTatkal || isSurge) ? 'text-rose-400' : 'text-emerald-500'} font-black`}>₹{b.amount_paid.toFixed(2)}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* Right: Booking Command Center */}
        <div className="lg:col-span-8">
          {selectedBooking ? (
            <Card className={`bg-slate-900 border-slate-800 border-t-4 shadow-2xl h-full flex flex-col ${(isTatkal || isSurge) ? 'border-t-rose-500' : 'border-t-primary'}`}>
              <CardHeader className="bg-slate-950/50 border-b border-slate-800 py-6 px-8 flex flex-row justify-between items-center">
                <div className="flex items-center gap-4">
                  <div className={`p-3 rounded-2xl border border-white/5 shadow-lg ${(isTatkal || isSurge) ? 'bg-rose-500/20 text-rose-500 shadow-rose-500/20' : 'bg-primary/20 text-primary shadow-primary/20'}`}>
                    <Ticket className="w-6 h-6" />
                  </div>
                  <div>
                    <CardTitle className="text-xl font-black uppercase tracking-tight text-white">
                      Processing Request
                    </CardTitle>
                    <p className={`text-[10px] font-black uppercase tracking-[0.2em] ${(isTatkal || isSurge) ? 'text-rose-500' : 'text-primary'}`}>ID: {selectedBooking.id}</p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <Button variant="outline" className="bg-slate-800 border-slate-700 font-black uppercase text-[10px] tracking-widest hover:bg-slate-700" onClick={() => window.open('https://www.irctc.co.in/')}>
                    <ExternalLink className="w-3.5 h-3.5 mr-2" />
                    Open IRCTC
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-8 space-y-10 flex-1 overflow-y-auto">
                <div className="grid md:grid-cols-2 gap-12">
                  {/* Passenger Manifest */}
                  <div className="space-y-4">
                    <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 flex items-center gap-2">
                      <UserIcon className="w-3 h-3" />
                      Passenger Manifest
                    </h3>
                    <div className="bg-slate-950/50 rounded-2xl p-6 border border-slate-800">
                      {selectedBooking.passengers.map((p, i) => (
                        <div key={i} className="flex justify-between items-center py-3 border-b border-slate-800/50 last:border-0">
                          <span className="font-black text-slate-200">{p.name}</span>
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{p.age}Y • {p.gender}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Trip Parameters */}
                  <div className="space-y-4">
                    <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 flex items-center gap-2">
                      <Search className="w-3 h-3" />
                      Trip Parameters
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800">
                        <p className="text-[8px] uppercase font-black text-slate-600 tracking-widest mb-1">Train</p>
                        <p className="font-black text-xl text-white">{selectedBooking.train_number}</p>
                      </div>
                      <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800">
                        <p className="text-[8px] uppercase font-black text-slate-600 tracking-widest mb-1">Travel Date</p>
                        <p className="font-black text-sm text-slate-300">{selectedBooking.travel_date}</p>
                      </div>
                      <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800">
                        <p className="text-[8px] uppercase font-black text-slate-600 tracking-widest mb-1">Preferences</p>
                        <p className="font-black text-sm text-slate-300">{selectedBooking.berth_preference || 'ANY'}</p>
                      </div>
                      <div className={`p-4 rounded-2xl border shadow-inner ${(isTatkal || isSurge) ? 'bg-rose-500/10 border-rose-500/20' : 'bg-emerald-500/10 border-emerald-500/20'}`}>
                        <p className={`text-[8px] uppercase font-black tracking-widest mb-1 ${(isTatkal || isSurge) ? 'text-rose-500' : 'text-emerald-600'}`}>Total Paid</p>
                        <p className={`font-black text-xl ${(isTatkal || isSurge) ? 'text-rose-500' : 'text-emerald-500'}`}>₹{selectedBooking.amount_paid.toFixed(2)}</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Final Execution */}
                <div className={`rounded-3xl p-8 border space-y-6 shadow-2xl transition-all duration-1000 ${(isTatkal || isSurge) ? 'bg-rose-500/10 border-rose-500/20 shadow-rose-500/10' : 'bg-primary/10 border-primary/20 shadow-primary/10'}`}>
                  <div>
                    <h3 className="text-lg font-black uppercase text-white tracking-tight">Finalize Transaction</h3>
                    <p className="text-xs text-slate-400 font-medium">Verify booking on IRCTC then commit PNR to notify user</p>
                  </div>
                  <div className="flex gap-4">
                    <div className="relative flex-1">
                      <Lock className={`absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 opacity-50 ${(isTatkal || isSurge) ? 'text-rose-500' : 'text-primary'}`} />
                      <input 
                        type="text" 
                        placeholder="INPUT 10-DIGIT PNR NUMBER" 
                        value={pnrInput} 
                        onChange={(e) => setPnrInput(e.target.value.replace(/\D/g, '').slice(0, 10))} 
                        className={`w-full bg-slate-950 border border-slate-800 rounded-xl pl-12 pr-4 h-14 font-mono font-black text-xl tracking-[0.3em] focus:ring-2 focus:outline-none uppercase ${(isTatkal || isSurge) ? 'text-rose-500 focus:ring-rose-500' : 'text-primary focus:ring-primary'}`}
                      />
                    </div>
                    <Button 
                      onClick={() => completeBooking(selectedBooking.id)} 
                      className={`h-14 px-10 font-black uppercase tracking-widest text-white shadow-lg ${(isTatkal || isSurge) ? 'bg-rose-600 hover:bg-rose-500 shadow-rose-500/30' : 'bg-primary hover:bg-primary/90 shadow-primary/30'}`}
                    >
                      Commit & Notify
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="h-full border-2 border-dashed border-slate-800 rounded-[2.5rem] flex flex-col items-center justify-center text-center p-12 space-y-6 bg-slate-900/20 backdrop-blur-sm opacity-50">
              <div className="bg-slate-800 p-6 rounded-full border border-slate-700 shadow-inner">
                <LayoutDashboard className="w-12 h-12 text-slate-600" />
              </div>
              <div className="space-y-2">
                <h3 className="font-black text-xl uppercase tracking-widest text-slate-400">Terminal Awaiting Data</h3>
                <p className="text-sm text-slate-600 font-medium max-w-sm">Select an active request from the manifest to begin the manual IRCTC fulfillment pipeline.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
