import hashlib
import json
import logging
import pickle
import os
import hmac
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import redis
import asyncio # New: Import asyncio

from backend.config import Config
from backend.models import Segment, Station
from backend.services.cache_service import cache_service
from backend.utils.time_utils import format_duration
from backend.etl.sqlite_to_postgres import REDIS_PUB_SUB_CHANNEL # New: Import Pub/Sub channel name
from backend.services.delay_predictor import delay_predictor  # New: Import delay predictor
from backend.services.route_ranking_predictor import route_ranking_predictor  # New: Import route ranking predictor
from backend.services.tatkal_demand_predictor import tatkal_demand_predictor  # New: Import tatkal demand predictor
from backend.services.event_producer import publish_route_searched  # New: Import event publisher
from backend.services.routemaster_client import get_train_reliabilities  # New: fetch train reliabilities from RMA

logger = logging.getLogger(__name__)

# Constants for Redis and HMAC (use values from Config)
REDIS_GRAPH_KEY = Config.ROUTE_GRAPH_REDIS_KEY
HMAC_SECRET_KEY = Config.GRAPH_HMAC_SECRET.encode() if Config.GRAPH_HMAC_SECRET else b"default-secret-key"


class RouteEngine:
    """
    A high-performance, date-aware route search engine implementing the RAPTOR algorithm.
    The graph is stored in a shared RedisJSON store to allow for stateless scaling.
    """
    CACHE_SCHEMA_VERSION = 3  # Incremented due to change in storage mechanism

    def __init__(self):
        self.stations_map: Dict[str, Dict] = {}
        self.segments_map: Dict[str, Dict] = {}
        self.station_name_to_id: Dict[str, str] = {}
        self.routes_by_station: Dict[str, List[Dict]] = {}
        self.route_segments: Dict[str, List[Dict]] = {}
        self.route_stop_index: Dict[str, Dict[str, List[int]]] = {}
        self.route_stop_departures: Dict[str, Dict[str, List[int]]] = {}
        self._is_loaded = False
        self._redis_client = None
        self._pubsub_client = None # New: Redis Pub/Sub client
        self._pubsub_task = None # New: To hold the background task

        # Instrumentation counters used by the benchmark harness. These are
        # lightweight and reset at the start of each search.
        self._last_metrics = {}
        self._metrics_enabled = os.getenv("ROUTEENGINE_ENABLE_METRICS", "1") == "1"
        # Maximum number of Pareto labels to keep per stop to prevent explosion
        # Can be tuned via Config.MAX_LABELS_PER_STOP
        self._max_labels_per_stop = getattr(Config, 'MAX_LABELS_PER_STOP', 20)

        # Start the Pub/Sub listener in the background if Redis is configured
        # and explicitly enabled via environment variable. Tests and some
        # execution contexts may not have Redis available, so default to
        # disabled unless ROUTEENGINE_ENABLE_PUBSUB=1 is set.
        pubsub_enabled = os.getenv("ROUTEENGINE_ENABLE_PUBSUB", "0") == "1"
        if Config.REDIS_URL and pubsub_enabled and not self._pubsub_task:
            self._start_pubsub_listener()

    def _get_redis_client(self):
        """Initializes and returns a Redis client."""
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
                self._redis_client.ping()
                logger.info("Redis client connected successfully.")
            except redis.exceptions.ConnectionError as e:
                logger.error(f"Could not connect to Redis: {e}")
                self._redis_client = None
        return self._redis_client

    def _start_pubsub_listener(self):
        """Starts the Redis Pub/Sub listener in a background task."""
        # Ensure an event loop is available (for FastAPI context)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Create a non-blocking Redis client for Pub/Sub
        pubsub_redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
        self._pubsub_client = pubsub_redis_client.pubsub()
        self._pubsub_client.subscribe(REDIS_PUB_SUB_CHANNEL)
        logger.info(f"Subscribed to Redis Pub/Sub channel: {REDIS_PUB_SUB_CHANNEL}")

        # Run the listener in a background task
        self._pubsub_task = loop.create_task(self._pubsub_listener())

    async def _pubsub_listener(self):
        """Listens for messages on the Redis Pub/Sub channel and invalidates cache."""
        while True:
            try:
                # get_message is blocking for timeout seconds, so it doesn't busy-wait
                message = self._pubsub_client.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    logger.info(f"Received Pub/Sub message: {message['data']}")
                    # Invalidate the in-memory graph
                    self._is_loaded = False
                    logger.info("RouteEngine graph invalidated due to Pub/Sub message.")
                await asyncio.sleep(0.1) # Small delay to prevent busy-waiting
            except redis.exceptions.ConnectionError as e:
                logger.error(f"Redis Pub/Sub connection error: {e}. Attempting to reconnect...", exc_info=True)
                self._pubsub_client = None # Reset client
                # Re-establish connection and resubscribe
                await asyncio.sleep(5) # Wait before retrying
                if Config.REDIS_URL:
                    pubsub_redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
                    self._pubsub_client = pubsub_redis_client.pubsub()
                    self._pubsub_client.subscribe(REDIS_PUB_SUB_CHANNEL)
                    logger.info(f"Re-subscribed to Redis Pub/Sub channel: {REDIS_PUB_SUB_CHANNEL}")
                else:
                    logger.error("Redis URL not configured, cannot reconnect Pub/Sub.")
                    break # Exit listener if Redis URL not available
            except Exception as e:
                logger.error(f"Error in Redis Pub/Sub listener: {e}", exc_info=True)
                await asyncio.sleep(1) # Wait before continuing


    def _save_graph_state(self):
        """Serializes and saves the graph state to RedisJSON with HMAC signing."""
        client = self._get_redis_client()
        if not client:
            logger.error("Cannot save graph state: Redis client is not available.")
            return

        try:
            state_data = {
                "stations_map": self.stations_map,
                "segments_map": self.segments_map,
                "station_name_to_id": self.station_name_to_id,
                "routes_by_station": self.routes_by_station,
                "route_segments": self.route_segments,
            }
            serialized_data = json.dumps(state_data).encode('utf-8')
            signature = hmac.new(HMAC_SECRET_KEY, serialized_data, hashlib.sha256).hexdigest()

            payload = {
                "signature": signature,
                "data": serialized_data.decode('utf-8'),
                "schema_version": self.CACHE_SCHEMA_VERSION,
                "etl_timestamp": datetime.utcnow().isoformat()
            }
            
            client.json().set(REDIS_GRAPH_KEY, '$', payload)
            logger.info(f"RouteEngine graph state saved to Redis at key '{REDIS_GRAPH_KEY}'.")
        except Exception as e:
            logger.error(f"Failed to save graph state to Redis: {e}")

    def _load_graph_state(self) -> bool:
        """Loads the graph state from RedisJSON and verifies the HMAC signature."""
        client = self._get_redis_client()
        if not client:
            logger.error("Cannot load graph state: Redis client is not available.")
            return False

        try:
            payload = client.json().get(REDIS_GRAPH_KEY)
            
            if not payload:
                logger.info("No graph state found in Redis.")
                return False

            # The payload from redis-py json().get() is a list containing the dict
            payload = payload[0]

            if payload.get("schema_version") != self.CACHE_SCHEMA_VERSION:
                logger.warning("Graph cache schema mismatch, ignoring Redis cache.")
                return False

            signature = payload.get("signature")
            serialized_data = payload.get("data").encode('utf-8')
            
            expected_signature = hmac.new(HMAC_SECRET_KEY, serialized_data, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected_signature):
                logger.error("HMAC signature verification failed. Graph data may be tampered with.")
                return False

            state = json.loads(serialized_data)
            self.stations_map = state.get("stations_map", {})
            self.segments_map = state.get("segments_map", {})
            self.station_name_to_id = state.get("station_name_to_id", {})
            self.routes_by_station = state.get("routes_by_station", {})
            self.route_segments = state.get("route_segments", {})
            
            self._build_route_indices()
            self._is_loaded = True
            logger.info("RouteEngine graph state loaded successfully from Redis.")
            return True
        except Exception as e:
            logger.error(f"Failed to load graph state from Redis: {e}")
            return False

    def load_graph_from_db(self, db: Session):
        if self._is_loaded:
            logger.info("Graph is already loaded.")
            return

        if self._load_graph_state():
            return

        logger.info("Building graph from DB as it was not found in Redis or was invalid.")
        # ... [rest of the DB loading logic remains the same]
        stations = db.query(Station).all()
        segments = db.query(Segment).all()

        for station in stations:
            self.stations_map[station.id] = {"name": station.name, "city": station.city, "lat": station.latitude, "lon": station.longitude}
            self.station_name_to_id[station.name.lower()] = station.id

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
        
        self._build_route_indices()
        self._is_loaded = True
        logger.info(f"Graph built from DB with {len(self.stations_map)} stations and {len(self.route_segments)} routes.")
        self._save_graph_state()

    def _time_to_minutes(self, hhmm: str) -> int:
        h, m = map(int, hhmm.split(":"))
        return h * 60 + m

    def _build_route_indices(self):
        """Precompute per-route station -> segment positions and departure minutes for binary-search boarding.
        Also (re)builds `routes_by_station` from `route_segments` when necessary so tests that set
        `route_segments` directly behave correctly.
        """
        import bisect
        self.route_stop_index = {}
        self.route_stop_departures = {}
        # rebuild routes_by_station from route_segments if it's empty
        if not self.routes_by_station:
            self.routes_by_station = {}
            for route_id, segs in self.route_segments.items():
                for order_index, seg in enumerate(segs):
                    for st_id in (seg["source_station_id"], seg["dest_station_id"]):
                        self.routes_by_station.setdefault(st_id, [])
                        if not any(r["route_id"] == route_id for r in self.routes_by_station[st_id]):
                            self.routes_by_station[st_id].append({"route_id": route_id, "station_order": order_index})

        for route_id, segs in self.route_segments.items():
            pos_map = {}
            dep_map = {}
            for idx, seg in enumerate(segs):
                # Account for day offsets on departures. Some segments encode
                # departures after midnight via 'departure_day_offset' or
                # by reusing 'arrival_day_offset'. Normalize departure minutes
                # to an absolute minute count so binary-search boarding works
                # correctly for overnight services.
                dep_offset = seg.get("departure_day_offset", seg.get("arrival_day_offset", 0))
                dep_min = self._time_to_minutes(seg["departure"]) + dep_offset * 24 * 60
                src = seg["source_station_id"]
                pos_map.setdefault(src, []).append(idx)
                dep_map.setdefault(src, []).append(dep_min)
            self.route_stop_index[route_id] = pos_map
            self.route_stop_departures[route_id] = dep_map

        # Ensure departures arrays are sorted (important if segments were not in
        # strictly increasing departure order due to day offsets); this keeps
        # binary searches deterministic.
        for route_id, dep_map in self.route_stop_departures.items():
            for st, deps in dep_map.items():
                deps.sort()

    def _raptor_mvp(self, source_id: str, dest_id: str, travel_date, max_rounds: int = 1):
        """RAPTOR rounds implementation with Pareto-optimality for time and cost."""
        # instrumentation
        try:
            from backend.utils.metrics import (
                RMA_RAPTOR_RUNTIME_SECONDS,
                RMA_RAPTOR_ROUNDS_TOTAL,
                RMA_RAPTOR_LABELS_GENERATED_TOTAL,
                RMA_RAPTOR_TRANSFER_EXPANSIONS_TOTAL,
                RMA_CACHE_HIT_TOTAL,
                RMA_CACHE_MISS_TOTAL,
                ROUTING_LABELS_GENERATED_TOTAL,
                ROUTING_ROUNDS_PROCESSED_TOTAL,
                RMA_ROUTING_RELIABILITY_APPLIED_TOTAL,
                RMA_ROUTE_AVG_RELIABILITY,
                RMA_ROUTE_SCORE_DELTA,
            )
        except Exception:
            RMA_RAPTOR_RUNTIME_SECONDS = RMA_RAPTOR_ROUNDS_TOTAL = RMA_RAPTOR_LABELS_GENERATED_TOTAL = RMA_RAPTOR_TRANSFER_EXPANSIONS_TOTAL = RMA_CACHE_HIT_TOTAL = RMA_CACHE_MISS_TOTAL = ROUTING_LABELS_GENERATED_TOTAL = ROUTING_ROUNDS_PROCESSED_TOTAL = RMA_ROUTING_RELIABILITY_APPLIED_TOTAL = RMA_ROUTE_AVG_RELIABILITY = RMA_ROUTE_SCORE_DELTA = None

        if source_id == dest_id:
            return []

        # ensure indices and routes_by_station are up-to-date (helps unit tests that set route_segments directly)
        if not self.route_stop_index or not self.route_stop_departures or not self.routes_by_station:
            self._build_route_indices()

        INF = float('inf')
        # Reset per-search metrics
        if self._metrics_enabled:
            self._last_metrics = {
                "labels_generated": 0,
                "max_labels_per_stop": 0,
                "transfer_expansions": 0,
                "binary_search_calls": 0,
                "rounds_processed": 0,
            }
        # start timer
        import time
        start_ts = time.time()
        best_labels = {s: [] for s in self.stations_map.keys()}
        prev_segment = {s: {} for s in self.stations_map.keys()}

        best_labels[source_id] = [(0, 0)]
        marked_stations = {source_id}

        min_transfer = getattr(Config, "TRANSFER_WINDOW_MIN", 0)
        max_transfer = getattr(Config, "TRANSFER_WINDOW_MAX", 24 * 60)

        import os
        debug = os.getenv('ROUTEENGINE_DEBUG', '0') == '1'

        for round_idx in range(max_rounds + 1):
            if not marked_stations:
                break
            
            if debug:
                print(f"[RAPTOR DEBUG] Round {round_idx}, marked_stations={marked_stations}")

            next_marked = set()
            
            for st in list(marked_stations):
                route_entries = self.routes_by_station.get(st, [])
                
                for route_info in route_entries:
                    route_id = route_info["route_id"]
                    segs = self.route_segments.get(route_id, [])
                    
                    positions = self.route_stop_index.get(route_id, {}).get(st, [])
                    departures_at_station = self.route_stop_departures.get(route_id, {}).get(st, [])

                    if not positions: continue

                    for arr_time, arr_cost in best_labels[st]:
                        import bisect
                        
                        min_allowed_dep = arr_time + min_transfer if round_idx > 0 else arr_time
                        max_allowed_dep = arr_time + max_transfer if round_idx > 0 else INF
                        # Count binary search usage (benchmarking)
                        if self._metrics_enabled:
                            self._last_metrics["binary_search_calls"] += 1

                        k = bisect.bisect_left(departures_at_station, min_allowed_dep)

                        for idx_in_list in range(k, len(positions)):
                            pos = positions[idx_in_list]
                            seg_dep = departures_at_station[idx_in_list]

                            if seg_dep > max_allowed_dep: break
                            
                            current_cost_on_route = 0
                            for j in range(pos, len(segs)):
                                downstream = segs[j]
                                
                                if not self._operates_on_date(downstream.get("operating_days", "1111111"), travel_date):
                                    continue

                                dst = downstream["dest_station_id"]
                                new_arrival_time = self._time_to_minutes(downstream["arrival"]) + downstream.get("arrival_day_offset", 0) * 24 * 60
                                current_cost_on_route += downstream['cost']
                                new_cost = arr_cost + current_cost_on_route
                                
                                existing_labels = best_labels[dst]
                                # Dominance check: skip if an existing label dominates the new label
                                is_dominated = any(ex_time <= new_arrival_time and ex_cost <= new_cost for ex_time, ex_cost in existing_labels)
                                if is_dominated:
                                    continue

                                # Remove labels that are dominated by the new label, then add the new one
                                new_labels = [(t, c) for t, c in existing_labels if not (new_arrival_time <= t and new_cost <= c)]
                                new_labels.append((new_arrival_time, new_cost))

                                # Normalize labels list (sorted by time then cost) for deterministic comparisons
                                new_labels = sorted(new_labels)

                                # Enforce a hard cap per-stop after dominance pruning to avoid
                                # exponential label growth in dense graphs. Keep the best K
                                # labels by arrival time (then cost). This implements the
                                # MAX_LABELS_PER_STOP safeguard from the project roadmap.
                                if len(new_labels) > self._max_labels_per_stop:
                                    # Select top-K by (arrival_time, cost)
                                    kept = new_labels[: self._max_labels_per_stop]
                                    kept_keys = set(f"{t}:{c}" for t, c in kept)
                                    # Prune prev_segment entries for labels that were dropped
                                    prev_segment_dst = prev_segment.get(dst, {})
                                    prev_segment[dst] = {k: v for k, v in prev_segment_dst.items() if k in kept_keys}
                                    new_labels = kept

                                if new_labels != existing_labels:
                                    best_labels[dst] = new_labels
                                    # Use a deterministic string key for label identification to avoid
                                    # issues with Python's randomized hash() across processes and
                                    # to make keys human-inspectable in tests/logs.
                                    label_key = f"{new_arrival_time}:{new_cost}"
                                    prev_segment[dst][label_key] = (downstream["id"], arr_time, arr_cost)
                                    next_marked.add(dst)
                                    # Metrics updates
                                    if self._metrics_enabled:
                                        self._last_metrics["labels_generated"] += 1
                                        cur_labels = len(best_labels[dst])
                                        if cur_labels > self._last_metrics["max_labels_per_stop"]:
                                            self._last_metrics["max_labels_per_stop"] = cur_labels
                                        self._last_metrics["transfer_expansions"] += 1
                                    if debug:
                                        print(f"[RAPTOR DEBUG] Updated label for {dst} -> time={new_arrival_time} cost={new_cost} via seg={downstream['id']}")

            marked_stations = next_marked
            if self._metrics_enabled:
                self._last_metrics["rounds_processed"] = round_idx + 1

        final_paths = []
        if not best_labels.get(dest_id):
            return []

        # Reconstruct all paths that reach destination with Pareto-optimal labels
        for final_time, final_cost in best_labels[dest_id]:
            path_seg_ids = []
            cur_time, cur_cost = final_time, final_cost
            cur = dest_id
            
            while cur != source_id:
                label_key = f"{cur_time}:{cur_cost}"
                if label_key not in prev_segment[cur]:
                    break

                seg_id, prev_time, prev_cost = prev_segment[cur][label_key]
                path_seg_ids.insert(0, seg_id)
                
                prev_seg_info = self.segments_map.get(seg_id)
                if not prev_seg_info: break
                
                cur = prev_seg_info["source_station_id"]
                cur_time, cur_cost = prev_time, prev_cost

            path = [self.segments_map[sid] for sid in path_seg_ids if sid in self.segments_map]
            if path:
                # Calculate total time and cost for the path
                total_time = sum(seg["duration"] for seg in path)
                total_cost = sum(seg["cost"] for seg in path)
                final_paths.append((path, total_time, total_cost))

        # Apply Pareto pruning across all reconstructed paths
        if not final_paths:
            return []

        # Sort by time and cost for easier processing
        final_paths.sort(key=lambda x: (x[1], x[2]))  # Sort by time, then cost

        pareto_paths = []
        for path, time, cost in final_paths:
            # Check if this path is dominated by any existing Pareto path
            is_dominated = any(
                existing_time <= time and existing_cost <= cost and (existing_time < time or existing_cost < cost)
                for _, existing_time, existing_cost in pareto_paths
            )
            if not is_dominated:
                # Remove any existing paths that are dominated by this one
                pareto_paths = [
                    (p, t, c) for p, t, c in pareto_paths
                    if not (time <= t and cost <= c and (time < t or cost < c))
                ]
                pareto_paths.append((path, time, cost))

        # Sort Pareto-optimal paths by time, then cost
        pareto_paths.sort(key=lambda x: (x[1], x[2]))

        # Limit to PARETO_LIMIT
        max_results = getattr(Config, 'PARETO_LIMIT', 3)
        pareto_paths = pareto_paths[:max_results]

        # Attach final metrics for the last search
        if self._metrics_enabled:
            # labels_generated may be 0 if source==dest or no paths
            self._last_metrics.setdefault("labels_generated", 0)
            self._last_metrics.setdefault("max_labels_per_stop", 0)
            self._last_metrics.setdefault("transfer_expansions", 0)
            self._last_metrics.setdefault("binary_search_calls", 0)
            self._last_metrics.setdefault("rounds_processed", 0)

        # report to prometheus client if available
        try:
            duration = time.time() - start_ts
            if RMA_RAPTOR_RUNTIME_SECONDS is not None:
                RMA_RAPTOR_RUNTIME_SECONDS.observe(duration)
            if RMA_RAPTOR_ROUNDS_TOTAL is not None:
                RMA_RAPTOR_ROUNDS_TOTAL.inc(self._last_metrics.get('rounds_processed', 0) or 0)
            if RMA_RAPTOR_LABELS_GENERATED_TOTAL is not None:
                RMA_RAPTOR_LABELS_GENERATED_TOTAL.inc(self._last_metrics.get('labels_generated', 0) or 0)
            # New routing stability metrics
            if ROUTING_LABELS_GENERATED_TOTAL is not None:
                ROUTING_LABELS_GENERATED_TOTAL.inc(self._last_metrics.get('labels_generated', 0) or 0)
            if ROUTING_ROUNDS_PROCESSED_TOTAL is not None:
                ROUTING_ROUNDS_PROCESSED_TOTAL.inc(self._last_metrics.get('rounds_processed', 0) or 0)
            if RMA_RAPTOR_TRANSFER_EXPANSIONS_TOTAL is not None:
                RMA_RAPTOR_TRANSFER_EXPANSIONS_TOTAL.inc(self._last_metrics.get('transfer_expansions', 0) or 0)
        except Exception:
            pass

        return [path for path, _, _ in pareto_paths]
    
    def _operates_on_date(self, operating_days: str, date_obj: datetime.date) -> bool:
        """Checks if a service operates on a given date."""
        weekday_index = date_obj.weekday()  # Monday=0
        return len(operating_days) == 7 and operating_days[weekday_index] == "1"

    async def search_routes(self, source: str, destination: str, travel_date: str, budget_category: Optional[str] = None) -> List[Dict]:
        if not self._is_loaded:
            raise RuntimeError("RouteEngine graph is not loaded.")

        cache_key = f"route:{source}:{destination}:{travel_date}:{budget_category}:{getattr(Config, 'MAX_TRANSFERS', Config.MAX_TRANSFERS)}"
        if cache_service.is_available():
            cached = cache_service.get(cache_key)
            # treat empty list as a cache-miss so engine can recompute (helps tests & fresh data)
            if cached:
                try:
                    RMA_CACHE_HIT_TOTAL.inc()  # type: ignore
                except Exception:
                    pass
                return cached
            else:
                try:
                    RMA_CACHE_MISS_TOTAL.inc()  # type: ignore
                except Exception:
                    pass

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
        routes = [await self._construct_route_from_segment_list(source, destination, p, travel_date, budget_category) for p in raw_paths]
        routes = [r for r in routes if r]

        budget_limits = {"economy": 1000, "standard": 2000, "premium": 5000}
        max_budget = budget_limits.get(budget_category, float("inf"))
        if budget_category and budget_category != "all":
            routes = [r for r in routes if r["total_cost"] <= max_budget]

        routes.sort(key=lambda r: (r["total_duration_minutes"], r["total_cost"]))

        # Apply dynamic route ranking using ML model
        routes = route_ranking_predictor.rank_routes(routes)

        if cache_service.is_available():
            ttl = getattr(Config, 'ROUTE_CACHE_TTL_SECONDS', getattr(Config, 'CACHE_TTL_SECONDS', 600))
            cache_service.set(cache_key, routes, ttl_seconds=ttl)

        # Fire-and-forget: publish route search event for analytics
        if Config.KAFKA_ENABLE_EVENTS:
            try:
                # Calculate search latency (approximate)
                search_latency = len(routes) * 0.1  # Rough estimate based on result count
                asyncio.create_task(
                    publish_route_searched(
                        user_id=None,  # TODO: pass from API layer
                        source=source,
                        destination=destination,
                        travel_date=travel_date,
                        routes_shown=len(routes),
                        search_latency_ms=search_latency,
                        filters={"budget_category": budget_category}
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to publish route search event: {e}")

        return routes

    async def _construct_route_from_segment_list(self, source: str, dest: str, segment_list: List[Dict], travel_date: str, budget_category: Optional[str]) -> Optional[Dict]:
        if not segment_list:
            return None
        total_cost = sum(s["cost"] for s in segment_list)
        total_duration_minutes = sum(s["duration"] for s in segment_list)
        
        # Predict total delay for the route
        date_obj = datetime.strptime(travel_date, "%Y-%m-%d").date()
        total_predicted_delay = 0.0
        for seg in segment_list:
            train_id = hash(seg.get('vehicle_id', 'unk')) % 10000
            
            # Check for real-time delay updates first
            real_time_delay = await delay_predictor.get_real_time_delay(train_id)
            if real_time_delay:
                # Use real-time delay information
                delay = real_time_delay['delay_minutes']
                logger.info(f"Using real-time delay for train {train_id}: {delay} minutes")
            else:
                # Fall back to ML prediction
                day_of_week = date_obj.weekday()
                month = date_obj.month
                dep_hour = int(seg['departure'].split(':')[0])
                past_delay_avg = 0.0  # TODO: integrate historical delay data
                weather_score = 0.5  # TODO: integrate weather API
                delay = delay_predictor.predict_delay(train_id, day_of_week, month, dep_hour, past_delay_avg, weather_score)
            
            total_predicted_delay += delay
        segments_data = []
        station_ids = []
        for s in segment_list:
            src = self.stations_map.get(s["source_station_id"], {"name": "unknown"})
            dst = self.stations_map.get(s["dest_station_id"], {"name": "unknown"})
            station_ids.append(s["source_station_id"])
            station_ids.append(s["dest_station_id"])
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

        # Compute route-level safety score: prefer explicit station safety if available, else fallback to heuristic
        safety_values = []
        for sid in set(station_ids):
            st = self.stations_map.get(sid, {})
            if isinstance(st.get("safety_score"), (int, float)):
                safety_values.append(float(st.get("safety_score")))
        if safety_values:
            safety_score = sum(safety_values) / len(safety_values)
        else:
            safety_score = max(1, 100 - (len(segment_list) - 1) * 10 - int(total_duration_minutes / 60 / 24))

        # Calculate layover penalties (penalize night layovers at low-safety stations)
        layover_penalty = 0.0
        NIGHT_START = 22 * 60
        NIGHT_END = 5 * 60
        for i in range(len(segment_list) - 1):
            prev = segment_list[i]
            nxt = segment_list[i + 1]
            # transfer detected if vehicle changes or station differs
            if prev["dest_station_id"] == nxt["source_station_id"] and prev.get("vehicle_id") != nxt.get("vehicle_id"):
                prev_arr = self._time_to_minutes(prev["arrival"]) + prev.get("arrival_day_offset", 0) * 24 * 60
                next_dep = self._time_to_minutes(nxt["departure"]) + nxt.get("departure_day_offset", 0) * 24 * 60
                layover_minutes = next_dep - prev_arr

                # Check if layover occurs during night window (rough check)
                arr_hour_min = prev_arr % (24 * 60)
                if (arr_hour_min >= NIGHT_START) or (arr_hour_min <= NIGHT_END):
                    # station safety (if available) affects penalty
                    st = self.stations_map.get(prev["dest_station_id"], {})
                    station_safety = float(st.get("safety_score", safety_score))
                    station_factor = max(0.0, 1.0 - station_safety / 100.0)
                    layover_penalty += station_factor * getattr(Config, 'NIGHT_LAYOVER_PENALTY', 1.0)

        # Compute feasibility score (higher = better)
        feasibility = self._compute_feasibility_score(
            total_time_minutes=total_duration_minutes,
            total_cost=total_cost,
            safety_score=safety_score,
            num_transfers=len(segment_list) - 1,
            layover_penalty=layover_penalty,
            delay_penalty=total_predicted_delay
        )

        # --- Reliability-aware deterministic adjustment ---
        # If configured, query RouteMaster Agent for per-train reliability and
        # apply a penalty to the feasibility score so lower-reliability trains
        # are deprioritized deterministically before ML ranking.
        avg_rel = 1.0
        reliability_penalty = 0.0
        try:
            if getattr(Config, 'ROUTE_RELIABILITY_WEIGHT', 0.0) > 0.0:
                # collect unique vehicle/train identifiers from the route
                train_ids = [str(s.get('vehicle_id')) for s in segment_list if s.get('vehicle_id')]
                unique_trains = list({t for t in train_ids if t})
                if unique_trains:
                    rel_map = await get_train_reliabilities(unique_trains)
                    vals = [rel_map.get(t, 1.0) for t in unique_trains]
                    avg_rel = sum(vals) / len(vals) if vals else 1.0
                    # penalty scales with (1 - avg_rel)
                    reliability_penalty = float(getattr(Config, 'ROUTE_RELIABILITY_WEIGHT', 0.0)) * (1.0 - avg_rel)
                    feasibility = feasibility - reliability_penalty

                    # Record reliability-aware routing metrics
                    if RMA_ROUTING_RELIABILITY_APPLIED_TOTAL is not None:
                        RMA_ROUTING_RELIABILITY_APPLIED_TOTAL.inc()
                    if RMA_ROUTE_AVG_RELIABILITY is not None:
                        RMA_ROUTE_AVG_RELIABILITY.observe(avg_rel)
                    if RMA_ROUTE_SCORE_DELTA is not None:
                        RMA_ROUTE_SCORE_DELTA.observe(-reliability_penalty)  # negative because it's a penalty
        except Exception:
            # fail-open: do not penalize if RMA is unavailable
            avg_rel = 1.0
            reliability_penalty = 0.0

```
        # Get Tatkal demand prediction
        current_time = datetime.now()
        route_info_for_tatkal = {
            'departure_datetime': datetime.strptime(travel_date + " " + segments_data[0]['departure_time'], "%Y-%m-%d %H:%M"),
            'booking_velocity_24h': 15,  # placeholder - would come from real data
            'popularity_score': 0.6,     # placeholder
            'current_occupancy': 0.4,    # placeholder
            'tatkal_premium': 1.5,       # placeholder
            'competition_score': 1.0,   # placeholder
        }
        tatkal_info = tatkal_demand_predictor.get_tatkal_recommendation(route_info_for_tatkal, current_time)

        # Extract additional fields for ML ranking
        departure_hour = int(segments_data[0]['departure_time'].split(':')[0])
        departure_day_of_week = date_obj.weekday()
        popularity_score = 0.5  # placeholder - would come from historical data

        return {
            "id": f"route_{hashlib.md5(json.dumps(segments_data, sort_keys=True).encode()).hexdigest()[:12]}",
            "source": source,
            "destination": dest,
            "segments": segments_data,
            "total_duration": format_duration(total_duration_minutes),
            "total_duration_minutes": total_duration_minutes,
            "total_cost": total_cost,
            "predicted_delay_minutes": total_predicted_delay,
            "safetyScore": safety_score,
            "budget_category": budget_category or "standard",
            "num_transfers": len(segment_list) - 1,
            "is_unlocked": False,
            "layover_penalty": layover_penalty,
            "feasibility_score": feasibility,
            "tatkal_info": tatkal_info,
            "departure_hour": departure_hour,
            "departure_day_of_week": departure_day_of_week,
            "popularity_score": popularity_score,
        }

    def _compute_feasibility_score(self, *, total_time_minutes: float, total_cost: float, safety_score: float, num_transfers: int, layover_penalty: float = 0.0, delay_penalty: float = 0.0) -> float:
        """Compute a scalar feasibility score for ranking routes (higher is better).
        Uses configurable weights in Config but keeps units normalized so tests remain stable.
        """
        wt = getattr(Config, 'FEASIBILITY_WEIGHT_TIME', 1.0)
        wc = getattr(Config, 'FEASIBILITY_WEIGHT_COST', 0.01)
        wf = getattr(Config, 'FEASIBILITY_WEIGHT_COMFORT', 0.5)
        wtr = getattr(Config, 'FEASIBILITY_WEIGHT_TRANSFERS', 5.0)
        wd = getattr(Config, 'FEASIBILITY_WEIGHT_DELAY', 0.1)

        time_hours = total_time_minutes / 60.0
        # Higher safety_score increases score; other terms decrease it
        score = (wf * (safety_score / 100.0)) - (wt * time_hours) - (wc * total_cost) - (wtr * num_transfers) - layover_penalty - (wd * delay_penalty)
        return score

    def is_loaded(self) -> bool:
        return self._is_loaded

route_engine = RouteEngine()