import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, Clock, Timer, Lock, ShieldCheck, ShieldAlert, BadgeCheck, ExternalLink, Save, Check, Zap, Sparkles, Gift, Coffee, TrendingDown, Info, ArrowRightCircle, Target, Percent, Briefcase, HeartHandshake, DollarSign, Train, MapPin, Users, Share2 } from "lucide-react"; 
import { motion, AnimatePresence } from "framer-motion";
import { Route, RouteSegment, formatDuration, formatCost, formatLiveFare, getAvailabilityBadgeClasses, getSeatAvailabilityState, formatAvailabilityForDisplay } from "@/data/routes";
import { getStationByCode } from "@/data/stations";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { fetchWithAuth } from "@/lib/apiClient";

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
  const { token } = useAuth();
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
      const response = await fetchWithAuth(`/api/v1/booking/segment-pnrs/${route.id}`);
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

  const handleWhatsAppShare = () => {
    const seg = route.segments[0];
    const lastSeg = route.segments[route.segments.length - 1];
    const irctcUrl = (route.metadata as any)?.irctc_url || '';
    const transfers = route.totalTransfers === 0 ? 'Direct' : `${route.totalTransfers} transfer${route.totalTransfers > 1 ? 's' : ''}`;
    const fare = route.totalCost > 0 ? `₹${route.totalCost}` : '';
    const dur = route.totalTime > 0 ? `${Math.floor(route.totalTime/60)}h ${route.totalTime%60}m` : '';
    const text = [
      `🚂 *${seg.fromName || seg.from} → ${lastSeg.toName || lastSeg.to}*`,
      `Train: ${seg.trainName || seg.trainNumber}`,
      `🕐 ${seg.departure} → ${lastSeg.arrival} (${dur})`,
      fare && `💰 ${fare} | ${transfers}`,
      irctcUrl && `🎟️ Book: ${irctcUrl}`,
      `\n📱 Found via Route Master — routemaster.vercel.app`,
    ].filter(Boolean).join('\n');
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank');
  };

  const [reliability, setReliability] = useState<{score:number;label:string;color:string} | null>(null);

  // Fetch reliability on first expand (lazy — don't burn on render)
  useEffect(() => {
    if (!isExpanded || reliability) return;
    const trainNo = route.segments[0]?.trainNumber;
    if (!trainNo || trainNo === 'N/A') return;
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    fetch(`${apiUrl}/api/v1/trains/${trainNo}/reliability`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.available && d.score != null) setReliability({ score: d.score, label: d.label, color: d.color }); })
      .catch(() => {});
  }, [isExpanded]);

  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSaveRoute = async () => {
    setSaving(true);
    try {
      const seg = route.segments[0];
      const lastSeg = route.segments[route.segments.length - 1];
      const body = {
        from_code: seg.from,
        to_code: lastSeg.to,
        from_name: seg.fromName || seg.from,
        to_name: lastSeg.toName || lastSeg.to,
        route_data: {
          journey_id: route.id,
          num_transfers: route.totalTransfers,
          total_duration: route.totalTime,
          total_cost: route.totalCost,
          departure: seg.departure,
          arrival: lastSeg.arrival,
          train_name: seg.trainName,
          irctc_url: (route.metadata as any)?.irctc_url,
        },
      };
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const headers: HeadersInit = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${apiUrl}/api/v1/users/saved-routes`, { method: 'POST', headers, body: JSON.stringify(body) });
      if (res.ok) { setSaved(true); toast.success('Route saved! View in Dashboard.'); }
      else toast.error('Could not save route. Please log in.');
    } catch { toast.error('Save failed.'); }
    finally { setSaving(false); }
  };

  const [showAlertDialog, setShowAlertDialog] = useState(false);
  const [alertThreshold, setAlertThreshold] = useState("");
  const [alertTgId, setAlertTgId] = useState("");
  const [alertSaving, setAlertSaving] = useState(false);

  const handleSetAlert = async () => {
    const threshold = parseInt(alertThreshold);
    if (!threshold || threshold < 50) { toast.error("Enter a valid fare threshold (min ₹50)"); return; }
    const firstSeg = route.segments[0];
    setAlertSaving(true);
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/alerts/fare`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            from_code: firstSeg.from,
            to_code: firstSeg.to,
            travel_date: travelDate || new Date().toISOString().slice(0, 10),
            travel_class: "SL",
            threshold_inr: threshold,
            telegram_chat_id: alertTgId || null,
          }),
        }
      );
      const data = await res.json();
      if (res.ok) {
        toast.success("Fare alert set!", { description: data.message });
        setShowAlertDialog(false);
        setAlertThreshold("");
      } else {
        toast.error("Failed to set alert");
      }
    } catch { toast.error("Could not connect"); }
    finally { setAlertSaving(false); }
  };

  const handleIrctcRedirect = async (segment: RouteSegment, segIdx: number) => {
    // Use backend-provided URL if available (from route metadata)
    const backendUrl = (route.metadata as any)?.irctc_url as string | undefined;
    if (backendUrl) {
      window.open(backendUrl, "_blank");
      toast.success(`Opening IRCTC booking for Train ${segment.trainNumber}`);
      return;
    }

    // Build IRCTC URL directly
    const dateToUse = travelDate || new Date().toISOString().split('T')[0];
    const [y, m, d] = dateToUse.split('-');
    const irctcDate = `${d}/${m}/${y}`;
    const params = new URLSearchParams({
      fromStn: segment.from,
      toStn: segment.to,
      jrnyDate: irctcDate,
      jrnyClass: 'SL',
      jrnySrc: 'P',
      returnDate: '',
      ticketType: 'E',
      quota: 'GN',
      trainNo: segment.trainNumber,
    });
    window.open(`https://www.irctc.co.in/nget/train-search?${params.toString()}`, "_blank");
    toast.success(`Opening IRCTC booking for Train ${segment.trainNumber}`);
  };

  const savePnr = async (segIdx: number, trainNumber: string) => {
    const pnr = segmentPnrs[segIdx];
    if (!pnr || pnr.length < 10) {
      toast.error("Please enter a valid 10-digit PNR");
      return;
    }

    setSavingPnrs(prev => ({ ...prev, [segIdx]: true }));
    try {
      const response = await fetchWithAuth("/api/v1/booking/save-segment-pnr", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json"
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

  const handleRequestSathi = async () => {
    try {
      const response = await fetchWithAuth(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/sathi/assign`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          sathi_id: "broadcast",
          journey_id: route.id,
          start_station_code: route.segments[0].from,
          end_station_code: route.segments[route.segments.length-1].to,
          expected_duration_minutes: route.totalTime,
          safety_context: {
            reason: "Standard journey protection",
            passenger_gender: "Not specified"
          }
        })
      });

      if (response.ok) {
        toast.success("Sathi Watch requested! Our nearby volunteers have been notified.");
      } else {
        const err = await response.json();
        toast.error(err.detail || "Request failed");
      }
    } catch (e) {
      toast.error("Failed to connect to safety network");
    }
  };

  return (
    <div className="bg-card rounded-2xl border-2 overflow-hidden transition-all duration-300 hover:shadow-card hover:border-primary/30 border-primary shadow-soft animate-slide-in opacity-0"
         style={{ animationDelay: `${index * 0.1}s`, animationFillMode: "forwards" }}>
      {/* Header */}
      <div className="p-5">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3 flex-wrap">
            <div
              className={cn(
                "px-3 py-1.5 rounded-full text-white text-xs font-black uppercase tracking-widest",
                "bg-gradient-to-r",
                getCategoryStyle(route.category)
              )}
            >
              {route.category.replace(/undefined/i, '').trim() || "Optimal Route"}
            </div>
            {isHighSafety && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 text-xs font-bold border border-blue-500/20 shadow-sm animate-in zoom-in duration-300">
                <ShieldCheck className="w-3.5 h-3.5" />
                Verified Safe
              </span>
            )}
            {route.metadata?.sathi_protected && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-bold border border-emerald-500/20 shadow-sm animate-in slide-in-from-right duration-300">
                <BadgeCheck className="w-3.5 h-3.5" />
                Sathi Protected
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
            {route.metadata?.is_proximity_alt && (
              <span className="px-2 py-1 bg-purple-500/15 text-purple-700 dark:text-purple-300 text-xs font-semibold rounded-full border border-purple-500/30 flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                Nearby Alternative
              </span>
            )}
            {route.metadata?.is_ml_scored && (
               <span className="px-2 py-1 bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 text-xs font-semibold rounded-full border border-indigo-500/30 flex items-center gap-1 animate-pulse">
                <Zap className="w-3 h-3 fill-indigo-500" />
                AI Confidence
              </span>
            )}
            {route.metadata?.heartbeat_verified && (
               <span className="px-2 py-1 bg-rose-500/15 text-rose-700 dark:text-rose-300 text-xs font-black rounded-full border border-rose-500/30 flex items-center gap-1">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
                </span>
                LIVE SYNC
              </span>
            )}
            {route.metadata?.persona_tags?.map((tag: string, i: number) => (
              <span key={i} className="px-2 py-1 bg-primary/10 text-primary text-xs font-bold rounded-full border border-primary/20 uppercase tracking-tighter">
                {tag}
              </span>
            ))}
            
            {/* Phase 6: Arbitrage Tags */}
            {route.metadata?.arbitrage_tag === "BEST_VALUE" && (
              <span className="px-2 py-1 bg-gradient-to-r from-yellow-400 to-amber-600 text-white text-xs font-black rounded-full border border-yellow-500 shadow-sm flex items-center gap-1 animate-shimmer">
                <Target className="w-3 h-3" />
                BEST VALUE
              </span>
            )}
            {route.metadata?.arbitrage_tag === "TIME_ARBITRAGE" && (
              <span className="px-2 py-1 bg-gradient-to-r from-blue-600 to-indigo-700 text-white text-xs font-black rounded-full border border-blue-400 shadow-sm flex items-center gap-1">
                <Clock className="w-3 h-3" />
                TIME OPTIMIZED
              </span>
            )}

            {/* Phase 5: Reliability Index */}
            {route.metadata?.cancellation_probability !== undefined && (
              <span className={cn(
                "px-2 py-1 text-xs font-bold rounded-full border flex items-center gap-1",
                route.metadata.cancellation_probability < 0.1 
                  ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20" 
                  : "bg-orange-500/10 text-orange-600 border-orange-500/20"
              )}>
                <Percent className="w-3 h-3" />
                {Math.round((1 - route.metadata.cancellation_probability) * 100)}% RELIABLE
              </span>
            )}
            
            {/* [TEACHER DEMO] Unlocked Badge */}
            {isUnlocked && (
              <span className="px-2 py-1 bg-gradient-to-r from-green-500 to-emerald-600 text-white text-xs font-black rounded-full border border-green-500 shadow-sm flex items-center gap-1 animate-pulse">
                <Check className="w-3 h-3" />
                UNLOCKED
              </span>
            )}
          </div>
          <div className="text-right shrink-0">
            <div className="text-2xl font-black text-foreground tracking-tighter">
              {route.totalCost > 0 ? formatCost(route.totalCost) : <span className="text-sm text-muted-foreground italic">Pricing Pending</span> }
            </div>
            <div className="flex flex-col items-end gap-1.5 mt-1">
              {route.metadata?.safety_badge === "SATHI_VERIFIED" && (
                <div className="flex items-center gap-1.5 px-2 py-0.5 bg-emerald-500/10 text-emerald-600 rounded-lg text-xs font-black uppercase tracking-tighter border border-emerald-500/20 shadow-sm animate-pulse group cursor-help">
                  <HeartHandshake className="w-3 h-3 animate-bounce" /> 
                  <span>Sathi Verified</span>
                  <div className="absolute bottom-full right-0 mb-2 w-48 p-2 bg-popover text-popover-foreground text-xs rounded-lg shadow-xl border border-border opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 normal-case font-medium">
                    Verified human safety guide available at transfer stations.
                  </div>
                </div>
              )}
              {reliability && (
                <div className={cn(
                  "flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-black border",
                  reliability.color === 'green' ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20" :
                  reliability.color === 'yellow' ? "bg-amber-500/10 text-amber-600 border-amber-500/20" :
                  reliability.color === 'orange' ? "bg-orange-500/10 text-orange-600 border-orange-500/20" :
                  "bg-red-500/10 text-red-600 border-red-500/20"
                )}>
                  <div className={cn("w-1.5 h-1.5 rounded-full", reliability.color === 'green' ? "bg-emerald-500" : reliability.color === 'yellow' ? "bg-amber-500" : "bg-red-500")} />
                  {reliability.score}% Punctual
                </div>
              )}
              <div className="flex items-center gap-1.5">
                <div className="group relative cursor-help">
                  <span className={cn("text-xs font-black uppercase tracking-widest border-b border-dotted", safetyColor)}>
                    Safety {route.safetyScore}/100
                  </span>
                  <div className="absolute bottom-full right-0 mb-2 w-48 p-2 bg-popover text-popover-foreground text-xs rounded-lg shadow-xl border border-border opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                    Score based on cancellation rates, delay history, and real-time crowd density.
                  </div>
                </div>
                {isHighSafety ? <BadgeCheck className="w-3.5 h-3.5 text-emerald-500" /> : <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />}
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="px-5 pb-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1.5 px-2 py-1 bg-secondary rounded-lg">
                <Train className="w-3.5 h-3.5 text-primary" />
                <span className="text-xs font-bold text-foreground">
                  {firstSegment.fromName || getStationByCode(firstSegment.from)?.name || firstSegment.from}
                </span>
              </div>
              
              {route.segments.length > 1 && route.segments.slice(0, -1).map((seg, i) => (
                <React.Fragment key={i}>
                  <span className="text-muted-foreground text-xs">→</span>
                  <div className="flex items-center gap-1 text-xs font-bold text-muted-foreground italic">
                     via {seg.toName || getStationByCode(seg.to)?.name || seg.to}
                  </div>
                </React.Fragment>
              ))}

              <span className="text-muted-foreground text-xs">→</span>
              <div className="flex items-center gap-1.5 px-2 py-1 bg-secondary rounded-lg">
                <MapPin className="w-3.5 h-3.5 text-accent" />
                <span className="text-xs font-bold text-foreground">
                  {lastSegment.toName || getStationByCode(lastSegment.to)?.name || lastSegment.to}
                </span>
              </div>
            </div>
            {route.metadata?.pulse_status && (
              <span className="text-xs font-black uppercase text-rose-500 bg-rose-500/10 px-1.5 py-0.5 rounded leading-none">
                Hub Status: {route.metadata.pulse_status}
              </span>
            )}
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
            <div className="flex items-center gap-3">
              {route.totalDistance > 0 && (
                <div className="flex items-center gap-1">
                  <span className="font-bold text-foreground">{route.totalDistance}</span>
                  <span>km</span>
                </div>
              )}
              <div className="flex items-center gap-1 border-l pl-3 border-border">
                <span className="font-bold text-foreground">{route.totalTransfers}</span>
                <span>transfer{route.totalTransfers !== 1 ? 's' : ''}</span>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <DollarSign className="w-3.5 h-3.5 text-emerald-500" />
              <span className="text-foreground font-black tracking-tight">
                {route.totalCost > 0 ? formatCost(route.totalCost) : "Pending"}
              </span>
            </div>
          </div>

          {/* Available classes + fare source */}
          {(() => {
            const classes: string[] = (route.metadata as any)?.available_classes || [];
            const fareSource: string = (route.metadata as any)?.fare_source || "estimate";
            if (classes.length === 0) return null;
            return (
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Classes:</span>
                {classes.map((cls: string) => (
                  <span key={cls} className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] font-black border border-primary/20">
                    {cls}
                  </span>
                ))}
                <span className={cn(
                  "ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full border",
                  fareSource === "erail"
                    ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                    : "bg-amber-500/10 text-amber-600 border-amber-500/20"
                )}>
                  {fareSource === "erail" ? "IRCTC Fare" : "Est. Fare"}
                </span>
              </div>
            );
          })()}

          {/* [RM-S-030] Safety Intelligence Vibe Section */}
          <div className="grid grid-cols-3 gap-3 p-4 bg-muted/30 rounded-2xl border border-border/50 mb-5 animate-in fade-in duration-500">
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5 text-xs font-black uppercase tracking-widest text-muted-foreground">
                <Zap className="w-3 h-3 text-amber-500" /> Lighting
              </div>
              <div className="flex items-center gap-2">
                 <div className="h-1.5 flex-1 bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" 
                      style={{ width: `${route.metadata?.vibe?.lighting || 85}%` }}
                    />
                 </div>
                 <span className="text-xs font-black">{route.metadata?.vibe?.lighting || 85}%</span>
              </div>
            </div>
            
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5 text-xs font-black uppercase tracking-widest text-muted-foreground">
                <Users className="w-3 h-3 text-blue-500" /> Crowd
              </div>
              <div className={cn(
                "text-xs font-black uppercase px-2 py-0.5 rounded-md w-fit",
                (route.metadata?.vibe?.crowd_density || 0.4) < 0.2 ? "bg-amber-100 text-amber-700" : "bg-blue-100 text-blue-700"
              )}>
                 {(route.metadata?.vibe?.crowd_density || 0.4) < 0.2 ? "Deserted" : (route.metadata?.vibe?.crowd_density || 0.4) > 0.7 ? "Crowded" : "Optimal"}
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5 text-xs font-black uppercase tracking-widest text-muted-foreground">
                <ShieldCheck className="w-3 h-3 text-emerald-500" /> Sathi
              </div>
              <div className="text-xs font-black uppercase text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-md w-fit">
                 {route.metadata?.sathi_coverage || 0} Ready
              </div>
            </div>
          </div>

          {/* AI Reasoning [Task 10] */}
          {route.metadata?.ui_reasons?.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-1.5">
              {route.metadata?.ui_reasons?.map((reason: string, i: number) => (
                <div key={i} className="flex items-center gap-1 text-xs font-bold text-amber-600 dark:text-amber-400 bg-amber-500/5 px-2 py-0.5 rounded border border-amber-500/10">
                  <div className="w-1 h-1 rounded-full bg-amber-500" />
                  {reason}
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            {!isUnlocked ? (
              <button
                type="button"
                onClick={() => onUnlock(route)}
                className="flex-1 min-w-[200px] py-4 px-6 rounded-xl font-black text-xs uppercase tracking-widest bg-primary text-primary-foreground hover:brightness-110 active:scale-95 transition-all flex items-center justify-center gap-3 shadow-lg shadow-primary/20 group"
              >
                <Lock size={16} className="group-hover:animate-bounce" /> 
                🚀 Get Full Itinerary + Live Booking Options — {route.metadata?.unlock_fee ? formatCost(route.metadata.unlock_fee) : "₹39"}
              </button>
            ) : (
              <>
                {/* [TEACHER DEMO] Show unlocked status */}
                <div className="w-full mb-3 flex items-center justify-center gap-2 px-4 py-2 bg-green-500/10 border border-green-500/20 rounded-lg">
                  <Check className="w-4 h-4 text-green-600" />
                  <span className="text-xs font-bold text-green-600 uppercase tracking-widest">
                    All Routes Unlocked for Demo
                  </span>
                </div>
                <div className="flex flex-col w-full gap-3">
                  {/* Book on IRCTC + Save side by side */}
                  <div className="flex gap-2">
                  <a
                    href={(route.metadata as any)?.irctc_url || `https://www.irctc.co.in/nget/train-search?fromStn=${route.segments?.[0]?.from}&toStn=${route.segments?.[route.segments.length-1]?.to}`}
                    target="_blank"
                    className="flex-1"
                    rel="noopener noreferrer"
                    className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-black uppercase tracking-widest text-sm bg-blue-600 text-white hover:bg-blue-700 transition-all shadow-lg active:scale-95"
                    onClick={() => toast.success("Opening IRCTC booking...")}
                  >
                    <ExternalLink size={16} />
                    Book on IRCTC
                  </a>
                  <button
                    type="button"
                    onClick={handleSaveRoute}
                    disabled={saving || saved}
                    title={saved ? "Saved!" : "Save this route"}
                    className={cn(
                      "px-4 py-3 rounded-xl font-black text-xs transition-all border-2 flex items-center gap-1.5",
                      saved
                        ? "border-emerald-500 bg-emerald-500/10 text-emerald-600"
                        : "border-border hover:border-primary/40 text-muted-foreground hover:text-primary"
                    )}
                  >
                    {saving ? <div className="w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin" /> : saved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                    {saved ? "Saved" : "Save"}
                  </button>
                  </div>

                  {/* WhatsApp Share */}
                  <button
                    type="button"
                    onClick={handleWhatsAppShare}
                    className="w-full py-2.5 px-4 rounded-xl font-black text-xs border-2 border-[#25D366]/40 text-[#25D366] hover:bg-[#25D366]/10 transition-all flex items-center justify-center gap-2"
                  >
                    <Share2 className="w-4 h-4" />
                    Share on WhatsApp
                  </button>

                  {/* Fare Alert button */}
                  <button
                    type="button"
                    onClick={() => setShowAlertDialog(true)}
                    className="w-full py-2.5 px-4 rounded-xl font-black uppercase tracking-widest text-xs border-2 border-dashed border-amber-500/40 text-amber-600 dark:text-amber-400 hover:bg-amber-500/10 transition-all flex items-center justify-center gap-2"
                  >
                    <Gift className="w-4 h-4" />
                    Set Fare Alert — Get notified when price drops
                  </button>

                  {/* Alert dialog */}
                  {showAlertDialog && (
                    <div className="bg-amber-500/10 border-2 border-amber-500/30 rounded-xl p-4 space-y-3 animate-in slide-in-from-top-2">
                      <p className="text-xs font-black uppercase tracking-widest text-amber-600">🔔 Set Fare Alert</p>
                      <div className="flex gap-2">
                        <input
                          type="number"
                          placeholder="Max fare ₹"
                          value={alertThreshold}
                          onChange={e => setAlertThreshold(e.target.value)}
                          className="flex-1 px-3 py-2 rounded-lg border border-border bg-background text-sm font-bold focus:outline-none focus:border-amber-500"
                          min={50} max={10000}
                        />
                        <input
                          type="text"
                          placeholder="Telegram Chat ID (optional)"
                          value={alertTgId}
                          onChange={e => setAlertTgId(e.target.value)}
                          className="flex-1 px-3 py-2 rounded-lg border border-border bg-background text-sm font-bold focus:outline-none focus:border-amber-500"
                        />
                      </div>
                      <p className="text-[10px] text-muted-foreground">
                        Get Telegram notification via <a href="https://t.me/RoutemasternagarindustrisBot" target="_blank" className="text-primary underline">@RoutemasterBot</a> (send /start to get Chat ID)
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={handleSetAlert}
                          disabled={alertSaving}
                          className="flex-1 py-2 rounded-lg bg-amber-500 text-white font-black text-xs disabled:opacity-50 flex items-center justify-center gap-1"
                        >
                          {alertSaving ? <><span className="w-3 h-3 border border-white/40 border-t-white rounded-full animate-spin inline-block" /> Saving...</> : "Set Alert"}
                        </button>
                        <button onClick={() => setShowAlertDialog(false)} className="px-4 py-2 rounded-lg border border-border text-xs font-bold text-muted-foreground hover:text-foreground">Cancel</button>
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2">
                    {onBook && (
                      <button
                        type="button"
                        onClick={() => onBook(route)}
                        className="flex-1 py-3 px-4 rounded-xl font-black uppercase tracking-widest text-xs bg-slate-900 text-white hover:bg-slate-800 transition-all shadow-lg active:scale-95"
                      >
                        Confirm Booking
                      </button>
                    )}
                    {(route.metadata?.sathi_protected || route.metadata?.safety_badge === "SATHI_VERIFIED") && (
                      <button
                        type="button"
                        onClick={handleRequestSathi}
                        className="flex-1 py-3 px-4 rounded-xl font-black uppercase tracking-widest text-xs bg-emerald-500 text-white hover:bg-emerald-600 transition-all shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-2 active:scale-95"
                      >
                        <HeartHandshake className="w-4 h-4" />
                        Request Sathi Watch
                      </button>
                    )}
                  </div>
                  <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    aria-expanded={isExpanded}
                    aria-controls={`itinerary-details-${route.id}`}
                    className="flex items-center justify-center gap-2 py-2 text-xs font-black uppercase tracking-widest text-muted-foreground hover:text-primary transition-colors"
                  >
                    <span>{isExpanded ? "Hide Tactical View" : "Examine Itinerary"}</span>
                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Phase 4: Redistribution / Network Load Balancer */}
        <AnimatePresence>
          {route.redistribution_options && route.redistribution_options.length > 0 && (
            <motion.div 
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="px-5 pb-5 pt-0"
            >
              <div className="rounded-xl border border-primary/30 bg-gradient-to-br from-primary/5 to-transparent overflow-hidden shadow-sm">
                <div className="bg-primary/10 px-4 py-2 flex items-center justify-between border-b border-primary/20">
                  <div className="flex items-center gap-2 text-primary">
                    <TrendingDown className="w-4 h-4" />
                    <span className="text-xs font-black uppercase tracking-widest">Network Load Alert</span>
                  </div>
                  <div className="text-xs font-bold text-primary/60 italic">Incentivized Alternative</div>
                </div>
                
                <div className="p-4 space-y-3">
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    This corridor is experiencing high demand. Select this alternative to receive 
                    <span className="font-bold text-foreground"> exclusive premium benefits</span>:
                  </p>
                  
                  <div className="flex flex-wrap gap-2">
                    {route.redistribution_options[0].incentives.map((offer, i) => (
                      <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-background border border-border shadow-xs animate-in slide-in-from-left duration-500" style={{ animationDelay: `${i * 0.1}s` }}>
                        {offer.type === 'LOUNGE_ACCESS' && <Coffee className="w-3.5 h-3.5 text-amber-500" />}
                        {offer.type === 'CASHBACK' && <Gift className="w-3.5 h-3.5 text-emerald-500" />}
                        {offer.type === 'MEAL_VOUCHER' && <Info className="w-3.5 h-3.5 text-blue-500" />}
                        <div className="flex flex-col">
                          <span className="text-xs font-black leading-none text-foreground uppercase">{offer.value}</span>
                          <span className="text-xs text-muted-foreground">{offer.description}</span>
                        </div>
                      </div>
                    ))}
                  </div>

                  <button 
                    onClick={() => toast.success("Switching to Optimized Route...")}
                    className="w-full flex items-center justify-center gap-2 py-2 bg-primary text-primary-foreground rounded-lg text-xs font-black uppercase tracking-widest hover:brightness-110 transition-all group"
                  >
                    Accept Optimized Path
                    <ArrowRightCircle className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Segments Detail */}
      { (isExpanded || !isUnlocked) && (
        <div id={`itinerary-details-${route.id}`} className={cn(
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
                    <span className={cn("text-xs font-semibold px-2 py-1 rounded flex flex-col items-end", getAvailabilityBadgeClasses(getSeatAvailabilityState(segment.liveSeatAvailability)))}>
                      <span>{formatAvailabilityForDisplay(segment.liveSeatAvailability) === "Check at booking" ? "Check at booking" : `${formatAvailabilityForDisplay(segment.liveSeatAvailability)} seats`}</span>
                      {segment.metadata?.virtual_capacity && (
                        <span className="text-xs font-black opacity-80 uppercase tracking-tighter">
                          + {segment.metadata.overbook_count || 0} Virtual Capacity
                        </span>
                      )}
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
                        <p className="text-xs text-emerald-600 font-medium flex items-center gap-1">
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
