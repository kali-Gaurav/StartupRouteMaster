import { useState, useEffect, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, Heart, Trash2, Play, Loader2, Star, Eraser } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/hooks/use-toast";
import { getRailwayApiUrl } from "@/lib/utils";

interface SavedRoute {
  id: string;
  origin: string;
  origin_code: string;
  destination: string;
  destination_code: string;
  saved_at: string;
  times_used: number;
  last_used?: string;
  frequency: string;
}

interface SelectedRoute {
  id: number;
  origin_code: string;
  origin_name: string;
  destination_code: string;
  destination_name: string;
  train_no?: string;
  train_name?: string;
  departure_time?: string;
  arrival_time?: string;
  fare?: number;
  route_type?: string;
  selected_at?: string;
}

const MiniAppSaved = () => {
  const navigate = useNavigate();
  const [savedRoutes, setSavedRoutes] = useState<SavedRoute[]>([]);
  const [selectedRoutes, setSelectedRoutes] = useState<SelectedRoute[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingSelected, setIsLoadingSelected] = useState(true);
  const [isStarting, setIsStarting] = useState<string | null>(null);
  const [isClearingHistory, setIsClearingHistory] = useState(false);

  const loadSavedRoutes = useCallback(async () => {
    setIsLoading(true);
    try {
      const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
      if (!userId) return;

      const response = await fetch(getRailwayApiUrl(`/api/saved-routes/${userId}`));
      if (response.ok) {
        const data = await response.json();
        const routes = (data.routes || []).map((r: SavedRoute) => ({
          ...r,
          origin_code: r.origin_code ?? r.origin,
          destination_code: r.destination_code ?? r.destination
        }));
        setSavedRoutes(routes);
      }
    } catch (error) {
      console.error("Failed to load saved routes:", error);
      toast({
        title: "Error",
        description: "Failed to load saved routes",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadSelectedRoutes = useCallback(async () => {
    setIsLoadingSelected(true);
    try {
      const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
      if (!userId) return;
      const response = await fetch(getRailwayApiUrl(`/api/selected-routes/${userId}`));
      if (response.ok) {
        const data = await response.json();
        setSelectedRoutes(data.routes || []);
      }
    } catch (error) {
      console.error("Failed to load selected routes:", error);
    } finally {
      setIsLoadingSelected(false);
    }
  }, []);

  useEffect(() => {
    loadSavedRoutes();
    loadSelectedRoutes();
  }, [loadSavedRoutes, loadSelectedRoutes]);

  const handleClearHistory = async () => {
    const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    if (!userId) return;
    setIsClearingHistory(true);
    try {
      const response = await fetch(getRailwayApiUrl(`/api/saved-routes/clear-history?user_id=${userId}`), {
        method: "POST"
      });
      if (response.ok) {
        await loadSavedRoutes();
        toast({
          title: "History cleared",
          description: "Saved routes list is cleared. Data is kept for future predictions."
        });
      } else {
        const err = await response.json().catch(() => ({}));
        toast({
          title: "Error",
          description: (err as { detail?: string }).detail || "Failed to clear history",
          variant: "destructive"
        });
      }
    } catch (error) {
      console.error("Clear history failed:", error);
      toast({
        title: "Error",
        description: "Failed to clear history",
        variant: "destructive"
      });
    } finally {
      setIsClearingHistory(false);
    }
  };

  const handleStartRoute = async (route: SavedRoute) => {
    setIsStarting(route.id);
    try {
      const searchData = {
        type: "SEARCH",
        origin: route.origin_code,
        origin_name: route.origin,
        destination: route.destination_code,
        destination_name: route.destination,
        date: new Date().toISOString().split('T')[0],
        timestamp: new Date().toISOString()
      };

      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.sendData(JSON.stringify(searchData));
        toast({
          title: "Route Search Started",
          description: "Check your Telegram chat for results"
        });
        setTimeout(() => navigate("/mini-app/home"), 1500);
      }
    } catch (error) {
      console.error("Error starting route:", error);
      toast({
        title: "Error",
        description: "Failed to start route search",
        variant: "destructive"
      });
    } finally {
      setIsStarting(null);
    }
  };

  const handleDeleteRoute = async (routeId: string) => {
    try {
      const response = await fetch(getRailwayApiUrl(`/api/saved-routes/${routeId}`), {
        method: "DELETE"
      });
      if (response.ok) {
        setSavedRoutes(savedRoutes.filter(r => r.id !== routeId));
        toast({
          title: "Route Deleted",
          description: "Route removed from favorites"
        });
      }
    } catch (error) {
      console.error("Error deleting route:", error);
      toast({
        title: "Error",
        description: "Failed to delete route",
        variant: "destructive"
      });
    }
  };

  const handleRemoveSelected = async (routeId: number) => {
    try {
      const response = await fetch(getRailwayApiUrl(`/api/selected-routes/${routeId}`), {
        method: "DELETE"
      });
      if (response.ok) {
        setSelectedRoutes(selectedRoutes.filter(r => r.id !== routeId));
        toast({
          title: "Removed from review",
          description: "Route removed from selected for review"
        });
      }
    } catch (error) {
      console.error("Error removing selected route:", error);
      toast({
        title: "Error",
        description: "Failed to remove from review",
        variant: "destructive"
      });
    }
  };

  const getFrequencyColor = (frequency: string) => {
    switch (frequency) {
      case "daily":
        return "bg-red-100 text-red-800";
      case "weekly":
        return "bg-orange-100 text-orange-800";
      case "monthly":
        return "bg-blue-100 text-blue-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4 flex items-center justify-center">
        <Card className="shadow-lg">
          <CardContent className="p-8 flex flex-col items-center">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600 mb-4" />
            <p className="text-gray-600">Loading saved routes...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-md mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center space-x-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/mini-app/home")}
            className="hover:bg-blue-200"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Saved Routes</h1>
            <p className="text-sm text-gray-600">Your favorite journeys</p>
          </div>
        </div>

        {savedRoutes.length === 0 ? (
          <Card className="text-center py-12">
            <CardContent className="space-y-4">
              <div className="text-4xl">❤️</div>
              <h3 className="text-lg font-bold text-gray-900">No Saved Routes</h3>
              <p className="text-gray-600 text-sm">
                Routes you frequently search will automatically be saved here for quick access.
              </p>
              <Button
                onClick={() => navigate("/mini-app/search")}
                className="w-full bg-blue-600 hover:bg-blue-700"
              >
                Search a Route
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            <p className="text-sm text-gray-600 px-1">
              You have {savedRoutes.length} saved route{savedRoutes.length !== 1 ? 's' : ''}
            </p>
            <div className="space-y-3">
              {savedRoutes.map((route) => (
                <Card
                  key={route.id}
                  className="hover:shadow-lg transition-shadow border-l-4 border-l-purple-500"
                >
                  <CardContent className="p-4 space-y-3">
                    {/* Route Info */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <div className="text-sm font-semibold text-gray-900">
                              {route.origin}
                            </div>
                            <div className="text-xs text-gray-500">({route.origin_code})</div>
                          </div>
                          <p className="text-xs text-gray-500 mt-1">Departure</p>
                        </div>
                        <Heart className="h-5 w-5 text-red-500 fill-red-500" />
                      </div>

                      <div className="border-t border-gray-200 py-2 px-2 text-center">
                        <p className="text-xs font-medium text-gray-600">via rail</p>
                      </div>

                      <div>
                        <div className="flex items-center space-x-2">
                          <div className="text-sm font-semibold text-gray-900">
                            {route.destination}
                          </div>
                          <div className="text-xs text-gray-500">({route.destination_code})</div>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">Destination</p>
                      </div>
                    </div>

                    <Separator />

                    {/* Stats */}
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-blue-50 p-2 rounded">
                        <p className="text-xs text-gray-600">Times Used</p>
                        <p className="font-semibold text-blue-600">{route.times_used}</p>
                      </div>
                      <div>
                        <Badge className={`${getFrequencyColor(route.frequency)}`}>
                          {route.frequency.charAt(0).toUpperCase() + route.frequency.slice(1)}
                        </Badge>
                      </div>
                    </div>

                    {route.last_used && (
                      <p className="text-xs text-gray-500">
                        Last used: {new Date(route.last_used).toLocaleDateString()}
                      </p>
                    )}

                    {/* Actions */}
                    <div className="flex gap-2 pt-2">
                      <Button
                        onClick={() => handleStartRoute(route)}
                        disabled={isStarting === route.id}
                        className="flex-1 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
                      >
                        {isStarting === route.id ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Starting...
                          </>
                        ) : (
                          <>
                            <Play className="h-4 w-4 mr-2" />
                            Start
                          </>
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDeleteRoute(route.id)}
                        className="text-red-600 hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Clear saved routes history - data kept for prediction */}
            <Card className="bg-amber-50 border-amber-200">
              <CardContent className="pt-4">
                <p className="text-sm font-semibold text-amber-900 mb-2">Clear saved routes list</p>
                <p className="text-xs text-amber-800 mb-3">
                  Clear the list you see here. Your data is kept in our database for future predictions and analytics.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClearHistory}
                  disabled={isClearingHistory}
                  className="border-amber-400 text-amber-800 hover:bg-amber-100"
                >
                  {isClearingHistory ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Clearing...
                    </>
                  ) : (
                    <>
                      <Eraser className="h-4 w-4 mr-2" />
                      Clear saved routes history
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </>
        )}

        {/* Selected for review section */}
        <Card className="border-l-4 border-l-amber-500">
          <CardContent className="pt-4">
            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2 mb-2">
              <Star className="h-5 w-5 text-amber-500" />
              Selected for review
            </h3>
            <p className="text-xs text-gray-600 mb-3">
              Routes you marked to review carefully (from bot or search). Remove when done.
            </p>
            {isLoadingSelected ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="h-6 w-6 animate-spin text-amber-600" />
              </div>
            ) : selectedRoutes.length === 0 ? (
              <p className="text-sm text-gray-500 py-4 text-center">
                No routes selected for review. Use the Telegram bot: search → select a route → &quot;⭐ Save for review&quot;.
              </p>
            ) : (
              <div className="space-y-3">
                {selectedRoutes.map((r) => (
                  <Card key={r.id} className="bg-gray-50">
                    <CardContent className="p-3 space-y-2">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="font-medium text-gray-900">
                            {r.origin_name || r.origin_code} → {r.destination_name || r.destination_code}
                          </p>
                          {r.train_no && (
                            <p className="text-xs text-gray-600">
                              Train {r.train_no}
                              {r.departure_time && r.arrival_time && ` · ${r.departure_time} → ${r.arrival_time}`}
                              {r.fare != null && ` · ₹${r.fare}`}
                            </p>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRemoveSelected(r.id)}
                          className="text-red-600 hover:bg-red-50 shrink-0"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Tip */}
        {savedRoutes.length > 0 && (
          <Card className="bg-blue-50 border-blue-200">
            <CardContent className="pt-4">
              <p className="text-sm font-semibold text-blue-900 mb-2">💡 Pro Tip</p>
              <p className="text-xs text-blue-800">
                Your most frequently searched routes are automatically saved. Tap &quot;Start&quot; to begin your journey!
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default MiniAppSaved;