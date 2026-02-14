import hashlib
import json
import logging
import pickle # Import pickle for serialization
import os # Import os for file path operations
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime, time, timedelta

from backend.config import Config
from backend.models import Segment, Station
from backend.services.cache_service import cache_service
# Removed TimeExpandedGraph and dijkstra_search as they will be replaced by RAPTOR
# from backend.utils.graph_utils import TimeExpandedGraph, dijkstra_search
from backend.utils.time_utils import format_duration

logger = logging.getLogger(__name__)

GRAPH_CACHE_FILE = "route_engine_graph.pkl" # Define cache file name (reload-trigger)


class RouteEngine:
    """
    A high-performance, date-aware route search engine implementing the RAPTOR algorithm (MVP).

    - Supports: direct trips, single-transfer (1 round), overnight/day-offset, operating_days checks.
    - Produces `segments`-based routes (uses `route_segments` preprocessed by vehicle_id).
    - Cache includes metadata (version + etl_timestamp) to detect stale caches.
    """
    CACHE_SCHEMA_VERSION = 2

    def __init__(self):
        self.stations_map: Dict[str, Dict] = {}
        self.segments_map: Dict[str, Dict] = {}
        self.station_name_to_id: Dict[str, str] = {}
        # RAPTOR specific data structures
        self.routes_by_station: Dict[str, List[Dict]] = {}  # Station ID -> List of routes passing through this station
        self.route_segments: Dict[str, List[Dict]] = {}  # Route ID -> List of segments in order
        self._is_loaded = False
        self._cache_meta = {}

    def _save_graph_state(self):
        """Atomically saves graph state + metadata (version + ETL timestamp) to disk."""
        try:
            meta = {"schema_version": self.CACHE_SCHEMA_VERSION, "etl_timestamp": datetime.utcnow().isoformat()}
            payload = {"meta": meta, "state": {
                "stations_map": self.stations_map,
                "segments_map": self.segments_map,
                "station_name_to_id": self.station_name_to_id,
                "routes_by_station": self.routes_by_station,
                "route_segments": self.route_segments,
            }}
            tmp_path = GRAPH_CACHE_FILE + ".tmp"
            with open(tmp_path, "wb") as f:
                pickle.dump(payload, f)
            os.replace(tmp_path, GRAPH_CACHE_FILE)
            self._cache_meta = meta
            logger.info(f"RouteEngine graph state saved to {GRAPH_CACHE_FILE} (schema={meta['schema_version']})")
        except Exception as e:
            logger.error(f"Failed to save graph state: {e}")

    def _load_graph_state(self) -> bool:
        """Loads the graph state and validates schema_version; returns True on successful load."""
        if not os.path.exists(GRAPH_CACHE_FILE):
            return False
        try:
            with open(GRAPH_CACHE_FILE, "rb") as f:
                payload = pickle.load(f)
            meta = payload.get("meta", {})
            if meta.get("schema_version") != self.CACHE_SCHEMA_VERSION:
                logger.warning(f"Graph cache schema mismatch (found={meta.get('schema_version')}, expected={self.CACHE_SCHEMA_VERSION}) — ignoring cache.")
                return False
            state = payload.get("state", {})
            self.stations_map = state.get("stations_map", {})
            self.segments_map = state.get("segments_map", {})
            self.station_name_to_id = state.get("station_name_to_id", {})
            self.routes_by_station = state.get("routes_by_station", {})
            self.route_segments = state.get("route_segments", {})
            self._cache_meta = meta
            self._is_loaded = True
            logger.info(f"RouteEngine graph state loaded from {GRAPH_CACHE_FILE} (schema={meta.get('schema_version')})")
            return True
        except Exception as e:
            logger.error(f"Failed to load graph state: {e}; will rebuild graph.")
            self._is_loaded = False
            return False

    def _get_cache_key(self, source: str, dest: str, date: str, budget: Optional[str]) -> str:
        """Generates a consistent MD5 hash for a search query."""
        query_data = json.dumps({"s": source, "d": dest, "dt": date, "b": budget}, sort_keys=True)
        return f"route:{hashlib.md5(query_data.encode()).hexdigest()}"

    def load_graph_from_db(self, db: Session):
        """
        Loads the transport network from the database into memory, preparing for RAPTOR.
        Attempts to load from cache first; invalidates cache on schema/version mismatch.
        """
        if self._is_loaded:
            logger.info("Graph is already loaded, skipping reload.")
            return

        if self._load_graph_state():
            return

        logger.info("Cache miss or invalid cache — building graph from DB for RAPTOR...")
        stations = db.query(Station).all()
        segments = db.query(Segment).all()

        # Build stations map and name lookup
        for station in stations:
            self.stations_map[station.id] = {"name": station.name, "city": station.city, "lat": station.latitude, "lon": station.longitude}
            self.station_name_to_id[station.name.lower()] = station.id

        # Group segments by vehicle to form ordered routes
        segments_by_vehicle: Dict[Optional[str], List[Segment]] = {}
        for segment in segments:
            segments_by_vehicle.setdefault(segment.vehicle_id, []).append(segment)

        for vehicle_id, vehicle_segments in segments_by_vehicle.items():
            vehicle_segments.sort(key=lambda s: (s.departure_time, getattr(s, "arrival_day_offset", 0)))
            route_id = f"route_{vehicle_id or 'unknown'}_{hashlib.md5((str(vehicle_id) or 'unk').encode()).hexdigest()[:8]}"
            self.route_segments[route_id] = []
            for order_index, segment in enumerate(vehicle_segments):
                seg = {
                    "id": segment.id,
                    "source_station_id": segment.source_station_id,
                    "dest_station_id": segment.dest_station_id,
                    "mode": segment.transport_mode,
                    "departure": segment.departure_time,
                    "arrival": segment.arrival_time,
                    "duration": segment.duration_minutes,
                    "cost": segment.cost,
                    "operating_days": segment.operating_days,
                    "vehicle_id": segment.vehicle_id,
                    "order_index": order_index,
                    "arrival_day_offset": getattr(segment, "arrival_day_offset", 0),
                }
                self.segments_map[segment.id] = seg
                self.route_segments[route_id].append(seg)
                for st_id in (segment.source_station_id, segment.dest_station_id):
                    self.routes_by_station.setdefault(st_id, [])
                    if not any(r["route_id"] == route_id for r in self.routes_by_station[st_id]):
                        self.routes_by_station[st_id].append({"route_id": route_id, "station_order": order_index})

        self._is_loaded = True
        logger.info(f"Graph built: {len(self.stations_map)} stations, {len(self.segments_map)} segments, {len(self.route_segments)} routes.")
        self._save_graph_state()

    # ---------------------- RAPTOR (MVP) implementation ----------------------
    def _time_to_minutes(self, hhmm: str) -> int:
        h, m = map(int, hhmm.split(":"))
        return h * 60 + m

    def _operates_on_date(self, operating_days: str, date_obj) -> bool:
        weekday_index = date_obj.weekday()  # Monday=0
        return len(operating_days) == 7 and operating_days[weekday_index] == "1"

    def _raptor_mvp(self, source_id: str, dest_id: str, travel_date, max_rounds: int = 1):
        """RAPTOR rounds implementation (round-based label setting).

        - Scans only routes passing through stations that were improved in the previous round
        - Honors operating_days and arrival_day_offset
        - Applies transfer window constraints from Config for transfers
        - Returns list with a single best path (list of segment dicts) or empty list
        """
        if source_id == dest_id:
            return []

        INF = 10 ** 9
        best_arrival = {s: INF for s in self.stations_map.keys()}
        prev_segment = {s: None for s in self.stations_map.keys()}

        # seed: source can be boarded at minute 0 (start of travel_date)
        best_arrival[source_id] = 0
        marked_stations = {source_id}

        min_transfer = getattr(Config, "TRANSFER_WINDOW_MIN", 0)
        max_transfer = getattr(Config, "TRANSFER_WINDOW_MAX", 24 * 60)

        for round_idx in range(0, max_rounds + 1):
            if not marked_stations:
                break
            next_marked = set()

            for st in list(marked_stations):
                route_entries = self.routes_by_station.get(st, [])
                # fallback: if routes_by_station is not populated (unit tests), scan all routes
                if not route_entries:
                    route_entries = [{"route_id": rid} for rid in self.route_segments.keys()]

                for route_info in route_entries:
                    route_id = route_info["route_id"]
                    segs = self.route_segments.get(route_id, [])

                    # find indices on route where station `st` appears as a source
                    for i, seg in enumerate(segs):
                        if seg.get("source_station_id") != st:
                            continue

                        # service must operate on travel_date
                        if not self._operates_on_date(seg.get("operating_days", "1111111"), travel_date):
                            continue

                        seg_dep = self._time_to_minutes(seg["departure"])
                        seg_arr = self._time_to_minutes(seg["arrival"]) + seg.get("arrival_day_offset", 0) * 24 * 60

                        # compute wait time between arrival at `st` and this trip's departure
                        wait = seg_dep - best_arrival.get(st, INF)

                        if round_idx == 0:
                            can_board = best_arrival.get(st, INF) <= seg_dep
                        else:
                            can_board = best_arrival.get(st, INF) <= seg_dep and (wait >= min_transfer and wait <= max_transfer)

                        if not can_board:
                            continue

                        # propagate arrival times forward along the route
                        for j in range(i, len(segs)):
                            downstream = segs[j]
                            if not self._operates_on_date(downstream.get("operating_days", "1111111"), travel_date):
                                continue
                            dst = downstream["dest_station_id"]
                            arrival_time = self._time_to_minutes(downstream["arrival"]) + downstream.get("arrival_day_offset", 0) * 24 * 60
                            if arrival_time < best_arrival.get(dst, INF):
                                best_arrival[dst] = arrival_time
                                prev_segment[dst] = downstream["id"]
                                next_marked.add(dst)

            marked_stations = next_marked

        # reconstruct best path for dest_id
        if prev_segment.get(dest_id) is None:
            return []

        path_seg_ids = []
        cur = dest_id
        while cur != source_id and prev_segment.get(cur):
            sid = prev_segment[cur]
            path_seg_ids.insert(0, sid)
            prev = self.segments_map.get(sid)
            if not prev:
                break
            cur = prev["source_station_id"]

        path = [self.segments_map[sid] for sid in path_seg_ids if sid in self.segments_map]
        return [path] if path else []

    def search_routes(self, source: str, destination: str, travel_date: str, budget_category: Optional[str] = None) -> List[Dict]:
        if not self._is_loaded:
            raise RuntimeError("RouteEngine graph is not loaded.")

        cache_key = self._get_cache_key(source, destination, travel_date, budget_category)
        if cache_service.is_available():
            cached = cache_service.get(cache_key)
            if cached is not None:
                return cached

        source_station_id = self.station_name_to_id.get(source.lower())
        dest_station_id = self.station_name_to_id.get(destination.lower())
        if not source_station_id or not dest_station_id:
            return []

        try:
            date_obj = datetime.strptime(travel_date, "%Y-%m-%d").date()
        except ValueError:
            logger.warning("Invalid travel_date format: %s", travel_date)
            return []

        raw_paths = self._raptor_mvp(source_station_id, dest_station_id, date_obj, max_rounds=Config.MAX_TRANSFERS)
        routes = [self._construct_route_from_segment_list(source, destination, p, budget_category) for p in raw_paths]
        routes = [r for r in routes if r]

        # Budget filter
        budget_limits = {"economy": 1000, "standard": 2000, "premium": 5000}
        max_budget = budget_limits.get(budget_category, float("inf"))
        if budget_category and budget_category != "all":
            routes = [r for r in routes if r["total_cost"] <= max_budget]

        routes.sort(key=lambda r: (r["total_duration_minutes"], r["total_cost"]))

        if cache_service.is_available():
            cache_service.set(cache_key, routes)

        return routes

    def _construct_route_from_segment_list(self, source: str, dest: str, segment_list: List[Dict], budget_category: Optional[str]) -> Optional[Dict]:
        if not segment_list:
            return None
        total_cost = sum(s["cost"] for s in segment_list)
        total_duration_minutes = sum(s["duration"] for s in segment_list)
        segments_data = []
        for s in segment_list:
            src = self.stations_map.get(s["source_station_id"], {"name": "unknown"})
            dst = self.stations_map.get(s["dest_station_id"], {"name": "unknown"})
            segments_data.append({
                "mode": s["mode"],
                "from": src["name"],
                "to": dst["name"],
                "departure_time": s["departure"],
                "arrival_time": s["arrival"],
                "duration": format_duration(s["duration"]),
                "cost": s["cost"],
                "details": f"Vehicle ID: {s.get('vehicle_id')}",
            })
        return {
            "id": f"route_{hashlib.md5(json.dumps(segments_data, sort_keys=True).encode()).hexdigest()[:12]}",
            "source": source,
            "destination": dest,
            "segments": segments_data,
            "total_duration": format_duration(total_duration_minutes),
            "total_duration_minutes": total_duration_minutes,
            "total_cost": total_cost,
            "safetyScore": max(1, 100 - (len(segment_list) - 1) * 10 - int(total_duration_minutes / 60 / 24)),
            "budget_category": budget_category or "standard",
            "num_transfers": len(segment_list) - 1,
            "is_unlocked": False,
        }

    def is_loaded(self) -> bool:
        """Returns whether the in-memory graph has been loaded from the database or cache."""
        return bool(self._is_loaded)

route_engine = RouteEngine()
