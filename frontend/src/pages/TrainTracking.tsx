import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Train, MapPin, Clock, AlertTriangle, RefreshCcw, ArrowLeft, Navigation, Search, Zap, Activity, ShieldAlert } from "lucide-react";
import { useTrainStatus } from "@/api/hooks/useTrainStatus";
import { cn } from "@/lib/utils";

export default function TrainTracking() {
  const { trainNumber } = useParams();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");

  const {
    data: statusData,
    isLoading: loading,
    refetch,
    isRefetching
  } = useTrainStatus(trainNumber || "");

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/track/${searchQuery.trim()}`);
    }
  };

  // 1. Search First State (Task: Better UX if no train number)
  if (!trainNumber) {
    return (
      <div className="min-h-screen flex flex-col bg-background selection:bg-primary selection:text-primary-foreground">
        <Navbar />
        <main className="flex-1 flex flex-col items-center pt-32 p-4 relative">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,rgba(var(--primary),0.05),transparent_50%)] pointer-events-none" />
          
          <Card className="w-full max-w-2xl shadow-2xl border-t-4 border-t-primary glass overflow-hidden relative z-10">
            {/* Header like IRCTC/Dashboard */}
            <div className="flex gap-1 px-6 pt-4 pb-2 bg-[#0f172a] dark:bg-[#0c4a6e]">
              <div className="px-4 py-2 text-sm font-semibold text-white border-b-2 border-white flex items-center gap-2">
                <Navigation className="w-4 h-4" />
                LIVE TRACKER
              </div>
            </div>

            <CardHeader className="text-center pt-10 pb-6">
              <div className="mx-auto w-16 h-16 rounded-3xl bg-primary/10 flex items-center justify-center mb-6 shadow-inner">
                <Train className="w-8 h-8 text-primary animate-pulse" />
              </div>
              <CardTitle className="text-4xl font-black uppercase tracking-tighter text-foreground">Mission Radar</CardTitle>
              <CardDescription className="text-base font-medium opacity-70">
                Synchronize with real-time rail telemetry via 5-digit ID
              </CardDescription>
            </CardHeader>
            <CardContent className="px-10 pb-10">
              <form onSubmit={handleSearch} className="space-y-6">
                <div className="relative group">
                  <Search className="absolute left-5 top-5 h-6 w-6 text-muted-foreground group-focus-within:text-primary transition-colors" />
                  <Input
                    placeholder="Enter Train Number (e.g. 12002)"
                    className="pl-14 py-9 text-2xl font-black rounded-2xl border-2 bg-muted/20 focus:bg-background transition-all shadow-inner tracking-[0.2em]"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    autoFocus
                  />
                </div>
                <Button type="submit" className="w-full py-9 rounded-2xl text-lg font-black uppercase tracking-[0.2em] shadow-xl shadow-primary/20 hover:scale-[1.01] active:scale-[0.99] transition-all">
                  INITIALIZE TELEMETRY
                </Button>
              </form>
            </CardContent>
            <CardFooter className="flex justify-center border-t p-8 bg-muted/30">
               <div className="flex gap-8 text-[10px] font-black text-muted-foreground uppercase tracking-[0.2em]">
                 <span className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-amber-500 fill-current" /> REAL-TIME GPS</span>
                 <span className="flex items-center gap-2"><Activity className="w-3.5 h-3.5 text-primary" /> VECTOR ANALYSIS</span>
               </div>
            </CardFooter>
          </Card>
        </main>
        <Footer />
      </div>
    );
  }

  // 2. Loading State
  if (loading && !statusData) {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <Navbar />
        <main className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <div className="relative">
              <Train className="w-16 h-16 text-primary animate-bounce" />
              <div className="absolute inset-0 w-16 h-16 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
            </div>
            <p className="font-black text-xl text-foreground tracking-tighter uppercase">Synchronizing Telemetry {trainNumber}...</p>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  const live = statusData?.live_status;
  const position = statusData?.estimated_position;

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-8 pt-24 flex-1 max-w-5xl">
        <div className="mb-8 flex items-center justify-between">
          <Button variant="ghost" onClick={() => navigate("/track")} className="gap-2 hover:bg-primary/5 font-bold">
            <ArrowLeft className="w-4 h-4" /> New Search
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-2 font-bold border-2 rounded-xl">
              <RefreshCcw className={cn("w-4 h-4", isRefetching ? 'animate-spin' : '')} /> Refresh
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Info Card */}
          <Card className="lg:col-span-2 shadow-2xl border-none glass overflow-hidden">
            <div className="h-2 w-full bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-600" />
            <CardHeader className="pb-4">
              <div className="flex flex-wrap justify-between items-start gap-4">
                <div>
                  <Badge className="mb-3 uppercase tracking-widest text-[10px] bg-primary/10 text-primary border-none font-black px-3">Live Mission Status</Badge>
                  <CardTitle className="text-4xl sm:text-5xl font-black tracking-tighter text-foreground mb-1">{trainNumber}</CardTitle>
                  <p className="text-muted-foreground font-bold text-lg">{live?.train_name || "Railway Express Service"}</p>
                </div>
                <div className="text-right">
                  <div className={cn(
                    "text-xs font-black px-4 py-2 rounded-2xl shadow-sm inline-flex items-center gap-2",
                    live?.delay_minutes > 0 ? 'bg-red-500/10 text-red-500 border border-red-500/20' : 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
                  )}>
                    <div className={cn("w-2 h-2 rounded-full animate-pulse", live?.delay_minutes > 0 ? "bg-red-500" : "bg-emerald-500")} />
                    {live?.delay_minutes > 0 ? `${live.delay_minutes}m Late` : 'Operating On Time'}
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-10">
              {/* Progress Visual */}
              <div className="relative pt-10 pb-6 px-4 bg-muted/30 rounded-3xl border border-border/50">
                <div className="absolute top-4 left-6 text-[10px] font-black text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                  <Activity className="w-3 h-3 text-primary" /> Route Vector Progress
                </div>
                <Progress value={position?.progress_percentage || 0} className="h-4 bg-muted border border-border rounded-full" />
                <div className="flex justify-between mt-4 text-[10px] font-black text-muted-foreground uppercase tracking-widest">
                  <div className="flex flex-col gap-1">
                    <span className="text-foreground text-sm">{position?.last_station?.name || "DEPARTURE"}</span>
                    <span className="text-[8px] opacity-60">Passed</span>
                  </div>
                  <div className="flex flex-col items-end gap-1 text-right">
                    <span className="text-foreground text-sm">{position?.next_station?.name || "DESTINATION"}</span>
                    <span className="text-[8px] opacity-60">Approaching</span>
                  </div>
                </div>
                {/* Train Icon Overlay */}
                <div 
                  className="absolute top-[40px] transition-all duration-1000 ease-in-out"
                  style={{ left: `${(position?.progress_percentage || 0)}%`, transform: 'translateX(-50%)' }}
                >
                  <div className="bg-primary text-primary-foreground p-2 rounded-xl shadow-[0_0_20px_rgba(var(--primary),0.4)] border-2 border-background animate-float">
                    <Train className="w-5 h-5" />
                  </div>
                </div>
              </div>

              {/* Current Status Box */}
              <div className="bg-primary/5 rounded-[2rem] p-8 border border-primary/10 relative overflow-hidden group">
                <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl -mr-32 -mt-32 group-hover:bg-primary/10 transition-colors" />
                <div className="relative flex items-center gap-6">
                  <div className="bg-primary text-primary-foreground p-4 rounded-2xl shadow-xl shadow-primary/20 rotate-3 group-hover:rotate-0 transition-transform">
                    <MapPin className="w-8 h-8" />
                  </div>
                  <div>
                    <p className="text-[10px] font-black text-primary uppercase mb-1 tracking-widest">Current Position Vector</p>
                    <h3 className="text-2xl font-black text-foreground tracking-tight">{live?.status_message || "In Transit"}</h3>
                    <p className="text-sm text-muted-foreground font-bold">Currently at or near <span className="text-primary">{live?.current_station_name}</span></p>
                  </div>
                </div>
              </div>

              {/* Telemetry Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-6">
                <div className="p-6 bg-card border rounded-3xl shadow-sm hover:shadow-md transition-shadow">
                  <Clock className="w-6 h-6 text-blue-500 mb-3" />
                  <p className="text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-1">Last Uplink</p>
                  <p className="text-lg font-black">{live?.last_updated ? new Date(live.last_updated).toLocaleTimeString() : '--:--'}</p>
                </div>
                <div className="p-6 bg-card border rounded-3xl shadow-sm hover:shadow-md transition-shadow">
                  <Navigation className="w-6 h-6 text-purple-500 mb-3" />
                  <p className="text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-1">Coordinates</p>
                  <p className="text-lg font-black font-mono tracking-tighter">{position?.lat?.toFixed(3)}, {position?.lon?.toFixed(3)}</p>
                </div>
                <div className="p-6 bg-card border rounded-3xl shadow-sm hover:shadow-md transition-shadow col-span-2 sm:col-span-1">
                  <AlertTriangle className="w-6 h-6 text-orange-500 mb-3" />
                  <p className="text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-1">Integrity</p>
                  <p className="text-lg font-black">{statusData?.metadata?.live_uplink ? 'HIGH' : 'ESTIMATED'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Sidebar Area */}
          <div className="space-y-8">
            <Card className="bg-slate-950 text-white border-none shadow-2xl overflow-hidden relative rounded-[2rem]">
              <div className="absolute top-0 right-0 w-48 h-48 bg-primary/30 rounded-full blur-[80px] -mr-24 -mt-24"></div>
              <div className="absolute bottom-0 left-0 w-32 h-32 bg-indigo-500/20 rounded-full blur-[60px] -ml-16 -mb-16"></div>
              <CardHeader className="relative">
                <CardTitle className="text-xl font-black uppercase tracking-tight flex items-center gap-2">
                  <Zap className="w-5 h-5 text-yellow-400 fill-current animate-pulse" strokeWidth={3} />
                  Neural Analytics
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6 relative">
                <div className="space-y-4">
                   <div className="flex justify-between items-center border-b border-white/10 pb-3">
                     <span className="text-white/40 text-xs font-bold uppercase tracking-widest">ETA Destination</span>
                     <span className="font-black text-base text-cyan-400">--:--</span>
                   </div>
                   <div className="flex justify-between items-center border-b border-white/10 pb-3">
                     <span className="text-white/40 text-xs font-bold uppercase tracking-widest">Rem. Distance</span>
                     <span className="font-black text-base">-- KM</span>
                   </div>
                   <div className="flex justify-between items-center">
                     <span className="text-white/40 text-xs font-bold uppercase tracking-widest">Avg Velocity</span>
                     <span className="font-black text-base">55 KM/H</span>
                   </div>
                </div>
                <Button className="w-full bg-white/10 hover:bg-white/20 text-white border border-white/10 font-black rounded-2xl py-6">
                  VIEW FULL SCHEDULE
                </Button>
              </CardContent>
            </Card>

            <Card className="rounded-[2rem] border-none bg-primary/5 p-1">
              <div className="bg-background rounded-[1.9rem] p-6 border border-border/50">
                <h4 className="font-black text-xs text-primary uppercase mb-3 tracking-widest flex items-center gap-2">
                  <ShieldAlert className="w-3 h-3" /> Security Protocol
                </h4>
                <p className="text-[11px] leading-relaxed text-muted-foreground font-bold">
                  Telemetry is synthesized from RapidAPI real-time feeds and Time-Differential Interpolation. 
                  Vector accuracy is verified at station checkpoints.
                </p>
              </div>
            </Card>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
