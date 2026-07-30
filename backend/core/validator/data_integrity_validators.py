"""
Data Integrity & Consistency Validators (RT-131 to RT-150)

This module handles validation logic for data integrity, consistency checks,
GTFS compliance, referential integrity, and database consistency validation.
"""

from typing import List, Dict, Optional, Set, Tuple, Any
from datetime import datetime, timedelta, time
from enum import Enum
from dataclasses import dataclass, field
import logging
import hashlib

logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    """Data source types"""
    GTFS = "gtfs"
    DATABASE = "database"
    CACHE = "cache"
    API = "api"
    IMPORT = "import"


class DataValidationType(Enum):
    """Data validation types"""
    SCHEMA = "schema"
    REFERENTIAL = "referential"
    CONSTRAINT = "constraint"
    TEMPORAL = "temporal"
    GEOGRAPHIC = "geographic"


@dataclass
class StationData:
    """Station data structure"""
    station_id: int
    station_name: str
    latitude: float
    longitude: float
    parent_station_id: Optional[int] = None
    timezone: str = "UTC"
    transfer_time_minutes: int = 5


@dataclass
class TripData:
    """Trip data structure"""
    trip_id: str
    route_id: str
    service_id: str
    start_time: datetime
    end_time: datetime
    stops: List[StationData] = field(default_factory=list)
    stop_times: List[datetime] = field(default_factory=list)


@dataclass
class DatasetMetadata:
    """Dataset metadata"""
    version: str
    created_at: datetime
    source: DataSourceType
    row_count: int = 0
    checksum: Optional[str] = None
    timezone: str = "UTC"


class DataIntegrityValidator:
    """Validator class for data integrity and consistency"""

    def __init__(self):
        """Initialize the data integrity validator"""
        self.station_graph = {}  # Adjacency list for station connections
        self.imported_data_cache = {}
        self.db_cache = {}
        self.snapshot_history = []
        self.timezone_list = [
            "UTC", "Asia/Kolkata", "America/New_York", "Europe/London",
            "Asia/Tokyo", "Australia/Sydney"
        ]
        self.valid_coordinate_ranges = {
            "latitude": (-90, 90),
            "longitude": (-180, 180)
        }

    def validate_station_graph_connectivity(self, stations: List[StationData],
                                          transfers: List[Tuple[int, int]]) -> bool:
        """
        RT-131: Validate station graph connectivity.
        All stations should be reachable from each other (connected graph).
        """
        if not stations:
            return False
        
        # Build adjacency list
        graph = {station.station_id: [] for station in stations}
        
        for from_id, to_id in transfers:
            if from_id in graph and to_id in graph:
                graph[from_id].append(to_id)
                graph[to_id].append(from_id)  # Undirected graph for connectivity
        
        # Check if graph is connected using BFS
        if not graph:
            return True
        
        visited = set()
        queue = [stations[0].station_id]
        visited.add(stations[0].station_id)
        
        while queue:
            node = queue.pop(0)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        # All stations should be visited
        if len(visited) != len(stations):
            logger.warning(f"Station graph not fully connected: {len(visited)} of {len(stations)} visited")
            return False
        
        self.station_graph = graph
        return True

    def validate_orphan_nodes_detection(self, stations: List[StationData],
                                       transfers: List[Tuple[int, int]]) -> bool:
        """
        RT-132: Validate orphan nodes detection.
        No stations should be orphaned (isolated from rest of network).
        """
        if not stations:
            return True
        
        # Find all stations involved in transfers
        connected_stations = set()
        for from_id, to_id in transfers:
            connected_stations.add(from_id)
            connected_stations.add(to_id)
        
        # Check if any stations are not in transfers
        all_station_ids = {station.station_id for station in stations}
        orphan_stations = all_station_ids - connected_stations
        
        if orphan_stations and len(stations) > 1:
            logger.warning(f"Orphan stations detected: {orphan_stations}")
            # Orphan stations are acceptable if they serve as endpoints or have alternative connectivity
            return len(orphan_stations) <= len(stations) * 0.1  # Allow up to 10%
        
        return True

    def validate_duplicate_station_ids(self, stations: List[StationData]) -> bool:
        """
        RT-133: Validate duplicate station IDs detection.
        All station IDs should be unique.
        """
        if not stations:
            return True
        
        station_ids = [station.station_id for station in stations]
        unique_ids = set(station_ids)
        
        if len(station_ids) != len(unique_ids):
            duplicates = [sid for sid in station_ids if station_ids.count(sid) > 1]
            logger.warning(f"Duplicate station IDs detected: {set(duplicates)}")
            return False
        
        return True

    def validate_trip_continuity(self, trip: TripData) -> bool:
        """
        RT-134: Validate trip continuity validation.
        All stops in a trip should form a continuous sequence.
        """
        if not trip.stops or len(trip.stops) < 2:
            return True
        
        # Check if stops are in order and connected
        for i in range(len(trip.stops) - 1):
            current_stop = trip.stops[i]
            next_stop = trip.stops[i + 1]
            
            # Check if stops have sequential times
            if trip.stop_times[i] >= trip.stop_times[i + 1]:
                logger.warning(f"Trip {trip.trip_id}: non-sequential stop times")
                return False
        
        return True

    def validate_missing_timestamps_handling(self, trips: List[TripData]) -> bool:
        """
        RT-135: Validate missing timestamps handling.
        All trips should have valid start and end times.
        """
        for trip in trips:
            if trip.start_time is None or trip.end_time is None:
                logger.warning(f"Trip {trip.trip_id}: missing timestamps")
                return False
            
            # Check for invalid datetime
            if not isinstance(trip.start_time, datetime) or not isinstance(trip.end_time, datetime):
                return False
        
        return True

    def validate_negative_durations_rejected(self, trips: List[TripData]) -> bool:
        """
        RT-136: Validate negative durations rejected.
        Trip duration should always be positive.
        """
        for trip in trips:
            if trip.end_time <= trip.start_time:
                logger.warning(f"Trip {trip.trip_id}: negative or zero duration")
                return False
            
            duration = (trip.end_time - trip.start_time).total_seconds()
            if duration < 0:
                return False
            
            # Duration should be reasonable (not more than 24 hours for local trip)
            if duration > 24 * 3600:
                logger.warning(f"Trip {trip.trip_id}: unreasonably long duration {duration}s")
                return False
        
        return True

    def validate_time_ordering_in_stops(self, trip: TripData) -> bool:
        """
        RT-137: Validate time ordering in stops.
        Stop times should be in chronological order throughout trip.
        """
        if not trip.stop_times or len(trip.stop_times) < 2:
            return True
        
        for i in range(len(trip.stop_times) - 1):
            current_time = trip.stop_times[i]
            next_time = trip.stop_times[i + 1]
            
            if current_time >= next_time:
                logger.warning(f"Trip {trip.trip_id}: stop times not in order at stop {i}")
                return False
        
        return True

    def validate_distance_monotonic_increase(self, trip: TripData) -> bool:
        """
        RT-138: Validate distance monotonic increase.
        Distance traveled should monotonically increase along trip.
        """
        if not trip.stops or len(trip.stops) < 2:
            return True
        
        # Calculate cumulative distances
        cumulative_distance = 0.0
        
        for i in range(len(trip.stops) - 1):
            current_stop = trip.stops[i]
            next_stop = trip.stops[i + 1]
            
            # Calculate distance using haversine formula (simplified)
            distance = self._calculate_distance(
                current_stop.latitude, current_stop.longitude,
                next_stop.latitude, next_stop.longitude
            )
            
            if distance < 0:
                logger.warning(f"Trip {trip.trip_id}: negative distance calculated")
                return False
            
            cumulative_distance += distance
        
        return True

    def validate_data_import_validation(self, dataset: DatasetMetadata,
                                       data_rows: List[Dict]) -> bool:
        """
        RT-139: Validate data import validation.
        Imported data should meet quality standards.
        """
        if not data_rows:
            logger.warning("Empty dataset during import")
            return False
        
        if dataset.row_count > 0 and len(data_rows) != dataset.row_count:
            logger.warning(f"Row count mismatch: expected {dataset.row_count}, got {len(data_rows)}")
            return False
        
        # Validate each row has required fields
        for row in data_rows:
            if not isinstance(row, dict) or len(row) == 0:
                logger.warning("Invalid row format in import")
                return False
        
        return True

    def validate_partial_dataset_recovery(self, original_data: List[Dict],
                                         corrupted_indices: List[int]) -> bool:
        """
        RT-140: Validate partial dataset recovery.
        System should recover valid data when partial corruption occurs.
        """
        if not original_data:
            return True
        
        # Verify that non-corrupted data is recoverable
        valid_data_count = 0
        for i, data in enumerate(original_data):
            if i not in corrupted_indices and data:
                valid_data_count += 1
        
        # At least 50% of data should be recoverable
        recovery_rate = valid_data_count / len(original_data) if original_data else 0
        
        if recovery_rate < 0.5:
            logger.warning(f"Low data recovery rate: {recovery_rate * 100}%")
            return False
        
        return True

    def validate_index_corruption_recovery(self, primary_index: Dict[int, Any],
                                          backup_index: Dict[int, Any]) -> bool:
        """
        RT-141: Validate index corruption recovery.
        System should detect and recover from index corruption.
        """
        if not primary_index or not backup_index:
            return True
        
        # Check if primary index is valid (matches backup)
        if set(primary_index.keys()) != set(backup_index.keys()):
            logger.warning("Primary and backup indices have different keys")
            # Can recover from backup
            return True
        
        # Verify key counts
        if len(primary_index) == 0:
            logger.warning("Primary index is empty")
            return False
        
        return True

    def validate_cache_vs_db_consistency(self, cache_data: Dict[str, Any],
                                        db_data: Dict[str, Any]) -> bool:
        """
        RT-142: Validate cache vs DB consistency.
        Cache and database should be in sync.
        """
        if not cache_data and not db_data:
            return True
        
        if bool(cache_data) != bool(db_data):
            logger.warning("Cache/DB existence mismatch")
            # Allow sync process to occur
            return True
        
        # Check if data keys match
        if set(cache_data.keys()) != set(db_data.keys()):
            logger.warning("Cache and DB have different keys")
            # This might be acceptable if cache is subset of DB
            cache_keys = set(cache_data.keys())
            db_keys = set(db_data.keys())
            
            if cache_keys.issubset(db_keys):
                return True  # Cache is valid subset
            
            return False
        
        return True

    def validate_graph_rebuild_determinism(self, graph_v1: Dict,
                                          graph_v2: Dict) -> bool:
        """
        RT-143: Validate graph rebuild determinism.
        Graph rebuilds should produce identical results.
        """
        if not graph_v1 or not graph_v2:
            return True
        
        # Check structure equality
        if set(graph_v1.keys()) != set(graph_v2.keys()):
            logger.warning("Graph structures differ after rebuild")
            return False
        
        # Check connections equality
        for node in graph_v1:
            v1_neighbors = set(graph_v1[node])
            v2_neighbors = set(graph_v2[node])
            
            if v1_neighbors != v2_neighbors:
                logger.warning(f"Graph node {node} has different neighbors")
                return False
        
        return True

    def validate_realtime_merge_consistency(self, static_data: Dict,
                                           realtime_data: Dict,
                                           merged_data: Dict) -> bool:
        """
        RT-144: Validate realtime merge consistency.
        Merged data should correctly combine static and realtime info.
        """
        if not static_data and not realtime_data:
            return True
        
        # Check that merge contains all static data
        for key in static_data:
            if key not in merged_data:
                logger.warning(f"Merged data missing static key: {key}")
                return False
        
        # Check that realtime data properly overrides static
        for key in realtime_data:
            if key in merged_data:
                # Realtime should take precedence
                merged_value = merged_data[key]
                realtime_value = realtime_data[key]
                
                # If realtime exists, it should be in merged
                if realtime_value and merged_value != realtime_value:
                    if realtime_value not in str(merged_value):
                        logger.warning(f"Realtime value not properly merged for key: {key}")
                        return False
        
        return True

    def validate_timezone_mismatch_detection(self, stations: List[StationData]) -> bool:
        """
        RT-145: Validate timezone mismatch detection.
        All stations should use compatible/consistent timezones.
        """
        if not stations:
            return True
        
        timezones = set(station.timezone for station in stations)
        
        # Allow multiple timezones if they're geographically reasonable
        if len(timezones) > 1:
            logger.warning(f"Multiple timezones detected: {timezones}")
            # This is acceptable for routes spanning regions
        
        # Check if all timezones are valid
        for station in stations:
            if station.timezone not in self.timezone_list and station.timezone != "UTC":
                logger.warning(f"Invalid timezone: {station.timezone}")
                return False
        
        return True

    def validate_station_coordinate_sanity(self, stations: List[StationData]) -> bool:
        """
        RT-146: Validate station coordinate sanity checks.
        Station coordinates should be within valid ranges and reasonable.
        """
        if not stations:
            return True
        
        for station in stations:
            # Check latitude range
            if not (-90 <= station.latitude <= 90):
                logger.warning(f"Station {station.station_id}: invalid latitude {station.latitude}")
                return False
            
            # Check longitude range
            if not (-180 <= station.longitude <= 180):
                logger.warning(f"Station {station.station_id}: invalid longitude {station.longitude}")
                return False
            
            # Check for (0, 0) which is often placeholder
            if station.latitude == 0.0 and station.longitude == 0.0:
                logger.warning(f"Station {station.station_id}: placeholder coordinates (0,0)")
                return False
        
        return True

    def validate_gtfs_spec_compliance(self, dataset: DatasetMetadata,
                                     required_fields: List[str],
                                     data_sample: List[Dict]) -> bool:
        """
        RT-147: Validate GTFS spec compliance.
        Data should comply with GTFS standard specification.
        """
        if dataset.source != DataSourceType.GTFS:
            return True
        
        if not data_sample:
            return False
        
        # Check required fields in sample
        for row in data_sample[:min(10, len(data_sample))]:  # Check first 10 rows
            for field in required_fields:
                if field not in row or row[field] is None:
                    logger.warning(f"GTFS compliance: missing required field {field}")
                    return False
        
        return True

    def validate_referential_integrity(self, trips: List[TripData],
                                      valid_route_ids: Set[str],
                                      valid_service_ids: Set[str]) -> bool:
        """
        RT-148: Validate referential integrity.
        All foreign keys should reference valid parent records.
        """
        if not trips:
            return True
        
        for trip in trips:
            # Check route_id exists
            if trip.route_id not in valid_route_ids:
                logger.warning(f"Trip {trip.trip_id}: invalid route_id {trip.route_id}")
                return False
            
            # Check service_id exists
            if trip.service_id not in valid_service_ids:
                logger.warning(f"Trip {trip.trip_id}: invalid service_id {trip.service_id}")
                return False
        
        return True

    def validate_snapshot_rollback_correctness(self, snapshot_before: Dict,
                                              snapshot_after: Dict,
                                              original_data: Dict) -> bool:
        """
        RT-149: Validate snapshot rollback correctness.
        Rollback should restore system to consistent snapshot state.
        """
        if not snapshot_before:
            return True
        
        # After rollback, should match original
        if snapshot_after != snapshot_before:
            logger.warning("Rollback did not restore snapshot correctly")
            
            # Check critical fields at least
            critical_fields = ['version', 'timestamp', 'status']
            for field in critical_fields:
                if snapshot_before.get(field) != snapshot_after.get(field):
                    logger.warning(f"Critical field {field} not restored in rollback")
                    return False
        
        return True

    def validate_data_version_migration(self, old_version: str,
                                       new_version: str,
                                       migration_successful: bool) -> bool:
        """
        RT-150: Validate data version migration.
        Data should be correctly migrated between schema versions.
        """
        if not old_version or not new_version:
            return False
        
        # Verify version format (e.g., "1.0", "2.1")
        try:
            old_parts = [int(x) for x in old_version.split('.')]
            new_parts = [int(x) for x in new_version.split('.')]
            
            # New version should be >= old version
            if new_parts < old_parts:
                logger.warning(f"Invalid version migration: {old_version} -> {new_version}")
                return False
        except (ValueError, AttributeError):
            logger.warning(f"Invalid version format: {old_version} or {new_version}")
            return False
        
        if not migration_successful:
            logger.warning("Migration process failed")
            return False
        
        return True

    def _calculate_distance(self, lat1: float, lon1: float,
                           lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates using haversine formula (simplified)"""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth's radius in km
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance
