import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Train, MapPin, Clock, AlertTriangle, RefreshCcw, ArrowLeft, Navigation } from "lucide-react";
import { getTrainStatusApi } from "@/services/railwayBackApi";
import { toast } from "sonner";

export default function TrainTracking() {
  const { trainNumber } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [statusData, setStatusData] = useState<any>(null);
  const [refreshKey, setRefreshCcw] = useState(0);

  useEffect(() => {
    async function fetchStatus() {
      if (!trainNumber) return;
      setLoading(true);
      try {
        const data = await getTrainStatusApi(trainNumber);
        setStatusData(data);
      } catch (err) {
        console.error("Tracking error:", err);
        toast.error("Failed to fetch live train status");
      } finally {
        setLoading(false);
      }
    }
    fetchStatus();
  }, [trainNumber, refreshKey]);

  if (loading && !statusData) {
    return (
      <div className="min-h-screen flex flex-col bg-slate-50">
        <Navbar />
        <main className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <Train className="w-12 h-12 text-primary animate-bounce" />
            <p className="font-bold text-slate-600">Locating Train {trainNumber}...</p>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  const live = statusData?.live_status;
  const position = statusData?.estimated_position;

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Navbar />
      <main className="container mx-auto px-4 py-8 flex-1 max-w-4xl">
        <div className="mb-6 flex items-center justify-between">
          <Button variant="ghost" onClick={() => navigate(-1)} className="gap-2">
            <ArrowLeft className="w-4 h-4" /> Back
          </Button>
          <Button variant="outline" size="sm" onClick={() => setRefreshCcw(prev => prev + 1)} className="gap-2">
            <RefreshCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh Live
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Main Info Card */}
          <Card className="md:col-span-2 shadow-xl border-t-4 border-t-primary">
            <CardHeader className="pb-2">
              <div className="flex justify-between items-start">
                <div>
                  <Badge variant="outline" className="mb-2 uppercase tracking-widest text-[10px]">Live Tracking</Badge>
                  <CardTitle className="text-3xl font-black">{trainNumber}</CardTitle>
                  <p className="text-slate-500 font-bold">{live?.train_name || "Railway Express"}</p>
                </div>
                <div className="text-right">
                  <div className={`text-sm font-black px-3 py-1 rounded-full ${live?.delay_minutes > 0 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                    {live?.delay_minutes > 0 ? `${live.delay_minutes}m Late` : 'On Time'}
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-8">
              {/* Progress Visual */}
              <div className="relative pt-8 pb-4 px-2">
                <div className="absolute top-0 left-0 text-[10px] font-black text-slate-400 uppercase">Route Progress</div>
                <Progress value={position?.progress_percentage || 0} className="h-3" />
                <div className="flex justify-between mt-2 text-xs font-bold text-slate-500">
                  <span>{position?.last_station?.name || "Departure"}</span>
                  <span>{position?.next_station?.name || "Destination"}</span>
                </div>
                {/* Train Icon Overlay */}
                <div 
                  className="absolute top-[34px] transition-all duration-1000"
                  style={{ left: `${(position?.progress_percentage || 0)}%`, transform: 'translateX(-50%)' }}
                >
                  <div className="bg-primary text-white p-1.5 rounded-full shadow-lg border-2 border-white">
                    <Train className="w-4 h-4" />
                  </div>
                </div>
              </div>

              {/* Current Status Box */}
              <div className="bg-primary/5 rounded-2xl p-6 border border-primary/10">
                <div className="flex items-start gap-4">
                  <div className="bg-primary text-white p-3 rounded-xl shadow-md">
                    <MapPin className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-[10px] font-black text-primary uppercase mb-1">Current Status</p>
                    <h3 className="text-xl font-black text-slate-900">{live?.status_message || "In Transit"}</h3>
                    <p className="text-sm text-slate-600 font-medium">Currently at or near <span className="font-bold text-slate-900">{live?.current_station_name}</span></p>
                  </div>
                </div>
              </div>

              {/* Telemetry Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <div className="p-4 bg-white border rounded-xl flex flex-col items-center text-center">
                  <Clock className="w-5 h-5 text-blue-500 mb-2" />
                  <p className="text-[10px] font-black text-slate-400 uppercase">Last Updated</p>
                  <p className="text-sm font-bold">{live?.last_updated ? new Date(live.last_updated).toLocaleTimeString() : '--:--'}</p>
                </div>
                <div className="p-4 bg-white border rounded-xl flex flex-col items-center text-center">
                  <Navigation className="w-5 h-5 text-purple-500 mb-2" />
                  <p className="text-[10px] font-black text-slate-400 uppercase">Coordinates</p>
                  <p className="text-sm font-bold font-mono">{position?.lat?.toFixed(4)}, {position?.lon?.toFixed(4)}</p>
                </div>
                <div className="p-4 bg-white border rounded-xl flex flex-col items-center text-center col-span-2 sm:col-span-1">
                  <AlertTriangle className="w-5 h-5 text-orange-500 mb-2" />
                  <p className="text-[10px] font-black text-slate-400 uppercase">Confidence</p>
                  <p className="text-sm font-bold">{statusData?.metadata?.live_uplink ? 'High (Live)' : 'Medium (Estimated)'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Sidebar Area */}
          <div className="space-y-6">
            <Card className="bg-slate-900 text-white border-none shadow-xl overflow-hidden relative">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/20 rounded-full blur-3xl -mr-16 -mt-16"></div>
              <CardHeader>
                <CardTitle className="text-lg font-black uppercase tracking-tight flex items-center gap-2">
                  <Zap className="w-5 h-5 text-yellow-400 fill-current" />
                  Quick Stats
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between border-b border-white/10 pb-2">
                  <span className="text-white/60 text-xs">Estimated ETA</span>
                  <span className="font-bold text-sm">--:--</span>
                </div>
                <div className="flex justify-between border-b border-white/10 pb-2">
                  <span className="text-white/60 text-xs">Distance Left</span>
                  <span className="font-bold text-sm">-- km</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60 text-xs">Avg. Speed</span>
                  <span className="font-bold text-sm">55 km/h</span>
                </div>
              </CardContent>
            </Card>

            <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-5">
              <h4 className="font-black text-xs text-yellow-800 uppercase mb-2">Safety Note</h4>
              <p className="text-[10px] leading-relaxed text-yellow-700 font-medium">
                Live position is estimated using RapidAPI status and Time-Differential Interpolation. Accuracy may vary depending on GPS uplink frequency.
              </p>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}

function Zap(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}
