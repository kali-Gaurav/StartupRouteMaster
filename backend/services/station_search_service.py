from __future__ import annotations

import sqlite3
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple, Any
from rapidfuzz import process, fuzz

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class StationSuggestion:
    code: str
    name: str
    city: str
    state: Optional[str] = None
    score: float = 100.0
    popularity: int = 0

class StationTrieNode:
    def __init__(self):
        self.children: Dict[str, StationTrieNode] = {}
        self.station_indices: List[int] = [] # Indices in the flat station list

class StationSearchEngine:
    """Ultra-fast In-Memory Station Search Engine with Trie Index."""

    TABLE_NAME = "stops"
    PREFIX_CACHE_TTL = 3600 # 1 hour for local RAM cache
    
    # Common aliases for major stations
    ALIASES = {
        "delhi": "NDLS",
        "bombay": "BCT",
        "mumbai": "BCT",
        "mumbai central": "BCT",
        "banglore": "SBC",
        "bangalore": "SBC",
        "madras": "MAS",
        "calcutta": "HWH",
        "howrah": "HWH",
        "pune": "PA",
        "secunderabad": "SC",
        "hyderabad": "HYB",
        "chennai": "MAS"
    }

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(__file__).resolve().parents[1] / "database" / "transit_graph.db"
        self.lock = Lock()
        
        # In-Memory Storage
        self._stations: List[StationSuggestion] = []
        self._station_map: Dict[str, StationSuggestion] = {} # code -> suggestion
        self._name_to_code: Dict[str, str] = {}
        
        # Trie Indices
        self._code_trie = StationTrieNode()
        self._name_trie = StationTrieNode()
        
        # Local RAM Query Cache (Debounce Cache - Upgrade 4)
        self._query_cache: Dict[str, Tuple[float, List[StationSuggestion]]] = {}
        
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self.lock:
            if self._initialized:
                return
            logger.info("🚀 Loading Station Index into RAM...")
            start_time = time.perf_counter()
            try:
                self._load_from_db()
                self._initialized = True
                duration = (time.perf_counter() - start_time) * 1000
                logger.info(f"✅ Station Index Loaded: {len(self._stations)} stations in {duration:.2f}ms")
            except Exception as e:
                logger.error(f"❌ Failed to load Station Index: {e}", exc_info=True)

    def _load_from_db(self) -> None:
        """Loads all stations from transit_graph.db into RAM-based Trie."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Check if table exists
            res = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.TABLE_NAME}';").fetchone()
            if not res:
                logger.warning(f"Station table {self.TABLE_NAME} not found. Trie will be empty.")
                return

            # Note: We assume popularity can be derived from number of trips or static list
            # For now, major hubs get higher popularity
            cursor = conn.execute(f"SELECT code, name, city, state FROM {self.TABLE_NAME}")
            rows = cursor.fetchall()
            
            for i, row in enumerate(rows):
                code = row['code'].upper()
                name = row['name']
                city = row['city'] or ""
                state = row['state']
                
                # Basic popularity heuristic (Major junctions / capitals)
                pop = 0
                if any(x in name.upper() for x in ['JN', 'CENTRAL', 'TERMINUS', 'CST', 'CANTT']):
                    pop = 10
                
                s = StationSuggestion(code=code, name=name, city=city, state=state, popularity=pop)
                self._stations.append(s)
                self._station_map[code] = s
                self._name_to_code[name.lower()] = code
                
                # Index in Tries
                self._insert_trie(self._code_trie, code.lower(), i)
                
                # Index name words
                name_parts = name.lower().split()
                for part in name_parts:
                    if len(part) >= 2:
                        self._insert_trie(self._name_trie, part, i)
                
                # Also index city
                if city:
                    city_parts = city.lower().split()
                    for part in city_parts:
                        if len(part) >= 2:
                            self._insert_trie(self._name_trie, part, i)

        finally:
            conn.close()

    def _insert_trie(self, root: StationTrieNode, key: str, index: int) -> None:
        node = root
        for char in key:
            if char not in node.children:
                node.children[char] = StationTrieNode()
            node = node.children[char]
            if index not in node.station_indices:
                node.station_indices.append(index)

    def _search_trie(self, root: StationTrieNode, prefix: str) -> List[int]:
        node = root
        for char in prefix.lower():
            if char not in node.children:
                return []
            node = node.children[char]
        return node.station_indices

    def suggest(self, query: str, limit: int = 10) -> List[StationSuggestion]:
        """Ultra-fast station suggestion using In-Memory Tries."""
        self._ensure_initialized()
        
        q = query.strip().lower()
        if not q: return []
        
        # 1. Check Query Cache (Upgrade 4)
        now = time.time()
        if q in self._query_cache:
            ts, results = self._query_cache[q]
            if now - ts < self.PREFIX_CACHE_TTL:
                return results[:limit]

        # 2. Check Aliases (Upgrade 2)
        if q in self.ALIASES:
            alias_code = self.ALIASES[q]
            if alias_code in self._station_map:
                return [self._station_map[alias_code]]

        # 3. Trie Lookups
        # Find matches where code starts with query
        code_matches = self._search_trie(self._code_trie, q)
        
        # Find matches where name words start with query
        name_matches = self._search_trie(self._name_trie, q)
        
        # Combine and Deduplicate
        all_indices = list(set(code_matches + name_matches))
        
        # 4. Result Ranking (Upgrade 3)
        # We score based on:
        # - Exact code match (100 pts)
        # - Code prefix match (80 pts)
        # - Name exact match (90 pts)
        # - Name word prefix match (60 pts)
        # - Popularity (+0 to 10 pts)
        
        candidates: List[Tuple[float, StationSuggestion]] = []
        for idx in all_indices:
            s = self._stations[idx]
            score = 0.0
            
            s_code_low = s.code.lower()
            s_name_low = s.name.lower()
            
            if s_code_low == q: score = 100
            elif s_code_low.startswith(q): score = 80
            elif s_name_low == q: score = 90
            elif any(part.startswith(q) for part in s_name_low.split()): score = 60
            else: score = 40 # Substring or fuzzy
            
            # Add popularity boost
            score += (s.popularity * 0.5)
            
            candidates.append((score, s))
        
        # Sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        results = [c[1] for c in candidates[:limit*2]] # Get a few more for fuzzy fallback
        
        # 5. Fuzzy Fallback if needed (Top 1)
        if len(results) < 3 and len(q) > 3:
            # Use a pre-filtered list of names for speed
            names = [s.name for s in self._stations[:2000]] # Limit fuzzy scope for performance
            fuzzy_results = process.extract(query, names, scorer=fuzz.WRatio, limit=3)
            for name, f_score, _ in fuzzy_results:
                if f_score > 80:
                    code = self._name_to_code.get(name.lower())
                    if code and code not in [r.code for r in results]:
                        results.append(self._station_map[code])

        final_results = results[:limit]
        
        # Update Cache
        self._query_cache[q] = (now, final_results)
        
        return final_results

    def resolve(self, query: str) -> Optional[StationSuggestion]:
        suggestions = self.suggest(query, limit=1)
        return suggestions[0] if suggestions else None

station_search_engine = StationSearchEngine()
