import { useState, useEffect, useRef } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
} from "@/components/ui/command";
import { ArrowLeftRight, Calendar, Clock, Search, MapPin, Loader2, ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/hooks/use-toast";
import { getRailwayApiUrl } from "@/lib/utils";
import { searchRoutesApi, unlockJourneyDetailsApi } from "@/services/railwayBackApi";
import { RouteCardMini } from "@/components/RouteCardMini";

interface RouteResult {
  journey_id?: string;
  train_no: string;
  train_name: string;
  departure: string;
  arrival: string;
  duration: string;
  fare?: number;
  availability?: string;
  transfers: number;
  legs?: any[];
  is_unlocked?: boolean;
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
  const [isLoadingStations, setIsLoadingStations] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [openPopover, setOpenPopover] = useState<"origin" | "destination" | null>(null);
  const searchTimeoutRef = useRef<number | undefined>();
  
  // NEW: Search results state for independent operation
  const [searchResults, setSearchResults] = useState<RouteResult[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [unlockedJourneys, setUnlockedJourneys] = useState<Record<string, any>>({});
  const [isUnlocking, setIsUnlocking] = useState<string | null>(null);

  // Load stations on mount
  useEffect(() => {
    loadStations();
    // Set today's date as default
    const today = new Date().toISOString().split('T')[0];
    setFormData(prev => ({ ...prev, date: today }));
  }, []);

  const loadStations = async () => {
    setIsLoadingStations(true);
    try {
      // Try backend API first
      const response = await fetch(getRailwayApiUrl("/stations/search?q=a"));
      if (response.ok) {
        const data = await response.json();
        // Cache stations for quick filtering
        if (data.stations && data.stations.length > 0) {
          setStations(data.stations);
        }
      }
    } catch (error) {
      console.error("Failed to load stations:", error);
      // Don't show error - stations will be searched on-demand
    } finally {
      setIsLoadingStations(false);
    }
  };
  
  // NEW: Search stations from backend API
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
    if (!query.trim()) {
      setFilteredStations(stations);
      return;
    }
    
    // First filter local cache
    const filtered = stations.filter(station =>
      station.name.toLowerCase().includes(query.toLowerCase()) ||
      station.code.toLowerCase().includes(query.toLowerCase())
    );
    setFilteredStations(filtered);
    
    // Also search API for better results (debounced)
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      searchStationsApi(query);
    }, 300);
  };

  const handleSelectStation = (station: Station, type: "origin" | "destination") => {
    setFormData(prev => ({
      ...prev,
      [type]: station
    }));
    setOpenPopover(null);
  };

  const swapStations = () => {
    setFormData(prev => ({
      ...prev,
      origin: prev.destination,
      destination: prev.origin
    }));
  };

  const handleSearch = async () => {
    // Validation
    if (!formData.origin) {
      toast({
        title: "Origin Required",
        description: "Please select an origin station",
        variant: "destructive"
      });
      return;
    }

    if (!formData.destination) {
      toast({
        title: "Destination Required",
        description: "Please select a destination station",
        variant: "destructive"
      });
      return;
    }

    setIsSearching(true);
    setSearchError(null);
    setSearchResults([]);

    const useDate = formData.date?.trim() || new Date().toISOString().slice(0, 10);
    try {
      const data = await searchRoutesApi(
        formData.origin.code,
        formData.destination.code,
        2,
        40,
        { date: useDate, sortBy: "duration" }
      );
      
      const results: RouteResult[] = [];
      const fmtTime = (m: number | undefined) => (m != null ? `${Math.floor(m / 60)}h ${m % 60}m` : "N/A");

      // NEW: Priority - Try using the unified 'journeys' if they exist (more integrated)
      if (data.journeys && Array.isArray(data.journeys) && data.journeys.length > 0) {
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
      } else {
        // Fallback to legacy routes parsing
        // Direct routes
        for (const route of (data.routes?.direct || [])) {
          results.push({
            train_no: String(route.train_no ?? ""),
            train_name: route.train_name || `Train ${route.train_no}`,
            departure: route.departure || "--:--",
            arrival: route.arrival || "--:--",
            duration: route.time_str ?? fmtTime(route.time_minutes),
            fare: route.fare,
            availability: route.availability,
            transfers: 0
          });
        }

        // One-transfer routes
        for (const route of (data.routes?.one_transfer || [])) {
          results.push({
            train_no: `${route.leg1?.train_no} → ${route.leg2?.train_no}`,
            train_name: `${route.leg1?.train_name || "Train"} + ${route.leg2?.train_name || "Train"}`,
            departure: route.leg1?.departure || "--:--",
            arrival: route.leg2?.arrival || "--:--",
            duration: fmtTime(route.total_time_minutes),
            fare: (route.leg1?.fare || 0) + (route.leg2?.fare || 0) || undefined,
            transfers: 1,
            legs: [route.leg1, route.leg2]
          });
        }
      }

      setSearchResults(results);

      // Two-transfer routes
      for (const route of (data.routes?.two_transfer || [])) {
        const legs = [route.leg1, route.leg2, route.leg3].filter(Boolean);
        results.push({
          train_no: legs.map((l: any) => l?.train_no).join(" → "),
          train_name: legs.map((l: any) => l?.train_name || "Train").join(" + "),
          departure: route.leg1?.departure || "--:--",
          arrival: route.leg3?.arrival || "--:--",
          duration: fmtTime(route.total_time_minutes),
          fare: legs.reduce((s: number, l: any) => s + (l?.fare || 0), 0) || undefined,
          transfers: 2,
          legs
        });
      }

      // Three-transfer routes
      for (const route of (data.routes?.three_transfer || [])) {
        const legs = [route.leg1, route.leg2, route.leg3, route.leg4].filter(Boolean);
        results.push({
          train_no: legs.map((l: any) => l?.train_no).join(" → "),
          train_name: legs.map((l: any) => l?.train_name || "Train").join(" + "),
          departure: route.leg1?.departure || "--:--",
          arrival: route.leg4?.arrival || "--:--",
          duration: fmtTime(route.total_time_minutes),
          fare: legs.reduce((s: number, l: any) => s + (l?.fare || 0), 0) || undefined,
          transfers: 3,
          legs
        });
      }

      setSearchResults(results);
      setShowResults(true);
      
      if (results.length === 0) {
        setSearchError("No routes found. Try different stations or dates.");
      } else {
        toast({
          title: "Routes Found!",
          description: `Found ${results.length} routes`
        });
      }
      
      // ALSO send to Telegram bot if available (progressive enhancement)
      if (window.Telegram?.WebApp) {
        try {
          const searchData = {
            type: "SEARCH",
            origin: formData.origin.code,
            origin_name: formData.origin.name,
            destination: formData.destination.code,
            destination_name: formData.destination.name,
            date: formData.date,
            time: formData.time,
            results_count: results.length,
            timestamp: new Date().toISOString()
          };
          window.Telegram.WebApp.sendData(JSON.stringify(searchData));
        } catch (e) {
          // Ignore bot communication errors - Mini App still works!
          console.log("Bot communication optional:", e);
        }
      }
      
    } catch (error) {
      console.error("Search error:", error);
      const msg = error instanceof Error ? error.message : "Could not connect to server.";
      setSearchError(msg.includes("504") || msg.includes("timeout") ? "Search took too long. Try again." : msg);
      toast({
        title: "Search Failed",
        description: msg.includes("504") ? "Server took too long. Try again." : msg,
        variant: "destructive"
      });
    } finally {
      setIsSearching(false);
    }
  };
  
  // NEW: Unlock journey details
  const handleUnlock = async (route: RouteResult) => {
    if (!route.journey_id) {
      toast({
        title: "Limited View",
        description: "Standard route info only available for this train.",
      });
      return;
    }

    setIsUnlocking(route.journey_id);
    try {
      const data = await unlockJourneyDetailsApi(route.journey_id, formData.date);
      setUnlockedJourneys(prev => ({
        ...prev,
        [route.journey_id!]: data
      }));
      
      // Update the result in searchResults
      setSearchResults(prev => prev.map(r => 
        r.journey_id === route.journey_id ? { ...r, is_unlocked: true, fare: data.journey.cheapest_fare } : r
      ));

      toast({
        title: "Journey Unlocked!",
        description: "Live seat availability and verification complete.",
      });
    } catch (error) {
      console.error("Unlock error:", error);
      toast({
        title: "Unlock Failed",
        description: error instanceof Error ? error.message : "Failed to fetch details",
        variant: "destructive"
      });
    } finally {
      setIsUnlocking(null);
    }
  };

  // NEW: Navigate to booking
  const handleBook = (route: RouteResult) => {
    const journeyDetails = route.journey_id ? unlockedJourneys[route.journey_id] : null;
    
    navigate("/mini-app/booking", { 
      state: { 
        route, 
        journeyDetails,
        origin: formData.origin,
        destination: formData.destination,
        date: formData.date
      } 
    });
  };

  // NEW: Save route to favorites
  const handleSaveRoute = async (route: RouteResult) => {
    const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    if (!userId) {
      toast({
        title: "Login Required",
        description: "Please open via Telegram to save routes",
        variant: "destructive"
      });
      return;
    }
    
    try {
      const response = await fetch(getRailwayApiUrl("/saved-routes"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: userId,
          origin_code: formData.origin?.code,
          origin_name: formData.origin?.name,
          destination_code: formData.destination?.code,
          destination_name: formData.destination?.name,
          preferred_train_no: route.train_no,
          route_name: `${formData.origin?.name} to ${formData.destination?.name}`
        })
      });
      
      if (response.ok) {
        toast({
          title: "Route Saved!",
          description: "Added to your favorites"
        });
      }
    } catch (error) {
      console.error("Save error:", error);
    }
  };

  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const minDate = new Date().toISOString().split('T')[0];
  const maxDate = tomorrow.toISOString().split('T')[0];

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
            <h1 className="text-2xl font-bold text-gray-900">Search Trains</h1>
            <p className="text-sm text-gray-600">Find the best routes for your journey</p>
          </div>
        </div>

        {/* Main Search Card */}
        <Card className="shadow-lg border-0">
          <CardContent className="p-6 space-y-5">
            {/* Origin */}
            <div className="space-y-2">
              <Label className="text-sm font-semibold text-gray-700">From</Label>
              <Popover open={openPopover === "origin"} onOpenChange={(open) => setOpenPopover(open ? "origin" : null)}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className="w-full justify-start text-left h-12 border-2"
                  >
                    <MapPin className="h-4 w-4 mr-2 text-blue-600" />
                    {formData.origin ? (
                      <div>
                        <p className="font-medium">{formData.origin.name}</p>
                        <p className="text-xs text-gray-500">{formData.origin.code}</p>
                      </div>
                    ) : (
                      "Select origin station"
                    )}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-80 p-0" align="start">
                  <Command>
                    <CommandInput
                      placeholder="Search stations..."
                      onValueChange={handleStationSearch}
                    />
                    <CommandEmpty>No station found.</CommandEmpty>
                    <CommandGroup className="max-h-64 overflow-auto">
                      {filteredStations.length === 0 ? (
                        <div className="p-4 text-center text-sm text-gray-500">
                          {isLoadingStations ? "Loading stations..." : "No results found"}
                        </div>
                      ) : (
                        filteredStations.map((station) => (
                          <CommandItem
                            key={station.code}
                            value={station.code}
                            onSelect={() => handleSelectStation(station, "origin")}
                          >
                            <div className="flex-1">
                              <p className="font-medium">{station.name}</p>
                              <p className="text-xs text-gray-500">{station.code}</p>
                            </div>
                          </CommandItem>
                        ))
                      )}
                    </CommandGroup>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            {/* Swap Button */}
            <div className="flex justify-center">
              <Button
                variant="ghost"
                size="icon"
                onClick={swapStations}
                className="rounded-full bg-blue-100 hover:bg-blue-200 text-blue-600"
              >
                <ArrowLeftRight className="h-4 w-4" />
              </Button>
            </div>

            {/* Destination */}
            <div className="space-y-2">
              <Label className="text-sm font-semibold text-gray-700">To</Label>
              <Popover open={openPopover === "destination"} onOpenChange={(open) => setOpenPopover(open ? "destination" : null)}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className="w-full justify-start text-left h-12 border-2"
                  >
                    <MapPin className="h-4 w-4 mr-2 text-green-600" />
                    {formData.destination ? (
                      <div>
                        <p className="font-medium">{formData.destination.name}</p>
                        <p className="text-xs text-gray-500">{formData.destination.code}</p>
                      </div>
                    ) : (
                      "Select destination station"
                    )}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-80 p-0" align="start">
                  <Command>
                    <CommandInput
                      placeholder="Search stations..."
                      onValueChange={handleStationSearch}
                    />
                    <CommandEmpty>No station found.</CommandEmpty>
                    <CommandGroup className="max-h-64 overflow-auto">
                      {filteredStations.length === 0 ? (
                        <div className="p-4 text-center text-sm text-gray-500">
                          {isLoadingStations ? "Loading stations..." : "No results found"}
                        </div>
                      ) : (
                        filteredStations.map((station) => (
                          <CommandItem
                            key={station.code}
                            value={station.code}
                            onSelect={() => handleSelectStation(station, "destination")}
                          >
                            <div className="flex-1">
                              <p className="font-medium">{station.name}</p>
                              <p className="text-xs text-gray-500">{station.code}</p>
                            </div>
                          </CommandItem>
                        ))
                      )}
                    </CommandGroup>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            <Separator />

            {/* Date */}
            <div className="space-y-2">
              <Label className="text-sm font-semibold text-gray-700">Travel Date</Label>
              <div className="relative">
                <Calendar className="absolute left-3 top-3 h-5 w-5 text-gray-400 pointer-events-none" />
                <input
                  type="date"
                  value={formData.date}
                  onChange={(e) => setFormData(prev => ({ ...prev, date: e.target.value }))}
                  min={minDate}
                  max={maxDate}
                  className="w-full pl-10 pr-4 py-2 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Time */}
            <div className="space-y-2">
              <Label className="text-sm font-semibold text-gray-700">Preferred Time (Optional)</Label>
              <div className="relative">
                <Clock className="absolute left-3 top-3 h-5 w-5 text-gray-400 pointer-events-none" />
                <input
                  type="time"
                  value={formData.time}
                  onChange={(e) => setFormData(prev => ({ ...prev, time: e.target.value }))}
                  className="w-full pl-10 pr-4 py-2 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <Separator />

            {/* Search Button */}
            <Button
              onClick={handleSearch}
              disabled={isSearching || !formData.origin || !formData.destination}
              className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white h-12 text-base font-semibold"
            >
              {isSearching ? (
                <>
                  <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="h-5 w-5 mr-2" />
                  Search Trains
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Search Results - Mini App displays directly! */}
        {showResults && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">
                {searchResults.length} Routes Found
              </h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowResults(false)}
                className="text-blue-600"
              >
                New Search
              </Button>
            </div>
            
            {searchError && (
              <Card className="bg-amber-50 border-amber-200">
                <CardContent className="pt-4">
                  <p className="text-sm text-amber-800">{searchError}</p>
                </CardContent>
              </Card>
            )}
            
            {searchResults.map((route, index) => (
              <RouteCardMini
                key={route.journey_id || index}
                route={route}
                originCode={formData.origin?.code || ""}
                destinationCode={formData.destination?.code || ""}
                isUnlocked={!!(route.journey_id && unlockedJourneys[route.journey_id])}
                isProcessing={route.journey_id && isUnlocking === route.journey_id}
                onUnlock={handleUnlock}
                onBook={handleBook}
                onSave={handleSaveRoute}
              />
            ))}
          </div>
        )}
        
        {/* Tips - show when no results */}
        {!showResults && (
          <Card className="bg-blue-50 border-blue-200">
            <CardContent className="pt-4">
              <p className="text-sm font-semibold text-blue-900 mb-2">Pro Tips</p>
              <ul className="text-xs text-blue-800 space-y-1">
                <li>• Search results display directly in the app</li>
                <li>• Tap the heart to save routes to favorites</li>
                <li>• Works offline once stations are loaded</li>
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default MiniAppSearch;