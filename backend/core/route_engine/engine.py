import asyncio
import logging
import time as _time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

from ...database import SessionLocal
from ...database.models import Stop

from ..validator.validation_manager import create_validation_manager_with_defaults, ValidationProfile, ValidationCategory

from .data_structures import Route, UserContext
from .constraints import RouteConstraints
from .raptor import OptimizedRAPTOR, HybridRAPTOR
from .graph import TimeDependentGraph, StaticGraphSnapshot, RealtimeOverlay
from .builder import GraphBuilder
from .hub import HubManager, HubConnectivityTable
from .snapshot_manager import SnapshotManager
from .data_provider import DataProvider
from ..realtime_event_processor import RealtimeEventProcessor
from ..ml_ranking_model import RouteRankingModel
from ..validator.live_validators import create_live_validators

from ...services.multi_layer_cache import multi_layer_cache

# Point 5: Advanced Booking Layer
from backend.services.booking.manager import SeatAvailabilityManager
from backend.services.booking.rapid_api_client import RapidAPIClient

logger = logging.getLogger(__name__)

class RailwayRouteEngine:
    """
    The main coordinator for all route-finding operations.
    Integrates Snapshots, Real-time Overlays, and Hybrid Hub-RAPTOR.
    (Aliased as RouteEngine for backward compatibility)
    """

    def __init__(self):
        self.hub_manager = HubManager(SessionLocal)
        self.hub_manager.initialize_hubs()

        # We use HybridRAPTOR as the default high-performance engine
        self.raptor = HybridRAPTOR(self.hub_manager, max_transfers=3)
        self.executor = ThreadPoolExecutor(max_workers=8)
        self.snapshot_manager = SnapshotManager()
        self.graph_builder = GraphBuilder(self.executor, snapshot_manager=self.snapshot_manager)

        # Persistent state for performance optimization
        self.current_snapshot: Optional[StaticGraphSnapshot] = None
        self.last_snapshot_time: Optional[datetime] = None
        self.current_overlay: RealtimeOverlay = RealtimeOverlay()

        self.validation_manager = create_validation_manager_with_defaults()

        # Phase 5: Realtime Event Processor
        self.realtime_event_processor = RealtimeEventProcessor(self)

        # concurrency guard for snapshot rebuilds (Phase 2)
        self._snapshot_lock = asyncio.Lock()
        self._snapshot_build_task: Optional[asyncio.Task] = None
        # Overlay sync state
        self._last_synced_version: int = -1  # -1 means never synced
        self._last_synced_at: datetime = datetime.min

        # Phase 6: ML Ranking Model
        self.route_ranking_model = RouteRankingModel()

        # Phase 3: Unified Data Provider with auto-detection
        self.data_provider = DataProvider()
        self._detect_available_features()

        # Advanced Booking Layer (Phase 7)
        self._init_booking_manager()

        # Phase 3: Conditional live validators (must be ready before logging)
        self.live_validators = create_live_validators(self.data_provider)

        self._log_startup_status()

    def _init_booking_manager(self):
        """Initialize seat availability manager with API keys from config."""
        try:
            from ... import config as cfg
            config = cfg.Config
            # Point 1: Securely fetch from environment via Config
            api_key = getattr(config, 'RAPIDAPI_KEY', "") 
            if api_key:
                client = RapidAPIClient(api_key)
                self.seat_manager = SeatAvailabilityManager(client)
                logger.info("✅ Seat Availability Manager initialized with RapidAPI (V1)")
            else:
                logger.warning("⚠️ RAPIDAPI_KEY not found in config. Booking layer disabled.")
                self.seat_manager = None
        except Exception as e:
            logger.error(f"❌ Booking manager failed to initialize: {e}")
            self.seat_manager = None

    def _detect_available_features(self):
        """
        Auto-detect which live features are available.
        Called during initialization to determine mode (offline/hybrid/online).
        """
        try:
            from ... import config as cfg
            config = cfg.Config
        except ImportError:
            logger.warning("Config not available, assuming offline mode")
            return

        self.data_provider.detect_available_features(config)

    def _log_startup_status(self):
        """
        Log startup status showing detected mode and available features.
        """
        logger.info("=" * 60)
        logger.info("🚀 Railway Route Engine - Phase 3 Initialization")
        logger.info("=" * 60)

        mode = "OFFLINE"
        if self.data_provider.has_live_fares or self.data_provider.has_live_delays or self.data_provider.has_live_seats:
            mode = "ONLINE" if (self.data_provider.has_live_fares and self.data_provider.has_live_delays and self.data_provider.has_live_seats) else "HYBRID"

        logger.info(f"🔄 Mode: {mode}")
        logger.info(f"📊 Data Sources:")
        logger.info(f"   • Fares: {'🌐 LIVE API' if self.data_provider.has_live_fares else '💾 DATABASE'}")
        logger.info(f"   • Delays: {'🌐 LIVE API' if self.data_provider.has_live_delays else '⏱️  ASSUME 0'}")
        logger.info(f"   • Seats: {'🌐 LIVE API' if self.data_provider.has_live_seats else '💾 DATABASE'}")
        logger.info(f"✅ Core Features:")
        logger.info(f"   • HybridRAPTOR: Enabled")
        logger.info(f"   • Graph Snapshots: Enabled")
        logger.info(f"   • Realtime Overlay: Enabled")
        logger.info(f"   • Live Validators: {len(self.live_validators)} loaded")
        logger.info("=" * 60)

    async def sync_realtime_overlay(self):
        """Phase 10: Sync distributed real-time state from Redis."""
        try:
            await multi_layer_cache.initialize()
            remote_state = await multi_layer_cache.get_overlay_state("global_v2")
            if remote_state:
                remote_overlay = RealtimeOverlay.from_dict(remote_state)
                needs_sync = (
                    remote_overlay.version > self._last_synced_version or
                    remote_overlay.last_updated > self._last_synced_at
                )
                if needs_sync:
                    self.current_overlay = remote_overlay
                    self._last_synced_at = remote_overlay.last_updated
                    self._last_synced_version = remote_overlay.version
                    try:
                        from backend.utils import metrics
                        metrics.OVERLAY_VERSION.set(self._last_synced_version)
                    except Exception:
                        pass
                    logger.info(
                        f"Phase 10: Synced overlay version {self._last_synced_version} "
                        f"({len(remote_overlay.delays)} delays) from Redis."
                    )
                else:
                    logger.debug("Phase 10: Local overlay is already up to date.")
            else:
                logger.debug("Phase 10: No remote overlay state found in Redis.")
        except Exception as e:
            logger.warning(f"Overlay sync failed: {e}")

    async def _get_current_graph(self, date: datetime) -> TimeDependentGraph:
        """
        Get or rebuild the graph, ensuring snapshot is fresh (valid for 24h).
        Implements Phase 2: Snapshot System & Phase 10: Redis Sync.
        """
        # Step 0: Sync overlay first
        await self.sync_realtime_overlay()

        # Step 1: Snapshot lifecycle (protected by lock to avoid races)
        async with self._snapshot_lock:
            needs_rebuild = (
                not self.current_snapshot or
                self.current_snapshot.date.date() != date.date() or
                (self.last_snapshot_time is None) or
                (datetime.utcnow() - self.last_snapshot_time).total_seconds() > 86400
            )

            if needs_rebuild:
                self.current_snapshot = await self.snapshot_manager.load_snapshot(date)
                if not self.current_snapshot:
                    logger.info(f"Building fresh static graph snapshot for {date.date()} (Phase 2)...")
                    build_start = _time.time()
                    temp_graph = await self.graph_builder.build_graph(date)
                    build_ms = (_time.time() - build_start) * 1000.0
                    try:
                        from backend.utils import metrics
                        metrics.SNAPSHOT_BUILD_TIME_MS.observe(build_ms)
                    except Exception:
                        pass
                    self.current_snapshot = temp_graph.snapshot
                    try:
                        await self.snapshot_manager.save_snapshot(self.current_snapshot)
                    except Exception:
                        logger.warning("Snapshot save failed during rebuild")
                else:
                    try:
                        from backend.utils import metrics
                        metrics.GRAPH_NODES.set(len(self.current_snapshot.stop_cache or {}))
                        edges = sum(len(v) for v in self.current_snapshot.trip_segments.values())
                        edges += sum(len(v) for v in self.current_snapshot.transfer_graph.values())
                        metrics.GRAPH_EDGES.set(edges)
                        if self.current_snapshot.stop_cache:
                            metrics.TRANSFER_DENSITY.set(edges / len(self.current_snapshot.stop_cache))
                    except Exception:
                        pass
            else:
                logger.debug(f"Reusing snapshot for {date.date()} - no rebuild required")

            if self.current_snapshot and not self.raptor._hub_table:
                self.hub_manager.initialize_hubs()
                hub_start = _time.time()
                hub_table = await self.hub_manager.precompute_hub_connectivity(
                    TimeDependentGraph(self.current_snapshot),
                    date
                )
                hub_ms = (_time.time() - hub_start) * 1000.0
                try:
                    from backend.utils import metrics
                    metrics.HUB_PRECOMPUTE_TIME_MS.observe(hub_ms)
                except Exception:
                    pass
                self.raptor.set_hub_table(hub_table)

            self.last_snapshot_time = datetime.utcnow()

        # Step 2: Overlay Layer (Copy-on-Write)
        graph = TimeDependentGraph(self.current_snapshot)
        graph.overlay = self.current_overlay
        return graph

    async def _acquire_base_snapshot(self, date: datetime) -> StaticGraphSnapshot:
        snapshot = self.current_snapshot
        if snapshot and snapshot.date.date() != date.date():
            snapshot = None
        if not snapshot:
            snapshot = await self.snapshot_manager.load_snapshot(date)
            if snapshot:
                self.current_snapshot = snapshot
                self.last_snapshot_time = datetime.utcnow()
        if snapshot and not self._validate_snapshot(snapshot):
            logger.warning("Snapshot failed integrity validation, triggering rebuild")
            snapshot = None
            self.current_snapshot = None
        needs_rebuild = (
            snapshot is None or
            self.last_snapshot_time is None or
            (datetime.utcnow() - (self.last_snapshot_time or datetime.min)).total_seconds() > 86400
        )
        print(f"DEBUG: needs_rebuild={needs_rebuild}, snapshot_loaded={snapshot is not None}")
        if needs_rebuild:
            if snapshot:
                self._launch_background_snapshot_build(date)
            else:
                logger.info(f"Building fresh static graph snapshot for {date.date()} (Phase 2)...")
                base_snapshot = await self._build_snapshot(date)
                self.current_snapshot = base_snapshot
                self.last_snapshot_time = datetime.utcnow()
                return base_snapshot
        if not snapshot:
            raise RuntimeError("Snapshot generation failed and no previous state exists")
        return snapshot

    def _launch_background_snapshot_build(self, date: datetime) -> None:
        if self._snapshot_build_task and not self._snapshot_build_task.done():
            return
        self._snapshot_build_task = asyncio.create_task(self._build_snapshot(date))
        self._snapshot_build_task.add_done_callback(self._snapshot_build_callback)

    async def _build_snapshot(self, date: datetime) -> StaticGraphSnapshot:
        build_start = _time.time()
        temp_graph = await self.graph_builder.build_graph(date)
        snapshot = temp_graph.snapshot
        try:
            await self.snapshot_manager.save_snapshot(snapshot)
        except Exception:
            logger.warning("Snapshot save failed during rebuild")
        build_ms = (_time.time() - build_start) * 1000.0
        try:
            from backend.utils import metrics
            metrics.SNAPSHOT_BUILD_TIME_MS.observe(build_ms)
        except Exception:
            pass
        return snapshot

    def _snapshot_build_callback(self, task: asyncio.Task):
        self._snapshot_build_task = None
        if task.cancelled():
            return
        try:
            snapshot = task.result()
        except Exception as exc:
            logger.error(f"Background snapshot build failed: {exc}")
            return
        asyncio.create_task(self._publish_snapshot(snapshot))

    async def _publish_snapshot(self, snapshot: StaticGraphSnapshot) -> None:
        async with self._snapshot_lock:
            self.current_snapshot = snapshot
            self.last_snapshot_time = datetime.utcnow()

    def _record_graph_metrics(self, snapshot: StaticGraphSnapshot) -> None:
        try:
            from backend.utils import metrics
            metrics.GRAPH_NODES.set(len(snapshot.stop_cache or {}))
            edges = sum(len(v) for v in snapshot.trip_segments.values())
            edges += sum(len(v) for v in snapshot.transfer_graph.values())
            metrics.GRAPH_EDGES.set(edges)
            if snapshot.stop_cache:
                metrics.TRANSFER_DENSITY.set(edges / len(snapshot.stop_cache))
        except Exception:
            pass

    def _validate_snapshot(self, snapshot: Optional[StaticGraphSnapshot]) -> bool:
        if not snapshot:
            return False
        stop_count = len(snapshot.stop_cache or {})
        trip_count = len(snapshot.trip_segments or {})
        if stop_count < 200:
            logger.warning(f"Snapshot appears too small ({stop_count} stops)")
            return False
        if trip_count < 300:
            logger.warning(f"Snapshot appears too small ({trip_count} trips)")
            return False
        transfer_edges = sum(len(v) for v in snapshot.transfer_graph.values())
        if transfer_edges == 0:
            logger.warning("Snapshot has no transfer edges")
            return False
        if not snapshot.date:
            logger.warning("Snapshot missing date")
            return False
        if snapshot.date < datetime.utcnow() - timedelta(days=5):
            logger.warning("Snapshot appears stale")
            return False
        if snapshot.date > datetime.utcnow() + timedelta(days=2):
            logger.warning("Snapshot date in future")
            return False
        return True

    async def _finalize_graph(self, base_snapshot: StaticGraphSnapshot, date: datetime) -> TimeDependentGraph:
        delta = await self.snapshot_manager.load_delta_snapshot(date, date.hour)
        static_snapshot = self._merge_static_snapshots(base_snapshot, delta) if delta else base_snapshot
        graph = TimeDependentGraph(static_snapshot)
        graph.overlay = self.current_overlay
        return graph

    def _merge_static_snapshots(self, base: StaticGraphSnapshot, delta: Optional[StaticGraphSnapshot]) -> StaticGraphSnapshot:
        if not delta:
            return base
        merged = StaticGraphSnapshot(date=base.date)
        merged.departures_by_stop = defaultdict(list)
        for stop, values in base.departures_by_stop.items():
            merged.departures_by_stop[stop].extend(values)
        for stop, values in delta.departures_by_stop.items():
            merged.departures_by_stop[stop].extend(values)
        merged.arrivals_by_stop = defaultdict(list)
        for stop, values in base.arrivals_by_stop.items():
            merged.arrivals_by_stop[stop].extend(values)
        for stop, values in delta.arrivals_by_stop.items():
            merged.arrivals_by_stop[stop].extend(values)
        merged.trip_segments = defaultdict(list)
        for trip, segments in base.trip_segments.items():
            merged.trip_segments[trip].extend(segments)
        for trip, segments in delta.trip_segments.items():
            merged.trip_segments[trip].extend(segments)
        merged.transfer_graph = defaultdict(list)
        for station, transfers in base.transfer_graph.items():
            merged.transfer_graph[station].extend(transfers)
        for station, transfers in delta.transfer_graph.items():
            merged.transfer_graph[station].extend(transfers)
        merged.stop_cache = {**base.stop_cache, **delta.stop_cache}
        merged.route_patterns = {**base.route_patterns, **delta.route_patterns}
        merged.transfer_cache = {**base.transfer_cache, **delta.transfer_cache}
        merged.stop_index = {**base.stop_index, **delta.stop_index}
        merged.transfer_metrics = {**base.transfer_metrics, **delta.transfer_metrics}
        merged.density_metrics = {**base.density_metrics, **delta.density_metrics}
        merged.version = delta.version or base.version
        merged.created_at = base.created_at
        return merged

    async def search_routes(self, source_code: str, destination_code: str,
                           departure_date: datetime,
                           constraints: Optional[RouteConstraints] = None,
                           user_context: Optional[UserContext] = None) -> List[Route]:
        """
        Search for routes between source and destination using Hybrid Hub-RAPTOR.
        """
        if constraints is None:
            constraints = RouteConstraints()

        session = SessionLocal()
        try:
            from sqlalchemy import or_
            source_stop = session.query(Stop).filter(
                or_(Stop.code == source_code.upper(), Stop.stop_id == source_code.upper())
            ).first()
            dest_stop = session.query(Stop).filter(
                or_(Stop.code == destination_code.upper(), Stop.stop_id == destination_code.upper())
            ).first()

            if not source_stop or not dest_stop:
                logger.warning(f"Stop not found: {source_code} or {destination_code}")
                return []

            if source_stop.id == dest_stop.id:
                return []

            date = departure_date
            graph = await self._get_current_graph(date)

            routes = await self.raptor.find_routes(
                source_stop.id, dest_stop.id, date, constraints, graph=graph
            )

            if user_context:
                routes = await self._apply_ml_ranking(routes, user_context)

            if self.seat_manager:
                for i, route in enumerate(routes):
                    route.is_locked = i >= 3
                asyncio.create_task(self._prefetch_availability(routes[:2], date))

            return routes
        finally:
            try:
                session.close()
            except Exception:
                pass

    async def _prefetch_availability(self, top_routes: List[Route], date: datetime):
        """Background task to prefetch seat availability for top routes."""
        if not self.seat_manager:
            return

        date_str = date.strftime("%Y-%m-%d")
        prefetch_items = []
        for route in top_routes:
            if not route.segments:
                continue
            seg = route.segments[0]
            if seg.train_number:
                prefetch_items.append({
                    "train_number": seg.train_number,
                    "from_station": getattr(seg, 'from_code', ''),
                    "to_station": getattr(seg, 'to_code', ''),
                    "date": date_str,
                })
        if prefetch_items:
            await self.seat_manager.prefetch_top_routes(prefetch_items)

    async def _apply_ml_ranking(self, routes: List[Route], user_context: UserContext) -> List[Route]:
        """Apply ML-based ranking and personalization (Phase 6)"""
        if self.route_ranking_model.loaded:
            # Pass constraints to the ranking model for feature engineering
            # Note: A real ML model would be trained on these features.
            # For heuristic, we can use them directly.
            constraints = RouteConstraints() # Assuming default constraints if not passed
            ranked_routes = await self.route_ranking_model.predict(routes, user_context, constraints)
            return ranked_routes
        else:
            logger.warning("Route ranking model not loaded, falling back to reliability sort.")
            routes.sort(key=lambda r: (-r.ml_score if r.ml_score else -r.reliability))
            return routes

    async def start_realtime_event_processor(self, interval_seconds: int = 60):
        """
        Starts a background task to periodically process real-time events.
        (Simulates continuous event stream consumption).
        """
        logger.info(f"Starting real-time event processor to run every {interval_seconds} seconds.")
        while True:
            await self.realtime_event_processor.process_events()
            await asyncio.sleep(interval_seconds)

    # ==============================================================================
    # REAL-TIME MUTATION (Phase 5)
    # ==============================================================================

    async def apply_realtime_updates(self, updates: List[Dict[str, Any]]):
        """
        Apply real-time updates (delays, cancellations) to the global overlay.
        Implements Phase 5: Real-Time Mutation Engine.
        """
        for update in updates:
            update_type = update.get('type')
            trip_id = update.get('trip_id')
            if not trip_id: continue # Must have trip_id
            
            if update_type == 'cancellation':
                self.current_overlay.cancel_trip(trip_id)
                logger.info(f"Applied cancellation to trip {trip_id}")
            elif update_type == 'delay':
                delay_minutes = update.get('delay_minutes')
                if delay_minutes is not None:
                    self.current_overlay.apply_delay(trip_id, delay_minutes)
                    logger.info(f"Applied {delay_minutes}min delay to trip {trip_id}")
            elif update_type == 'occupancy':
                # Occupancy is generally handled by ML scoring, not graph mutation
                logger.debug(f"Occupancy update for trip {trip_id} received, but not directly applied to graph overlay.")
            else:
                logger.warning(f"Unknown real-time update type: {update_type}")
                
        # Invalidate cache for affected routes if necessary (Phase 5)
        # This is a future step, as it requires knowing which cache entries
        # are tied to specific trips or stations.
        # await self._invalidate_affected_routes(affected_trip_ids)
                
        logger.info(f"Applied {len(updates)} realtime updates to global overlay")

    # ==============================================================================
    # VALIDATION FACADES
    # ==============================================================================

    def validate_multimodal_route(self, multimodal_route, validation_config: dict = None) -> bool:
        """Validate multi-modal route using ValidationManager."""
        if validation_config is None:
            validation_config = {}
        config = {'route': multimodal_route}
        config.update(validation_config)
        report = self.validation_manager.validate(
            config, profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.MULTIMODAL}
        )
        return report.all_passed

    def validate_fare_and_availability(self, route: Route, travel_class: str = "SL") -> bool:
        """Validate fare and availability using ValidationManager."""
        config = {'route': route, 'travel_class': travel_class}
        report = self.validation_manager.validate(
            config, profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.FARE_AVAILABILITY}
        )
        return report.all_passed

    def validate_api_and_security(self, request_data: dict, auth_token: str) -> bool:
        """Validate API security using ValidationManager."""
        report = self.validation_manager.validate_api_request(
            request_data, auth_token, profile=ValidationProfile.STANDARD
        )
        return report.all_passed

    def validate_data_integrity(self, graph_data: dict) -> bool:
        """Validate data integrity using ValidationManager."""
        config = {'graph_data': graph_data}
        report = self.validation_manager.validate(
            config, profile=ValidationProfile.FULL,
            specific_categories={ValidationCategory.DATA_INTEGRITY}
        )
        return report.all_passed

    def validate_ai_ranking(self, ranked_routes: list, user_context: dict) -> bool:
        """Validate AI ranking using ValidationManager."""
        config = {'ranked_routes': ranked_routes, 'user_context': user_context}
        report = self.validation_manager.validate(
            config, profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.AI_RANKING}
        )
        return report.all_passed

    def validate_resilience(self, validation_config: dict = None) -> bool:
        """Run chaos / failure-recovery validations (RT-171 — RT-200)."""
        if validation_config is None:
            validation_config = {}
        report = self.validation_manager.validate(
            validation_config,
            profile=ValidationProfile.FULL,
            specific_categories={ValidationCategory.RESILIENCE}
        )
        return report.all_passed

    def validate_production_excellence(self, validation_config: dict = None) -> bool:
        """Run production-excellence validations (RT-201 — RT-220)."""
        if validation_config is None:
            validation_config = {}
        report = self.validation_manager.validate(
            validation_config,
            profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.PRODUCTION_EXCELLENCE}
        )
        return report.all_passed