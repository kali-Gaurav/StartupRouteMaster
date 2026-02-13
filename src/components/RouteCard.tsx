import React, { useState } from "react";
import { ChevronDown, ChevronUp, Clock, Timer, Lock } from "lucide-react"; // Removed ArrowRight, Check, AlertTriangle
import { Route, RouteSegment, formatDuration, formatCost, formatLiveFare, getAvailabilityBadgeClasses, summarizeAvailability, getSeatAvailabilityState, formatAvailabilityForDisplay } from "@/data/routes"; // Added RouteSegment
import { getStationByCode } from "@/data/stations";
import { cn } from "@/lib/utils";

export interface RouteCardBadges {
  fastest?: boolean;
  cheapest?: boolean;
  mostReliable?: boolean;
}

interface RouteCardProps {
  route: Route;
  index: number;
  isRecommended?: boolean;
  badges?: RouteCardBadges;
  /** Called when user clicks Book. Omit to hide the button. */
  onBook?: (route: Route) => void;
  /** Indicates if the route details have been unlocked. */
  isUnlocked: boolean;
  /** Called when user clicks Unlock Details. */
  onUnlock: (route: Route) => void;
}

function RouteCardComponent({ route, index, isRecommended, badges, onBook, isUnlocked, onUnlock }: RouteCardProps) {

  const [isExpanded, setIsExpanded] = useState(false);

  const getCategoryStyle = (category: string) => {
    if (category.includes("FASTEST") || category.includes("FAST")) {
      return "from-amber-500 to-orange-500";
    }
    if (category.includes("DIRECT")) {
      return "from-blue-500 to-cyan-500";
    }
    if (category.includes("SEAT")) {
      return "from-green-500 to-emerald-500";
    }
    if (category.includes("CHEAP")) {
      return "from-emerald-500 to-teal-500";
    }
    if (category.includes("BALANCED")) {
      return "from-purple-500 to-violet-500";
    }
    if (category.includes("3 TRANSFERS")) {
      return "from-violet-500 to-purple-500";
    }
    if (category.includes("TRANSFER") || category.includes("TRANSFERS")) {
      return "from-indigo-500 to-blue-500";
    }
    return "from-slate-500 to-gray-500";
  };

  const firstSegment = route.segments[0];
  const lastSegment = route.segments[route.segments.length - 1];
  const availabilitySummary = summarizeAvailability(route.segments);
  const availabilityBadgeClasses = getAvailabilityBadgeClasses(availabilitySummary.state);
  // Removed const liveFareDisplay = formatLiveFare(route.liveFareTotal ?? route.totalCost);

  return (
    <div className="bg-card rounded-2xl border-2 overflow-hidden transition-all duration-300 hover:shadow-card hover:border-primary/30 border-primary shadow-soft animate-slide-in opacity-0"
         style={{ animationDelay: `${index * 0.1}s`, animationFillMode: "forwards" }}>
      {/* Header */}
      <div className="p-5">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "px-3 py-1.5 rounded-full text-white text-sm font-semibold",
                "bg-gradient-to-r",
                getCategoryStyle(route.category)
              )}
            >
              {route.category}
            </div>
            {isRecommended && (
              <span className="px-2 py-1 bg-green-500/10 text-green-600 dark:text-green-400 text-xs font-semibold rounded-full border border-green-500/20">
                Best overall
              </span>
            )}
            {badges?.fastest && (
              <span className="px-2 py-1 bg-amber-500/15 text-amber-700 dark:text-amber-300 text-xs font-semibold rounded-full border border-amber-500/30">
                Fastest
              </span>
            )}
            {badges?.cheapest && (
              <span className="px-2 py-1 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-xs font-semibold rounded-full border border-emerald-500/30">
                Cheapest
              </span>
            )}
            {badges?.mostReliable && (
              <span className="px-2 py-1 bg-blue-500/15 text-blue-700 dark:text-blue-300 text-xs font-semibold rounded-full border border-blue-500/30">
                Most reliable
              </span>
            )}
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-foreground">
              {route.totalCost > 0 ? formatCost(route.totalCost) : "N/A" }
            </div>
            <div className="text-sm text-muted-foreground">Total fare</div>
          </div>
        </div>

        {/* Main Content */}
        <div className="px-5 pb-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-foreground">
                {getStationByCode(firstSegment.from)?.name || firstSegment.from}
              </span>
              <span className="text-muted-foreground">→</span>
              <span className="text-sm font-semibold text-foreground">
                {getStationByCode(lastSegment.to)?.name || lastSegment.to}
              </span>
            </div>
            <div className={cn("px-2 py-1 rounded-md text-xs font-semibold", availabilityBadgeClasses)} title={availabilitySummary.state === "unknown" ? "Fare and seat availability will be shown at booking" : undefined}>
              {availabilitySummary.label}
            </div>
          </div>
          
          <div className="flex items-center justify-between text-sm mb-3">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Clock size={16} />
              <span>{firstSegment.departure}</span>
              <span>→</span>
              <span>{lastSegment.arrival}</span>
            </div>
            <span className="font-semibold">{formatDuration(route.totalTime)}</span>
          </div>

          {route.totalTransfers > 0 && (
            <div className="text-xs text-muted-foreground mb-3">
              {route.totalTransfers} transfer{route.totalTransfers > 1 ? 's' : ''}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            {!isUnlocked ? (
              <button
                type="button"
                onClick={() => onUnlock(route)}
                className="flex-1 min-w-[120px] py-3 px-4 rounded-lg font-bold text-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-opacity flex items-center justify-center gap-2"
              >
                <Lock size={16} /> Unlock Details - ₹39
              </button>
            ) : (
              <>
                {onBook && (
                  <button
                    type="button"
                    onClick={() => onBook(route)}
                    className="flex-1 min-w-[120px] py-2.5 px-4 rounded-lg font-semibold text-sm bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
                  >
                    Book
                  </button>
                )}
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className={cn(
                    "flex items-center justify-between text-sm font-semibold text-primary hover:text-primary/80 transition-colors",
                    onBook ? "py-2.5 px-3" : "w-full"
                  )}
                >
                  <span>{isExpanded ? "Hide Details" : "View Details"}</span>
                  {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Segments Detail */}
      { (isExpanded || !isUnlocked) && (
        <div className={cn(
          "p-5 bg-secondary/20 border-t border-border space-y-4 animate-fade-in",
          !isUnlocked && "relative" // Add relative for overlay
        )}>
          {!isUnlocked && (
            <div className="absolute inset-0 bg-gradient-to-t from-background/90 to-transparent flex items-center justify-center z-10">
              <div className="p-4 rounded-lg bg-card border border-border shadow-md text-center">
                <Lock className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground font-semibold">Details locked</p>
                <p className="text-xs text-muted-foreground">Unlock to see full itinerary</p>
              </div>
            </div>
          )}
          <div className={cn(!isUnlocked && "opacity-50 blur-sm pointer-events-none")}>
            {route.segments.map((segment: RouteSegment, idx: number) => ( // Explicitly typed
              <div key={idx}>
                {idx > 0 && segment.waitBefore > 0 && (
                  <div className="flex items-center gap-3 py-3 px-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-500/20">
                      <Timer className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-amber-700 dark:text-amber-300 uppercase tracking-wide">
                        Transfer at {getStationByCode(segment.from)?.name || segment.from}
                      </div>
                      <div className="text-lg font-bold text-foreground">
                        Wait time: {formatDuration(segment.waitBefore)}
                      </div>
                    </div>
                  </div>
                )}
                <div className="border border-border rounded-lg p-4 bg-card/50">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-sm">
                      Train {segment.trainNumber}
                    </span>
                    <span className={cn("text-xs font-semibold px-2 py-1 rounded", getAvailabilityBadgeClasses(getSeatAvailabilityState(segment.liveSeatAvailability)))}>
                      {formatAvailabilityForDisplay(segment.liveSeatAvailability) === "Check at booking" ? "Check at booking" : `${formatAvailabilityForDisplay(segment.liveSeatAvailability)} seats`}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground mb-2">
                    <div>
                      <div className="text-foreground font-semibold">{segment.departure}</div>
                      <div>{getStationByCode(segment.from)?.name || segment.from}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-foreground font-semibold">{segment.arrival}</div>
                      <div>{getStationByCode(segment.to)?.name || segment.to}</div>
                    </div>
                  </div>
                  {(segment.liveFare != null && segment.liveFare > 0) && (
                    <div className="text-xs text-primary font-semibold">
                      {formatLiveFare(segment.liveFare)}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export const RouteCard = React.memo(RouteCardComponent);
