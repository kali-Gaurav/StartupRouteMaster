import { useState, useEffect } from "react";
import {
  CreditCard,
  TrendingUp,
  ArrowUpRight,
  CheckCircle2,
  RefreshCw,
  Wallet,
  ArrowRightLeft
} from "lucide-react";
import { fetchWithAuth } from "@/lib/apiClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";

interface VPAStat {
  vpa: string;
  name: string;
  utilization_pct: number;
  volume: number;
  limit: number;
  is_active: boolean;
  history: any[];
}

interface FinanceOverview {
  gross_revenue: number;
  net_profit: number;
  active_escrow: number;
  total_transactions: number;
  success_rate: number;
  daily_target_pct: number;
}

interface FinanceChartData {
  date: string;
  revenue: number;
  profit: number;
}

interface BankTransaction {
  id: string;
  amount: number;
  utr_number: string;
  sender_vpa: string;
  received_at: string;
  is_reconciled: boolean;
}

export default function AdminFinance() {
  const [vpaStats, setVpaStats] = useState<VPAStat[]>([]);
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [chartData, setChartData] = useState<FinanceChartData[]>([]);
  const [bankFeed, setBankFeed] = useState<BankTransaction[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    refreshFinance();
    const interval = setInterval(refreshFinance, 15000);
    return () => clearInterval(interval);
  }, []);

  const refreshFinance = async () => {
    try {
      const [v, o, c, b] = await Promise.all([
        fetchWithAuth("/v2/admin/vpa/stats"),
        fetchWithAuth("/v2/admin/finance/overview"),
        fetchWithAuth("/v2/admin/finance/charts"),
        fetchWithAuth("/v2/admin/finance/bank-feed")
      ]);
      setVpaStats(await v.json());
      setOverview(await o.json());
      setChartData(await c.json());
      setBankFeed(await b.json());
    } catch (e) { console.error("Finance refresh error"); }
  };

  const forceReconcile = async () => {
    toast.info("Triggering automated bank reconciliation...");
    try {
      const res = await fetchWithAuth("/v2/admin/reconcile", { method: "POST" });
      const data = await res.json();
      if (data.matched > 0) {
        toast.success(`Matched ${data.matched} new payments!`);
        refreshFinance();
      } else {
        toast.info("No new matches found.");
      }
    } catch (e) { toast.error("Reconciliation failed"); }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2">
          <CreditCard className="w-6 h-6 text-emerald-500" />
          Financial Suite
        </h2>
        <div className="flex gap-3">
          <Button 
            variant="outline" 
            className="bg-slate-900 border-slate-800 text-xs font-bold uppercase tracking-widest gap-2 hover:bg-emerald-500/10 hover:text-emerald-500 transition-all"
            onClick={forceReconcile}
          >
            <RefreshCw className="w-3.5 h-3.5" />
            TRIGGER RECONCILIATION
          </Button>
        </div>
      </div>

      {/* High-Level Revenue Ledger */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-emerald-600 text-white border-0 shadow-[0_0_30px_rgba(16,185,129,0.2)]">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] opacity-70">Monthly Revenue</p>
            <p className="text-3xl font-black italic tracking-tighter">₹{overview?.gross_revenue.toLocaleString()}</p>
            <div className="flex items-center gap-1 text-[10px] font-bold text-emerald-100">
              <ArrowUpRight className="w-3 h-3" />
              +18.4% from Feb
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Net Platform Profit</p>
            <p className="text-3xl font-black italic tracking-tighter text-emerald-500">₹{overview?.net_profit.toLocaleString()}</p>
            <p className="text-[10px] font-medium text-slate-500 italic">Effective Margin: 6.2%</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Active Escrow</p>
            <p className="text-3xl font-black italic tracking-tighter text-amber-500">₹{overview?.active_escrow.toLocaleString()}</p>
            <p className="text-[10px] font-medium text-slate-500 italic">Held in Trust (NPCI)</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Success Velocity</p>
            <p className="text-3xl font-black italic tracking-tighter text-blue-500">{overview?.success_rate}%</p>
            <p className="text-[10px] font-medium text-slate-500 italic">Across {overview?.total_transactions} txns</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8 space-y-8">
          {/* Growth Trends */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 flex flex-row items-center justify-between py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Revenue & Profit Lifecycle (7D)
              </CardTitle>
              <TrendingUp className="w-4 h-4 text-emerald-500" />
            </CardHeader>
            <CardContent className="p-8 h-[350px] flex items-end justify-between gap-3">
              {chartData.map((d, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-3 group">
                  <div className="relative w-full flex flex-col-reverse gap-1">
                    <div 
                      className="w-full bg-slate-800 rounded-t-lg transition-all group-hover:bg-slate-700" 
                      style={{ height: `${(d.revenue / (Math.max(...chartData.map(x => x.revenue)) || 1)) * 250}px` }} 
                    />
                    <div 
                      className="w-full bg-emerald-500 rounded-t-sm absolute bottom-0 left-0 transition-all group-hover:brightness-110 shadow-[0_0_15px_rgba(16,185,129,0.3)]" 
                      style={{ height: `${(d.profit / (Math.max(...chartData.map(x => x.revenue)) || 1)) * 250}px` }} 
                    />
                  </div>
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-tighter">{d.date}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Task 18.4: Bank Transaction Feed */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Live Bank Statement Feed (NPCI / SMS)
              </CardTitle>
              <ArrowRightLeft className="w-4 h-4 text-primary animate-pulse" />
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[400px]">
                {bankFeed.length === 0 ? (
                  <div className="p-12 text-center opacity-30 italic text-xs uppercase font-black">No recent bank interactions</div>
                ) : (
                  <table className="w-full text-left border-collapse">
                    <thead className="bg-slate-950/50 text-slate-500 font-black uppercase text-[8px] tracking-[0.2em] sticky top-0 z-10 border-b border-slate-800">
                      <tr>
                        <th className="p-4">Timeline</th>
                        <th className="p-4">UTR Number</th>
                        <th className="p-4">Amount</th>
                        <th className="p-4">Sender VPA</th>
                        <th className="p-4 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {bankFeed.map((txn) => (
                        <tr key={txn.id} className="hover:bg-slate-800/30 transition-colors group text-[10px]">
                          <td className="p-4 text-slate-400 font-mono">{new Date(txn.received_at).toLocaleTimeString()}</td>
                          <td className="p-4 font-black text-slate-200 tracking-widest uppercase">{txn.utr_number}</td>
                          <td className="p-4 font-black text-emerald-500">₹{txn.amount.toFixed(2)}</td>
                          <td className="p-4 text-slate-500 font-mono">{txn.sender_vpa || 'NOT_PARSED'}</td>
                          <td className="p-4 text-right">
                            <Badge variant="outline" className={`text-[8px] font-black uppercase ${txn.is_reconciled ? 'text-emerald-500 border-emerald-500/20 bg-emerald-500/5' : 'text-amber-500 border-amber-500/20 bg-amber-500/5'}`}>
                              {txn.is_reconciled ? 'RECONCILED' : 'AWAITING MATCH'}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* VPA Sentinel Sidebar */}
        <div className="lg:col-span-4 space-y-6">
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Wallet className="w-4 h-4 text-primary" />
                VPA Rotation Limits
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-slate-800">
                {vpaStats.map((v) => (
                  <div key={v.vpa} className="p-6 space-y-4 hover:bg-slate-800/30 transition-colors">
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="font-black text-sm text-slate-200">{v.name}</p>
                        <p className="text-[10px] font-mono text-slate-500">{v.vpa}</p>
                      </div>
                      <Badge className={v.is_active ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-[8px] font-black' : 'bg-rose-500/10 text-rose-500 border-rose-500/20 text-[8px] font-black'}>
                        {v.is_active ? 'NOMINAL' : 'INACTIVE'}
                      </Badge>
                    </div>

                    <div className="space-y-2">
                      <div className="flex justify-between text-[10px] font-black uppercase tracking-widest text-slate-500">
                        <span>Daily Quota</span>
                        <span className={v.utilization_pct > 80 ? 'text-rose-500' : 'text-slate-300'}>
                          ₹{v.volume.toLocaleString()} / ₹{(v.limit / 1000)}k
                        </span>
                      </div>
                      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div 
                          className={`h-full transition-all duration-1000 ${v.utilization_pct > 90 ? 'bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.5)]' : v.utilization_pct > 70 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                          style={{ width: `${v.utilization_pct}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800 shadow-2xl p-6">
            <CardContent className="p-0 space-y-4">
              <div className="flex items-center gap-3">
                <div className="bg-primary/10 p-2 rounded-lg"><CheckCircle2 className="w-4 h-4 text-primary" /></div>
                <div><p className="text-[10px] font-black uppercase text-slate-400">Escrow Security</p><p className="text-xs font-bold text-slate-200">100% Matching Active</p></div>
              </div>
              <p className="text-[9px] text-slate-500 leading-relaxed italic">The platform uses a random ₹0.01 - ₹0.99 cent-offset for every booking to ensure automated, unambiguous bank reconciliation.</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
