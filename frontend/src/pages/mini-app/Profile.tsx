import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { 
  User, 
  Settings, 
  Shield, 
  LogOut, 
  ArrowLeft, 
  ChevronRight, 
  Bell, 
  Moon, 
  Smartphone,
  CheckCircle2,
  RefreshCw,
  Clock
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/context/AuthContext";
import { supabase } from "@/lib/supabase";
import { toast } from "sonner";
import { useTelegramWebApp } from "@/hooks/useTelegramWebApp";
import { cn } from "@/lib/utils";

const MiniAppProfile = () => {
  const navigate = useNavigate();
  const { user, signOut } = useAuth();
  const { webApp } = useTelegramWebApp();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (webApp) {
      webApp.BackButton.show();
      webApp.BackButton.onClick(() => navigate("/mini-app"));
    }
    return () => webApp?.BackButton.hide();
  }, [webApp, navigate]);

  const handleSignOut = async () => {
    setLoading(true);
    try {
      await signOut();
      navigate("/login");
      toast.success("Session decommissioned");
    } catch (e) {
      toast.error("Decommissioning failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-primary selection:text-primary-foreground">
      <div className="p-4 border-b border-border sticky top-0 z-20 bg-background/80 backdrop-blur-xl">
        <div className="max-w-md mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate("/mini-app")} className="rounded-xl lg:hidden">
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-xl font-black uppercase tracking-tighter">Terminal ID</h1>
          </div>
          <Button variant="ghost" size="icon" className="rounded-xl">
            <Settings className="h-5 w-5" />
          </Button>
        </div>
      </div>

      <main className="flex-1 max-w-md mx-auto w-full p-6 space-y-8">
        {/* User Identity Section */}
        <div className="text-center space-y-4 pt-4">
          <div className="relative inline-block">
            <div className="w-24 h-24 rounded-3xl bg-primary/10 flex items-center justify-center mx-auto shadow-inner border-2 border-primary/20 group">
              <User className="h-12 w-12 text-primary group-hover:scale-110 transition-transform" />
            </div>
            <div className="absolute -bottom-2 -right-2 bg-emerald-500 text-white p-1.5 rounded-xl border-4 border-background shadow-lg">
              <CheckCircle2 className="h-4 w-4" />
            </div>
          </div>
          <div>
            <h2 className="text-2xl font-black uppercase tracking-tighter">{user?.first_name || "Authorized Entity"}</h2>
            <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest opacity-60 mt-1">{user?.email}</p>
          </div>
          <div className="flex justify-center gap-2">
            <Badge className="bg-primary/10 text-primary border-none font-black text-[9px] px-3 uppercase tracking-widest">GOLD_TIER</Badge>
            <Badge className="bg-emerald-500/10 text-emerald-500 border-none font-black text-[9px] px-3 uppercase tracking-widest">VERIFIED</Badge>
          </div>
        </div>

        {/* Action Groups */}
        <div className="space-y-6 pb-10">
          <div className="space-y-3">
            <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground ml-1">System Interface</h3>
            <Card className="border-none glass divide-y divide-border overflow-hidden">
              <div className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer group">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                    <Bell className="h-5 w-5 text-blue-500" />
                  </div>
                  <span className="text-sm font-black uppercase tracking-tight">Signal Config</span>
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground opacity-40 group-hover:opacity-100 transition-opacity" />
              </div>
              <div className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer group">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                    <Moon className="h-5 w-5 text-purple-500" />
                  </div>
                  <span className="text-sm font-black uppercase tracking-tight">Interface Theme</span>
                </div>
                <Badge variant="outline" className="text-[8px] font-black uppercase">AUTO</Badge>
              </div>
              <div className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer group">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center">
                    <Smartphone className="h-5 w-5 text-orange-500" />
                  </div>
                  <span className="text-sm font-black uppercase tracking-tight">Link Device</span>
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground opacity-40 group-hover:opacity-100 transition-opacity" />
              </div>
            </Card>
          </div>

          <div className="space-y-3">
            <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground ml-1">Security Node</h3>
            <Card className="border-none glass divide-y divide-border overflow-hidden">
              <div className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer group">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
                    <Shield className="h-5 w-5 text-red-500" />
                  </div>
                  <span className="text-sm font-black uppercase tracking-tight">Biometric Lock</span>
                </div>
                <Badge variant="outline" className="text-[8px] font-black uppercase text-red-500 border-red-500/20 bg-red-500/5">OFF</Badge>
              </div>
              <div className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors cursor-pointer group" onClick={handleSignOut}>
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center">
                    <LogOut className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <span className="text-sm font-black uppercase tracking-tight text-muted-foreground group-hover:text-red-500 transition-colors">Decommission Session</span>
                </div>
                {loading && <RefreshCw className="h-4 w-4 animate-spin text-primary" />}
              </div>
            </Card>
          </div>
        </div>

        {/* Footer info */}
        <div className="pt-4 text-center space-y-4">
          <div className="flex items-center justify-center gap-2 text-muted-foreground opacity-40">
            <Clock className="h-3 w-3" />
            <span className="text-[9px] font-black uppercase tracking-widest">Last Auth: {new Date().toLocaleDateString()}</span>
          </div>
          <p className="text-[8px] font-black uppercase text-muted-foreground tracking-[0.3em] opacity-30 leading-relaxed">
            RouteMaster Mini-App Terminal v2.5.0-alpha<br/>
            Neural Link Status: STABLE
          </p>
        </div>
      </main>
    </div>
  );
};

export default MiniAppProfile;
