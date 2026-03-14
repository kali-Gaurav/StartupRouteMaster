import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Search,
  MapPin,
  AlertTriangle,
  Heart,
  BarChart3,
  Settings,
  Train,
  Clock,
  Star,
  Shield,
  RefreshCw,
  Zap,
  Activity
} from "lucide-react";
import { getRailwayApiUrl } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { useTelegramWebApp } from "@/hooks/useTelegramWebApp";
import { fetchWithAuth } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

interface Recommendation {
  origin_code: string;
  origin_name: string;
  destination_code: string;
  destination_name: string;
  score: number;
}

const MiniAppHome = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user, isAuthenticated } = useAuth();
  const { webApp, applyTheme } = useTelegramWebApp();
  const [stats, setStats] = useState({
    totalJourneys: 0,
    savedRoutes: 0,
    badges: 0
  });
  const [statsError, setStatsError] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [popularRoutes, setPopularRoutes] = useState<Recommendation[]>([]);

  useEffect(() => {
    if (webApp) {
      webApp.ready();
      webApp.expand();
      applyTheme();
    }
  }, [webApp, applyTheme]);

  useEffect(() => {
    if (isAuthenticated && user?.user_id) {
      loadUserStats();
      loadRecommendations(Number(user.user_id));
    }
    loadPopularRoutes();

    const startApp = searchParams.get("startapp");
    if (startApp) {
      switch (startApp) {
        case "search":
          navigate("/mini-app/search");
          break;
        case "sos":
          navigate("/mini-app/sos");
          break;
        case "track":
          navigate("/mini-app/track");
          break;
      }
    }
  }, [searchParams, navigate, isAuthenticated, user?.user_id]);

  const loadRecommendations = async (userId: number) => {
    try {
      const response = await fetch(getRailwayApiUrl(`/api/recommendations/${userId}?limit=3`));
      if (response.ok) {
        const data = await response.json();
        setRecommendations(data.recommendations || []);
      }
    } catch (error) {
      console.error("Failed to load recommendations:", error);
    }
  };

  const loadPopularRoutes = async () => {
    try {
      const response = await fetch(getRailwayApiUrl("/api/popular-routes?limit=3"));
      if (response.ok) {
        const data = await response.json();
        setPopularRoutes(data.popular_routes || []);
      }
    } catch (error) {
      console.error("Failed to load popular routes:", error);
    }
  };

  const handleQuickSearch = (origin: string, destination: string) => {
    navigate(`/mini-app/search?from=${origin}&to=${destination}`);
  };

  const loadUserStats = async () => {
    setStatsError(null);
    try {
      const response = await fetchWithAuth("/user/me/stats");
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      } else {
        setStatsError("Could not load stats.");
      }
    } catch (error) {
      console.error("Failed to load user stats:", error);
      setStatsError("Could not load. Retry?");
    }
  };

  const handleCardClick = (path: string) => {
    navigate(path);
  };

  const quickActions = [
    {
      title: "Search Trains",
      description: "Find routes between stations",
      icon: Search,
      path: "/mini-app/search",
      gradient: "from-blue-500 to-blue-600"
    },
    {
      title: "Track Journey",
      description: "Monitor active trips",
      icon: MapPin,
      path: "/mini-app/track",
      gradient: "from-green-500 to-green-600"
    },
    {
      title: "Emergency SOS",
      description: "Get help in emergencies",
      icon: AlertTriangle,
      path: "/mini-app/sos",
      gradient: "from-red-500 to-red-600"
    },
    {
      title: "Saved Routes",
      description: "Your favorite journeys",
      icon: Heart,
      path: "/mini-app/saved",
      gradient: "from-purple-500 to-purple-600"
    }
  ];

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-primary selection:text-primary-foreground p-4">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(var(--primary),0.05),transparent_50%)] pointer-events-none" />
      
      <div className="max-w-md mx-auto space-y-6 relative z-10">
        {/* Header */}
        <div className="text-center space-y-2 py-4">
          <div className="flex items-center justify-center gap-3">
            <div className="w-12 h-12 bg-primary/10 rounded-2xl flex items-center justify-center shadow-lg shadow-primary/5">
              <Train className="h-7 w-7 text-primary" />
            </div>
            <h1 className="text-3xl font-black tracking-tighter text-foreground uppercase">RouteMaster</h1>
          </div>
          <div className="flex items-center justify-center gap-2">
             <span className="px-2 py-0.5 rounded bg-muted text-[10px] font-black uppercase tracking-widest text-muted-foreground border border-border">System v2.5</span>
             <span className="flex items-center gap-1 text-[10px] font-black uppercase text-emerald-500">
               <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
               Live
             </span>
          </div>
          {user && (
            <p className="text-sm font-bold text-muted-foreground mt-4">
              Welcome back, <span className="text-foreground">{user.first_name || "Traveler"}</span>!
            </p>
          )}
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-3 gap-3">
          <Card className="text-center border-none glass overflow-hidden shadow-sm">
            <CardContent className="p-4">
              <div className="text-xl font-black text-primary">{stats.totalJourneys}</div>
              <p className="text-[10px] font-black uppercase text-muted-foreground tracking-tighter">Journeys</p>
            </CardContent>
          </Card>
          <Card className="text-center border-none glass overflow-hidden shadow-sm">
            <CardContent className="p-4">
              <div className="text-xl font-black text-emerald-500">{stats.savedRoutes}</div>
              <p className="text-[10px] font-black uppercase text-muted-foreground tracking-tighter">Saved</p>
            </CardContent>
          </Card>
          <Card className="text-center border-none glass overflow-hidden shadow-sm">
            <CardContent className="p-4">
              <div className="text-xl font-black text-amber-500">{stats.badges}</div>
              <p className="text-[10px] font-black uppercase text-muted-foreground tracking-tighter">Badges</p>
            </CardContent>
          </Card>
        </div>

        {statsError && isAuthenticated && (
          <div className="flex items-center justify-between gap-2 rounded-2xl bg-amber-500/10 border border-amber-500/20 px-4 py-3 text-xs font-bold text-amber-600">
            <span className="flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> {statsError}</span>
            <Button size="sm" variant="ghost" onClick={() => loadUserStats()} className="h-8 rounded-xl font-black uppercase text-[10px] bg-amber-500/10">
              <RefreshCw className="h-3 w-3 mr-1" />
              Sync
            </Button>
          </div>
        )}

        {/* Quick Actions */}
        <div className="space-y-4">
          <h2 className="text-xs font-black uppercase tracking-widest text-muted-foreground ml-1">Core Modules</h2>
          <div className="grid grid-cols-2 gap-4">
            {quickActions.map((action) => (
              <Card
                key={action.path}
                className="cursor-pointer border-2 border-transparent hover:border-primary/20 transition-all duration-300 hover:scale-[1.02] active:scale-95 glass group"
                onClick={() => handleCardClick(action.path)}
              >
                <CardContent className="p-5">
                  <div className={cn(
                    "w-12 h-12 rounded-2xl flex items-center justify-center mb-4 shadow-xl transition-transform group-hover:rotate-3 bg-gradient-to-br",
                    action.gradient
                  )}>
                    <action.icon className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="font-black text-foreground text-sm uppercase tracking-tight mb-1">{action.title}</h3>
                  <p className="text-[10px] font-bold text-muted-foreground uppercase opacity-60 leading-tight">{action.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Personalized Recommendations */}
        {recommendations.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-xs font-black uppercase tracking-widest text-muted-foreground ml-1">Frequent Corridors</h2>
            <div className="space-y-2">
              {recommendations.map((rec, index) => (
                <Card 
                  key={index}
                  className="cursor-pointer border-none glass hover:bg-muted/30 transition-all active:scale-[0.98]"
                  onClick={() => handleQuickSearch(rec.origin_code, rec.destination_code)}
                >
                  <CardContent className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shadow-inner">
                        <Star className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <p className="font-black text-foreground text-sm uppercase tracking-tight">
                          {rec.origin_code} → {rec.destination_code}
                        </p>
                        <p className="text-[10px] font-bold text-muted-foreground uppercase opacity-60">{rec.origin_name || "Origin"} corridor</p>
                      </div>
                    </div>
                    <div className="bg-muted p-2 rounded-lg">
                      <Clock className="h-4 w-4 text-muted-foreground" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}
        
        {/* Popular Routes */}
        {popularRoutes.length > 0 && recommendations.length === 0 && (
          <div className="space-y-3">
            <h2 className="text-xs font-black uppercase tracking-widest text-muted-foreground ml-1">Trending Vectors</h2>
            <div className="space-y-2">
              {popularRoutes.map((route, index) => (
                <Card 
                  key={index}
                  className="cursor-pointer border-none glass hover:bg-muted/30 transition-all active:scale-[0.98]"
                  onClick={() => handleQuickSearch(route.origin_code, route.destination_code)}
                >
                  <CardContent className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center shadow-inner">
                        <Activity className="h-5 w-5 text-blue-500" />
                      </div>
                      <div>
                        <p className="font-black text-foreground text-sm uppercase tracking-tight">
                          {route.origin_code} → {route.destination_code}
                        </p>
                        <p className="text-[10px] font-bold text-muted-foreground uppercase opacity-60">{route.origin_name} sector</p>
                      </div>
                    </div>
                    <Zap className="h-4 w-4 text-amber-500 animate-pulse" />
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Additional Features */}
        <div className="space-y-4">
          <h2 className="text-xs font-black uppercase tracking-widest text-muted-foreground ml-1">Terminal Utility</h2>
          <div className="grid grid-cols-1 gap-2">
            <Button
              variant="outline"
              className="w-full justify-between h-14 rounded-2xl border-2 hover:bg-muted font-black uppercase text-xs tracking-widest group px-6"
              onClick={() => handleCardClick("/mini-app/profile")}
            >
              <div className="flex items-center gap-3">
                <BarChart3 className="h-5 w-5 text-primary" />
                <span>Neural Statistics</span>
              </div>
              <RefreshCw className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity" />
            </Button>
            <Button
              variant="outline"
              className="w-full justify-between h-14 rounded-2xl border-2 hover:bg-muted font-black uppercase text-xs tracking-widest group px-6"
              onClick={() => handleCardClick("/mini-app/profile")}
            >
              <div className="flex items-center gap-3">
                <Settings className="h-5 w-5 text-muted-foreground" />
                <span>Interface Config</span>
              </div>
              <RefreshCw className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity" />
            </Button>
          </div>
        </div>

        {/* Safety Notice */}
        <Card className="border-none glass bg-red-500/5 overflow-hidden">
          <div className="h-1 w-full bg-red-500/20" />
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center shrink-0">
                <Shield className="h-6 w-6 text-red-500" />
              </div>
              <div>
                <p className="text-xs font-black uppercase tracking-widest text-red-600 mb-1">Safety Protocol Active</p>
                <p className="text-[10px] font-bold text-muted-foreground uppercase leading-relaxed opacity-80">
                  Global SOS node 112 integrated. Emergency telemetry sharing is synchronized with railway OPS center.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default MiniAppHome;
