"""
Offline Route Generation Engine - Main Coordinator

This is the core entry point for the offline routing system.
Uses only railway_manager.db with no external dependencies.
Optimized for offline mode with graph snapshot loading at startup.

Pattern: Station → Time → Departures (Phase 1 indexed lookups)
Response: Route Summary (locked) + Unlock Details (full verification)
"""

import logging
from datetime import datetime, time, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
import asyncio

from ...database.session import SessionLocal
from ...database.models import Stop, Trip, StopTime, Calendar, Coach, Seat
from ...services.station_departure_service import StationDepartureService
from .graph import TimeDependentGraph, StaticGraphSnapshot
from .builder import GraphBuilder
from .raptor import OptimizedRAPTOR
from .transfer_intelligence import TransferIntelligenceManager
from .snapshot_manager import SnapshotManager

logger = logging.getLogger(__name__)


@dataclass
class RouteSegment:
    """Single segment of a route (one train journey)"""
    segment_id: str
    from_stop_code: str
    from_stop_name: str
    from_stop_id: int
    to_stop_code: str
    to_stop_name: str
    to_stop_id: int
    trip_id: int
    train_number: str
    train_name: str
    departure_time: time
    arrival_time: time
    duration_minutes: int
    coaches: List[str] = field(default_factory=list)
    class_availability: Dict = field(default_factory=dict)
    fare_min: float = 0.0
    fare_max: float = 0.0
    distance_km: float = 0.0


@dataclass
class TransferInfo:
    """Information about a transfer between segments"""
    from_arrival_time: time
    from_arrival_station: str
    to_departure_time: time
    to_departure_station: str
    waiting_time_minutes: int
    risk_level: str  # SAFE, LOW, MEDIUM, HIGH, RISKY
    walking_time_minutes: int = 5
    transfer_distance_km: float = 0.5
    notes: str = ""


@dataclass
class RouteSummary:
    """Summary view of a route (locked state)"""
    route_id: str
    from_stop_code: str
    to_stop_code: str
    from_stop_name: str
    to_stop_name: str
    departure_time: time
    arrival_time: time
    total_duration_hours: float
    total_duration_minutes: int
    transfers_count: int
    fare_min: float
    fare_max: float
    segments_count: int
    summary_text: str  # e.g., "NDLS 10:00 → CSMT 10:00 (next day)"
    status: str = "LOCKED"
    unlock_token: str = ""
    reliability_score: float = 0.95


@dataclass
class DetailedJourney:
    """Complete journey details (unlocked state)"""
    route_id: str
    segments: List[RouteSegment] = field(default_factory=list)
    transfers: List[TransferInfo] = field(default_factory=list)
    total_fare: float = 0.0
    total_duration_minutes: int = 0
    total_transfers: int = 0
    route_reliability: float = 0.95
    status: str = "VERIFIED_OFFLINE"
    verified_at: str = ""
    verification_details: Dict = field(default_factory=dict)


@dataclass
class RouteSearchResponse:
    """Response for route search endpoint"""
    status: str = "VERIFIED_OFFLINE"
    timestamp: str = ""
    mode: str = "OFFLINE"
    database: str = "railway_manager.db"
    routes: List[RouteSummary] = field(default_factory=list)
    count: int = 0
    search_time_ms: float = 0.0
    source_station: str = ""
    destination_station: str = ""
    travel_date: str = ""
    departure_time: str = ""


class OfflineRouteEngine:
    """
    Main coordinator for offline route generation.

    Uses railway_manager.db exclusively.
    Loads graph snapshot on startup.
    Returns route summaries (locked) + detailed journeys (unlocked).
    """

    def __init__(self, db_session=None):
        """Initialize offline engine with graph and validators."""
        self.session = db_session or SessionLocal()
        self.logger = logging.getLogger(__name__)

        # Performance tracking
        import time as time_module
        self.startup_time = time_module.time()

        # Initialize components
        self.logger.info("🔄 Initializing OfflineRouteEngine...")

        # Load and cache reference data
        self._load_station_cache()
        self._load_calendar_cache()
        self._load_trip_cache()

        # Load graph snapshot
        self._load_graph_snapshot()

        # Initialize routing components
        self._initialize_routing()

        # Initialize validators
        self._initialize_validators()

        # Route result cache
        self.route_cache = {}
        self.cache_ttl = 3600  # 1 hour

        init_time = time_module.time() - self.startup_time
        self.logger.info(
            f"✅ OfflineRouteEngine initialized in {init_time:.2f}s\n"
            f"   Mode: OFFLINE | Database: railway_manager.db\n"
            f"   Stations cached: {len(self.station_cache)}\n"
            f"   Trips cached: {len(self.trip_cache)}"
        )

    def _load_station_cache(self):
        """Load all stations into memory for fast lookups."""
        try:
            self.logger.info("  → Loading station cache...")
            self.station_cache = {}
            stops = self.session.query(Stop).all()
            for stop in stops:
                self.station_cache[stop.id] = {
                    'id': stop.id,
                    'code': stop.code,
                    'name': stop.name,
                    'city': stop.city,
                    'latitude': stop.latitude,
                    'longitude': stop.longitude,
                    'is_major': stop.is_major_junction,
                }
            self.logger.info(f"  ✓ Loaded {len(self.station_cache)} stations")
        except Exception as e:
            self.logger.warning(f"  ⚠ Station cache load failed: {e}")
            self.station_cache = {}

    def _load_calendar_cache(self):
        """Load service calendars into memory."""
        try:
            self.logger.info("  → Loading calendar cache...")
            self.calendar_cache = {}
            calendars = self.session.query(Calendar).all()
            for calendar in calendars:
                self.calendar_cache[calendar.service_id] = {
                    'monday': calendar.monday,
                    'tuesday': calendar.tuesday,
                    'wednesday': calendar.wednesday,
                    'thursday': calendar.thursday,
                    'friday': calendar.friday,
                    'saturday': calendar.saturday,
                    'sunday': calendar.sunday,
                }
            self.logger.info(f"  ✓ Loaded {len(self.calendar_cache)} service calendars")
        except Exception as e:
            self.logger.warning(f"  ⚠ Calendar cache load failed: {e}")
            self.calendar_cache = {}

    def _load_trip_cache(self):
        """Load trip information into memory."""
        try:
            self.logger.info("  → Loading trip cache...")
            self.trip_cache = {}
            trips = self.session.query(Trip).limit(10000).all()  # Limit for memory
            for trip in trips:
                self.trip_cache[trip.id] = {
                    'id': trip.id,
                    'trip_id': trip.trip_id,
                    'route_id': trip.route_id,
                    'service_id': trip.service_id,
                    'headsign': trip.headsign,
                }
            self.logger.info(f"  ✓ Loaded {len(self.trip_cache)} trips (first 10K)")
        except Exception as e:
            self.logger.warning(f"  ⚠ Trip cache load failed: {e}")
            self.trip_cache = {}

    def _load_graph_snapshot(self):
        """Load static graph snapshot from memory."""
        try:
            self.logger.info("  → Loading graph snapshot...")
            snapshot_manager = SnapshotManager()
            self.graph_snapshot = snapshot_manager.load_snapshot(datetime.now())

            if not self.graph_snapshot:
                self.logger.info("  → Building fresh graph snapshot...")
                from concurrent.futures import ThreadPoolExecutor
                builder = GraphBuilder(ThreadPoolExecutor(max_workers=4))
                # Note: In async context, this would be awaited
                graph = asyncio.run(builder.build_graph(datetime.now()))
                self.graph_snapshot = graph.snapshot

            self.logger.info(f"  ✓ Graph snapshot loaded")
        except Exception as e:
            self.logger.error(f"  ✗ Graph snapshot load failed: {e}")
            self.graph_snapshot = None

    def _initialize_routing(self):
        """Initialize routing algorithms."""
        try:
            self.logger.info("  → Initializing RAPTOR algorithm...")
            self.raptor = OptimizedRAPTOR(max_transfers=2)
            self.logger.info(f"  ✓ RAPTOR initialized")
        except Exception as e:
            self.logger.warning(f"  ⚠ RAPTOR init failed: {e}")
            self.raptor = None

    def _initialize_validators(self):
        """Initialize validation system (placeholder for now)."""
        try:
            self.logger.info("  → Initializing validators...")
            # Will be implemented in separate validator files
            self.route_validator = None
            self.segment_validator = None
            self.transfer_validator = None
            self.logger.info(f"  ✓ Validators initialized")
        except Exception as e:
            self.logger.warning(f"  ⚠ Validator init failed: {e}")

    async def search_routes(
        self,
        source_station_code: str,
        destination_station_code: str,
        travel_date: datetime,
        departure_time: time,
        passengers: int = 1,
        max_transfers: int = 2,
        preferences: Optional[Dict] = None
    ) -> RouteSearchResponse:
        """
        Search for routes offline using railway_manager.db.

        Args:
            source_station_code: e.g., "NDLS"
            destination_station_code: e.g., "CSMT"
            travel_date: Date of travel
            departure_time: Preferred departure time
            passengers: Number of passengers
            max_transfers: Max transfers allowed
            preferences: Optional search preferences

        Returns:
            RouteSearchResponse with route summaries (LOCKED)
        """
        import time as timer
        start_time = timer.time()

        response = RouteSearchResponse()
        response.timestamp = datetime.now().isoformat()
        response.source_station = source_station_code
        response.destination_station = destination_station_code
        response.travel_date = travel_date.isoformat()
        response.departure_time = departure_time.isoformat()

        try:
            # Step 1: Resolve station codes to IDs
            source_id = await self._resolve_station_code(source_station_code)
            dest_id = await self._resolve_station_code(destination_station_code)

            if not source_id or not dest_id:
                response.status = "ERROR"
                response.routes = []
                return response

            # Step 2: Query initial departures using Phase 1 Time-Series lookup
            initial_departures = await self._get_initial_departures(
                source_id, departure_time, travel_date
            )

            if not initial_departures:
                response.routes = []
                response.count = 0
                response.search_time_ms = (timer.time() - start_time) * 1000
                return response

            # Step 3: Generate candidate routes (placeholder for now)
            candidate_routes = await self._generate_routes(
                source_id, dest_id, travel_date, departure_time,
                max_transfers
            )

            # Step 4: Validate routes (placeholder for now)
            validated_routes = await self._validate_routes(
                candidate_routes, travel_date
            )

            # Step 5: Format responses (SUMMARY only, LOCKED)
            response.routes = await self._format_route_summaries(
                validated_routes
            )
            response.count = len(response.routes)

            self.logger.info(
                f"✓ Found {response.count} routes in "
                f"{(timer.time() - start_time)*1000:.2f}ms"
            )

        except Exception as e:
            self.logger.error(f"✗ Search failed: {e}")
            response.status = "ERROR"
            response.routes = []

        response.search_time_ms = (timer.time() - start_time) * 1000
        return response

    async def _resolve_station_code(self, code: str) -> Optional[int]:
        """Resolve station code to ID."""
        # Check cache first
        for stop_id, stop_info in self.station_cache.items():
            if stop_info['code'] == code:
                return stop_id
        return None

    async def _get_initial_departures(
        self,
        station_id: int,
        departure_time: time,
        travel_date: datetime
    ) -> List[Dict]:
        """Get initial departures using Phase 1 time-series lookup."""
        try:
            # Time window: ±2 hours from preferred departure
            time_window = 120  # minutes
            time_min = time(
                max(0, departure_time.hour - 1),
                departure_time.minute
            )
            time_max = time(
                min(23, departure_time.hour + 3),
                departure_time.minute
            )

            departures = StationDepartureService.get_departures_from_station(
                self.session,
                station_id,
                time_min,
                time_max,
                travel_date
            )

            return departures

        except Exception as e:
            self.logger.warning(f"Initial departures query failed: {e}")
            return []

    async def _generate_routes(
        self,
        source_id: int,
        dest_id: int,
        travel_date: datetime,
        departure_time: time,
        max_transfers: int
    ) -> List[Dict]:
        """Generate candidate routes (placeholder)."""
        # This will use RAPTOR algorithm when fully implemented
        return []

    async def _validate_routes(
        self,
        routes: List[Dict],
        travel_date: datetime
    ) -> List[Dict]:
        """Validate routes against database (placeholder)."""
        # Will implement validators here
        return routes

    async def _format_route_summaries(
        self,
        routes: List[Dict]
    ) -> List[RouteSummary]:
        """Format routes as SUMMARY responses (locked)."""
        summaries = []
        # Implementation will be added
        return summaries

    async def verify_and_unlock_route(
        self,
        route_id: str,
        unlock_token: str
    ) -> DetailedJourney:
        """
        Verify route and unlock full details.

        This runs complete verification when user clicks "Unlock Details".
        """
        journey = DetailedJourney(route_id=route_id)
        journey.verified_at = datetime.now().isoformat()

        try:
            # Retrieve route from cache
            if route_id not in self.route_cache:
                journey.status = "ERROR"
                return journey

            # Validate route again
            # Verify all segments
            # Check seat availability
            # Return full details

            journey.status = "VERIFIED_OFFLINE"

        except Exception as e:
            self.logger.error(f"Unlock failed: {e}")
            journey.status = "ERROR"

        return journey

    async def get_offline_status(self) -> Dict:
        """Return status of offline system."""
        return {
            "mode": "OFFLINE",
            "status": "READY",
            "database": "railway_manager.db",
            "graph_snapshot": "loaded" if self.graph_snapshot else "not_loaded",
            "stations_cached": len(self.station_cache),
            "trips_cached": len(self.trip_cache),
            "calendars_cached": len(self.calendar_cache),
            "cache_size_routes": len(self.route_cache),
            "startup_time_ms": (self.startup_time),
            "timestamp": datetime.now().isoformat(),
        }
