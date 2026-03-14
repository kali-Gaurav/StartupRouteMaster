import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { 
  MapPin, 
  Train, 
  Clock, 
  ArrowLeft, 
  Navigation, 
  ShieldCheck, 
  AlertTriangle,
  Zap,
  RefreshCw,
  MoreVertical
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { useTelegramWebApp } from "@/hooks/useTelegramWebApp";
import { cn } from "@/lib/utils";

const MiniAppTrack = () => {
  const navigate = useNavigate();
  const { webApp } = useTelegramWebApp();
  const [loading, setLoading] = useState(false);
  
  // Mock data for mini-app feel
  const activeJourney = {
    train_number: "12002",
    train_name: "SHATABDI EXPRESS",
    from: "NDLS",
    to: "BCT",
    status: "ON_TIME",
    delay: 0,
    progress: 65,
    last_station: "KOTA JN",
    next_station: "RATLAM JN",
    eta: "22:40"
  };

  useEffect(() => {
    if (webApp) {
      webApp.BackButton.show();
      webApp.BackButton.onClick(() => navigate("/mini-app"));
    }
    return () => webApp?.BackButton.hide();
  }, [webApp, navigate]);

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-primary selection:text-primary-foreground">
      <div className="p-4 border-b border-border sticky top-0 z-20 bg-background/80 backdrop-blur-xl">
        <div className="max-w-md mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate("/mini-app")} className="rounded-xl lg:hidden">
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-xl font-black uppercase tracking-tighter">Live Vector</h1>
          </div>
          <Button variant="ghost" size="icon" className="rounded-xl">
            <RefreshCw className={cn("h-5 w-5", loading ? "animate-spin" : "")} />
          </Button>
        </div>
      </div>

      <main className="flex-1 max-w-md mx-auto w-full p-4 space-y-6">
        {/* Active Journey Card */}
        <Card className="border-none glass overflow-hidden shadow-xl animate-in zoom-in duration-500">
          <div className="h-2 w-full bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-600" />
          <CardHeader className="pb-4">
            <div className="flex justify-between items-start">
              <div>
                <Badge className="mb-2 bg-emerald-500/10 text-emerald-500 border-none font-black uppercase text-[9px] tracking-widest px-2">Active Mission</Badge>
                <CardTitle className="text-3xl font-black tracking-tighter uppercase">{activeJourney.train_number}</CardTitle>
                <p className="text-xs font-bold text-muted-foreground uppercase opacity-60">{activeJourney.train_name}</p>
              </div>
              <div className="text-right">
                <div className="bg-emerald-500/10 text-emerald-500 text-[10px] font-black px-3 py-1 rounded-full border border-emerald-500/20 inline-flex items-center gap-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  LIVE
                </div>
              </div>
            </div>
          </CardHeader>
          
          <CardContent className="space-y-8">
            {/* Progress Area */}
            <div className="relative pt-8 pb-4">
              <div className="absolute top-0 left-0 w-full flex justify-between text-[10px] font-black text-muted-foreground uppercase tracking-widest">
                <span>{activeJourney.from}</span>
                <span>{activeJourney.to}</span>
              </div>
              <Progress value={activeJourney.progress} className="h-3 bg-muted rounded-full overflow-hidden border border-border">
                <div className="h-full bg-primary shadow-[0_0_15px_rgba(var(--primary),0.5)]" />
              </Progress>
              <div 
                className="absolute top-[22px] transition-all duration-1000 ease-in-out"
                style={{ left: `${activeJourney.progress}%`, transform: 'translateX(-50%)' }}
              >
                <div className="bg-primary text-primary-foreground p-1.5 rounded-lg shadow-lg border-2 border-background animate-float">
                  <Train className="w-4 h-4" />
                </div>
              </div>
              <div className="flex justify-between mt-6 text-[10px] font-black uppercase tracking-tighter">
                <div className="flex flex-col">
                  <span className="text-muted-foreground">Passed</span>
                  <span className="text-sm text-foreground">{activeJourney.last_station}</span>
                </div>
                <div className="flex flex-col items-end text-right">
                  <span className="text-primary">Approaching</span>
                  <span className="text-sm text-foreground">{activeJourney.next_station}</span>
                </div>
              </div>
            </div>

            {/* Current Metrics */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-4 rounded-2xl bg-muted/50 border border-border flex flex-col gap-1">
                <Clock className="w-4 h-4 text-primary mb-1" />
                <span className="text-[9px] font-black text-muted-foreground uppercase tracking-widest">Est. Arrival</span>
                <span className="text-lg font-black tabular-nums">{activeJourney.eta}</span>
              </div>
              <div className="p-4 rounded-2xl bg-muted/50 border border-border flex flex-col gap-1">
                <Zap className="w-4 h-4 text-amber-500 mb-1" />
                <span className="text-[9px] font-black text-muted-foreground uppercase tracking-widest">Latency</span>
                <span className="text-lg font-black text-emerald-500 uppercase tracking-tighter">On Time</span>
              </div>
            </div>

            <Button className="w-full h-14 rounded-2xl font-black uppercase tracking-widest shadow-lg shadow-primary/20 active:scale-95 transition-all">
              FULL TELEMETRY LOG
            </Button>
          </CardContent>
        </Card>

        {/* Action List */}
        <div className="space-y-3">
          <h2 className="text-xs font-black uppercase tracking-widest text-muted-foreground ml-1">Mission Support</h2>
          <Card className="border-none glass divide-y divide-border overflow-hidden">
            <div className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer group">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                  <Navigation className="w-5 h-5 text-blue-500" />
                </div>
                <span className="text-sm font-black uppercase tracking-tight">Interactive Map</span>
              </div>
              <Badge variant="outline" className="text-[8px] font-black uppercase group-hover:bg-primary group-hover:text-white transition-colors">OSM</Badge>
            </div>
            <div className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer group">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5 text-purple-500" />
                </div>
                <span className="text-sm font-black uppercase tracking-tight">Safety Protocol</span>
              </div>
              <Badge variant="outline" className="text-[8px] font-black uppercase group-hover:bg-emerald-500 group-hover:text-white transition-colors">ACTIVE</Badge>
            </div>
            <div className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer group">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5 text-orange-500" />
                </div>
                <span className="text-sm font-black uppercase tracking-tight">Report Delay</span>
              </div>
              <MoreVertical className="w-4 h-4 text-muted-foreground opacity-40" />
            </div>
          </Card>
        </div>

        {/* Disclaimer */}
        <p className="text-[9px] text-center font-black uppercase text-muted-foreground tracking-widest leading-relaxed opacity-50 px-6">
          Telemetry synthesized from RapidAPI real-time node feeds and TDI interpolation. 
          Positional accuracy validated at station checkpoints.
        </p>
      </main>
    </div>
  );
};

export default MiniAppTrack;
