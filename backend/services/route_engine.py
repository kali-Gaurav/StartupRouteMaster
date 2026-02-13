import hashlib
import json
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from config import Config
from models import Segment, Station
from services.cache_service import cache_service
from utils.graph_utils import TimeExpandedGraph, dijkstra_search
from utils.time_utils import format_duration

logger = logging.getLogger(__name__)


class RouteEngine:
    """
    A high-performance, date-aware route search engine.
    """
    def __init__(self):
        self.stations_map: Dict[str, Dict] = {}
        self.segments_map: Dict[str, Dict] = {}
        self.station_name_to_id: Dict[str, str] = {}
        self.graph = TimeExpandedGraph()
        self._is_loaded = False

    def load_graph_from_db(self, db: Session):
        """
        Loads the transport network from the database into memory.
        This method is idempotent and will only load the graph once.
        """
        if self._is_loaded:
            logger.info("Graph is already loaded, skipping reload.")
            return
            
        logger.info("Loading route graph from database into memory...")
        stations = db.query(Station).all()
        segments = db.query(Segment).all()

        for station in stations:
            self.stations_map[station.id] = {"name": station.name, "city": station.city, "lat": station.latitude, "lon": station.longitude}
            self.station_name_to_id[station.name.lower()] = station.id
            self.graph.add_station(station.id, station.latitude, station.longitude)

        for segment in segments:
            segment_data = {
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
            }
            self.segments_map[segment.id] = segment_data
            self.graph.add_edge(segment.source_station_id, {"segment_id": segment.id})

        self._is_loaded = True
        logger.info(f"Graph loaded: {len(self.stations_map)} stations, {len(self.segments_map)} segments.")

    def search_routes(
        self, source: str, destination: str, travel_date: str, budget_category: Optional[str] = None
    ) -> List[Dict]:
        """Finds routes using the date-aware, in-memory graph."""
        if not self._is_loaded:
            raise RuntimeError("RouteEngine graph is not loaded.")

        cache_key = self._get_cache_key(source, destination, travel_date, budget_category)
        if cache_service.is_available():
            cached_result = cache_service.get(cache_key)
            if cached_result is not None:
                return cached_result

        source_station_id = self.station_name_to_id.get(source.lower())
        dest_station_id = self.station_name_to_id.get(destination.lower())

        if not source_station_id or not dest_station_id:
            return []

        try:
            start_datetime = datetime.strptime(travel_date, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"Invalid travel_date format: {travel_date}")
            return []

        paths = dijkstra_search(
            graph=self.graph,
            segments_map=self.segments_map,
            start_station=source_station_id,
            end_station=dest_station_id,
            start_datetime=start_datetime,
            max_transfers=Config.MAX_TRANSFERS,
            transfer_window_minutes=(Config.TRANSFER_WINDOW_MIN, Config.TRANSFER_WINDOW_MAX),
        )

        # Define budget limits
        budget_limits = {
            "economy": 1000,  # Example: Max cost for economy
            "standard": 2000, # Example: Max cost for standard
            "premium": 5000,  # Example: Max cost for premium
        }
        max_budget = budget_limits.get(budget_category, float('inf')) # Default to no limit if category not found

        routes = [self._construct_route_from_path(source, destination, path, budget_category) for path in paths]
        # Filter out any None results from construction
        valid_routes = [route for route in routes if route is not None]

        # Apply budget filtering
        if budget_category and budget_category != "all":
            valid_routes = [route for route in valid_routes if route["total_cost"] <= max_budget]

        # Sort by total cost
        sorted_routes = sorted(valid_routes, key=lambda x: x["total_cost"])

        if cache_service.is_available():
            cache_service.set(cache_key, sorted_routes)

        return sorted_routes

    def _get_cache_key(self, source: str, dest: str, date: str, budget: Optional[str]) -> str:
        """Generates a consistent MD5 hash for a search query."""
        query_data = json.dumps({"s": source, "d": dest, "dt": date, "b": budget}, sort_keys=True)
        return f"route:{hashlib.md5(query_data.encode()).hexdigest()}"

    def _construct_route_from_path(
        self, source: str, dest: str, path: List[Dict], budget_category: Optional[str]
    ) -> Optional[Dict]:
        """Builds a detailed route dictionary from a path of segments."""
        if not path:
            return None

        total_cost = sum(step["cost"] for step in path)
        
        # Calculate total duration
        first_segment = self.segments_map[path[0]["segment_id"]]
        last_segment = self.segments_map[path[-1]["segment_id"]]
        
        # This is a simplification; the exact duration comes from the Dijkstra path datetimes
        # For now, summing segment durations is a close approximation.
        total_duration_minutes = sum(self.segments_map[step["segment_id"]]["duration"] for step in path)
        # We could add wait times in the future for more accuracy
        
        segments_data = []
        for step in path:
            segment = self.segments_map[step["segment_id"]]
            source_station = self.stations_map[segment["source_station_id"]]
            dest_station = self.stations_map[segment["dest_station_id"]]
            segments_data.append({
                "mode": segment["mode"],
                "from": source_station["name"],
                "to": dest_station["name"],
                "departure_time": segment["departure"],
                "arrival_time": segment["arrival"],
                "duration": format_duration(segment["duration"]),
                "cost": segment["cost"],
                "details": f"Vehicle ID: {segment['vehicle_id']}"
            })

        return {
            "id": f"route_{hashlib.md5(json.dumps(segments_data, sort_keys=True).encode()).hexdigest()[:12]}",
            "source": source,
            "destination": dest,
            "segments": segments_data,
            "total_duration": format_duration(total_duration_minutes),
            "total_cost": total_cost,
            "safetyScore": max(1, 100 - (len(path) - 1) * 10 - int(total_duration_minutes / 60 / 24)), # Example placeholder: -10 per transfer, -1 per day of travel
            "budget_category": budget_category or "standard",
            "num_transfers": len(path) - 1,
        }

route_engine = RouteEngine()
