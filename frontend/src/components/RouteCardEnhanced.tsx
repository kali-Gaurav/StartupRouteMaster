import { Route, RouteSegment } from "@/data/routes";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Clock, MapPin, Train, Lock, ArrowRight } from "lucide-react";
import { formatDuration, formatCost } from "@/data/routes";
import { cn } from "@/lib/utils";

interface RouteCardEnhancedProps {
  route: Route;
  isLiveVerified?: boolean;
  className?: string;
  /** Indicates if the route details have been unlocked. */
  isUnlocked: boolean;
  /** Called when user clicks Unlock Details. */
  onUnlock: (route: Route) => void;
}

export function RouteCardEnhanced({
  route,
  isLiveVerified = false,
  className,
  isUnlocked,
  onUnlock,
}: RouteCardEnhancedProps) {
  return (
    <Card className={cn("p-6 space-y-4", className)}>
      {/* Header with Live Verified Badge */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-semibold">
            {route.category}
          </Badge>
          {isLiveVerified && (
            <Badge variant="default" className="bg-green-500 hover:bg-green-600">
              <CheckCircle2 className="w-3 h-3 mr-1" />
              Live Verified
            </Badge>
          )}
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-primary">
            {formatCost(route.totalCost)}
          </div>
          <div className="text-sm text-muted-foreground">
            {formatDuration(route.totalTime)}
          </div>
        </div>
      </div>

      {!isUnlocked ? (
        <button
          type="button"
          onClick={() => onUnlock(route)}
          className="w-full py-3 px-4 rounded-lg font-semibold text-sm bg-primary text-primary-foreground hover:opacity-90 transition-opacity flex items-center justify-center gap-2 mt-4"
        >
          <Lock size={16} /> Unlock Details - ₹39
        </button>
      ) : (
        <>
          {/* Detailed Itinerary */}
          {route.segments.length > 0 && (
            <div className="space-y-3 pt-2 border-t">
              {route.segments.map((segment: RouteSegment, idx: number) => ( // Explicitly typed
                <div key={idx} className="flex items-start gap-3">
                  {/* Train Icon */}
                  <div className="flex-shrink-0 mt-1">
                    <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                      <Train className="w-5 h-5 text-primary" />
                    </div>
                  </div>

                  {/* Segment Details */}
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">
                        {segment.trainNumber} - {segment.trainName}
                      </span>
                      {segment.liveSeatAvailability && (
                        <Badge
                          variant={
                            segment.seatAvailable ? "default" : "secondary"
                          }
                          className="text-xs"
                        >
                          {segment.liveSeatAvailability}
                        </Badge>
                      )}
                    </div>

                    {/* Station Timeline */}
                    <div className="flex items-center gap-2 text-sm">
                      <div className="flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-muted-foreground" />
                        <span className="font-medium">{segment.from}</span>
                      </div>
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        <span>{segment.departure}</span>
                      </div>
                      <ArrowRight className="w-4 h-4 text-muted-foreground mx-1" />
                      <div className="flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-muted-foreground" />
                        <span className="font-medium">{segment.to}</span>
                      </div>
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        <span>{segment.arrival}</span>
                      </div>
                    </div>

                    {/* Duration and Distance */}
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span>{formatDuration(segment.duration)}</span>
                      <span>{segment.distance} km</span>
                      {segment.liveFare > 0 && (
                        <span className="text-green-600 dark:text-green-400">
                          {formatCost(segment.liveFare)}
                        </span>
                      )}
                    </div>

                    {/* Transfer Wait Time */}
                    {segment.waitBefore > 0 && idx < route.segments.length - 1 && (
                      <div className="mt-2 pt-2 border-t border-dashed">
                        <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
                          <Clock className="w-3 h-3" />
                          <span>
                            Transfer wait: {formatDuration(segment.waitBefore)} at{" "}
                            {segment.to}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Summary Stats */}
          <div className="flex items-center justify-between pt-4 border-t">
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <div className="text-muted-foreground">Transfers</div>
                <div className="font-semibold">{route.totalTransfers}</div>
              </div>
              <div>
                <div className="text-muted-foreground">Distance</div>
                <div className="font-semibold">{route.totalDistance} km</div>
              </div>
              <div>
                <div className="text-muted-foreground">Safety</div>
                <div className="font-semibold">{route.safetyScore}/100</div>
              </div>
            </div>
          </div>
        </>
      )}
    </Card>
  );
}
