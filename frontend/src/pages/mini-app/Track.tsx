import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import { ArrowLeft, Train, Share2, StopCircle, Loader2, Shield } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/hooks/use-toast";
import { getRailwayApiUrl } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";

interface ActiveJourney {
  id: string;
  train_no: string;
  train_name: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  status: string;
  progress: number;
  current_station?: string;
  next_station?: string;
  distance_covered?: number;
  total_distance?: number;
}

const MiniAppTrack = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const userId = user?.telegram_id ?? window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  
  const [activeJourney, setActiveJourney] = useState<ActiveJourney | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isStopping, setIsStopping] = useState(false);
  const [pastJourneys, setPastJourneys] = useState<ActiveJourney[]>([]);

  const loadJourneyData = useCallback(async () => {
    try {
      if (!userId) return;
      const response = await fetch(getRailwayApiUrl(`/api/journey/${userId}/active`));
      if (response.ok) {
        const data = await response.json();
        setActiveJourney(data.active_journey || null);
        setPastJourneys(data.past_journeys || []);
      }
    } catch (error) {
      console.error("Failed to load journey data:", error);
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (!userId) return;
    loadJourneyData();
    const interval = setInterval(loadJourneyData, 30000);
    return () => clearInterval(interval);
  }, [userId, loadJourneyData]);

  const handleStopJourney = async () => {
    if (!activeJourney) return;

    setIsStopping(true);
    try {
      const stopData = {
        type: "STOP_JOURNEY",
        journey_id: activeJourney.id,
        timestamp: new Date().toISOString()
      };

      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.sendData(JSON.stringify(stopData));
        toast({
          title: "Journey Ended",
          description: "Your journey tracking has been stopped"
        });
        setTimeout(() => navigate("/mini-app/home"), 1500);
      }
    } catch (error) {
      console.error("Error stopping journey:", error);
      toast({
        title: "Error",
        description: "Failed to stop journey tracking",
        variant: "destructive"
      });
    } finally {
      setIsStopping(false);
    }
  };

  const handleShareLocation = async () => {
    if ("geolocation" in navigator) {
      try {
        const position = await new Promise((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject);
        }) as GeolocationPosition;

        const shareData = {
          type: "SHARE_LOCATION",
          journey_id: activeJourney?.id,
          location: {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude
          },
          timestamp: new Date().toISOString()
        };

        if (window.Telegram?.WebApp) {
          window.Telegram.WebApp.sendData(JSON.stringify(shareData));
          toast({
            title: "Location Shared",
            description: "Your current location has been shared with emergency contacts"
          });
        }
      } catch (error) {
        console.error("Location error:", error);
        toast({
          title: "Error",
          description: "Could not access location",
          variant: "destructive"
        });
      }
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4 flex items-center justify-center">
        <Card className="shadow-lg">
          <CardContent className="p-8 flex flex-col items-center">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600 mb-4" />
            <p className="text-gray-600">Loading journey data...</p>
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
            <h1 className="text-2xl font-bold text-gray-900">Track Journey</h1>
            <p className="text-sm text-gray-600">Monitor your active trips</p>
          </div>
        </div>

        {activeJourney ? (
          <>
            {/* Active Journey Card */}
            <Card className="shadow-lg border-2 border-green-200 bg-gradient-to-br from-green-50 to-white">
              <CardHeader className="bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-t-lg">
                <div className="space-y-1">
                  <Badge className="w-fit bg-white text-green-600 mb-2">Active Journey</Badge>
                  <h2 className="text-xl font-bold">{activeJourney.train_no}</h2>
                  <p className="text-sm text-green-100">{activeJourney.train_name}</p>
                </div>
              </CardHeader>

              <CardContent className="pt-6 space-y-6">
                {/* Route Info */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <p className="text-xs text-gray-500 mb-1">From</p>
                      <p className="font-bold text-gray-900">{activeJourney.origin}</p>
                      <p className="text-sm text-gray-600">{activeJourney.departure_time}</p>
                    </div>
                    <Train className="h-6 w-6 text-blue-600 mx-2" />
                    <div className="flex-1 text-right">
                      <p className="text-xs text-gray-500 mb-1">To</p>
                      <p className="font-bold text-gray-900">{activeJourney.destination}</p>
                      <p className="text-sm text-gray-600">{activeJourney.arrival_time}</p>
                    </div>
                  </div>
                </div>

                <Separator />

                {/* Progress Bar */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <p className="text-sm font-semibold text-gray-700">Journey Progress</p>
                    <Badge variant="outline">{activeJourney.progress}%</Badge>
                  </div>
                  <Progress value={activeJourney.progress} className="h-3" />
                  <p className="text-xs text-gray-600 text-center">
                    {activeJourney.distance_covered || 0} / {activeJourney.total_distance || "?"} km
                  </p>
                </div>

                {/* Current Status */}
                {activeJourney.current_station && (
                  <>
                    <Separator />
                    <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                      <p className="text-xs text-gray-600 mb-1">Current Station</p>
                      <p className="font-bold text-blue-600 text-lg">{activeJourney.current_station}</p>
                      {activeJourney.next_station && (
                        <p className="text-sm text-gray-600 mt-2">
                          Next: {activeJourney.next_station}
                        </p>
                      )}
                    </div>
                  </>
                )}

                {/* Status */}
                <div className="flex items-center justify-center space-x-2 bg-green-50 p-3 rounded-lg">
                  <div className="w-2 h-2 bg-green-600 rounded-full animate-pulse" />
                  <p className="text-sm font-medium text-green-700">On Schedule</p>
                </div>

                <Separator />

                {/* Action Buttons */}
                <div className="grid grid-cols-2 gap-3">
                  <Button
                    variant="outline"
                    className="border-2"
                    onClick={handleShareLocation}
                  >
                    <Share2 className="h-4 w-4 mr-2" />
                    Share Location
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={handleStopJourney}
                    disabled={isStopping}
                  >
                    {isStopping ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Stopping...
                      </>
                    ) : (
                      <>
                        <StopCircle className="h-4 w-4 mr-2" />
                        End Journey
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Tips */}
            <Card className="bg-blue-50 border-blue-200">
              <CardContent className="pt-4">
                <p className="text-sm font-semibold text-blue-900 mb-2">💡 Journey Tips</p>
                <ul className="text-xs text-blue-800 space-y-1">
                  <li>• Share your location for faster help in emergencies</li>
                  <li>• Keep this window open to track real-time updates</li>
                  <li>• End your journey when you reach your destination</li>
                </ul>
              </CardContent>
            </Card>
          </>
        ) : (
          <>
            {/* No Active Journey */}
            <Card className="text-center py-12">
              <CardContent className="space-y-4">
                <div className="text-4xl">🚂</div>
                <h3 className="text-lg font-bold text-gray-900">No Active Journey</h3>
                <p className="text-gray-600 text-sm">You don't have any active journey tracking right now.</p>
                <Button
                  onClick={() => navigate("/mini-app/search")}
                  className="w-full bg-blue-600 hover:bg-blue-700"
                >
                  Start a New Journey
                </Button>
              </CardContent>
            </Card>

            {/* Past Journeys */}
            {pastJourneys.length > 0 && (
              <>
                <Separator className="my-4" />
                <h2 className="text-lg font-semibold text-gray-900">Recent Journeys</h2>
                <div className="space-y-3">
                  {pastJourneys.slice(0, 5).map((journey) => (
                    <Card key={journey.id} className="cursor-pointer hover:shadow-md transition-shadow">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-semibold text-gray-900">{journey.train_no}</p>
                            <p className="text-sm text-gray-600">
                              {journey.origin} → {journey.destination}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">{journey.departure_time}</p>
                          </div>
                          <Badge variant="outline">Completed</Badge>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </>
            )}
          </>
        )}

        {/* Live location consent: opt-in, time-limited, for safety only */}
        <Card className="bg-slate-50 border-slate-200">
          <CardContent className="p-3 flex items-start gap-2">
            <Shield className="h-4 w-4 text-slate-500 mt-0.5 shrink-0" />
            <p className="text-xs text-slate-600">
              Location sharing is opt-in and used only for your safety during the journey. It is time-limited and stops when you end the journey.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default MiniAppTrack;