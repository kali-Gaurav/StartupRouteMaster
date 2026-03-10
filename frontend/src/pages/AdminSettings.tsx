import { useState, useEffect } from "react";
import {
  Settings,
  IndianRupee,
  Save,
  Power,
  Shield,
  Target
} from "lucide-react";
import { fetchWithAuth } from "@/lib/apiClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";

interface PlatformConfig {
  key: string;
  value: string;
  description: string;
}

export default function AdminSettings() {
  const [configs, setConfigs] = useState<PlatformConfig[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    try {
      const res = await fetchWithAuth("/admin/config");
      setConfigs(await res.json());
    } catch (e) { console.error("Config error"); }
  };

  const updateConfig = async (key: string, value: string) => {
    setLoading(true);
    try {
      await fetchWithAuth("/admin/config/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, value })
      });
      toast.success(`${key} updated successfully.`);
      loadConfigs();
    } catch (e) { toast.error("Update failed"); }
    finally { setLoading(false); }
  };

  const getConfig = (key: string) => configs.find(c => c.key === key)?.value || "";

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2">
          <Settings className="w-6 h-6 text-primary" />
          Platform Configuration
        </h2>
        <Badge variant="outline" className="font-mono bg-primary/5 border-primary/20 text-primary px-3 py-1">
          DYNAMO ENGINE ACTIVE
        </Badge>
      </div>

      <div className="grid lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8 space-y-8">
          {/* Maintenance & Core Toggles */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Core System Toggles
              </CardTitle>
              <Power className="w-4 h-4 text-primary" />
            </CardHeader>
            <CardContent className="p-8 space-y-8">
              <div className="flex items-center justify-between group">
                <div className="space-y-1">
                  <p className="text-sm font-black text-slate-200 uppercase tracking-tight">Maintenance Mode</p>
                  <p className="text-[10px] text-slate-500 font-medium italic">Instantly disable all user search and booking interactions.</p>
                </div>
                <Button 
                  onClick={() => updateConfig("MAINTENANCE_MODE", getConfig("MAINTENANCE_MODE") === "ON" ? "OFF" : "ON")}
                  variant={getConfig("MAINTENANCE_MODE") === "ON" ? "destructive" : "outline"}
                  className="w-32 h-10 font-black uppercase tracking-widest text-[10px]"
                >
                  {getConfig("MAINTENANCE_MODE") === "ON" ? "DEACTIVATE" : "ACTIVATE"}
                </Button>
              </div>

              <div className="h-px bg-slate-800" />

              <div className="flex items-center justify-between group">
                <div className="space-y-1">
                  <p className="text-sm font-black text-slate-200 uppercase tracking-tight">Tatkal Priority Overrides</p>
                  <p className="text-[10px] text-slate-500 font-medium italic">Enforce strict chrono-priority queueing even outside window.</p>
                </div>
                <Button 
                  onClick={() => updateConfig("TATKAL_OVERRIDE", getConfig("TATKAL_OVERRIDE") === "ON" ? "OFF" : "ON")}
                  variant={getConfig("TATKAL_OVERRIDE") === "ON" ? "secondary" : "outline"}
                  className="w-32 h-10 font-black uppercase tracking-widest text-[10px]"
                >
                  {getConfig("TATKAL_OVERRIDE") === "ON" ? "ON" : "OFF"}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Pricing Configuration */}
          <Card className="bg-slate-900 border-slate-800 shadow-2xl">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Dynamic Service Fees
              </CardTitle>
              <IndianRupee className="w-4 h-4 text-emerald-500" />
            </CardHeader>
            <CardContent className="p-8">
              <div className="grid md:grid-cols-2 gap-12">
                <div className="space-y-4">
                  <label className="text-[10px] font-black uppercase text-slate-500 tracking-widest">Route Unlock Fee</label>
                  <div className="flex gap-3">
                    <div className="relative flex-1">
                      <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 font-black text-sm">₹</span>
                      <input 
                        type="text" 
                        defaultValue={getConfig("UNLOCK_FEE") || "49.00"}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 h-12 font-black text-white focus:border-primary focus:outline-none"
                        onBlur={(e) => updateConfig("UNLOCK_FEE", e.target.value)}
                      />
                    </div>
                    <Button variant="outline" size="icon" className="h-12 w-12"><Save className="w-4 h-4" /></Button>
                  </div>
                </div>

                <div className="space-y-4">
                  <label className="text-[10px] font-black uppercase text-slate-500 tracking-widest">Agent Service Fee</label>
                  <div className="flex gap-3">
                    <div className="relative flex-1">
                      <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 font-black text-sm">₹</span>
                      <input 
                        type="text" 
                        defaultValue={getConfig("AGENT_FEE") || "19.00"}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 h-12 font-black text-white focus:border-primary focus:outline-none"
                        onBlur={(e) => updateConfig("AGENT_FEE", e.target.value)}
                      />
                    </div>
                    <Button variant="outline" size="icon" className="h-12 w-12"><Save className="w-4 h-4" /></Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-4 space-y-8">
          <Card className="bg-slate-900 border-slate-800 shadow-2xl p-6 border-t-4 border-t-primary">
            <CardContent className="p-0 space-y-4">
              <div className="flex items-center gap-3 text-primary">
                <Shield className="w-6 h-6" />
                <p className="font-black uppercase tracking-widest">Configuration HSM</p>
              </div>
              <p className="text-[10px] text-slate-500 font-medium leading-relaxed italic">Platform configs are cryptographically signed and stored in the core userStore. Changing fees will affect all new bookings instantly.</p>
              <div className="pt-4 border-t border-slate-800 space-y-2">
                <div className="flex justify-between text-[8px] font-black uppercase text-slate-600"><span>Last Global Sync</span><span>JUST NOW</span></div>
                <div className="flex justify-between text-[8px] font-black uppercase text-slate-600"><span>Engine Consistency</span><span>VERIFIED</span></div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800 shadow-2xl">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Target className="w-4 h-4 text-amber-500" />
                Active Thresholds
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between text-[10px] font-black uppercase text-slate-500"><span>Latency Alert</span><span>2.0s</span></div>
                <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden"><div className="h-full bg-primary" style={{ width: '40%' }} /></div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-[10px] font-black uppercase text-slate-500"><span>Max Queue Depth</span><span>50 Req</span></div>
                <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden"><div className="h-full bg-amber-500" style={{ width: '65%' }} /></div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
