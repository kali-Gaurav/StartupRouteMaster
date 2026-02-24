from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from threading import Lock, RLock
from typing import Dict, Iterable, List, Optional, Tuple
@dataclass(frozen=True)
class StationSuggestion:
    code: str
    name: str
    city: str
    state: Optional[str] = None


@dataclass
class PrefixCacheEntry:
    results: Tuple[Tuple[str, str, str, Optional[str]], ...]
    timestamp: float = field(default_factory=time.time)


class StationSearchEngine:
    """High-performance autosuggest powered by railway_data.db."""

    TABLE_NAME = "stations_master"
    FTS_TABLE = "station_search"
    PREFIX_CACHE_TTL_SECONDS = 7 * 60
    HOT_PREFIXES = ("d", "m", "n", "b")

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(__file__).resolve().parents[1] / "database" / "railway_data.db"
        self.lock = Lock()
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._prefix_cache: Dict[str, PrefixCacheEntry] = {}
        self.cache_lock = RLock()
        self._prepare_database()
        self._prewarm_prefixes()

    def _prepare_database(self) -> None:
        with self.lock:
            # SQLite tuning pragmas
            self.conn.execute("PRAGMA journal_mode = WAL;")
            self.conn.execute("PRAGMA synchronous = NORMAL;")
            self.conn.execute("PRAGMA temp_store = MEMORY;")
            self.conn.execute("PRAGMA mmap_size = 30000000000;")

            self._ensure_normalized_columns()
            self._create_indexes()
            self._refresh_fts()
            self.conn.commit()

    def _ensure_normalized_columns(self) -> None:
        columns = {row[1] for row in self.conn.execute(f"PRAGMA table_info({self.TABLE_NAME})").fetchall()}
        normalized_columns = ["code_norm", "name_norm", "city_norm"]
        for col in normalized_columns:
            if col not in columns:
                self.conn.execute(f"ALTER TABLE {self.TABLE_NAME} ADD COLUMN {col} TEXT;")
        updates = [
            ("code_norm", "station_code"),
            ("name_norm", "station_name"),
            ("city_norm", "city"),
        ]
        for norm, source in updates:
            self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET {norm} = LOWER({source}) WHERE {norm} IS NULL OR TRIM({norm}) = ''"
            )

    def _create_indexes(self) -> None:
        index_statements = [
            f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_code_norm ON {self.TABLE_NAME}(code_norm);",
            f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_name_norm ON {self.TABLE_NAME}(name_norm);",
            f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_city_norm ON {self.TABLE_NAME}(city_norm);",
        ]
        for stmt in index_statements:
            self.conn.execute(stmt)

    def _refresh_fts(self) -> None:
        self.conn.execute(f"DROP TABLE IF EXISTS {self.FTS_TABLE}")
        self.conn.execute(
            f"""
            CREATE VIRTUAL TABLE {self.FTS_TABLE} USING fts5(
                station_code UNINDEXED,
                station_name,
                city,
                state,
                content='{self.TABLE_NAME}',
                content_rowid='rowid'
            );
            """
        )
        self.conn.execute(
            f"INSERT INTO {self.FTS_TABLE}(rowid, station_code, station_name, city, state) "
            f"SELECT rowid, station_code, station_name, city, state FROM {self.TABLE_NAME};"
        )

    @staticmethod
    def _normalize(query: str) -> str:
        return " ".join(query.strip().split()).lower()

    def _store_prefix_cache(self, normalized: str, raw: Tuple[Tuple[str, str, str, Optional[str]], ...]) -> None:
        entry = PrefixCacheEntry(results=tuple(raw))
        with self.cache_lock:
            self._store_prefix_cache_locked(normalized, entry)

    def _cached_query(self, normalized_query: str, limit: int) -> Tuple[Tuple[str, str, str, Optional[str]], ...]:
        with self.cache_lock:
            self._purge_expired_cache_locked()
            entry = self._prefix_cache.get(normalized_query)
            if entry and self._is_cache_valid(entry):
                return entry.results[:limit]

        filtered = self._reuse_prefix_results(normalized_query, limit)
        if filtered:
            return filtered

        raw = self._db_query(normalized_query, limit)
        self._store_prefix_cache(normalized_query, raw)
        return raw

    def _is_cache_valid(self, entry: PrefixCacheEntry) -> bool:
        return (time.time() - entry.timestamp) < self.PREFIX_CACHE_TTL_SECONDS

    def _purge_expired_cache_locked(self) -> None:
        now = time.time()
        expired = [key for key, entry in self._prefix_cache.items() if (now - entry.timestamp) >= self.PREFIX_CACHE_TTL_SECONDS]
        for key in expired:
            del self._prefix_cache[key]

    def _reuse_prefix_results(self, normalized_query: str, limit: int) -> Optional[Tuple[Tuple[str, str, str, Optional[str]], ...]]:
        with self.cache_lock:
            self._purge_expired_cache_locked()
            for length in range(len(normalized_query) - 1, 0, -1):
                prefix = normalized_query[:length]
                entry = self._prefix_cache.get(prefix)
                if not entry or not self._is_cache_valid(entry):
                    continue
                filtered = self._filter_cached_results(entry.results, normalized_query, limit)
                if filtered:
                    self._store_prefix_cache_locked(normalized_query, PrefixCacheEntry(results=filtered))
                    return filtered
        return None

    def _store_prefix_cache_locked(self, normalized: str, entry: PrefixCacheEntry) -> None:
        max_depth = min(len(normalized), 8)
        for i in range(1, max_depth + 1):
            prefix = normalized[:i]
            self._prefix_cache[prefix] = entry
        self._prefix_cache[normalized] = entry

    def _filter_cached_results(
        self,
        cached_results: Tuple[Tuple[str, str, str, Optional[str]], ...],
        normalized_query: str,
        limit: int,
    ) -> Tuple[Tuple[str, str, str, Optional[str]], ...]:
        tokens = [token for token in normalized_query.split() if token]
        filtered: List[Tuple[str, str, str, Optional[str]]] = []
        normalized_query_lower = normalized_query.lower()
        for code, name, city, state in cached_results:
            if len(filtered) >= limit:
                break
            code_lower = (code or "").lower()
            name_lower = (name or "").lower()
            city_lower = (city or "").lower()
            combined = " ".join((code_lower, name_lower, city_lower))
            if (
                code_lower.startswith(normalized_query_lower)
                or name_lower.startswith(normalized_query_lower)
                or city_lower.startswith(normalized_query_lower)
                or (tokens and all(token in combined for token in tokens))
            ):
                filtered.append((code, name, city, state))
        return tuple(filtered)

    def _prewarm_prefixes(self) -> None:
        for prefix in self.HOT_PREFIXES:
            normalized_prefix = self._normalize(prefix)
            if normalized_prefix:
                self._cached_query(normalized_prefix, limit=20)

    @lru_cache(maxsize=8192)
    def _db_query(self, normalized_query: str, limit: int) -> Tuple[Tuple[str, str, str, Optional[str]], ...]:
        return tuple(self._execute_query(normalized_query, limit))

    def _execute_query(self, normalized_query: str, limit: int) -> Iterable[Tuple[str, str, str, Optional[str]]]:
        if not normalized_query:
            return []

        prefix = f"{normalized_query}%"
        params = {
            "exact_code": normalized_query,
            "code_prefix": prefix,
            "name_prefix": prefix,
            "city_prefix": prefix,
            "limit": limit,
        }

        ranked_query = f"""
        SELECT station_code, station_name, city, state
        FROM (
            SELECT station_code, station_name, city, state,
                   CASE
                       WHEN code_norm = :exact_code THEN 1
                       WHEN code_norm LIKE :code_prefix THEN 2
                       WHEN name_norm LIKE :name_prefix THEN 3
                       WHEN city_norm LIKE :city_prefix THEN 4
                       ELSE 5
                   END AS rank_priority
            FROM {self.TABLE_NAME}
            WHERE code_norm LIKE :code_prefix
               OR name_norm LIKE :name_prefix
               OR city_norm LIKE :city_prefix
        ) AS ranked
        ORDER BY rank_priority, station_name ASC
        LIMIT :limit;
        """

        with self.lock:
            matches = self.conn.execute(ranked_query, params).fetchall()
            result = [(row[0], row[1], row[2], row[3]) for row in matches]

            if len(result) >= limit:
                return result

            fts_tokens = " ".join(f"{token}*" for token in normalized_query.split(" ") if token)
            if not fts_tokens:
                return result

            fts_rows = self.conn.execute(
                f"SELECT rowid FROM {self.FTS_TABLE} WHERE {self.FTS_TABLE} MATCH ? LIMIT ?",
                (fts_tokens, limit * 2),
            ).fetchall()
            if not fts_rows:
                return result

            rowids = [str(row[0]) for row in fts_rows]
            placeholders = ",".join("?" for _ in rowids)
            extra_matches = self.conn.execute(
                f"SELECT station_code, station_name, city, state FROM {self.TABLE_NAME} WHERE rowid IN ({placeholders}) ORDER BY station_name ASC LIMIT ?",
                [*rowids, limit],
            ).fetchall()

            added = {(code, name, city, state) for code, name, city, state in result}
            for code, name, city, state in extra_matches:
                if len(result) >= limit:
                    break
                if (code, name, city, state) in added:
                    continue
                result.append((code, name, city, state))
                added.add((code, name, city, state))
            return result

    def suggest(self, query: str, limit: int = 10) -> List[StationSuggestion]:
        normalized = self._normalize(query)
        if not normalized:
            return []
        raw = self._cached_query(normalized, limit)
        return [StationSuggestion(code=code, name=name, city=city, state=state) for code, name, city, state in raw]

    def resolve(self, query: str) -> Optional[StationSuggestion]:
        suggestions = self.suggest(query, limit=1)
        return suggestions[0] if suggestions else None


station_search_engine = StationSearchEngine()
