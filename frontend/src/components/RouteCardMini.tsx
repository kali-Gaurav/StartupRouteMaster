import { useState, memo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Train, Lock, Loader2, MapPin, Route as RouteIcon } from "lucide-react";

interface MiniLeg {
  train_no: string;
  train_name: string;
  departure: string;
  arrival: string;
  distance?: number;
  time_minutes?: number;
  fare?: number;
}

interface MiniRoute {
  journey_id?: string;
  train_no: string;
  train_name: string;
  departure: string;
  arrival: string;
  duration: string;
  transfers: number;
  fare?: number | null;
  availability?: string | null;
  legs?: MiniLeg[];
}

interface RouteCardMiniProps {
  route: MiniRoute;
  originCode: string;
  destinationCode: string;
  isUnlocked: boolean;
  isProcessing?: boolean;
  onUnlock: (route: MiniRoute) => void;
  onSave: (route: MiniRoute) => void;
  onBook: (route: MiniRoute) => void;
}

export const RouteCardMini = memo(function RouteCardMini({ 
  route, originCode, destinationCode, isUnlocked, isProcessing, onUnlock, onSave, onBook 
}: RouteCardMiniProps) {
  const [showSegments, setShowSegments] = useState(false);

  const calculateTotalDistance = () => {
    if (route.legs) {
      return route.legs.reduce((sum: number, leg: MiniLeg) => sum + (leg.distance || 0), 0);
    }
    return 0;
  };
  
  const totalDistance = calculateTotalDistance();

  return (
    <Card 
      className="shadow-md hover:shadow-lg transition-shadow overflow-hidden"
      style={{ contentVisibility: 'auto', containIntrinsicSize: '150px' } as any}
    >
      <CardContent className="p-0">
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 p-4 border-b">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 flex-1">
              <div className="w-9 h-9 rounded-lg bg-blue-600 text-white flex items-center justify-center flex-shrink-0 mt-0.5">
                <Train className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2 flex-wrap">
                  <h3 className="font-bold text-gray-900 text-sm leading-tight">
                    {route.train_name}
                  </h3>
                  <span className="text-xs font-semibold text-blue-600 bg-blue-100 px-2 py-0.5 rounded whitespace-nowrap">
                    #{route.train_no}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {route.transfers === 0 ? "Direct" : `${route.transfers} Transfer${route.transfers > 1 ? 's' : ''}`}
                </p>
              </div>
            </div>
            
            <div className="flex gap-1.5 flex-shrink-0">
              <Button variant="ghost" size="icon" onClick={() => onSave(route)} className="h-8 w-8">
                <Train className="h-4 w-4 text-gray-400" />
              </Button>
              {!isUnlocked ? (
                <Button size="sm" onClick={() => onUnlock(route)} disabled={isProcessing} className="h-8 px-2.5 text-xs font-semibold">
                  {isProcessing ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Lock className="h-3 w-3 mr-1" />}
                  Unlock
                </Button>
              ) : (
                <Button size="sm" onClick={() => onBook(route)} className="h-8 px-2.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700">
                  Book
                </Button>
              )}
            </div>
          </div>
        </div>

        <div className="p-4">
          <div className="flex items-center justify-between gap-2 mb-4">
            <div className="text-center">
              <p className="text-base font-bold text-gray-900">{route.departure}</p>
              <p className="text-xs text-gray-500 mt-0.5">{originCode}</p>
            </div>
            <div className="flex-1 px-3">
              <div className="h-1 bg-gradient-to-r from-blue-400 to-indigo-400 rounded-full"></div>
              <p className="text-xs font-semibold text-gray-600 text-center mt-1">{route.duration}</p>
            </div>
            <div className="text-center">
              <p className="text-base font-bold text-gray-900">{route.arrival}</p>
              <p className="text-xs text-gray-500 mt-0.5">{destinationCode}</p>
            </div>
          </div>

          {isUnlocked && (
            <>
              <Separator className="my-3" />
              <div className="grid grid-cols-3 gap-2 mb-4">
                <div className="bg-blue-50 rounded-lg p-2.5 text-center">
                  <p className="text-xs text-gray-600 font-medium mb-0.5">Distance</p>
                  <p className="text-sm font-bold text-blue-600">{totalDistance > 0 ? `${Math.round(totalDistance)} km` : "—"}</p>
                </div>
                <div className="bg-indigo-50 rounded-lg p-2.5 text-center">
                  <p className="text-xs text-gray-600 font-medium mb-0.5">Duration</p>
                  <p className="text-sm font-bold text-indigo-600">{route.duration}</p>
                </div>
                <div className="bg-green-50 rounded-lg p-2.5 text-center">
                  <p className="text-xs text-gray-600 font-medium mb-0.5">{route.fare ? "Fare" : "Status"}</p>
                  {route.fare ? <p className="text-sm font-bold text-green-600">₹{Math.round(route.fare)}</p> : <p className="text-xs text-gray-500">Check IRCTC</p>}
                </div>
              </div>
              {route.availability && (
                <div className="text-center mb-3">
                  <Badge variant={route.availability.includes("AVAILABLE") ? "default" : "secondary"} className="text-xs">
                    {route.availability}
                  </Badge>
                </div>
              )}

              {route.legs && route.legs.length > 1 && (
                <div className="mt-2">
                  <Button variant="ghost" size="sm" onClick={() => setShowSegments(!showSegments)} className="w-full text-blue-600 text-xs">
                    <RouteIcon className="w-3 h-3 mr-1" />
                    {showSegments ? "Hide Segments" : "Show Segments"}
                  </Button>
                  {showSegments && (
                    <div className="mt-2 space-y-2">
                      {route.legs.map((leg, i) => (
                        <div key={i} className="text-[10px] p-2 bg-slate-50 rounded">
                          <div className="flex justify-between font-bold">
                            <span>Train {leg.train_no}</span>
                            <span className="text-green-600">₹{leg.fare}</span>
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <MapPin className="w-2 h-2 text-blue-500" /> {leg.departure} → {leg.arrival}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}, (prev, next) => {
  return prev.route.journey_id === next.route.journey_id && 
         prev.isUnlocked === next.isUnlocked && 
         prev.isProcessing === next.isProcessing;
});
