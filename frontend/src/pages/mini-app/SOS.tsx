import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { 
  ShieldAlert, 
  ArrowLeft, 
  MapPin, 
  Phone, 
  Loader2, 
  Zap,
  Activity,
  User,
  Navigation,
  CheckCircle,
  Heart
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useTelegramWebApp } from "@/hooks/useTelegramWebApp";
import { cn } from "@/lib/utils";

const MiniAppSOS = () => {
  const navigate = useNavigate();
  const { webApp } = useTelegramWebApp();
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(false);
  const [activeMode, setActiveMode] = useState<'emergency' | 'shield'>('emergency');

  useEffect(() => {
    if (webApp) {
      webApp.BackButton.show();
      webApp.BackButton.onClick(() => navigate("/mini-app"));
    }
    return () => webApp?.BackButton.hide();
  }, [webApp, navigate]);

  const handleTrigger = () => {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setActive(true);
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-red-500 selection:text-white">
      <div className="p-4 border-b border-border sticky top-0 z-20 bg-background/80 backdrop-blur-xl">
        <div className="max-w-md mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate("/mini-app")} className="rounded-xl">
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-xl font-black uppercase tracking-tighter">SafeGuard Node</h1>
          </div>
          <div className="flex items-center gap-2">
             <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
             <span className="text-[10px] font-black uppercase text-emerald-500">Live</span>
          </div>
        </div>
      </div>

      <main className="flex-1 max-w-md mx-auto w-full p-6 flex flex-col items-center">
        {active ? (
          /* ACTIVE MONITORING VIEW */
          <div className="w-full space-y-10 animate-in zoom-in duration-500 py-10">
            <div className="relative flex justify-center">
              <div className="w-48 h-48 rounded-full border-4 border-red-500/20 flex items-center justify-center relative z-10">
                <div className="w-36 h-36 rounded-full bg-red-600 flex items-center justify-center shadow-[0_0_60px_rgba(220,38,38,0.5)] animate-pulse">
                  <ShieldAlert className="w-16 h-16 text-white" />
                </div>
              </div>
              <div className="absolute inset-0 bg-red-500/10 rounded-full animate-ping" />
            </div>

            <div className="text-center space-y-3">
              <h2 className="text-3xl font-black uppercase tracking-tighter">Active Distress</h2>
              <p className="text-muted-foreground text-sm font-bold uppercase opacity-70">Telemetry uplink established</p>
            </div>

            <Card className="border-none glass bg-red-500/5">
              <CardContent className="p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-border/50 pb-3">
                  <span className="text-[10px] font-black uppercase text-muted-foreground">Coordinates</span>
                  <span className="text-xs font-mono font-black tabular-nums text-red-500">28.6139, 77.2090</span>
                </div>
                <div className="flex items-center justify-between border-b border-border/50 pb-3">
                  <span className="text-[10px] font-black uppercase text-muted-foreground">Accuracy</span>
                  <span className="text-xs font-black uppercase text-emerald-500">High (GPS)</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-black uppercase text-muted-foreground">Response Node</span>
                  <span className="text-xs font-black uppercase">NDLS_CENTRAL</span>
                </div>
              </CardContent>
            </Card>

            <div className="space-y-3">
              <Button className="w-full h-16 bg-white text-black hover:bg-white/90 rounded-2xl font-black uppercase tracking-widest text-lg shadow-xl" onClick={() => window.location.href="tel:112"}>
                <Phone className="w-6 h-6 mr-3 fill-current" /> CALL EMERGENCY
              </Button>
              <Button variant="ghost" className="w-full h-14 rounded-2xl font-black uppercase tracking-widest text-xs text-muted-foreground" onClick={() => setActive(false)}>
                I AM SAFE - END UPLINK
              </Button>
            </div>
          </div>
        ) : (
          /* INITIAL ACTIVATION VIEW */
          <div className="w-full space-y-8 py-4 animate-in slide-in-from-bottom-4 duration-500">
            <div className="space-y-2">
              <h2 className="text-5xl font-black uppercase tracking-tighter leading-none italic">CRITICAL<br/>RESPONSE</h2>
              <p className="text-sm font-bold text-muted-foreground uppercase opacity-60">Instant Distress Signal Deployment</p>
            </div>

            <div className="flex flex-col items-center py-10">
              <button 
                onClick={handleTrigger}
                disabled={loading}
                className="group relative active:scale-95 transition-transform"
              >
                <div className="absolute inset-0 bg-red-600 rounded-full blur-[80px] opacity-20 group-hover:opacity-40 transition-opacity" />
                <div className="w-64 h-64 rounded-full border-8 border-background bg-red-600 flex flex-col items-center justify-center shadow-2xl relative z-10 hover:scale-105 transition-transform">
                  {loading ? <Loader2 className="w-16 h-16 animate-spin text-white" /> : (
                    <>
                      <Zap className="w-12 h-12 text-white fill-current mb-2" />
                      <span className="text-4xl font-black text-white uppercase tracking-widest italic">SOS</span>
                    </>
                  )}
                </div>
              </button>
              <p className="mt-8 text-[10px] font-black uppercase text-muted-foreground tracking-[0.3em] opacity-50">Press to broadcast</p>
            </div>

            <div className="grid grid-cols-1 gap-4">
              <Card className="border-none glass bg-primary/5 hover:bg-primary/10 transition-colors cursor-pointer group" onClick={() => setActiveMode('shield')}>
                <CardContent className="p-6 flex items-center gap-5">
                  <div className="w-14 h-14 rounded-2xl bg-primary/20 flex items-center justify-center shrink-0">
                    <Heart className="w-7 h-7 text-primary" />
                  </div>
                  <div>
                    <h4 className="font-black uppercase text-sm tracking-tight">Proactive Shield</h4>
                    <p className="text-[10px] font-bold text-muted-foreground uppercase leading-tight opacity-60 mt-1">Continuous telemetry sharing for late night travel</p>
                  </div>
                </CardContent>
              </Card>
              
              <Card className="border-none glass bg-blue-500/5 hover:bg-blue-500/10 transition-colors cursor-pointer">
                <CardContent className="p-6 flex items-center gap-5">
                  <div className="w-14 h-14 rounded-2xl bg-blue-500/20 flex items-center justify-center shrink-0">
                    <Activity className="w-7 h-7 text-blue-500" />
                  </div>
                  <div>
                    <h4 className="font-black uppercase text-sm tracking-tight">AI Guardian</h4>
                    <p className="text-[10px] font-bold text-muted-foreground uppercase leading-tight opacity-60 mt-1">Neural risk detection via motion sensors</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        <footer className="mt-auto pt-10 pb-4 text-center">
          <p className="text-[9px] font-black uppercase text-muted-foreground tracking-widest opacity-40 leading-relaxed max-w-[200px] mx-auto">
            Authorized safety node. Synchronized with IRCTC Safe-Journey telemetry protocols.
          </p>
        </footer>
      </main>
    </div>
  );
};

export default MiniAppSOS;
