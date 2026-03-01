import { useState, useRef, useEffect, useCallback } from "react";
import { Search, MapPin, Loader2, Landmark, X } from "lucide-react";
import React from "react";
import { cn } from "@/lib/utils";
import { Station as StationType, addStationsToCache, searchStations as searchStationsLocal } from "@/data/stations";
import { searchStationsApi } from "@/services/railwayBackApi";

const STATION_SEARCH_DEBOUNCE_MS = 300;

interface StationSearchProps {
  label: string;
  placeholder: string;
  value: StationType | null;
  onChange: (station: StationType | null) => void;
  icon?: "origin" | "destination";
  /** Shown when input is empty/focused for quick pick (e.g. last origin/destination, recent searches). */
  recentStations?: StationType[];
}

export function StationSearch({
  label,
  placeholder,
  value,
  onChange,
  icon = "origin",
  recentStations = [],
}: StationSearchProps) {
  const [query, setQuery] = useState(value ? `${value?.name ?? ""} (${value?.code ?? ""})` : "");
  const [isOpen, setIsOpen] = useState(false);
  const [results, setResults] = useState<StationType[]>([]);
  const [groupedCity, setGroupedCity] = useState<string | null>(null);
  const [highlightedIdx, setHighlightedIdx] = useState<number>(-1);
  const [isLoading, setIsLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const abortControllerRef = useRef<AbortController | null>(null);
  const resultsCache = useRef<Map<string, StationType[]>>(new Map());

  const performBackendSearch = useCallback(async (searchQuery: string, hadLocalResults: boolean) => {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    setIsLoading(true);
    setSearchError(null);
    try {
      const remoteResults = await searchStationsApi(searchQuery, controller.signal);
      if (controller.signal.aborted) return;
      if (remoteResults.length > 0) {
        const cacheKey = searchQuery.toLowerCase();
        resultsCache.current.set(cacheKey, remoteResults);
        addStationsToCache(remoteResults);
        setResults(remoteResults);
        setIsOpen(true);
        setHighlightedIdx(-1);
        setSearchError(null);
      } else if (!hadLocalResults) {
        setResults([]);
        setIsOpen(false);
        setSearchError("No stations matched that query.");
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }
      if (!hadLocalResults) {
        setResults([]);
        setIsOpen(false);
        setSearchError("Station search failed. Check your connection.");
      }
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightedIdx >= 0 && dropdownRef.current) {
      const highlightedElement = dropdownRef.current.querySelector(`[data-idx="${highlightedIdx}"]`) as HTMLElement;
      if (highlightedElement) {
        highlightedElement.scrollIntoView({
          block: 'nearest',
          behavior: 'smooth'
        });
      }
    }
  }, [highlightedIdx]);

  // Search stations via local DB and backend API
  const searchStations = useCallback((searchQuery: string) => {
    const trimmedQuery = searchQuery.trim();
    if (trimmedQuery.length < 2) {
      abortControllerRef.current?.abort();
      setResults([]);
      setGroupedCity(null);
      setIsOpen(false);
      setSearchError(null);
      setIsLoading(false);
      return;
    }

    const cacheKey = trimmedQuery.toLowerCase();
    const cachedResults = resultsCache.current.get(cacheKey);
    if (cachedResults) {
      setResults(cachedResults);
      setIsOpen(cachedResults.length > 0);
      setHighlightedIdx(-1);
      setIsLoading(false);
      setSearchError(null);
      return;
    }

    setSearchError(null);
    const localResults = searchStationsLocal(trimmedQuery);
    if (localResults.length > 0) {
      resultsCache.current.set(cacheKey, localResults);
      setResults(localResults);
      setIsOpen(true);
      setHighlightedIdx(-1);
    } else {
      setResults([]);
      setIsOpen(false);
    }

    performBackendSearch(trimmedQuery, localResults.length > 0);
  }, [performBackendSearch]);

  // Click outside handler
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Debounced search handler - uses local search (no API call needed)
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    onChange(null);

    // Clear previous debounce timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Local search is fast, but still debounce for better UX (100ms instead of 300ms)
    debounceTimerRef.current = setTimeout(() => {
      searchStations(val);
    }, STATION_SEARCH_DEBOUNCE_MS);
  };

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      abortControllerRef.current?.abort();
    };
  }, []);

  const handleSelect = (station: StationType) => {
    setQuery(`${station.name} (${station.code})`);
    onChange(station);
    setIsOpen(false);
    setHighlightedIdx(-1);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen || results.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIdx(prev => 
          prev < results.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIdx(prev => prev > 0 ? prev - 1 : -1);
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightedIdx >= 0 && highlightedIdx < results.length) {
          handleSelect(results[highlightedIdx]);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        setHighlightedIdx(-1);
        break;
    }
  };

  const handleBlur = () => {
    // Delay to allow click on dropdown items (150ms is enough for button click to register)
    setTimeout(() => {
      setIsOpen(false);
      setHighlightedIdx(-1);
    }, 150);
  };

  // Highlight matched text (supports multi-token fuzzy: each token highlighted)
  function highlightMatch(text: string, query: string) {
    if (!query || !text) return text;
    const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (tokens.length === 0) return text;
    const lower = text.toLowerCase();
    const parts: { start: number; end: number; match: boolean }[] = [];
    let lastEnd = 0;
    for (const token of tokens) {
      const idx = lower.indexOf(token, lastEnd);
      if (idx === -1) continue;
      if (idx > lastEnd) parts.push({ start: lastEnd, end: idx, match: false });
      parts.push({ start: idx, end: idx + token.length, match: true });
      lastEnd = idx + token.length;
    }
    if (lastEnd < text.length) parts.push({ start: lastEnd, end: text.length, match: false });
    if (parts.length === 0) return text;
    return (
      <>
        {parts.map((p, i) =>
          p.match ? (
            <span key={i} className="bg-primary/20 font-bold">{text.slice(p.start, p.end)}</span>
          ) : (
            <span key={i}>{text.slice(p.start, p.end)}</span>
          )
        )}
      </>
    );
  }

  const showRecent = isOpen && query.length < 2 && recentStations.length > 0;

  return (
    <div ref={containerRef} className="relative flex-1">
      <label className="block text-sm font-medium text-muted-foreground mb-2">
        {label}
      </label>
      <div className="relative">
        <div className="absolute left-4 top-1/2 -translate-y-1/2 z-10">
          {icon === "origin" ? (
            <div className="w-3 h-3 rounded-full bg-green-500 ring-4 ring-green-500/20" />
          ) : (
            <MapPin className="w-5 h-5 text-primary" />
          )}
        </div>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          onFocus={() => {
            if (query.length >= 2 && results.length > 0) setIsOpen(true);
            else if (recentStations.length > 0) setIsOpen(true);
          }}
          placeholder={placeholder}
          autoComplete="off"
          className={cn(
            "w-full pl-10 pr-10 py-3 rounded-lg",
            "bg-secondary/50 border-2 border-border",
            "text-foreground placeholder:text-muted-foreground",
            "focus:border-primary focus:ring-4 focus:ring-primary/10",
            "transition-all duration-200 outline-none",
            "text-base font-medium"
          )}
        />
        <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
          {query && (
            <button
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setQuery("");
                setResults([]);
                setIsOpen(false);
                onChange(null);
              }}
              className="text-muted-foreground hover:text-foreground transition-colors"
              title="Clear"
            >
              <X className="w-5 h-5" />
            </button>
          )}
          {isLoading ? (
            <Loader2 className="w-5 h-5 text-muted-foreground animate-spin" />
          ) : (
            <Search className="w-5 h-5 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* Error message display */}
      {searchError && (
        <div className="mt-2 p-2 bg-destructive/10 border border-destructive/20 rounded-lg">
          <p className="text-xs text-destructive">{searchError}</p>
        </div>
      )}

      {/* Recent stations (when input empty or short) */}
      {showRecent && (
        <div ref={dropdownRef} className="absolute z-50 w-full mt-2 bg-card border border-border rounded-xl shadow-card overflow-hidden animate-fade-in">
          <div className="flex items-center gap-2 px-4 py-2 bg-muted/30 border-b border-border/50">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Recent</span>
          </div>
          {recentStations.slice(0, 6).map((station, idx) => (
            <button
              type="button"
              key={`recent-${station?.code ?? ""}-${idx}`}
              onMouseDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleSelect(station);
              }}
              className="w-full px-4 py-3 text-left flex items-center gap-2 hover:bg-primary/10 transition-colors border-b border-border/50 last:border-b-0"
            >
              <MapPin className="w-4 h-4 text-muted-foreground flex-shrink-0" />
              <div className="font-semibold text-foreground text-sm">
                {station?.name ?? ""} <span className="font-mono text-primary">{station?.code ?? ""}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Results dropdown with city grouping and icons */}
      {isOpen && results.length > 0 && !showRecent && (
        <div ref={dropdownRef} className="absolute z-50 w-full mt-2 bg-card border border-border rounded-xl shadow-card overflow-y-auto max-h-80 animate-fade-in custom-scrollbar">
          {groupedCity ? (
            <>
              <div className="flex items-center gap-2 px-4 py-2 bg-muted/30 border-b border-border/50">
                <Landmark className="w-5 h-5 text-primary" />
                <span className="font-bold text-primary">{highlightMatch(groupedCity, query)}</span>
                <span className="ml-2 text-xs text-muted-foreground">(City)</span>
              </div>
              {results.map((station, idx) => (
                <button
                  type="button"
                  key={`${station?.code ?? ""}-${station?.name ?? ""}-${idx}`}
                  data-idx={idx}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleSelect(station);
                  }}
                  className={cn(
                    "w-full px-4 py-3 text-left",
                    "hover:bg-primary/10 transition-colors",
                    "flex flex-col gap-1",
                    idx !== results.length - 1 && "border-b border-border/50",
                    idx === highlightedIdx && "bg-primary/10"
                  )}
                >
                  {/* IRCTC-style: Station Name - Code in one line */}
                  <div className="flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    <div className="font-semibold text-foreground text-base leading-tight">
                      {highlightMatch(station?.name ?? "", query)}
                      {" - "}
                      <span className="font-mono text-sm text-primary">{station?.code ?? ""}</span>
                    </div>
                  </div>
                  {/* IRCTC-style: State in uppercase on second line */}
                  {station?.state && (
                    <div className="text-xs text-muted-foreground uppercase tracking-wide ml-6">
                      {station.state}
                    </div>
                  )}
                </button>
              ))}
            </>
          ) : (
            results.map((station, idx) => (
              <button
                type="button"
                key={`${station?.code ?? ""}-${station?.name ?? ""}-${idx}`}
                data-idx={idx}
                onMouseDown={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleSelect(station);
                }}
                className={cn(
                  "w-full px-4 py-3 text-left",
                  "hover:bg-primary/10 transition-colors",
                  "flex flex-col gap-1",
                  idx !== results.length - 1 && "border-b border-border/50",
                  idx === highlightedIdx && "bg-primary/10"
                )}
              >
                {/* IRCTC-style: Station Name - Code (City) in one line */}
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  <div className="font-semibold text-foreground text-base leading-tight">
                    {highlightMatch(station?.name ?? "", query)}
                    {" - "}
                    <span className="font-mono text-sm text-primary">{station?.code ?? ""}</span>
                    {station?.city && station?.city !== station?.name && (
                      <span className="text-sm font-normal"> ({station.city})</span>
                    )}
                  </div>
                </div>
                {/* IRCTC-style: State in uppercase on second line */}
                {station?.state && (
                  <div className="text-xs text-muted-foreground uppercase tracking-wide ml-6">
                    {station.state}
                  </div>
                )}
              </button>
            ))
          )}
        </div>
      )}

      {/* No results message */}
      {isOpen && query.length >= 2 && results.length === 0 && !isLoading && !searchError && (
        <div className="absolute z-50 w-full mt-2 bg-card border border-border rounded-xl shadow-card p-4 text-center">
          <p className="text-sm text-muted-foreground">
            No stations found for "{query}"
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Try searching by station name, code, or city
          </p>
        </div>
      )}
    </div>
  );
}
