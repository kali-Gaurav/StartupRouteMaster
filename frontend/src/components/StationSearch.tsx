import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { Search, MapPin, Loader2, Landmark, X } from "lucide-react";
import React from "react";
import { cn } from "@/lib/utils";
import { Station as StationType, addStationsToCache, searchStations as searchStationsLocal } from "@/data/stations";
import { searchStationsApi } from "@/services/railwayBackApi";
import { useRafState } from "@/hooks/useRafState";
import { StationTrie } from "@/lib/trie";

const STATION_SEARCH_DEBOUNCE_MS = 300;

interface StationSearchProps {
  label: string;
  placeholder: string;
  value: StationType | null;
  onChange: (station: StationType | null) => void;
  icon?: "origin" | "destination";
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
  const id = React.useId();
  const [query, setQuery] = useState(value ? `${value?.name ?? ""} (${value?.code ?? ""})` : "");
  const [isOpen, setIsOpen] = useState(false);
  const [results, setResults] = useState<StationType[]>([]);
  const [groupedCity, setGroupedCity] = useState<string | null>(null);
  const [highlightedIdx, setHighlightedIdx] = useRafState<number>(-1);
  const [isLoading, setIsLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const abortControllerRef = useRef<AbortController | null>(null);
  const resultsCache = useRef<Map<string, StationType[]>>(new Map());

  // Suggestion #24: Persistent Trie for instant prefix matching
  const trie = useMemo(() => new StationTrie(), []);

  useEffect(() => {
    // Populate with a base set of stations for instant offline search
    const baseStations = searchStationsLocal("");
    baseStations.forEach(s => {
      trie.insert(s.name, s);
      trie.insert(s.code, s);
    });
  }, [trie]);

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
        // Also update Trie with new results for future instant search
        remoteResults.forEach(s => {
          trie.insert(s.name, s);
          trie.insert(s.code, s);
        });
      } else if (!hadLocalResults) {
        setResults([]);
        setIsOpen(false);
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (!hadLocalResults) setSearchError("Search failed.");
    } finally {
      if (!controller.signal.aborted) setIsLoading(false);
    }
  }, [trie]);

  const searchStations = useCallback((searchQuery: string) => {
    const trimmedQuery = searchQuery.trim();
    if (trimmedQuery.length < 2) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    // Suggestion #24: Instant local lookup
    const trieResults = trie.search(trimmedQuery, 10);
    if (trieResults.length > 0) {
      setResults(trieResults);
      setIsOpen(true);
    }

    const cacheKey = trimmedQuery.toLowerCase();
    const cachedResults = resultsCache.current.get(cacheKey);
    if (cachedResults) {
      setResults(cachedResults);
      setIsOpen(true);
      setIsLoading(false);
      return;
    }

    performBackendSearch(trimmedQuery, trieResults.length > 0);
  }, [performBackendSearch, trie]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    onChange(null);
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => searchStations(val), STATION_SEARCH_DEBOUNCE_MS);
  };

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
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
        setHighlightedIdx(prev => prev < results.length - 1 ? prev + 1 : prev);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIdx(prev => prev > 0 ? prev - 1 : -1);
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightedIdx >= 0 && highlightedIdx < results.length) handleSelect(results[highlightedIdx]);
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        setHighlightedIdx(-1);
        break;
    }
  };

  const handleBlur = () => setTimeout(() => setIsOpen(false), 150);

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
    return parts.length === 0 ? text : (
      <>
        {parts.map((p, i) => p.match ? <span key={i} className="bg-primary/20 font-bold">{text.slice(p.start, p.end)}</span> : <span key={i}>{text.slice(p.start, p.end)}</span>)}
      </>
    );
  }

  const showRecent = isOpen && query.length < 2 && recentStations.length > 0;

  return (
    <div ref={containerRef} className="relative flex-1">
      <label htmlFor={id} className="block text-sm font-medium text-muted-foreground mb-2">{label}</label>
      <div className="relative">
        <div className="absolute left-4 top-1/2 -translate-y-1/2 z-10">
          {icon === "origin" ? <div className="w-3 h-3 rounded-full bg-green-500 ring-4 ring-green-500/20" /> : <MapPin className="w-5 h-5 text-primary" />}
        </div>
        <input
          id={id}
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          onFocus={() => { if (query.length >= 2 || recentStations.length > 0) setIsOpen(true); }}
          placeholder={placeholder}
          autoComplete="off"
          className={cn("w-full pl-10 pr-10 py-3 rounded-lg bg-secondary/50 border-2 border-border focus:border-primary transition-all duration-200 outline-none text-base font-medium")}
        />
        <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
          {query && <button type="button" onMouseDown={(e) => { e.preventDefault(); setQuery(""); setResults([]); setIsOpen(false); onChange(null); }} className="text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>}
          {isLoading ? <Loader2 className="w-5 h-5 text-muted-foreground animate-spin" /> : <Search className="w-5 h-5 text-muted-foreground" />}
        </div>
      </div>
      {searchError && <div className="mt-2 p-2 bg-destructive/10 border border-destructive/20 rounded-lg"><p className="text-xs text-destructive">{searchError}</p></div>}
      {showRecent && (
        <div ref={dropdownRef} className="absolute z-50 w-full mt-2 bg-card border border-border rounded-xl shadow-card overflow-hidden">
          <div className="px-4 py-2 bg-muted/30 border-b"><span className="text-xs font-semibold text-muted-foreground uppercase">Recent</span></div>
          {recentStations.slice(0, 6).map((station, idx) => (
            <button type="button" key={idx} onMouseDown={(e) => { e.preventDefault(); handleSelect(station); }} className="w-full px-4 py-3 text-left flex items-center gap-2 hover:bg-primary/10 transition-colors border-b last:border-b-0">
              <MapPin className="w-4 h-4 text-muted-foreground" />
              <div className="font-semibold text-sm">{station?.name} <span className="font-mono text-primary">{station?.code}</span></div>
            </button>
          ))}
        </div>
      )}
      {isOpen && results.length > 0 && !showRecent && (
        <div ref={dropdownRef} className="absolute z-50 w-full mt-2 bg-card border border-border rounded-xl shadow-card overflow-y-auto max-h-80 custom-scrollbar">
          {results.map((station, idx) => (
            <button
              type="button"
              key={idx}
              data-idx={idx}
              onMouseDown={(e) => { e.preventDefault(); handleSelect(station); }}
              className={cn("w-full px-4 py-3 text-left hover:bg-primary/10 transition-colors flex flex-col gap-1 border-b last:border-b-0", idx === highlightedIdx && "bg-primary/10")}
            >
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <div className="font-semibold text-foreground text-base leading-tight">
                  {highlightMatch(station?.name || "", query)} - <span className="font-mono text-sm text-primary">{station?.code}</span>
                </div>
              </div>
              {station?.state && <div className="text-xs text-muted-foreground uppercase ml-6">{station.state}</div>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
