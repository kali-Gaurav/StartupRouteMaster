import { useState, useEffect, useRef, useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
} from "@/components/ui/command";
import { ArrowLeftRight, Search, MapPin, Loader2, ArrowLeft, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/hooks/use-toast";
import { getRailwayApiUrl } from "@/lib/utils";
import { searchRoutesApi, unlockJourneyDetailsApi } from "@/services/railwayBackApi";
import { RouteCardMini } from "@/components/RouteCardMini";
import { TrainCardSkeleton } from "@/components/TrainCardSkeleton";
import { HighlightedText } from "@/components/HighlightedText"; // [47.2]
import { useVirtualizer } from "@tanstack/react-virtual";
import RouteSorterWorker from "@/workers/route-sorter.worker?worker";
import { useSearchCache } from "@/hooks/useSearchCache";

interface RouteResult {
  journey_id?: string;
  train_no: string;
  train_name: string;
  departure: string;
  arrival: string;
  duration: string;
  fare?: number | null;
  availability?: string | null;
  transfers: number;
  legs?: Leg[];
  is_unlocked?: boolean;
}

interface Leg {
  train_no?: string | number;
  train_name?: string;
  departure?: string;
  arrival?: string;
  fare?: number | null;
  distance?: number;
  time_minutes?: number;
}

interface Station {
  code: string;
  name: string;
  state?: string;
}

interface SearchFormData {
  origin: Station | null;
  destination: Station | null;
  date: string;
  time: string;
}

const MiniAppSearch = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<SearchFormData>({
    origin: null,
    destination: null,
    date: "",
    time: "00:00"
  });

  const [stations, setStations] = useState<Station[]>([]);
  const [filteredStations, setFilteredStations] = useState<Station[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isRevalidating, setIsRevalidating] = useState(false);
  const [openPopover, setOpenPopover] = useState<"origin" | "destination" | null>(null);
  const [stationSearchQuery, setStationSearchQuery] = useState(""); // [47.2]
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>();
  
  const [searchResults, setSearchResults] = useState<RouteResult[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [searchHistory, setSearchHistory] = useState<any[]>([]); // [46.1]
  const [searchError, setSearchError] = useState<string | null>(null);
  const [unlockedJourneys, setUnlockedJourneys] = useState<Record<string, unknown>>({});
  const [isUnlocking, setIsUnlocking] = useState<string | null>(null);

  // Suggestion #7: SWR Cache
  const { getCachedResults, saveToCache } = useSearchCache();

  // Suggestion #5: Persistent worker
  const sorterWorker = useMemo(() => new RouteSorterWorker(), []);

  // Suggestion #1: Virtualization Setup
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: searchResults.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 180,
    overscan: 5,
  });

  useEffect(() => {
    loadStations();
    const today = new Date().toISOString().split('T')[0];
    setFormData(prev => ({ ...prev, date: today }));
    
    // [46.1] Load search history from local storage
    const saved = localStorage.getItem("rm_search_history");
    if (saved) {
      try {
        setSearchHistory(JSON.parse(saved));
      } catch (e) {
        console.error("Failed to parse search history", e);
      }
    }
  }, []);

  const saveToHistory = (origin: Station, destination: Station) => {
    const newEntry = { origin, destination, timestamp: Date.now() };
    const filtered = searchHistory.filter(h => 
      h.origin.code !== origin.code || h.destination.code !== destination.code
    );
    const updated = [newEntry, ...filtered].slice(0, 3);
    setSearchHistory(updated);
    localStorage.setItem("rm_search_history", JSON.stringify(updated));
  };

  const loadStations = async () => {
    try {
      const response = await fetch(getRailwayApiUrl("/stations/search?q=a"));
      if (response.ok) {
        const data = await response.json();
        if (data.stations && data.stations.length > 0) {
          setStations(data.stations);
        }
      }
    } catch (error) {
      console.error("Failed to load stations:", error);
    }
  };
  
  const searchStationsApi = async (query: string) => {
    if (!query || query.length < 2) return;
    try {
      const response = await fetch(getRailwayApiUrl(`/stations/search?q=${encodeURIComponent(query)}`));
      if (response.ok) {
        const data = await response.json();
        setFilteredStations(data.stations || []);
      }
    } catch (error) {
      console.error("Station search error:", error);
    }
  };

  const handleStationSearch = (query: string) => {
    setStationSearchQuery(query); // [47.2]
    if (!query.trim()) {
      setFilteredStations(stations);
      return;
    }
    const filtered = stations.filter(station =>
      station.name.toLowerCase().includes(query.toLowerCase()) ||
      station.code.toLowerCase().includes(query.toLowerCase())
    );
    setFilteredStations(filtered);
    
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      searchStationsApi(query);
    }, 300);
  };

  const handleSelectStation = (station: Station, type: "origin" | "destination") => {
    setFormData(prev => ({ ...prev, [type]: station }));
    setOpenPopover(null);
  };

  const swapStations = () => {
    setFormData(prev => ({
      ...prev,
      origin: prev.destination,
      destination: prev.origin
    }));
  };

  const handleSearch = async (isPrefetch = false) => {
    if (!formData.origin || !formData.destination) return;

    const useDate = formData.date?.trim() || new Date().toISOString().slice(0, 10);
    
    if (isPrefetch && (isSearching || searchResults.length > 0)) return;

    if (!isPrefetch) {
      const cached = getCachedResults(formData.origin.code, formData.destination.code, useDate);
      if (cached) {
        setSearchResults(cached);
        setShowResults(true);
        setIsRevalidating(true);
      } else {
        setIsSearching(true);
        setShowResults(true); // Show results container early for skeleton
        setSearchResults([]);
      }
    }

    setSearchError(null);

    try {
      const data = await searchRoutesApi(
        formData.origin.code,
        formData.destination.code,
        2,
        100,
        { date: useDate, sortBy: "duration" }
      );
      
      const results: RouteResult[] = [];
      if (data.journeys && Array.isArray(data.journeys)) {
        for (const journey of data.journeys) {
          results.push({
            journey_id: journey.journey_id,
            train_no: journey.train_no || "N/A",
            train_name: journey.train_name || "Express Train",
            departure: journey.departure_time || "--:--",
            arrival: journey.arrival_time || "--:--",
            duration: journey.travel_time || "N/A",
            fare: journey.cheapest_fare,
            availability: journey.availability_status,
            transfers: journey.num_transfers,
            is_unlocked: false
          });
        }
      }

      setSearchResults(results);
      saveToCache(formData.origin.code, formData.destination.code, useDate, results);
      saveToHistory(formData.origin, formData.destination); // [46.1]
      
      if (results.length > 30) {
        sorterWorker.onmessage = (e) => setSearchResults(e.data.sorted);
        sorterWorker.postMessage({ routes: results, sortBy: 'departure', order: 'asc' });
      }
    } catch (error) {
      if (!isPrefetch) setSearchError("Search failed.");
    } finally {
      setIsSearching(false);
      setIsRevalidating(false);
    }
  };
  
  const handleUnlock = async (route: RouteResult) => {
    if (!route.journey_id) return;
    setIsUnlocking(route.journey_id);
    try {
      const data = await unlockJourneyDetailsApi(route.journey_id, formData.date) as any;
      setUnlockedJourneys(prev => ({ ...prev, [route.journey_id!]: data }));
      setSearchResults(prev => prev.map(r => 
        r.journey_id === route.journey_id ? { ...r, is_unlocked: true, fare: data.journey.cheapest_fare } : r
      ));
      toast({ title: "Unlocked!" });
    } catch (error) {
      toast({ title: "Unlock Failed", variant: "destructive" });
    } finally {
      setIsUnlocking(null);
    }
  };

  const handleBook = (route: RouteResult) => {
    navigate("/mini-app/booking", { 
      state: { route, origin: formData.origin, destination: formData.destination, date: formData.date } 
    });
  };

  const handleSaveRoute = () => {
    toast({ title: "Saved!" });
  };

  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const minDate = new Date().toISOString().split('T')[0];
  
  // [48.2] IRCTC 120-day booking window
  const maxDateObj = new Date();
  maxDateObj.setDate(maxDateObj.getDate() + 120);
  const maxDate = maxDateObj.toISOString().split('T')[0];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <div className="p-4 bg-white border-b sticky top-0 z-10 shadow-sm">
        <div className="max-w-md mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Button variant="ghost" size="icon" onClick={() => navigate("/mini-app/home")}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-xl font-bold">Search Trains</h1>
          </div>
          {isRevalidating && (
            <div className="flex items-center gap-1.5 text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded-full animate-pulse">
              <RefreshCw className="h-3 w-3 animate-spin" />
              UPDATING
            </div>
          )}
        </div>
      </div>

      <div ref={parentRef} className="flex-1 overflow-auto p-4">
        <div className="max-w-md mx-auto space-y-6">
          {!showResults && (
            <Card className="shadow-sm border-0">
              <CardContent className="p-6 space-y-5">
                <div className="space-y-4">
                  <div>
                    <Label className="text-xs uppercase text-slate-500 font-bold mb-1.5 block">From</Label>
                    <Popover open={openPopover === "origin"} onOpenChange={(open) => setOpenPopover(open ? "origin" : null)}>
                      <PopoverTrigger asChild>
                        <Button variant="outline" className="w-full justify-start text-left h-12 px-4 text-base">
                          <MapPin className="h-5 w-5 mr-3 text-blue-600" />
                          {formData.origin ? formData.origin.name : "Select origin"}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-[calc(100vw-2rem)] max-w-md p-0" align="start">
                        <Command>
                          <CommandInput placeholder="Search station..." className="h-12 text-base" onValueChange={handleStationSearch} />
                          <CommandGroup className="max-h-80 overflow-auto">
                            {filteredStations.map((s) => (
                              <CommandItem key={s.code} value={s.code} onSelect={() => handleSelectStation(s, "origin")} className="h-12 text-base px-4">
                                <HighlightedText text={s.name} highlight={stationSearchQuery} />
                                <span className="ml-2 text-slate-400">(<HighlightedText text={s.code} highlight={stationSearchQuery} />)</span>
                              </CommandItem>
                            ))}
                          </CommandGroup>
                        </Command>
                      </PopoverContent>
                    </Popover>
                  </div>

                  <div className="flex justify-center -my-2 relative z-10">
                    <Button variant="ghost" size="icon" onClick={swapStations} className="h-11 w-11 rounded-full bg-white shadow-md border border-slate-100 hover:bg-slate-50">
                      <ArrowLeftRight className="h-5 w-5 text-blue-600" />
                    </Button>
                  </div>

                  <div>
                    <Label className="text-xs uppercase text-slate-500 font-bold mb-1.5 block">To</Label>
                    <Popover open={openPopover === "destination"} onOpenChange={(open) => setOpenPopover(open ? "destination" : null)}>
                      <PopoverTrigger asChild>
                        <Button variant="outline" className="w-full justify-start text-left h-12 px-4 text-base">
                          <MapPin className="h-5 w-5 mr-3 text-green-600" />
                          {formData.destination ? formData.destination.name : "Select destination"}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-[calc(100vw-2rem)] max-w-md p-0" align="start">
                        <Command>
                          <CommandInput placeholder="Search station..." className="h-12 text-base" onValueChange={handleStationSearch} />
                          <CommandGroup className="max-h-80 overflow-auto">
                            {filteredStations.map((s) => (
                              <CommandItem key={s.code} value={s.code} onSelect={() => handleSelectStation(s, "destination")} className="h-12 text-base px-4">
                                <HighlightedText text={s.name} highlight={stationSearchQuery} />
                                <span className="ml-2 text-slate-400">(<HighlightedText text={s.code} highlight={stationSearchQuery} />)</span>
                              </CommandItem>
                            ))}
                          </CommandGroup>
                        </Command>
                      </PopoverContent>
                    </Popover>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs uppercase text-slate-500 font-bold">Date</Label>
                    <input
                      type="date"
                      value={formData.date}
                      onChange={(e) => setFormData(prev => ({ ...prev, date: e.target.value }))}
                      min={minDate}
                      max={maxDate} // [48.2]
                      className="w-full h-12 px-3 border rounded-md"
                    />
                  </div>
                  <div>
                    <Label className="text-xs uppercase text-slate-500 font-bold">Time</Label>
                    <input
                      type="time"
                      value={formData.time}
                      onChange={(e) => setFormData(prev => ({ ...prev, time: e.target.value }))}
                      className="w-full h-12 px-3 border rounded-md"
                    />
                  </div>
                </div>

                <Button 
                  onClick={() => handleSearch(false)} 
                  onMouseEnter={() => handleSearch(true)}
                  disabled={isSearching} 
                  className="w-full h-12 bg-blue-600 hover:bg-blue-700 font-bold"
                >
                  {isSearching ? <Loader2 className="animate-spin mr-2" /> : <Search className="mr-2 h-4 w-4" />}
                  SEARCH TRAINS
                </Button>
              </CardContent>
            </Card>
          )}

          {/* [46.2] Recent Searches Chips */}
          {!showResults && searchHistory.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs uppercase text-slate-500 font-bold px-1">Recent Searches</h3>
              <div className="flex flex-wrap gap-2">
                {searchHistory.map((h, i) => (
                  <Button
                    key={i}
                    variant="outline"
                    size="sm"
                    className="h-10 px-4 rounded-full bg-white border-slate-200 text-slate-700 hover:bg-blue-50 hover:border-blue-200 transition-colors"
                    onClick={() => {
                      setFormData(prev => ({ ...prev, origin: h.origin, destination: h.destination }));
                      // Trigger search immediately
                      handleSearch(false);
                    }}
                  >
                    <RefreshCw className="h-3 w-3 mr-2 text-slate-400" />
                    <span className="font-bold">{h.origin.code}</span>
                    <ArrowLeftRight className="h-3 w-3 mx-2 text-slate-300" />
                    <span className="font-bold">{h.destination.code}</span>
                  </Button>
                ))}
              </div>
            </div>
          )}

          {showResults && (
            <div className="space-y-4 pb-10">
              <div className="flex items-center justify-between px-1">
                <h2 className="font-bold text-slate-700">{searchResults.length} Routes found</h2>
                <Button variant="ghost" size="sm" onClick={() => setShowResults(false)} className="text-blue-600">Change</Button>
              </div>

              {isSearching && (
                <div className="space-y-4">
                  <TrainCardSkeleton />
                  <TrainCardSkeleton />
                  <TrainCardSkeleton />
                </div>
              )}

              {searchError && <p className="text-red-500 text-center py-10">{searchError}</p>}

              <div
                style={{
                  height: `${virtualizer.getTotalSize()}px`,
                  width: '100%',
                  position: 'relative',
                }}
              >
                {virtualizer.getVirtualItems().map((virtualRow) => {
                  const route = searchResults[virtualRow.index];
                  return (
                    <div
                      key={virtualRow.key}
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: `${virtualRow.size}px`,
                        transform: `translateY(${virtualRow.start}px)`,
                        paddingBottom: '16px'
                      }}
                    >
                      <RouteCardMini
                        route={route as any}
                        originCode={formData.origin?.code || ""}
                        destinationCode={formData.destination?.code || ""}
                        isUnlocked={!!(route.journey_id && unlockedJourneys[route.journey_id])}
                        isProcessing={isUnlocking === route.journey_id}
                        onUnlock={handleUnlock}
                        onBook={handleBook}
                        onSave={handleSaveRoute}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MiniAppSearch;
