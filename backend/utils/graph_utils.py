import heapq
import logging
from math import radians, cos, sin, asin, sqrt
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime, timedelta

from utils.time_utils import is_operating_on_day, time_string_to_minutes

logger = logging.getLogger(__name__)

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great circle distance between two points in kilometers."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

class TimeExpandedGraph:
    """A simplified graph structure for route search."""
    def __init__(self):
        self.nodes = set()
        # All segments originating from a station
        self.edges: Dict[str, List[Dict]] = defaultdict(list)
        self.station_coords: Dict[str, Tuple[float, float]] = {}

    def add_station(self, station_id: str, lat: float, lon: float):
        """Add station coordinates for A* heuristic."""
        self.station_coords[station_id] = (lat, lon)

    def add_edge(self, from_station: str, segment_data: dict):
        """Add a segment as an edge from a station."""
        self.nodes.add(from_station)
        self.edges[from_station].append(segment_data)
    
    def get_heuristic(self, current_station: str, target_station: str) -> float:
        """A* heuristic: estimated time in minutes to reach the target."""
        if current_station not in self.station_coords or target_station not in self.station_coords:
            return 0
        lat1, lon1 = self.station_coords[current_station]
        lat2, lon2 = self.station_coords[target_station]
        distance_km = haversine_distance(lat1, lon1, lat2, lon2)
        # Assume an average speed of 60km/h to estimate time
        avg_speed_kmh = 60
        return (distance_km / avg_speed_kmh) * 60

def dijkstra_search(
    graph: TimeExpandedGraph,
    segments_map: Dict[str, Dict],
    start_station: str,
    end_station: str,
    start_datetime: datetime,
    max_transfers: int,
    transfer_window_minutes: Tuple[int, int],
) -> List[List[Dict]]:
    """
    Date-aware Dijkstra's algorithm for finding optimal routes.
    """
    logger.debug(f"Starting Dijkstra search from {start_station} to {end_station} at {start_datetime}")
    
    pq = [(0, 0, -1, start_station, [], start_datetime)]
    visited = {}
    final_paths = []

    while pq:
        total_minutes, cost, transfers, current_station, path, current_time = heapq.heappop(pq)

        if current_station in visited and visited[current_station] <= total_minutes:
            continue
        visited[current_station] = total_minutes

        if current_station == end_station:
            logger.debug(f"Found a valid path to destination {end_station}. Path: {[p['segment_id'] for p in path]}")
            final_paths.append(path)
            if len(final_paths) >= 10:
                break
            continue

        if transfers >= max_transfers:
            logger.debug(f"Pruning path due to exceeding max transfers ({transfers}). Path: {[p['segment_id'] for p in path]}")
            continue

        # Explore outgoing segments
        for segment_data in graph.edges.get(current_station, []):
            segment_id = segment_data["segment_id"]
            segment = segments_map[segment_id]
            logger.debug(f"Considering segment {segment_id} from {current_station} at time {current_time}")

            departure_time_of_day_mins = time_string_to_minutes(segment["departure"])

            # If this is the first leg (no transfers yet), only check the specified start date.
            # For connections, we can look a few days ahead.
            day_range = 1 if transfers == -1 else 3

            for day_offset in range(day_range):
                check_date = current_time.date() + timedelta(days=day_offset)
                
                if not is_operating_on_day(segment["operating_days"], check_date.strftime("%Y-%m-%d")):
                    continue

                departure_datetime = datetime.combine(check_date, datetime.min.time()) + timedelta(minutes=departure_time_of_day_mins)
                
                # For the first leg, the departure must be after the search start time (usually midnight)
                # For transfers, it must be after the arrival from the previous segment.
                min_departure_datetime = current_time + timedelta(minutes=transfer_window_minutes[0] if transfers > -1 else 0)

                if departure_datetime >= min_departure_datetime:
                    wait_time = (departure_datetime - current_time).total_seconds() / 60
                    
                    # Only apply max transfer window check for actual transfers
                    if transfers > -1 and wait_time > transfer_window_minutes[1]:
                        logger.debug(f"Skipping segment {segment_id}: wait time {wait_time} exceeds transfer window {transfer_window_minutes[1]}")
                        continue
                        
                    new_transfers = transfers + 1
                    duration = segment["duration"]
                    arrival_datetime = departure_datetime + timedelta(minutes=duration)
                    new_total_minutes = (arrival_datetime - start_datetime).total_seconds() / 60
                    new_cost = cost + segment["cost"]
                    
                    heuristic_minutes = graph.get_heuristic(segment["dest_station_id"], end_station)
                    f_score = new_total_minutes + heuristic_minutes

                    new_path = path + [{"segment_id": segment_id, "cost": segment["cost"]}]
                    
                    logger.debug(f"Pushing valid connection to PQ: Seg={segment_id}, Dest={segment['dest_station_id']}, Arrival={arrival_datetime}, Cost={new_cost}")
                    heapq.heappush(
                        pq,
                        (f_score, new_cost, new_transfers, segment["dest_station_id"], new_path, arrival_datetime),
                    )
                    break 
    
    logger.debug(f"Dijkstra search finished. Found {len(final_paths)} paths.")
    return final_paths
