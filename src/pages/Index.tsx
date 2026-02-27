import { useState, useMemo, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowLeftRight, CalendarDays, Search, Sparkles, Train, MapPin, Filter, Zap, DollarSign, Shield, Database, FileText, WifiOff, ShieldAlert } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { StationSearch } from "@/components/StationSearch";
import { RouteCard } from "@/components/RouteCard";
import { RouteSkeleton } from "@/components/skeletons";
import { BookingFlowModal } from "@/components/booking";
import { useBookingFlowContext } from "@/context/BookingFlowContext";
import { CategoryFilter } from "@/components/CategoryFilter";
import { FeaturesSection } from "@/components/FeaturesSection";
import { Station, addStationsToCache, searchStations as searchStationsLocal } from "@/data/stations";
import { Route, getCategoryBase } from "@/data/routes";
import { getCachedRoutes, normalizeDate } from "@/data/cachedRoutes";
import { searchRoutesApi, mapBackendRoutesToRoutes, resolveStationCode, getStatsRailway, getSearchHistory } from "@/services/railwayBackApi";
import { ackFlow } from "@/api/flow";
import { cn } from "@/lib/utils";
import { toast, Toast } from "@/hooks/use-toast";
import { logEvent, logPerf } from "@/lib/observability";
import { RouteSourceToggle, type RouteSource } from "@/components/RouteSourceToggle";
import { getUnlockedRoutes } from "@/lib/paymentApi";
import { useAuth } from "@/context/AuthContext";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import { predictivePreloadService } from "@/services/predictivePreloadService";
import { storageService } from "@/services/storageService";

const Index = () => {
  const isBackendOnline = useBackendHealth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [origin, setOrigin] = useState<Station | null>(null);
  const [destination, setDestination] = useState<Station | null>(null);
  const [travelDate, setTravelDate] = useState<string>(() => new Date().toISOString().slice(0, 10));
  const [isSearching, setIsSearching] = useState(false);
  const [optimalRoutes, setOptimalRoutes] = useState<Route[]>([]);
  const [allRoutes, setAllRoutes] = useState<Route[]>([]);
  const [displayedAlternatives, setDisplayedAlternatives] = useState<number>(5);
  const [viewMode, setViewMode] = useState<"optimal" | "all">("optimal");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [isFromCache, setIsFromCache] = useState(false);
  const [routeSource, setRouteSource] = useState<RouteSource>("live"); // "live" or "cached"
  const [dateWindow] = useState(1); // ±N days around travel date
  const [sortBy, setSortBy] = useState<"duration" | "cost" | "score">("duration");
  /** Client-side sort preset for results (instant, no re-fetch). */
  const [sortPreset, setSortPreset] = useState<"duration" | "cost" | "reliable">("duration");
  const [filterTransfers, setFilterTransfers] = useState<number | null>(null);
  const [filterDeparture, setFilterDeparture] = useState<"morning" | "afternoon" | "evening" | null>(null);
  const [filterMaxDurationHours, setFilterMaxDurationHours] = useState<number | null>(null);
  const [filterMaxCost, setFilterMaxCost] = useState<number | null>(null);
  const [journeyMessage, setJourneyMessage] = useState<string | null>(null);
  const [bookingTips, setBookingTips] = useState<string[]>([]);
  const [stats, setStats] = useState<{ total_trains?: number; total_stations?: number } | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const flowCorrelationIdRef = useRef<string | null>(null);
  const hasTriggeredChatbotSearch = useRef<boolean>(false);
  const hasRestoredLastSearch = useRef<boolean>(false);
  const [unlockedRouteIds, setUnlockedRouteIds] = useState<Set<string>>(new Set());

  const {
    openReview: openBookingReview,
    recoverableSession,
    resumeSession,
    dismissRecoverableSession,
    openUnlockPayment, // Get openUnlockPayment from context
    lastUnlockedRouteId, // Get lastUnlockedRouteId from context
  } = useBookingFlowContext();
  const { token } = useAuth();

  useEffect(() => {
    getStatsRailway()
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  // Effect to update unlockedRouteIds when a route is successfully unlocked via the modal
  useEffect(() => {
    if (lastUnlockedRouteId) {
      setUnlockedRouteIds(prev => new Set(prev).add(lastUnlockedRouteId));
    }
  }, [lastUnlockedRouteId]);

  // When user logs in (token becomes available) re-check unlocked status for visible routes
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        if (!token || allRoutes.length === 0) return;
        const resp = await getUnlockedRoutes().catch(() => ({ routes: [] }));
        if (!mounted) return;
        const unlockedSet = new Set<string>(resp?.routes ?? []);
        const newlyUnlocked = allRoutes.filter((r) => unlockedSet.has(r.id)).map((r) => r.id);
        if (newlyUnlocked.length > 0) {
          setUnlockedRouteIds((prev) => {
            const merged = new Set(prev);
            newlyUnlocked.forEach((id) => merged.add(id));
            return merged;
          });
        }
      } catch (e) {
        console.warn("Failed to reconcile unlocked routes after login", e);
      }
    })();
    return () => { mounted = false; };
  }, [token, allRoutes]);

  // Consolidated helper: fetch bulk unlocked IDs and merge into visible route set
  const reconcileUnlockedRoutes = useCallback(async (visibleRoutes: Route[]) => {
    if (!token || visibleRoutes.length === 0) return;
    try {
      const resp = await getUnlockedRoutes().catch(() => ({ routes: [] }));
      const unlockedSet = new Set<string>(resp?.routes ?? []);
      const visibleUnlocked = visibleRoutes.filter((r) => unlockedSet.has(r.id)).map((r) => r.id);
      if (visibleUnlocked.length > 0) {
        setUnlockedRouteIds((prev) => {
          const merged = new Set(prev);
          visibleUnlocked.forEach((id) => merged.add(id));
          return merged;
        });
      }
    } catch (e) {
      console.warn("Failed to reconcile unlocked routes:", e);
    }
  }, [token]);

  const handleUnlockRoute = useCallback(async (route: Route) => {
    if (!origin || !destination || !travelDate) {
      toast({
        title: "Missing Information",
        description: "Origin, Destination, or Travel Date is missing for unlock.",
        variant: "destructive",
      } as Toast);
      return;
    }
    openUnlockPayment({ route, travelDate, originName: origin?.name ?? "", destName: destination?.name ?? "" });
  }, [origin, destination, travelDate, openUnlockPayment]);

  const resolveStationForChatbot = useCallback(
    async (value: string) => {
      const trimmed = (value ?? "").trim();
      if (!trimmed) return null;
      try {
        const resolved = await resolveStationCode(trimmed);
        if (resolved) return resolved;
      } catch (error) {
        console.warn("Station resolve via backend failed", error);
      }

      const normalized = trimmed.toUpperCase();
      const localMatches = searchStationsLocal(trimmed);
      if (localMatches.length === 0) return null;
      return (
        localMatches.find(
          (station) =>
            station.code.toUpperCase() === normalized ||
            (station.name ?? "").toUpperCase() === normalized
        ) ?? localMatches[0]
      );
    },
    []
  );

  const runSearchFromCodes = useCallback(
    async (fromCode: string, toCode: string, date?: string, correlationId?: string) => {
      const trimmedFrom = (fromCode ?? "").trim();
      const trimmedTo = (toCode ?? "").trim();
      if (!trimmedFrom || !trimmedTo) return;

      const [fromStation, toStation] = await Promise.all([
        resolveStationForChatbot(trimmedFrom),
        resolveStationForChatbot(trimmedTo),
      ]);

      if (!fromStation || !toStation) return;

      hasTriggeredChatbotSearch.current = false;
      setOrigin(fromStation);
      setDestination(toStation);
      const resolvedFromCode = fromStation.code.toUpperCase();
      const resolvedToCode = toStation.code.toUpperCase();
      setTravelDate(date || "");
      setSearchParams(
        { from: resolvedFromCode, to: resolvedToCode, ...(date && { date }) },
        { replace: true }
      );
      setPendingChatbotSearch({
        fromCode: resolvedFromCode,
        toCode: resolvedToCode,
        date,
        correlationId,
      });
    },
    [resolveStationForChatbot, setSearchParams]
  );

  const [pendingChatbotSearch, setPendingChatbotSearch] = useState<{
    fromCode: string;
    toCode: string;
    date?: string;
    correlationId?: string;
  } | null>(null);

  // Suggestions emitted by Rail Assistant (chatbot) — shown as chips under the station inputs
  const [chatSuggestions, setChatSuggestions] = useState<Array<{ label: string; type?: string; value?: string; fromName?: string; toName?: string }>>([]);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as { suggestions?: Array<{ label: string; type?: string; value?: string; fromName?: string; toName?: string }> };
      if (!detail?.suggestions || !Array.isArray(detail.suggestions)) return;
      setChatSuggestions(detail.suggestions.slice(0, 6));
    };
    window.addEventListener("rail-assistant-suggestions", handler as EventListener);
    return () => window.removeEventListener("rail-assistant-suggestions", handler as EventListener);
  }, []);

  useEffect(() => {
    const handler = (e: CustomEvent<{ fromCode: string; toCode: string; date?: string; correlationId?: string }>) => {
      runSearchFromCodes(e.detail.fromCode, e.detail.toCode, e.detail.date, e.detail.correlationId);
    };
    window.addEventListener("rail-assistant-search", handler as EventListener);
    return () => window.removeEventListener("rail-assistant-search", handler as EventListener);
  }, [runSearchFromCodes]);

  useEffect(() => {
    const fromCode = searchParams.get("from");
    const toCode = searchParams.get("to");
    const date = searchParams.get("date");
    if (fromCode && toCode && !origin && !destination) {
      runSearchFromCodes(fromCode, toCode, date || undefined);
    }
  }, [searchParams, origin, destination, runSearchFromCodes]);

  useEffect(() => {
    if (hasRestoredLastSearch.current) return;
    const fromCode = searchParams.get("from");
    const toCode = searchParams.get("to");
    if (fromCode && toCode) return;
    const history = getSearchHistory();
    const last = history[0];
    if (!last?.origin?.code || !last?.destination?.code) return;
    hasRestoredLastSearch.current = true;
    runSearchFromCodes(last.origin.code, last.destination.code, last.date);
  }, [runSearchFromCodes, searchParams]);

  const handleSwapStations = () => {
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
  };

  const handleSuggestionClick = (s: { label: string; fromName?: string; toName?: string }) => {
    // Prefer parsed names if available; otherwise use the label and let runSearchFromCodes resolve it
    const from = s.fromName ?? s.label.split(/\s+(?:to|-|→)\s+/i)[0];
    const to = s.toName ?? s.label.split(/\s+(?:to|-|→)\s+/i)[1];
    if (!from || !to) return;
    setChatSuggestions([]);
    runSearchFromCodes(from, to, undefined, undefined);
  };

  const handleSearch = async () => {
    const origCode = origin?.code ?? "";
    const destCode = destination?.code ?? "";
    if (!origin || !destination || !origCode || !destCode) {
      toast({
        title: "Missing Information",
        description: "Please select both origin and destination stations.",
        variant: "destructive",
      } as Toast);
      return;
    }

    setIsSearching(true);
    setIsFromCache(false);
    setSearchError(null);
    const searchStart = performance.now();

    try {
      // If route source is cached and backend unavailable, use local cache directly
      if (routeSource === "cached") {
        const normalizedDate = normalizeDate(travelDate || new Date().toISOString().slice(0, 10));
        const cached = getCachedRoutes(origCode, destCode, normalizedDate);
        if (cached) {
          setIsFromCache(true);
          setJourneyMessage(cached.journey_message ?? "Showing precomputed routes.");
          setBookingTips(cached.booking_tips ?? []);
          const allResults = mapBackendRoutesToRoutes(cached, origCode, destCode);
          setOptimalRoutes(allResults.slice(0, 10));
          setAllRoutes(allResults);
          setViewMode("optimal");
          setDisplayedAlternatives(5);
          setSearchError(null);
          toast({
            title: "Precomputed Routes",
            description: `Showing ${allResults.length} cached route(s) for ${normalizedDate}.`,
          } as Toast);
          setTimeout(() => {
            document.getElementById("results")?.scrollIntoView({ behavior: "smooth" });
          }, 100);
          return;
        } else {
          toast({
            title: "No Cached Routes",
            description: "No precomputed routes available for this search. Try switching to Live mode.",
            variant: "destructive",
          } as Toast);
          return;
        }
      }

      // Live routes from backend
      const data = await searchRoutesApi(origCode, destCode, 2, 50, {
        date: travelDate || new Date().toISOString().slice(0, 10),
        dateWindow: travelDate ? dateWindow : 0,
        sortBy,
        routeSource: routeSource, // Pass route source to backend
        ...(flowCorrelationIdRef.current && { correlationId: flowCorrelationIdRef.current }),
      });

      setJourneyMessage(data.journey_message ?? null);
      setBookingTips(data.booking_tips ?? []);

      const hasRoutes =
        (data.routes?.direct?.length ?? 0) > 0 ||
        (data.routes?.one_transfer?.length ?? 0) > 0 ||
        (data.routes?.two_transfer?.length ?? 0) > 0 ||
        (data.routes?.three_transfer?.length ?? 0) > 0;

      if (data.message && !hasRoutes) {
        setOptimalRoutes([]);
        setAllRoutes([]);
        flowCorrelationIdRef.current = null;
        toast({
          title: "No routes found",
          description: data.journey_message || data.message,
          variant: "destructive",
        } as Toast);
        return;
      }

      if (data.stations && Object.keys(data.stations).length > 0) {
        addStationsToCache(Object.values(data.stations));
      }
      const allResults = mapBackendRoutesToRoutes(data, origCode, destCode);
      setOptimalRoutes(allResults.slice(0, 10));
      setAllRoutes(allResults);

          // Reconcile unlocked routes in bulk (keeps network calls consolidated)
      reconcileUnlockedRoutes(allResults);

      setViewMode("optimal");
      setDisplayedAlternatives(5);
      setSearchError(null);
      // In this code path we've already handled the `cached` early-return above,
      // so here the active source is the live backend — mark not-from-cache.
      setIsFromCache(false);
      if (flowCorrelationIdRef.current) {
        ackFlow(flowCorrelationIdRef.current, "ROUTE_RENDERED").finally(() => {
          flowCorrelationIdRef.current = null;
        });
      }
      logPerf("search_latency", {
        ms: Math.round(performance.now() - searchStart),
        origin: origCode,
        destination: destCode,
        count: allResults.length,
      });

      toast({
        title: "Routes Found!",
        description: `Found ${allResults.slice(0, 10).length} optimal routes and ${allResults.length} total.`,
      } as Toast);

      setTimeout(() => {
        document.getElementById("results")?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    } catch (err) {
      flowCorrelationIdRef.current = null;
      const errMsg = err instanceof Error ? err.message : String(err);
      const isTimeout = /timeout|504|exceeded/i.test(errMsg);
      if (isTimeout) {
        setSearchError("Search took too long. Try again or pick a different route (e.g. fewer transfers).");
        toast({
          title: "Search timed out",
          description: "The server took too long. Try again or try a different From/To pair.",
          variant: "destructive",
        } as Toast);
        return;
      }
      // Backend unavailable: use cached routes only for (origin, dest, date) we generated
      const normalizedDate = normalizeDate(travelDate);
      if (!normalizedDate) {
        toast({
          title: "Select a travel date",
          description: "Cached routes are per date. Pick a date and try again, or start the backend for live search.",
          variant: "destructive",
        } as Toast);
        return;
      }
      const cached = getCachedRoutes(origCode, destCode, normalizedDate);
      if (cached) {
        setIsFromCache(true);
        setJourneyMessage(cached.journey_message ?? "Backend unavailable. Showing cached routes for this date.");
        setBookingTips(cached.booking_tips?.length ? cached.booking_tips : ["Connect backend for live search and fares."]);
        const allResults = mapBackendRoutesToRoutes(cached, origCode, destCode);
        setOptimalRoutes(allResults.slice(0, 10));
        setAllRoutes(allResults);
        setViewMode("optimal");
        setDisplayedAlternatives(5);
        toast({
          title: "Cached Routes",
          description: `Showing ${allResults.length} route(s) for ${normalizedDate}. Start backend for live search.`,
        } as Toast);
        setTimeout(() => {
          document.getElementById("results")?.scrollIntoView({ behavior: "smooth" });
        }, 100);
      } else {
        setSearchError("Backend unavailable and no cached routes for this search. Try Delhi→Mumbai, Kolkata→Delhi, or start the backend for live search.");
        logEvent("search_failed", { origin: origCode, destination: destCode, reason: "no_cache" }, "error");
        toast({
          title: "Backend Unavailable & No Cache",
          description: "Try these cached routes: Delhi→Mumbai • Kolkata→Delhi • Chennai→Bangalore • Pune→Delhi • Lucknow→Mumbai",
          variant: "destructive",
        } as Toast);
      }
    } finally {
      setIsSearching(false);
      // Allow chatbot to trigger subsequent searches again
      hasTriggeredChatbotSearch.current = false;
    }
  };

  const handleSearchRef = useRef(handleSearch);
  handleSearchRef.current = handleSearch;

  useEffect(() => {
    const sortHandler = (e: CustomEvent<{ sortBy: "duration" | "cost" }>) => {
      setSortBy(e.detail.sortBy);
      if (origin && destination) handleSearchRef.current();
    };
    window.addEventListener("rail-assistant-sort", sortHandler as EventListener);
    return () => window.removeEventListener("rail-assistant-sort", sortHandler as EventListener);
  }, [origin, destination]);

  useEffect(() => {
    if (!pendingChatbotSearch || !origin || !destination || hasTriggeredChatbotSearch.current) return;
    if ((origin?.code ?? "").toUpperCase() !== (pendingChatbotSearch.fromCode ?? "").toUpperCase() || (destination?.code ?? "").toUpperCase() !== (pendingChatbotSearch.toCode ?? "").toUpperCase()) return;
    hasTriggeredChatbotSearch.current = true;
    flowCorrelationIdRef.current = pendingChatbotSearch.correlationId ?? null;
    setPendingChatbotSearch(null);
    if (pendingChatbotSearch.date) setTravelDate(pendingChatbotSearch.date);
    handleSearchRef.current();
    setTimeout(() => document.getElementById("results")?.scrollIntoView({ behavior: "smooth" }), 400);
  }, [pendingChatbotSearch, origin, destination]);

  const currentRoutes = viewMode === "optimal" ? optimalRoutes : allRoutes;

  // Recent stations for smart defaults (from search history → Station-like for autocomplete)
  const recentStations = useMemo(() => {
    const history = getSearchHistory();
    const seen = new Set<string>();
    const out: Station[] = [];
    for (const item of history) {
      for (const node of [item.origin, item.destination]) {
        if (!node?.code || seen.has(node.code.toUpperCase())) continue;
        seen.add(node.code.toUpperCase());
        out.push({
          code: node.code,
          name: node.name ?? node.code,
          city: node.name ?? node.code,
          state: "",
          isJunction: (node as any).isJunction ?? false,
        });
      }
      if (out.length >= 8) break;
    }
    return out;
  }, []); // history is loaded from localStorage on each memo call if needed

  const categories = useMemo(() => {
    const uniqueCategories = new Set<string>();
    currentRoutes.forEach((route) => {
      const base = getCategoryBase(route.category);
      if (base) uniqueCategories.add(base);
    });
    return Array.from(uniqueCategories);
  }, [currentRoutes]);

  const filteredRoutes = useMemo(() => {
    let routes = currentRoutes;
    if (selectedCategory) {
      routes = routes.filter((r) => getCategoryBase(r.category) === selectedCategory);
    }
    if (filterTransfers !== null) {
      routes = routes.filter((r) => r.totalTransfers <= filterTransfers);
    }
    if (filterDeparture) {
      const [startH, endH] =
        filterDeparture === "morning"
          ? [0, 12]
          : filterDeparture === "afternoon"
            ? [12, 17]
            : [17, 24];
      routes = routes.filter((r) => {
        const dep = r.segments[0]?.departure ?? "";
        const match = /^(\d{1,2}):(\d{2})/.exec(dep);
        if (!match) return true;
        const hour = parseInt(match[1], 10) + parseInt(match[2], 10) / 60;
        return hour >= startH && hour < endH;
      });
    }
    if (filterMaxDurationHours != null) {
      const maxMins = filterMaxDurationHours * 60;
      routes = routes.filter((r) => r.totalTime <= maxMins);
    }
    if (filterMaxCost != null && filterMaxCost > 0) {
      routes = routes.filter((r) => (r.totalCost ?? 0) <= filterMaxCost);
    }
    return routes;
  }, [currentRoutes, selectedCategory, filterTransfers, filterDeparture, filterMaxDurationHours, filterMaxCost]);

  // Client-side sort by preset (Fastest / Cheapest / Most Reliable)
  const sortedRoutes = useMemo(() => {
    const list = [...filteredRoutes];
    if (sortPreset === "duration") list.sort((a, b) => a.totalTime - b.totalTime);
    else if (sortPreset === "cost") list.sort((a, b) => (a.totalCost || 0) - (b.totalCost || 0));
    else list.sort((a, b) => (b.safetyScore ?? 0) - (a.safetyScore ?? 0));
    return list;
  }, [filteredRoutes, sortPreset]);

  // Paginated routes: show optimal routes (no pagination) or alternative routes (paginated)
  const displayedRoutes = useMemo(() => {
    if (viewMode === "optimal") return sortedRoutes;
    return sortedRoutes.slice(0, displayedAlternatives);
  }, [sortedRoutes, viewMode, displayedAlternatives]);

  // Which route wins each dimension (for badges)
  const routeBadges = useMemo(() => {
    if (displayedRoutes.length === 0) return new Map<string, { fastest?: boolean; cheapest?: boolean; mostReliable?: boolean }>();
    const fastestId = displayedRoutes.reduce((best, r) => (r.totalTime < (best?.totalTime ?? Infinity) ? r : best), displayedRoutes[0]).id;
    const cheapestId = displayedRoutes.reduce((best, r) => ((r.totalCost || Infinity) < (best?.totalCost ?? Infinity) ? r : best), displayedRoutes[0]).id;
    const mostReliableId = displayedRoutes.reduce((best, r) => ((r.safetyScore ?? 0) > (best?.safetyScore ?? 0) ? r : best), displayedRoutes[0]).id;
    const map = new Map<string, { fastest?: boolean; cheapest?: boolean; mostReliable?: boolean }>();
    displayedRoutes.forEach((r) => {
      map.set(r.id, {
        fastest: r.id === fastestId,
        cheapest: r.id === cheapestId,
        mostReliable: r.id === mostReliableId,
      });
    });
    return map;
  }, [displayedRoutes]);

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      {!isBackendOnline && (
        <div className="bg-orange-600 text-white text-center py-2 text-[10px] sm:text-xs font-bold flex items-center justify-center gap-2 animate-in slide-in-from-top-full duration-500">
          <WifiOff className="w-4 h-4" />
          OFFLINE MODE: Using local station database and cached journeys. Some AI features may be limited.
        </div>
      )}

      {recoverableSession && (
        <div className="fixed top-16 left-0 right-0 z-40 container mx-auto px-4 pt-2">
          <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 flex flex-wrap items-center justify-between gap-2 shadow-lg">
            <p className="text-sm font-medium text-foreground">
              Unfinished booking: <strong>{recoverableSession.originName} → {recoverableSession.destName}</strong>
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={dismissRecoverableSession}
                className="text-sm text-muted-foreground hover:text-foreground underline"
              >
                Dismiss
              </button>
              <button
                type="button"
                onClick={resumeSession}
                className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-primary text-primary-foreground hover:opacity-90"
              >
                Resume
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Hero Section - IRCTC-style layout */}
      <section className="relative pt-20 pb-16 overflow-hidden">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-80 h-80 rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 w-80 h-80 rounded-full bg-accent/10 blur-3xl" />
        </div>

        <div className="container mx-auto px-4 relative flex flex-col lg:flex-row gap-8 items-start justify-center">
          {/* IRCTC-style Booking Box - Large prominent form */}
          <div className="w-full max-w-2xl flex-shrink-0">
            {/* Trust Banner */}
            <div className="mb-6 flex flex-wrap items-center justify-center gap-4 bg-emerald-500/5 border border-emerald-500/20 rounded-2xl p-4 animate-in slide-in-from-top-4 duration-500">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-emerald-500" />
                <span className="text-xs font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-widest">Verified Safe Routes</span>
              </div>
              <div className="h-4 w-px bg-emerald-500/20 hidden sm:block" />
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" />
                <span className="text-xs font-bold text-amber-700 dark:text-amber-400 uppercase tracking-widest">Women-Friendly Scores</span>
              </div>
              <div className="h-4 w-px bg-emerald-500/20 hidden sm:block" />
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-red-500" />
                <span className="text-xs font-bold text-red-700 dark:text-red-400 uppercase tracking-widest">Instant SOS Link</span>
              </div>
            </div>

            <div className="bg-white dark:bg-card rounded-2xl border-2 border-border shadow-xl overflow-hidden">
              {/* Dark header like IRCTC */}
              <div className="flex gap-1 px-6 pt-4 pb-2 bg-[#0f172a] dark:bg-[#0c4a6e]">
                <button className="px-4 py-2 text-sm font-semibold text-white border-b-2 border-white">
                  BOOK TICKET
                </button>
                <a href="/sos" className="px-4 py-2 text-sm font-medium text-white/80 hover:text-white transition-colors">
                  SOS
                </a>
              </div>
              <h2 className="text-xl font-bold text-foreground mb-6 px-6 pt-4">BOOK TICKET</h2>
              <div className="relative mb-6 px-6">
                <div className="grid md:grid-cols-2 gap-6">
                  <StationSearch
                    label="From"
                    placeholder="e.g. Delhi, Mumbai, Kolkata"
                    value={origin}
                    onChange={(s) => {
                      setOrigin(s);
                      console.log("Selected origin station:", s);
                      if (s?.code) {
                        predictivePreloadService.preloadPotentialRoutes(s.code);
                        storageService.addRecentSearch(s.code, destination?.code || "");
                      }
                    }}
                    icon="origin"
                    recentStations={recentStations}
                  />
                  <StationSearch
                    label="To"
                    placeholder="e.g. Delhi, Mumbai, Kolkata"
                    value={destination}
                    onChange={(s) => {
                      setDestination(s);
                      if (s?.code && origin?.code) {
                        storageService.addRecentSearch(origin.code, s.code);
                      }
                    }}
                    icon="destination"
                    recentStations={recentStations}
                  />
                </div>
                <button
                  onClick={handleSwapStations}
                  className={cn(
                    "absolute top-12 left-1/2 -translate-x-1/2 z-20 hidden md:flex",
                    "w-11 h-11 rounded-full bg-muted border-2 border-border",
                    "items-center justify-center",
                    "hover:bg-primary hover:border-primary hover:text-white transition-all"
                  )}
                >
                  <ArrowLeftRight className="w-5 h-5" />
                </button>

                {/* Chatbot suggestions (if any) */}
                {chatSuggestions.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="text-xs font-semibold text-muted-foreground mr-2 self-center">Suggestions from Assistant:</span>
                    {chatSuggestions.map((s, i) => (
                      <button
                        key={`${s.label}-${i}`}
                        onClick={() => handleSuggestionClick(s)}
                        className="px-3 py-1.5 rounded-full text-sm font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="mb-6 px-6">
                <div className="mb-4">
                  <RouteSourceToggle
                    value={routeSource}
                    onChange={setRouteSource}
                    showStatus={true}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-muted-foreground mb-2">DD/MM/YYYY *</label>
                  <div className="relative">
                    <CalendarDays className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <input
                      type="date"
                      value={travelDate}
                      onChange={(e) => setTravelDate(e.target.value)}
                      className={cn(
                        "w-full pl-12 pr-4 py-3 rounded-lg",
                        "bg-secondary/50 border-2 border-border",
                        "text-foreground placeholder:text-muted-foreground",
                        "focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none",
                        "text-base font-medium"
                      )}
                    />
                  </div>
                </div>
              </div>

              {(!origin || !destination) && (
                <p className="text-sm text-amber-600 dark:text-amber-400 mb-3 px-6">
                  Select both stations from the list for accurate results.
                </p>
              )}
              <button
                onClick={handleSearch}
                disabled={isSearching}
                className={cn(
                  "w-full py-4 px-6 rounded-lg font-bold text-lg",
                  "bg-orange-500 hover:bg-orange-600 text-white",
                  "hover:opacity-95 active:scale-[0.99] transition-all",
                  "flex items-center justify-center gap-2",
                  "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
              >
                {isSearching ? (
                  <>
                    <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Searching...
                  </>
                ) : (
                  <>
                    <Search className="w-6 h-6" />
                    Search
                  </>
                )}
              </button>

              {/* Quick Stats */}
              <div className="flex flex-wrap items-center justify-center gap-6 pt-4 border-t border-border px-6 pb-4">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <MapPin className="w-4 h-4 text-primary" />
                  <span>{stats?.total_trains != null ? `${stats.total_trains.toLocaleString()}+ Trains` : "11,000+ Trains"}</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <MapPin className="w-4 h-4 text-primary" />
                  <span>{stats?.total_stations != null ? `${stats.total_stations.toLocaleString()}+ Stations` : "8,000+ Stations"}</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Sparkles className="w-4 h-4 text-primary" />
                  <span>Pareto-Optimal</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right side - Railway visual (IRCTC-style) */}
          <div className="hidden lg:flex flex-1 max-w-md items-center justify-center">
            <div className="relative w-full aspect-[4/3] rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 border-2 border-border flex items-center justify-center overflow-hidden">
              <Train className="w-32 h-32 text-primary/30" />
              <div className="absolute bottom-4 left-4 right-4 text-center">
                <p className="text-sm font-medium text-muted-foreground">Indian Railways</p>
                <p className="text-xs text-muted-foreground">11,000+ Trains • 8,000+ Stations</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Results Section */}
      {(optimalRoutes.length > 0 || allRoutes.length > 0 || isSearching || searchError) && (
        <section id="results" className="py-12 bg-secondary/30">
          <div className="container mx-auto px-4">
            {searchError && (
              <div className="mb-6 p-4 rounded-xl bg-destructive/10 border border-destructive/20 flex flex-wrap items-center gap-3">
                <p className="text-sm font-medium text-destructive flex-1">{searchError}</p>
                <button
                  type="button"
                  onClick={() => {
                    setSearchError(null);
                    handleSearch();
                  }}
                  className="shrink-0 px-4 py-2 rounded-lg bg-destructive text-destructive-foreground text-sm font-medium hover:opacity-90"
                >
                  Retry search
                </button>
              </div>
            )}
            {/* Show skeleton during search */}
            {isSearching ? (
              <>
                <div className="mb-8">
                  <div className="h-8 w-48 bg-secondary rounded-lg mb-2 animate-pulse" />
                  <div className="h-4 w-96 bg-secondary rounded animate-pulse" />
                </div>
                <RouteSkeleton count={3} />
              </>
            ) : (
              <>
                    {journeyMessage && (
                  <div className="mb-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
                    <p className="text-sm font-medium text-amber-800 dark:text-amber-200">{journeyMessage}</p>
                  </div>
                )}
                {bookingTips.length > 0 && (
                  <div className="mb-6 p-4 rounded-xl bg-primary/5 border border-primary/20">
                    <p className="text-sm font-semibold text-foreground mb-2">Booking tips for confirmed seats:</p>
                    <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                      {bookingTips.map((tip, i) => (
                        <li key={i}>{tip}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <h2 className="text-2xl font-bold text-foreground">
                        {viewMode === "optimal" ? optimalRoutes.length : allRoutes.length} {viewMode === "optimal" ? "Optimal" : "Possible"} Routes Found
                      </h2>
                      {(isFromCache || routeSource === "cached") && (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 text-xs font-medium border border-amber-500/20">
                          <FileText className="w-3 h-3" />
                          Precomputed Routes
                        </span>
                      )}
                      {routeSource === "live" && !isFromCache && (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 text-xs font-medium border border-blue-500/20">
                          <Database className="w-3 h-3" />
                          Live Routes
                        </span>
                      )}
                    </div>
                    <p className="text-muted-foreground">
                      Showing {optimalRoutes.length} optimal and {allRoutes.length} total routes from {origin?.name} to {destination?.name}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-4">
                    <div className="flex flex-wrap gap-2">
                      <span className="text-sm font-medium text-muted-foreground self-center">Sort:</span>
                      <button
                        onClick={() => setSortPreset("duration")}
                        className={cn(
                          "inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-semibold transition-all",
                          sortPreset === "duration" ? "bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/30" : "bg-secondary text-muted-foreground hover:text-foreground border border-transparent"
                        )}
                      >
                        <Zap className="w-4 h-4" /> Fastest
                      </button>
                      <button
                        onClick={() => setSortPreset("cost")}
                        className={cn(
                          "inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-semibold transition-all",
                          sortPreset === "cost" ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30" : "bg-secondary text-muted-foreground hover:text-foreground border border-transparent"
                        )}
                      >
                        <DollarSign className="w-4 h-4" /> Cheapest
                      </button>
                      <button
                        onClick={() => setSortPreset("reliable")}
                        className={cn(
                          "inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-semibold transition-all",
                          sortPreset === "reliable" ? "bg-blue-500/20 text-blue-700 dark:text-blue-300 border border-blue-500/30" : "bg-secondary text-muted-foreground hover:text-foreground border border-transparent"
                        )}
                      >
                        <Shield className="w-4 h-4" /> Most Reliable
                      </button>
                    </div>
                    <div className="bg-card p-1 rounded-xl border border-border flex">
                      <button
                        onClick={() => setViewMode("optimal")}
                        className={cn(
                          "px-4 py-2 rounded-lg text-sm font-semibold transition-all",
                          viewMode === "optimal"
                            ? "bg-primary text-white shadow-sm"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        Optimal Routes
                      </button>
                      <button
                        onClick={() => setViewMode("all")}
                        className={cn(
                          "px-4 py-2 rounded-lg text-sm font-semibold transition-all",
                          viewMode === "all"
                            ? "bg-primary text-white shadow-sm"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        All Possible
                      </button>
                    </div>

                    <CategoryFilter
                      categories={categories}
                      selected={selectedCategory}
                      onChange={setSelectedCategory}
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-3 mb-6">
                    <span className="text-sm font-medium text-muted-foreground">Transfers:</span>
                    {([null, 0, 1, 2] as const).map((n) => (
                      <button
                        key={n ?? "all"}
                        onClick={() => setFilterTransfers(n)}
                        className={cn(
                          "px-3 py-1.5 rounded-lg text-sm font-medium transition-all",
                          filterTransfers === n ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {n === null ? "All" : n === 2 ? "2+" : String(n)}
                      </button>
                    ))}
                    <span className="text-sm font-medium text-muted-foreground ml-2">Departure:</span>
                    {(["morning", "afternoon", "evening"] as const).map((w) => (
                      <button
                        key={w}
                        onClick={() => setFilterDeparture(filterDeparture === w ? null : w)}
                        className={cn(
                          "px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-all",
                          filterDeparture === w ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {w}
                      </button>
                    ))}
                    {filterTransfers !== null || filterDeparture !== null ? (
                      <button
                        type="button"
                        onClick={() => { setFilterTransfers(null); setFilterDeparture(null); setFilterMaxDurationHours(null); setFilterMaxCost(null); }}
                        className="text-sm text-muted-foreground hover:text-foreground underline"
                      >
                        Reset filters
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className="space-y-4">
                  {displayedRoutes.length > 0 ? (
                    <>
                      {displayedRoutes.map((route, idx) => (
                        <RouteCard
                          key={route.id}
                          route={route}
                          index={idx}
                          isRecommended={viewMode === "optimal" && idx === 0 && !selectedCategory}
                          badges={routeBadges.get(route.id)}
                          isUnlocked={unlockedRouteIds.has(route.id)}
                          onUnlock={handleUnlockRoute}
                          onBook={(r) =>
                            openBookingReview({
                              route: r,
                              travelDate,
                              originName: origin?.name ?? "",
                              destName: destination?.name ?? "",
                            })
                          }
                        />
                      ))}

                      {/* Load More Button */}
                      {viewMode === "all" && displayedAlternatives < sortedRoutes.length && (
                        <div className="flex justify-center pt-4">
                          <button
                            onClick={() => setDisplayedAlternatives((prev) => prev + 5)}
                            className={cn(
                              "px-6 py-3 rounded-lg font-semibold text-sm",
                              "border-2 border-primary text-primary",
                              "hover:bg-primary hover:text-white transition-all"
                            )}
                          >
                            Load More ({sortedRoutes.length - displayedAlternatives} remaining)
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="text-center py-16 bg-card rounded-2xl border-2 border-dashed border-border animate-in fade-in slide-in-from-bottom-4 duration-500">
                      <div className="w-20 h-20 bg-muted rounded-full flex items-center justify-center mx-auto mb-6">
                        <Filter className="w-10 h-10 text-muted-foreground opacity-40" />
                      </div>
                      <h3 className="text-xl font-bold text-foreground mb-2">No routes match your filters</h3>
                      <p className="text-muted-foreground max-w-sm mx-auto mb-8">
                        Try adjusting your filters or enabling flexible search to see more options.
                      </p>
                      <button
                        onClick={() => {
                          setFilterTransfers(null);
                          setFilterDeparture(null);
                          setFilterMaxDurationHours(null);
                          setFilterMaxCost(null);
                          setSelectedCategory(null);
                          setViewMode("all");
                        }}
                        className="px-6 py-3 bg-primary text-primary-foreground rounded-xl font-bold shadow-lg shadow-primary/20 hover:opacity-90 active:scale-95 transition-all"
                      >
                        Reset All Filters
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </section>
      )}

      {/* Features Section */}
      <FeaturesSection />

      <BookingFlowModal />
      <Footer />
    </div>
  );
};

export default Index;
