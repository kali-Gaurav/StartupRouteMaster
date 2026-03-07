import { useState, useEffect } from "react";
import { 
  Shield, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  CreditCard, 
  Database, 
  Activity, 
  LayoutDashboard, 
  Ticket, 
  AlertCircle,
  ExternalLink,
  Copy,
  ChevronRight,
  TrendingUp,
  User as UserIcon
} from "lucide-react";
import { fetchWithAuth } from "@/lib/apiClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface VPAStat {
  vpa: string;
  name: string;
  utilization_pct: number;
  volume: number;
  limit: number;
  is_active: boolean;
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

export default function AdminDashboard() {
  const [vpaStats, setVpaStats] = useState<VPAStat[]>([]);
  const [pendingBookings, setPendingBookings] = useState<PendingBooking[]>([]);
  const [selectedBooking, setSelectedBooking] = useState<BookingDetails | null>(null);
  const [pnrInput, setPnrInput] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadStats();
    loadPending();
    const interval = setInterval(() => {
      loadStats();
      loadPending();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadStats = async () => {
    try {
      const res = await fetchWithAuth("/admin/vpa/stats");
      const data = await res.json();
      setVpaStats(data);
    } catch (e) {
      console.error("Failed to load VPA stats");
    }
  };

  const loadPending = async () => {
    try {
      const res = await fetchWithAuth("/admin/bookings/pending");
      const data = await res.json();
      setPendingBookings(data);
    } catch (e) {
      console.error("Failed to load pending bookings");
    }
  };

  const forceReconcile = async () => {
    toast.info("Started bank statement reconciliation...");
    try {
      const res = await fetchWithAuth("/admin/reconcile", { method: "POST" });
      const data = await res.json();
      if (data.matched > 0) {
        toast.success(`Matched ${data.matched} new payments!`);
        loadPending();
      } else {
        toast.info("No new matches found in statement.");
      }
    } catch (e) {
      toast.error("Reconciliation service unavailable");
    }
  };

  const fetchDetails = async (id: string) => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`/admin/bookings/${id}/details`);
      const data = await res.json();
      setSelectedBooking(data);
      setPnrInput("");
    } catch (e) {
      toast.error("Failed to load booking details");
    } finally {
      setLoading(false);
    }
  };

  const completeBooking = async (id: string) => {
    if (!pnrInput || pnrInput.length < 10) {
      toast.error("Valid 10-digit PNR is required");
      return;
    }
    try {
      await fetchWithAuth(`/admin/bookings/${id}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pnr_number: pnrInput })
      });
      toast.success("Booking completed and user notified!");
      setSelectedBooking(null);
      loadPending();
    } catch (e) {
      toast.error("Failed to complete booking");
    }
  };

  const getAutofillScript = (details: BookingDetails) => {
    const passengers = JSON.stringify(details.passengers);
    return `
      (function() {
        const ps = ${passengers};
        console.log("Auto-filling IRCTC with", ps);
        // This is a simplified example. A real extension would target IRCTC DOM.
        alert("Autofill ready for " + ps.length + " passengers. Check console.");
      })();
    `;
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard!");
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 p-4 md:p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-3xl font-black tracking-tight flex items-center gap-2">
              <Shield className="w-8 h-8 text-primary" />
              RouteMaster <span className="text-primary">Ops</span>
            </h1>
            <p className="text-muted-foreground mt-1 font-medium">Production Control & Escrow Management</p>
          </div>
          <div className="flex gap-3">
            <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 px-3 py-1">
              <Activity className="w-3 h-3 mr-1.5 animate-pulse" />
              Backend Online
            </Badge>
          </div>
        </div>

        <Tabs defaultValue="bookings" className="space-y-6">
          <TabsList className="bg-white dark:bg-slate-900 border border-border shadow-sm p-1 h-12">
            <TabsTrigger value="bookings" className="gap-2 px-6">
              <Ticket className="w-4 h-4" />
              Booking Pipeline
              {pendingBookings.length > 0 && (
                <span className="ml-1 bg-primary text-primary-foreground text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                  {pendingBookings.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="vpas" className="gap-2 px-6">
              <CreditCard className="w-4 h-4" />
              Merchant VPAs
            </TabsTrigger>
            <TabsTrigger value="system" className="gap-2 px-6">
              <Database className="w-4 h-4" />
              System Infrastructure
            </TabsTrigger>
          </TabsList>

          <TabsContent value="bookings" className="space-y-6">
            <div className="grid lg:grid-cols-12 gap-6">
              
              {/* Sidebar: Pending List */}
              <div className="lg:col-span-4 space-y-4">
                <Card className="border-border shadow-sm">
                  <CardHeader className="pb-3 border-b border-border/50 flex flex-row items-center justify-between">
                    <CardTitle className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                      Pending Requests
                      <Clock className="w-4 h-4" />
                    </CardTitle>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="h-8 w-8 rounded-full text-primary hover:bg-primary/10"
                      onClick={forceReconcile}
                      title="Sync with Bank Statement"
                    >
                      <Database className="w-4 h-4" />
                    </Button>
                  </CardHeader>
                  <CardContent className="p-0">
                    <ScrollArea className="h-[600px]">
                      {pendingBookings.length === 0 ? (
                        <div className="p-8 text-center space-y-2">
                          <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto opacity-20" />
                          <p className="text-xs text-muted-foreground">Queue is empty. Great job!</p>
                        </div>
                      ) : (
                        <div className="divide-y divide-border/50">
                          {pendingBookings.map((b) => (
                            <button
                              key={b.id}
                              onClick={() => fetchDetails(b.id)}
                              className={`w-full p-4 text-left hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors flex items-center justify-between group ${selectedBooking?.id === b.id ? 'bg-primary/5 border-l-4 border-l-primary' : ''}`}
                            >
                              <div className="space-y-1">
                                <p className="font-bold text-sm">Train #{b.train_number}</p>
                                <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                                  <span className="font-mono">{b.id.substring(0, 8).toUpperCase()}</span>
                                  <span>•</span>
                                  <span>₹{b.amount_paid.toFixed(2)}</span>
                                </div>
                              </div>
                              <ChevronRight className={`w-4 h-4 text-muted-foreground transition-transform ${selectedBooking?.id === b.id ? 'translate-x-1' : ''}`} />
                            </button>
                          ))}
                        </div>
                      )}
                    </ScrollArea>
                  </CardContent>
                </Card>
              </div>

              {/* Main Detail Area */}
              <div className="lg:col-span-8">
                {selectedBooking ? (
                  <Card className="border-border shadow-md border-t-4 border-t-primary overflow-hidden">
                    <CardHeader className="bg-slate-50 dark:bg-slate-900/50 border-b border-border flex flex-row items-center justify-between py-4">
                      <div className="flex items-center gap-3">
                        <div className="bg-primary/10 p-2 rounded-lg text-primary">
                          <Ticket className="w-5 h-5" />
                        </div>
                        <div>
                          <CardTitle className="text-lg font-black uppercase tracking-tight">
                            Booking ID: {selectedBooking.id.substring(0, 8).toUpperCase()}
                          </CardTitle>
                          <p className="text-xs text-muted-foreground font-medium">Awaiting manual IRCTC processing</p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="h-8 gap-1.5 font-bold"
                          onClick={() => copyToClipboard(getAutofillScript(selectedBooking))}
                        >
                          <Copy className="w-3.5 h-3.5" />
                          Copy Autofill
                        </Button>
                        <Button 
                          variant="secondary" 
                          size="sm" 
                          className="h-8 gap-1.5 font-bold"
                          onClick={() => window.open('https://www.irctc.co.in/', '_blank')}
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          Open IRCTC
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="p-6 space-y-8">
                      {/* Passenger Info */}
                      <div className="grid md:grid-cols-2 gap-8">
                        <div className="space-y-4">
                          <h3 className="text-xs font-black uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                            <UserIcon className="w-3.5 h-3.5" />
                            Passenger Details
                          </h3>
                          <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-4 border border-border/50">
                            {selectedBooking.passengers.map((p, i) => (
                              <div key={i} className="flex justify-between items-center py-2 first:pt-0 last:pb-0 border-b border-border/20 last:border-0">
                                <span className="font-bold text-sm">{p.name}</span>
                                <span className="text-xs font-medium text-muted-foreground">{p.age}y • {p.gender}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="space-y-4">
                          <h3 className="text-xs font-black uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                            <TrendingUp className="w-3.5 h-3.5" />
                            Journey Details
                          </h3>
                          <div className="grid grid-cols-2 gap-4">
                            <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3 border border-border/50">
                              <p className="text-[10px] text-muted-foreground uppercase font-bold">Train No.</p>
                              <p className="font-black text-lg">{selectedBooking.train_number}</p>
                            </div>
                            <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3 border border-border/50">
                              <p className="text-[10px] text-muted-foreground uppercase font-bold">Date</p>
                              <p className="font-black text-lg">{selectedBooking.travel_date}</p>
                            </div>
                            <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3 border border-border/50">
                              <p className="text-[10px] text-muted-foreground uppercase font-bold">Berth</p>
                              <p className="font-black text-lg">{selectedBooking.berth_preference || 'NONE'}</p>
                            </div>
                            <div className="bg-emerald-500/10 rounded-xl p-3 border border-emerald-500/20">
                              <p className="text-[10px] text-emerald-600 uppercase font-bold">Amount Paid</p>
                              <p className="font-black text-lg text-emerald-700">₹{selectedBooking.amount_paid.toFixed(2)}</p>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Manual Entry Action */}
                      <div className="bg-primary/5 rounded-2xl p-6 border border-primary/20 space-y-4">
                        <div>
                          <h3 className="text-sm font-bold">Finalize Booking</h3>
                          <p className="text-xs text-muted-foreground">Once you book on IRCTC, enter the PNR below to notify the user.</p>
                        </div>
                        <div className="flex gap-3">
                          <input 
                            type="text" 
                            placeholder="Enter 10-digit PNR"
                            value={pnrInput}
                            onChange={(e) => setPnrInput(e.target.value.replace(/\D/g, '').slice(0, 10))}
                            className="flex-1 bg-white dark:bg-slate-900 border border-border rounded-lg px-4 h-12 font-mono font-bold tracking-[0.2em] text-lg focus:ring-2 focus:ring-primary focus:outline-none"
                          />
                          <Button 
                            onClick={() => completeBooking(selectedBooking.id)}
                            className="h-12 px-8 font-bold"
                          >
                            Complete & Send
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="h-[600px] border-2 border-dashed border-border rounded-3xl flex flex-col items-center justify-center text-center p-8 space-y-4">
                    <div className="bg-muted p-4 rounded-full">
                      <LayoutDashboard className="w-8 h-8 text-muted-foreground" />
                    </div>
                    <div>
                      <h3 className="font-bold">Select a request to process</h3>
                      <p className="text-sm text-muted-foreground max-w-xs">Pending AGENT_BOOKING requests will appear here for your manual action.</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="vpas" className="space-y-6">
            <div className="grid md:grid-cols-3 gap-6">
              {vpaStats.map((v) => (
                <Card key={v.vpa} className="border-border shadow-sm overflow-hidden group hover:shadow-md transition-shadow">
                  <div className={`h-1.5 w-full ${v.utilization_pct > 90 ? 'bg-destructive' : v.utilization_pct > 70 ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-bold flex items-center justify-between">
                      {v.name}
                      <Badge variant={v.is_active ? "default" : "destructive"} className="text-[10px] px-1.5 py-0">
                        {v.is_active ? 'ACTIVE' : 'INACTIVE'}
                      </Badge>
                    </CardTitle>
                    <p className="text-[10px] font-mono text-muted-foreground">{v.vpa}</p>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex justify-between items-end">
                      <div className="space-y-1">
                        <p className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Daily Volume</p>
                        <p className="text-2xl font-black">₹{v.volume.toFixed(0)}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Limit</p>
                        <p className="text-sm font-bold">₹{(v.limit / 1000).toFixed(0)}k</p>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-[10px] font-bold">
                        <span>Utilization</span>
                        <span>{v.utilization_pct.toFixed(1)}%</span>
                      </div>
                      <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                        <div 
                          className={`h-full transition-all duration-1000 ${v.utilization_pct > 90 ? 'bg-destructive' : v.utilization_pct > 70 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                          style={{ width: `${v.utilization_pct}%` }}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="system" className="space-y-6">
            <Card className="border-border shadow-sm">
              <CardHeader>
                <CardTitle className="text-sm font-bold uppercase tracking-widest flex items-center gap-2">
                  <Activity className="w-4 h-4 text-primary" />
                  Real-time Node Health
                </CardTitle>
              </CardHeader>
              <CardContent className="p-8 text-center space-y-4">
                <AlertCircle className="w-12 h-12 text-muted-foreground mx-auto opacity-20" />
                <p className="text-sm text-muted-foreground">Detailed infrastructure metrics coming in Phase 10.</p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
