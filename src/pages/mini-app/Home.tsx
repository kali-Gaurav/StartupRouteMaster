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
  RefreshCw
} from "lucide-react";
import { getRailwayApiUrl } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { useTelegramWebApp } from "@/hooks/useTelegramWebApp";
import { fetchWithAuth } from "@/lib/apiClient";

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
      loadRecommendations(user.user_id);
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
      color: "bg-blue-500",
      gradient: "from-blue-500 to-blue-600"
    },
    {
      title: "Track Journey",
      description: "Monitor active trips",
      icon: MapPin,
      path: "/mini-app/track",
      color: "bg-green-500",
      gradient: "from-green-500 to-green-600"
    },
    {
      title: "Emergency SOS",
      description: "Get help in emergencies",
      icon: AlertTriangle,
      path: "/mini-app/sos",
      color: "bg-red-500",
      gradient: "from-red-500 to-red-600"
    },
    {
      title: "Saved Routes",
      description: "Your favorite journeys",
      icon: Heart,
      path: "/mini-app/saved",
      color: "bg-purple-500",
      gradient: "from-purple-500 to-purple-600"
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-md mx-auto space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="flex items-center justify-center space-x-2">
            <Train className="h-8 w-8 text-blue-600" />
            <h1 className="text-2xl font-bold text-gray-900">RouteMaster</h1>
          </div>
          <p className="text-gray-600">Smart Railway Assistant</p>
          {user && (
            <p className="text-sm text-gray-500">
              Welcome back, {user.first_name || user.last_name || "Traveler"}!
            </p>
          )}
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-3 gap-4">
          <Card className="text-center">
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-blue-600">{stats.totalJourneys}</div>
              <p className="text-xs text-gray-600">Journeys</p>
            </CardContent>
          </Card>
          <Card className="text-center">
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-green-600">{stats.savedRoutes}</div>
              <p className="text-xs text-gray-600">Saved Routes</p>
            </CardContent>
          </Card>
          <Card className="text-center">
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-purple-600">{stats.badges}</div>
              <p className="text-xs text-gray-600">Badges</p>
            </CardContent>
          </Card>
        </div>
        {statsError && isAuthenticated && (
          <div className="flex items-center justify-between gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-800">
            <span>{statsError}</span>
            <Button size="sm" variant="outline" onClick={() => loadUserStats()} className="shrink-0">
              <RefreshCw className="h-4 w-4 mr-1" />
              Retry
            </Button>
          </div>
        )}

        {/* Quick Actions */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Quick Actions</h2>
          <div className="grid grid-cols-2 gap-4">
            {quickActions.map((action) => (
              <Card
                key={action.path}
                className="cursor-pointer hover:shadow-lg transition-all duration-200 hover:scale-105"
                onClick={() => handleCardClick(action.path)}
              >
                <CardContent className="p-4">
                  <div className={`w-12 h-12 rounded-lg bg-gradient-to-r ${action.gradient} flex items-center justify-center mb-3`}>
                    <action.icon className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="font-semibold text-gray-900 mb-1">{action.title}</h3>
                  <p className="text-sm text-gray-600">{action.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Personalized Recommendations (if user logged in) */}
        {recommendations.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">Your Frequent Routes</h2>
            <div className="space-y-2">
              {recommendations.map((rec, index) => (
                <Card 
                  key={index}
                  className="cursor-pointer hover:shadow-md transition-shadow"
                  onClick={() => handleQuickSearch(rec.origin_code, rec.destination_code)}
                >
                  <CardContent className="p-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
                        <Star className="h-5 w-5 text-purple-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 text-sm">
                          {rec.origin_name || rec.origin_code} → {rec.destination_name || rec.destination_code}
                        </p>
                        <p className="text-xs text-gray-500">Tap to search</p>
                      </div>
                    </div>
                    <Clock className="h-4 w-4 text-gray-400" />
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}
        
        {/* Popular Routes (works without login - standalone!) */}
        {popularRoutes.length > 0 && recommendations.length === 0 && (
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">Popular Routes</h2>
            <div className="space-y-2">
              {popularRoutes.map((route, index) => (
                <Card 
                  key={index}
                  className="cursor-pointer hover:shadow-md transition-shadow"
                  onClick={() => handleQuickSearch(route.origin_code, route.destination_code)}
                >
                  <CardContent className="p-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                        <Train className="h-5 w-5 text-blue-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 text-sm">
                          {route.origin_name} → {route.destination_name}
                        </p>
                        <p className="text-xs text-gray-500">Trending route</p>
                      </div>
                    </div>
                    <Clock className="h-4 w-4 text-gray-400" />
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Additional Features */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">More Features</h2>
          <div className="space-y-3">
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => handleCardClick("/mini-app/profile")}
            >
              <BarChart3 className="h-4 w-4 mr-2" />
              Travel Statistics
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => handleCardClick("/mini-app/profile")}
            >
              <Settings className="h-4 w-4 mr-2" />
              Profile &amp; Settings
            </Button>
          </div>
        </div>

        {/* Safety Notice */}
        <Card className="bg-amber-50 border-amber-200">
          <CardContent className="pt-4">
            <div className="flex items-start space-x-3">
              <Shield className="h-5 w-5 text-amber-600 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-amber-800">Safety First</p>
                <p className="text-xs text-amber-700 mt-1">
                  For emergencies, call 112. This app provides location sharing for faster assistance.
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