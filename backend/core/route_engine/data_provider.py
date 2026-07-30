"""
RouteMaster Data Provider — GTFS Edition
=========================================
Queries the actual Supabase GTFS schema:
  stops        — stations (code, name, city, state, lat, lon)
  trips        — train instances (trip_id = train number, route_id, service_id)
  stop_times   — arrival/departure at each stop, with stop_sequence
  trains_master — master train list (train_number, train_name, source, destination)

Core operations:
  find_stop(code)               → Stop row
  get_stop_times(stop_id)       → all StopTime rows for a station
  find_direct_trains(from, to)  → trips serving both stops in order
  find_hub_trains(from, hub, to)→ 1-transfer options
  get_schedule(train_no)        → full timetable for a train
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("routemaster.data_provider")

# ---------------------------------------------------------------------------
# Result dataclasses (simple, no SQLAlchemy dependency outside this file)
# ---------------------------------------------------------------------------

@dataclass
class StopInfo:
    id: int
    code: str
    name: str
    city: str
    state: str
    latitude: float = 0.0
    longitude: float = 0.0
    is_major_junction: bool = False

@dataclass
class TrainStopTime:
    """A train's arrival/departure at one station."""
    trip_db_id: int
    trip_id: str        # GTFS trip_id / effectively train number
    route_id: str       # e.g. "12951" — the train number
    stop_id: int
    stop_code: str
    stop_name: str
    stop_sequence: int
    arrival_time: str   # stored as TEXT "HH:MM:SS" or minutes past midnight
    departure_time: str
    arrival_timestamp: Optional[int] = None
    departure_timestamp: Optional[int] = None

@dataclass
class DirectTrain:
    """A train that serves both from_stop and to_stop in sequence."""
    trip_db_id: int
    trip_id: str
    route_id: str       # train number
    train_name: str
    from_stop: StopInfo
    to_stop: StopInfo
    departure_time: str
    arrival_time: str
    from_sequence: int
    to_sequence: int
    duration_minutes: int
    distance_km: float = 0.0
    classes: List[str] = field(default_factory=lambda: ["SL", "3A", "2A", "1A"])
    days_of_run: Optional[Dict] = None

@dataclass
class TransferRoute:
    """A 1-transfer route via a hub station."""
    leg1: DirectTrain
    leg2: DirectTrain
    hub_stop: StopInfo
    layover_minutes: int
    total_duration_minutes: int

# ---------------------------------------------------------------------------
# Core data provider
# ---------------------------------------------------------------------------

class DataProvider:
    """
    Clean GTFS data provider. Uses raw SQL for performance.
    All heavy logic (RAPTOR, ranking) lives in the route engine.
    This class only answers: what trains exist, what stops do they serve.
    """

    def __init__(self, session: Optional[Session] = None):
        self._session = session
        self._stop_cache: Dict[str, Optional[StopInfo]] = {}
        self._train_cache: Dict[str, str] = {}  # route_id → train_name

    @property
    def session(self) -> Session:
        if self._session is None:
            from database.session import SessionTransit
            self._session = SessionTransit()
        return self._session

    # ── Station lookup ─────────────────────────────────────────────────────

    def find_stop(self, station_code: str) -> Optional[StopInfo]:
        """Find a stop by station code (e.g. 'NDLS', 'BCT')."""
        code = station_code.upper().strip()
        if code in self._stop_cache:
            return self._stop_cache[code]

        try:
            row = self.session.execute(
                text("""
                    SELECT id, code, name, city, state, latitude, longitude, is_major_junction
                    FROM stops
                    WHERE UPPER(code) = :code
                    LIMIT 1
                """),
                {"code": code}
            ).fetchone()

            if row:
                stop = StopInfo(
                    id=row[0], code=row[1], name=row[2] or "",
                    city=row[3] or "", state=row[4] or "",
                    latitude=row[5] or 0.0, longitude=row[6] or 0.0,
                    is_major_junction=bool(row[7])
                )
                self._stop_cache[code] = stop
                return stop

            # Fallback: search by name fragment
            row = self.session.execute(
                text("""
                    SELECT id, code, name, city, state, latitude, longitude, is_major_junction
                    FROM stops
                    WHERE UPPER(name) LIKE :q
                    ORDER BY is_major_junction DESC
                    LIMIT 1
                """),
                {"q": f"%{code}%"}
            ).fetchone()

            result = StopInfo(
                id=row[0], code=row[1], name=row[2] or "",
                city=row[3] or "", state=row[4] or "",
                latitude=row[5] or 0.0, longitude=row[6] or 0.0,
                is_major_junction=bool(row[7])
            ) if row else None

            self._stop_cache[code] = result
            return result

        except Exception as e:
            logger.error(f"find_stop({code}) failed: {e}")
            return None

    def get_train_name(self, route_id: str) -> str:
        """Get human-readable train name from trains_master."""
        if route_id in self._train_cache:
            return self._train_cache[route_id]
        try:
            row = self.session.execute(
                text("SELECT train_name FROM trains_master WHERE train_number = :tid LIMIT 1"),
                {"tid": route_id}
            ).fetchone()
            name = row[0] if row else route_id
            self._train_cache[route_id] = name
            return name
        except Exception:
            return route_id

    def _get_train_dest(self, route_id: str) -> str:
        """Get destination station name for a train."""
        try:
            row = self.session.execute(
                text("""
                    SELECT s.name FROM stops s
                    JOIN stop_times st ON st.stop_id = s.id
                    JOIN trips t ON t.id = st.trip_id
                    WHERE t.route_id = :tid
                    ORDER BY st.stop_sequence DESC
                    LIMIT 1
                """),
                {"tid": route_id}
            ).fetchone()
            return row[0] if row else ""
        except Exception:
            return ""

    def get_train_days(self, route_id: str) -> Optional[str]:
        """Get days_of_run string ('1111111') for a train. None = runs every day."""
        try:
            row = self.session.execute(
                text("SELECT days_of_run FROM trains_master WHERE train_number = :tid LIMIT 1"),
                {"tid": route_id}
            ).fetchone()
            return row[0] if row else None
        except Exception:
            return None

    # ── Direct train search ────────────────────────────────────────────────

    def find_direct_trains(
        self,
        from_code: str,
        to_code: str,
        travel_date: Optional[date] = None,
        limit: int = 20
    ) -> List[DirectTrain]:
        """
        Find all trains that serve both from_code and to_code,
        with from_stop appearing before to_stop in sequence.

        Uses GTFS stop_times + trips.
        """
        from_stop = self.find_stop(from_code)
        to_stop = self.find_stop(to_code)

        if not from_stop or not to_stop:
            logger.warning(f"Station not found: {from_code}={from_stop}, {to_code}={to_stop}")
            return []

        try:
            rows = self.session.execute(
                text("""
                    SELECT
                        t.id           AS trip_db_id,
                        t.trip_id      AS trip_id,
                        t.route_id     AS route_id,
                        st_from.stop_sequence  AS from_seq,
                        st_from.departure_time AS dep_time,
                        st_from.departure_timestamp AS dep_ts,
                        st_to.stop_sequence    AS to_seq,
                        st_to.arrival_time     AS arr_time,
                        st_to.arrival_timestamp AS arr_ts
                    FROM trips t
                    JOIN stop_times st_from ON st_from.trip_id = t.id
                    JOIN stop_times st_to   ON st_to.trip_id   = t.id
                    WHERE st_from.stop_id = :from_id
                      AND st_to.stop_id   = :to_id
                      AND st_from.stop_sequence < st_to.stop_sequence
                      AND (t.is_cancelled IS NULL OR t.is_cancelled = false)
                    ORDER BY st_from.departure_timestamp ASC NULLS LAST,
                             st_from.departure_time ASC
                    LIMIT :lim
                """),
                {"from_id": from_stop.id, "to_id": to_stop.id, "lim": limit}
            ).fetchall()

            trains: List[DirectTrain] = []
            for row in rows:
                trip_db_id, trip_id, route_id, from_seq, dep_time, dep_ts, to_seq, arr_time, arr_ts = row
                duration = self._calc_duration(dep_time, arr_time, dep_ts, arr_ts)
                train_name = self.get_train_name(route_id or trip_id)

                trains.append(DirectTrain(
                    trip_db_id=trip_db_id,
                    trip_id=trip_id or str(trip_db_id),
                    route_id=route_id or trip_id or str(trip_db_id),
                    train_name=train_name,
                    from_stop=from_stop,
                    to_stop=to_stop,
                    departure_time=dep_time or "00:00:00",
                    arrival_time=arr_time or "00:00:00",
                    from_sequence=from_seq,
                    to_sequence=to_seq,
                    duration_minutes=duration,
                ))

            logger.info(f"Direct trains {from_code}→{to_code}: {len(trains)} found")
            return trains

        except Exception as e:
            logger.error(f"find_direct_trains({from_code}→{to_code}) failed: {e}")
            return []

    # ── Hub / 1-transfer search ────────────────────────────────────────────

    def find_hub_trains(
        self,
        from_code: str,
        to_code: str,
        hub_codes: Optional[List[str]] = None,
        min_layover_mins: int = 45,
        max_layover_mins: int = 240,
        limit_per_leg: int = 10,
    ) -> List[TransferRoute]:
        """
        Find 1-transfer routes via major hubs.
        Returns pairs of (leg1: DirectTrain, leg2: DirectTrain).
        """
        if hub_codes is None:
            hub_codes = self._get_major_hubs()

        transfers: List[TransferRoute] = []

        for hub_code in hub_codes[:8]:  # limit hub search to top 8
            if hub_code in (from_code, to_code):
                continue

            leg1_trains = self.find_direct_trains(from_code, hub_code, limit=limit_per_leg)
            if not leg1_trains:
                continue

            leg2_trains = self.find_direct_trains(hub_code, to_code, limit=limit_per_leg)
            if not leg2_trains:
                continue

            hub_stop = leg1_trains[0].to_stop

            for leg1 in leg1_trains:
                arr1_mins = self._time_to_minutes(leg1.arrival_time)
                for leg2 in leg2_trains:
                    dep2_mins = self._time_to_minutes(leg2.departure_time)

                    # Handle overnight — add 24h if departure is before arrival
                    if dep2_mins < arr1_mins:
                        dep2_mins += 1440

                    layover = dep2_mins - arr1_mins
                    if min_layover_mins <= layover <= max_layover_mins:
                        total = leg1.duration_minutes + layover + leg2.duration_minutes
                        transfers.append(TransferRoute(
                            leg1=leg1,
                            leg2=leg2,
                            hub_stop=hub_stop,
                            layover_minutes=layover,
                            total_duration_minutes=total,
                        ))

            if len(transfers) >= 5:  # enough 1-transfer options
                break

        # Sort by total duration
        transfers.sort(key=lambda r: r.total_duration_minutes)
        logger.info(f"1-transfer routes {from_code}→{to_code}: {len(transfers)} found")
        return transfers[:10]

    # ── 2-transfer routes ─────────────────────────────────────────────────

    def find_two_transfer_routes(
        self,
        from_code: str,
        to_code: str,
        limit: int = 3,
    ) -> List[tuple]:
        """
        Find 2-transfer routes: from_code → hub1 → hub2 → to_code.
        Returns list of (transfer1: TransferRoute, transfer2: TransferRoute) tuples.
        Uses major hubs as intermediate waypoints.
        """
        hubs = self._get_major_hubs()[:10]
        results = []

        # Get all 1-transfer routes ending at each hub2, starting from from_code
        for hub1 in hubs:
            if hub1 in (from_code, to_code):
                continue
            leg1_trains = self.find_direct_trains(from_code, hub1, limit=5)
            if not leg1_trains:
                continue

            for hub2 in hubs:
                if hub2 in (from_code, to_code, hub1):
                    continue
                leg2_trains = self.find_direct_trains(hub1, hub2, limit=5)
                if not leg2_trains:
                    continue
                leg3_trains = self.find_direct_trains(hub2, to_code, limit=5)
                if not leg3_trains:
                    continue

                hub1_stop = leg1_trains[0].to_stop
                hub2_stop = leg2_trains[0].to_stop

                for leg1 in leg1_trains[:3]:
                    arr1 = self._time_to_minutes(leg1.arrival_time)
                    for leg2 in leg2_trains[:3]:
                        dep2 = self._time_to_minutes(leg2.departure_time)
                        if dep2 < arr1:
                            dep2 += 1440
                        layover1 = dep2 - arr1
                        if not (45 <= layover1 <= 300):
                            continue

                        for leg3 in leg3_trains[:3]:
                            dep3 = self._time_to_minutes(leg3.departure_time)
                            arr2 = self._time_to_minutes(leg2.arrival_time)
                            if dep3 < arr2:
                                dep3 += 1440
                            layover2 = dep3 - arr2
                            if not (45 <= layover2 <= 300):
                                continue

                            total = (leg1.duration_minutes + layover1 +
                                     leg2.duration_minutes + layover2 +
                                     leg3.duration_minutes)

                            tr1 = TransferRoute(
                                leg1=leg1, leg2=leg2,
                                hub_stop=hub1_stop,
                                layover_minutes=layover1,
                                total_duration_minutes=leg1.duration_minutes + layover1 + leg2.duration_minutes,
                            )
                            tr2 = TransferRoute(
                                leg1=leg2, leg2=leg3,
                                hub_stop=hub2_stop,
                                layover_minutes=layover2,
                                total_duration_minutes=leg2.duration_minutes + layover2 + leg3.duration_minutes,
                            )
                            results.append((tr1, tr2, total))

                if len(results) >= limit * 3:
                    break
            if len(results) >= limit * 3:
                break

        results.sort(key=lambda x: x[2])
        logger.info(f"2-transfer routes {from_code}→{to_code}: {len(results)} found")
        return [(r[0], r[1]) for r in results[:limit]]

    # ── Train schedule ─────────────────────────────────────────────────────

    def get_train_schedule(self, train_number: str) -> List[Dict]:
        """Full timetable for one train (all stops in sequence)."""
        try:
            rows = self.session.execute(
                text("""
                    SELECT
                        s.code, s.name, s.city,
                        st.stop_sequence,
                        st.arrival_time,
                        st.departure_time
                    FROM trips t
                    JOIN stop_times st ON st.trip_id = t.id
                    JOIN stops s ON s.id = st.stop_id
                    WHERE t.route_id = :tno OR t.trip_id = :tno
                    ORDER BY st.stop_sequence ASC
                """),
                {"tno": train_number}
            ).fetchall()

            return [
                {
                    "station_code": r[0], "station_name": r[1], "city": r[2],
                    "sequence": r[3], "arrival": r[4], "departure": r[5]
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"get_train_schedule({train_number}) failed: {e}")
            return []

    # ── Station search (for autocomplete) ──────────────────────────────────

    def search_stations(self, query: str, limit: int = 15) -> List[StopInfo]:
        """Fuzzy station search — fallback for when trie index is unavailable."""
        q = query.strip().upper()
        try:
            rows = self.session.execute(
                text("""
                    SELECT id, code, name, city, state, latitude, longitude, is_major_junction
                    FROM stops
                    WHERE UPPER(code) LIKE :q OR UPPER(name) LIKE :q OR UPPER(city) LIKE :q
                    ORDER BY is_major_junction DESC, name ASC
                    LIMIT :lim
                """),
                {"q": f"{q}%", "lim": limit}
            ).fetchall()

            return [
                StopInfo(id=r[0], code=r[1], name=r[2] or "", city=r[3] or "",
                         state=r[4] or "", latitude=r[5] or 0.0, longitude=r[6] or 0.0,
                         is_major_junction=bool(r[7]))
                for r in rows
            ]
        except Exception as e:
            logger.error(f"search_stations({query}) failed: {e}")
            return []

    # ── Helpers ────────────────────────────────────────────────────────────

    def _get_major_hubs(self) -> List[str]:
        """Return high-connectivity stations to use as transfer hubs."""
        try:
            rows = self.session.execute(
                text("""
                    SELECT code FROM stops
                    WHERE is_major_junction = true
                    ORDER BY connectivity_score DESC NULLS LAST
                    LIMIT 20
                """)
            ).fetchall()
            if rows:
                return [r[0] for r in rows]
        except Exception:
            pass
        # Hardcoded fallback — top Indian rail junctions
        return [
            "NDLS", "BCT", "MMCT", "MAS", "HWH", "SC", "NGP",
            "PUNE", "LKO", "CNB", "JP", "ADI", "BPL", "SBC", "PNBE"
        ]

    @staticmethod
    def _time_to_minutes(time_str: str) -> int:
        """Convert 'HH:MM:SS' or 'HH:MM' to minutes past midnight. Handles >24h GTFS times."""
        if not time_str:
            return 0
        try:
            parts = str(time_str).strip().split(":")
            h, m = int(parts[0]), int(parts[1])
            return h * 60 + m
        except Exception:
            return 0

    @staticmethod
    def _calc_duration(
        dep_time: Optional[str],
        arr_time: Optional[str],
        dep_ts: Optional[int],
        arr_ts: Optional[int]
    ) -> int:
        """Calculate journey duration in minutes."""
        # Prefer timestamp if available
        if dep_ts and arr_ts and arr_ts > dep_ts:
            return (arr_ts - dep_ts) // 60

        # Fall back to time strings
        if dep_time and arr_time:
            dep_mins = DataProvider._time_to_minutes(dep_time)
            arr_mins = DataProvider._time_to_minutes(arr_time)
            if arr_mins < dep_mins:
                arr_mins += 1440  # overnight journey
            return max(0, arr_mins - dep_mins)

        return 0

    def close(self):
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None


# Module-level singleton (lazy)
_provider: Optional[DataProvider] = None

def get_data_provider(session: Optional[Session] = None) -> DataProvider:
    """Get or create the data provider."""
    global _provider
    if session:
        return DataProvider(session)
    if _provider is None:
        _provider = DataProvider()
    return _provider
