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
    popularity: float = 0.0

class StationTrieNode:
    def __init__(self):
        self.children: Dict[str, StationTrieNode] = {}
        self.station_indices: List[int] = [] 

class StationSearchEngine:
    """Ultra-fast In-Memory Station Search Engine with Trie Index and Popularity Ranking."""

    TABLE_NAME = "stops"
    PREFIX_CACHE_TTL = 3600 
    
    ALIASES = {
        "delhi": "NDLS", "bombay": "BCT", "mumbai": "BCT", "mumbai central": "BCT",
        "banglore": "SBC", "bangalore": "SBC", "madras": "MAS", "calcutta": "HWH",
        "howrah": "HWH", "pune": "PA", "secunderabad": "SC", "hyderabad": "HYB", "chennai": "MAS"
    }

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(__file__).resolve().parents[1] / "database" / "transit_graph.db"
        self.lock = Lock()
        self._stations: List[StationSuggestion] = []
        self._station_map: Dict[str, StationSuggestion] = {} 
        self._name_to_code: Dict[str, str] = {}
        self._code_trie = StationTrieNode()
        self._name_trie = StationTrieNode()
        self._query_cache: Dict[str, Tuple[float, List[StationSuggestion]]] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized: return
        with self.lock:
            if self._initialized: return
            self._load_from_db()
            self._initialized = True

    def _load_from_db(self) -> None:
        """Loads all stations with connectivity-based popularity ranking (Task 2 upgrade)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            query = f"""
                SELECT s.id, s.code, s.name, s.city, s.state, COALESCE(r.connectivity_score, 0) as connectivity
                FROM {self.TABLE_NAME} s
                LEFT JOIN station_rank r ON s.id = r.station_id
            """
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            
            for i, row in enumerate(rows):
                code = row['code'].upper()
                name = row['name']
                city = row['city'] or ""
                
                pop = row['connectivity']
                if any(x in name.upper() for x in ['JN', 'CENTRAL', 'TERMINUS']): pop += 50
                
                s = StationSuggestion(code=code, name=name, city=city, state=row['state'], popularity=float(pop))
                # Store by internal ID for FTS mapping
                self._station_map[str(row['id'])] = s
                # Store by code for suggestions
                self._station_map[code] = s
                
                self._stations.append(s)
                self._name_to_code[name.lower()] = code
                
                self._insert_trie(self._code_trie, code.lower(), i)
                for part in name.lower().split():
                    if len(part) >= 2: self._insert_trie(self._name_trie, part, i)
        finally:
            conn.close()

    def _insert_trie(self, root: StationTrieNode, key: str, index: int) -> None:
        node = root
        for char in key:
            if char not in node.children: node.children[char] = StationTrieNode()
            node = node.children[char]
            if index not in node.station_indices: node.station_indices.append(index)

    def _search_trie(self, root: StationTrieNode, prefix: str) -> List[int]:
        node = root
        for char in prefix.lower():
            if char not in node.children: return []
            node = node.children[char]
        return node.station_indices

    def suggest(self, query: str, limit: int = 10) -> List[StationSuggestion]:
        self._ensure_initialized()
        q = query.strip().lower()
        if not q: return []
        
        now = time.time()
        # 1. Check RAM Cache
        if q in self._query_cache:
            ts, results = self._query_cache[q]
            if now - ts < self.PREFIX_CACHE_TTL: return results[:limit]

        # 1.5 Direct Code Lookup (Highest Priority)
        if q.upper() in self._station_map:
            return [self._station_map[q.upper()]]

        # 2. Check Aliases (Suggestion #3)
        if q in self.ALIASES:
            alias_code = self.ALIASES[q]
            if alias_code in self._station_map: 
                return [self._station_map[alias_code]]

        # 3. Candidate Selection (FTS5 + Trie Fallback)
        candidates_list: List[StationSuggestion] = []
        try:
            conn = sqlite3.connect(str(self.db_path))
            # FTS rowid matches our stops.id
            cursor = conn.execute("SELECT rowid FROM stops_fts WHERE stops_fts MATCH ?", (f"{q}*",))
            ids = [str(r[0]) for r in cursor.fetchall()]
            for sid in ids:
                if sid in self._station_map: candidates_list.append(self._station_map[sid])
            conn.close()
        except:
            # Fallback to Tries
            idx_list = list(set(self._search_trie(self._code_trie, q) + self._search_trie(self._name_trie, q)))
            for idx in idx_list: candidates_list.append(self._stations[idx])

        # 4. Scoring & Ranking (Suggestion #4)
        scored: List[Tuple[float, StationSuggestion]] = []
        for s in candidates_list:
            score = 0.0
            scode, sname = s.code.lower(), s.name.lower()
            
            if scode == q: score = 2000 # Exact code match is king
            elif sname == q: score = 1800 # Exact name match is second
            elif scode.startswith(q): score = 1200
            elif any(p == q for p in sname.split()): score = 1500 # Exact word match in name
            elif any(p.startswith(q) for p in sname.split()): score = 800
            else: score = 100
            
            # Popularity boost (Connectivity Score) - Weight it more
            score += min(500, s.popularity * 2)
            scored.append((score, s))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Deduplicate and limit
        seen_codes = set()
        final_results = []
        for _, s in scored:
            if s.code not in seen_codes:
                final_results.append(s)
                seen_codes.add(s.code)
            if len(final_results) >= limit: break
            
        self._query_cache[q] = (now, final_results)
        return final_results

    def resolve(self, query: str) -> Optional[StationSuggestion]:
        suggestions = self.suggest(query, limit=1)
        return suggestions[0] if suggestions else None

station_search_engine = StationSearchEngine()
