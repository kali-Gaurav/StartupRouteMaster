import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, Clock, Timer, Lock, ShieldCheck, ShieldAlert, BadgeCheck, ExternalLink, Save, Check } from "lucide-react"; // Added ExternalLink, Save, Check
import { Route, RouteSegment, formatDuration, formatCost, formatLiveFare, getAvailabilityBadgeClasses, getSeatAvailabilityState, formatAvailabilityForDisplay } from "@/data/routes";
import { getStationByCode } from "@/data/stations";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

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
  /** The travel date for this route. */
  travelDate?: string;
}

function RouteCardComponent({ route, index, isRecommended, badges, onBook, isUnlocked, onUnlock, travelDate }: RouteCardProps) {

  const [isExpanded, setIsExpanded] = useState(false);
  const [segmentPnrs, setSegmentPnrs] = useState<Record<number, string>>({});
  const [savingPnrs, setSavingPnrs] = useState<Record<number, boolean>>({});
  const [savedPnrs, setSavedPnrs] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (isExpanded && isUnlocked) {
      fetchPnrs();
    }
  }, [isExpanded, isUnlocked]);

  const fetchPnrs = async () => {
    try {
      const token = localStorage.getItem("supabase.auth.token") || localStorage.getItem("sb-vclitvpgmqzntscvshje-auth-token");
      const accessToken = token ? JSON.parse(token)?.access_token : null;
      
      const response = await fetch(`/api/v1/booking/segment-pnrs/${route.id}`, {
        headers: {
          "Authorization": `Bearer ${accessToken}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        const pnrMap: Record<number, string> = {};
        const savedMap: Record<number, boolean> = {};
        data.forEach((p: any) => {
          pnrMap[p.segment_index] = p.pnr;
          savedMap[p.segment_index] = true;
        });
        setSegmentPnrs(prev => ({ ...prev, ...pnrMap }));
        setSavedPnrs(prev => ({ ...prev, ...savedMap }));
      }
    } catch (error) {
      console.error("Error fetching PNRs:", error);
    }
  };

  const handleIrctcRedirect = async (segment: RouteSegment, segIdx: number) => {
    // Use travelDate from props, fallback to current date if missing
    const dateToUse = travelDate || new Date().toISOString().split('T')[0];
    
    // Redirect to our internal redirection page which then goes to IRCTC
    const params = new URLSearchParams({
      train: segment.trainNumber,
      from: segment.from,
      to: segment.to,
      date: dateToUse
    });
    
    window.open(`/redirect/irctc?${params.toString()}`, "_blank");
    toast.info(`Preparing redirection for Train ${segment.trainNumber}`);
  };

  const savePnr = async (segIdx: number, trainNumber: string) => {
    const pnr = segmentPnrs[segIdx];
    if (!pnr || pnr.length < 10) {
      toast.error("Please enter a valid 10-digit PNR");
      return;
    }

    setSavingPnrs(prev => ({ ...prev, [segIdx]: true }));
    try {
      const token = localStorage.getItem("supabase.auth.token") || localStorage.getItem("sb-vclitvpgmqzntscvshje-auth-token");
      const accessToken = token ? JSON.parse(token)?.access_token : null;

      const response = await fetch("/api/v1/booking/save-segment-pnr", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${accessToken}`
        },
        body: JSON.stringify({
          journey_id: route.id,
          segment_index: segIdx,
          train_number: trainNumber,
          pnr: pnr
        })
      });

      if (response.ok) {
        toast.success(`PNR saved for segment ${segIdx + 1}`);
        setSavedPnrs(prev => ({ ...prev, [segIdx]: true }));
      } else {
        toast.error("Failed to save PNR");
      }
    } catch (error) {
      toast.error("Error saving PNR");
    } finally {
      setSavingPnrs(prev => ({ ...prev, [segIdx]: false }));
    }
  };

  // Defensive rendering: avoid crashes when route data is malformed.
  if (!route?.segments || route.segments.length === 0) {
    return (
      <div className="bg-card rounded-2xl border-2 border-dashed border-red-200 p-6 text-center">
        <div className="text-sm font-bold text-red-700">Invalid route data</div>
        <div className="text-xs text-muted-foreground">This route is missing required details and cannot be displayed.</div>
      </div>
    );
  }

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
  
  // Safety Logic
  const isHighSafety = (route.safetyScore ?? 0) >= 90;
  const safetyColor = isHighSafety ? "text-emerald-500" : (route.safetyScore ?? 0) > 60 ? "text-amber-500" : "text-red-500";

  return (
    <div className="bg-card rounded-2xl border-2 overflow-hidden transition-all duration-300 hover:shadow-card hover:border-primary/30 border-primary shadow-soft animate-slide-in opacity-0"
         style={{ animationDelay: `${index * 0.1}s`, animationFillMode: "forwards" }}>
      {/* Header */}
      <div className="p-5">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3 flex-wrap">
            <div
              className={cn(
                "px-3 py-1.5 rounded-full text-white text-sm font-semibold",
                "bg-gradient-to-r",
                getCategoryStyle(route.category)
              )}
            >
              {route.category}
            </div>
            {isHighSafety && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 text-xs font-bold border border-blue-500/20 shadow-sm animate-in zoom-in duration-300">
                <ShieldCheck className="w-3.5 h-3.5" />
                Verified Safe
              </span>
            )}
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
          </div>
          <div className="text-right shrink-0">
            <div className="text-2xl font-bold text-foreground">
              {route.totalCost > 0 ? formatCost(route.totalCost) : "N/A" }
            </div>
            <div className="flex items-center justify-end gap-1.5 mt-1">
              <span className={cn("text-xs font-black uppercase tracking-tighter", safetyColor)}>
                Safety {route.safetyScore}/100
              </span>
              {isHighSafety ? <BadgeCheck className="w-3.5 h-3.5 text-emerald-500" /> : <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />}
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="px-5 pb-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-foreground">
                {firstSegment.fromName || getStationByCode(firstSegment.from)?.name || firstSegment.from}
              </span>
              <span className="text-muted-foreground">→</span>
              <span className="text-sm font-semibold text-foreground">
                {lastSegment.toName || getStationByCode(lastSegment.to)?.name || lastSegment.to}
              </span>
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

          <div className="flex items-center justify-between text-sm mb-3 text-muted-foreground">
            <span>Distance: {route.totalDistance} km</span>
            <span className="text-foreground font-semibold">
              Total: {formatCost(route.totalCost)}
            </span>
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
                        Transfer at {segment.fromName || getStationByCode(segment.from)?.name || segment.from}
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
                      Train {segment.trainNumber} - {segment.trainName}
                    </span>
                    <span className={cn("text-xs font-semibold px-2 py-1 rounded", getAvailabilityBadgeClasses(getSeatAvailabilityState(segment.liveSeatAvailability)))}>
                      {formatAvailabilityForDisplay(segment.liveSeatAvailability) === "Check at booking" ? "Check at booking" : `${formatAvailabilityForDisplay(segment.liveSeatAvailability)} seats`}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground mb-2">
                    <div>
                      <div className="text-foreground font-semibold">{segment.departure}</div>
                      <div>{segment.fromName || getStationByCode(segment.from)?.name || segment.from}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-foreground font-semibold">{segment.arrival}</div>
                      <div>{segment.toName || getStationByCode(segment.to)?.name || segment.to}</div>
                    </div>
                  </div>
                  {(segment.liveFare != null && segment.liveFare > 0) && (
                    <div className="text-xs text-primary font-semibold">
                      {formatLiveFare(segment.liveFare)}
                    </div>
                  )}

                  {isUnlocked && (
                    <div className="mt-4 pt-4 border-t border-border flex flex-col gap-3">
                      <button
                        onClick={() => handleIrctcRedirect(segment, idx)}
                        className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-md transition-colors shadow-sm"
                      >
                        <ExternalLink size={14} />
                        Check Seats on IRCTC
                      </button>
                      
                      <div className="flex items-center gap-2">
                        <div className="relative flex-1">
                          <input
                            type="text"
                            placeholder="Enter 10-digit PNR"
                            maxLength={10}
                            value={segmentPnrs[idx] || ""}
                            onChange={(e) => {
                              const val = e.target.value.replace(/\D/g, "");
                              setSegmentPnrs(prev => ({ ...prev, [idx]: val }));
                              if (savedPnrs[idx]) setSavedPnrs(prev => ({ ...prev, [idx]: false }));
                            }}
                            className="w-full bg-background border border-border rounded-md py-2 px-3 text-xs focus:ring-1 focus:ring-primary outline-none transition-all"
                          />
                          {savedPnrs[idx] && (
                            <div className="absolute right-2 top-1/2 -translate-y-1/2 text-emerald-500">
                              <Check size={14} />
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => savePnr(idx, segment.trainNumber)}
                          disabled={savingPnrs[idx]}
                          className={cn(
                            "p-2 rounded-md transition-all flex items-center justify-center",
                            savedPnrs[idx] 
                              ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200" 
                              : "bg-secondary text-secondary-foreground hover:bg-secondary/80",
                            savingPnrs[idx] && "opacity-50 cursor-not-allowed animate-pulse"
                          )}
                          title="Save PNR for tracking"
                        >
                          {savingPnrs[idx] ? <Clock size={16} className="animate-spin" /> : <Save size={16} />}
                        </button>
                      </div>
                      {savedPnrs[idx] && (
                        <p className="text-[10px] text-emerald-600 font-medium flex items-center gap-1">
                          <BadgeCheck size={10} /> PNR tracked for alerts & SOS
                        </p>
                      )}
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
