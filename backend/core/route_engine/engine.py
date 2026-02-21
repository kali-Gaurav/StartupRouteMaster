import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

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
                # Sync if remote is newer OR if we haven't synced anything yet
                # Added robust logs for Phase 10 validation
                if (not hasattr(self, "_last_synced_at") or 
                    remote_overlay.last_updated > self._last_synced_at):
                    self.current_overlay = remote_overlay
                    self._last_synced_at = remote_overlay.last_updated
                    logger.info(f"Phase 10: Synced {len(remote_overlay.delays)} delays from Redis.")
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
        # Step 0: Sync Real-time Overlay (Phase 10)
        await self.sync_realtime_overlay()

        # Step 1: Manage Static Snapshot (Daily build)
        needs_rebuild = (
            not self.current_snapshot or 
            self.current_snapshot.date.date() != date.date() or
            (self.last_snapshot_time is None) or # Rebuild if never built
            (datetime.utcnow() - self.last_snapshot_time).total_seconds() > 86400 # 24 hours
        )

        if needs_rebuild:
            # Try loading from disk first
            self.current_snapshot = await self.snapshot_manager.load_snapshot(date)
            
            if not self.current_snapshot:
                logger.info(f"Building fresh static graph snapshot for {date.date()} (Phase 2)...")
                
                # Use GraphBuilder to get a new graph
                temp_graph = await self.graph_builder.build_graph(date)
                
                # Extract snapshot data (graph.snapshot is already set by builder)
                self.current_snapshot = temp_graph.snapshot
                
                # Precompute hub connectivity (Phase 3, Step 2)
                self.hub_manager.initialize_hubs() # Ensure hubs are loaded
                hub_table = await self.hub_manager.precompute_hub_connectivity(
                    TimeDependentGraph(self.current_snapshot), # Use the newly built snapshot
                    date
                )
                self.raptor.set_hub_table(hub_table) # Set in HybridRAPTOR

                # Save to disk for future use (already done by builder)
            else:
                # If loaded from disk, ensure hub_table is also loaded or re-initialized
                # For simplicity, if snapshot is loaded, we can re-run hub precomputation
                # or serialize/deserialize hub_table with the snapshot.
                # For now, let's just ensure hubs are initialized and precompute if not.
                if not self.raptor._hub_table: # Check if hub_table is empty
                    self.hub_manager.initialize_hubs()
                    hub_table = await self.hub_manager.precompute_hub_connectivity(
                        TimeDependentGraph(self.current_snapshot), # Use the loaded snapshot
                        date
                    )
                    self.raptor.set_hub_table(hub_table)
            
            self.last_snapshot_time = datetime.utcnow()
            
        # Step 2: Overlay Layer (Copy-on-Write)
        # We create a new TimeDependentGraph that points to the snapshot but has its own overlay
        graph = TimeDependentGraph(self.current_snapshot)
        graph.overlay = self.current_overlay
        
        return graph

    async def search_routes(self, source_code: str, destination_code: str,
                           departure_date: datetime,
                           constraints: Optional[RouteConstraints] = None,
                           user_context: Optional[UserContext] = None) -> List[Route]:
        """
        Search for routes between source and destination using Hybrid Hub-RAPTOR.
        """
        if constraints is None:
            constraints = RouteConstraints()

        # Get station IDs
        session = SessionLocal()
        try:
            # Search both 'code' and 'stop_id' for source and destination
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

            # Step 1: Get the current graph (Snapshot + Overlay)
            graph = await self._get_current_graph(departure_date)

            # Step 2: Execute RAPTOR search (Delegates to HybridRAPTOR for Phase 3)
            routes = await self.raptor.find_routes(
                source_stop.id, dest_stop.id, departure_date, constraints, graph=graph
            )

            # Step 3: Apply ML ranking if user context provided
            if user_context:
                routes = await self._apply_ml_ranking(routes, user_context)

            # Step 4: Apply Booking Intelligence Unlock Logic (Phase 7)
            if self.seat_manager:
                # Mark first 3 unlocked
                for i, route in enumerate(routes):
                    route.is_locked = i >= 3
                
                # Silent Prefetching for top 2 routes (Point 12)
                # Note: This is an async fire-and-forget task
                asyncio.create_task(self._prefetch_availability(routes[:2], departure_date))

            return routes

        finally:
            session.close()

    async def _prefetch_availability(self, top_routes: List[Route], date: datetime):
        """Background task to prefetch seat availability for top routes."""
        if not self.seat_manager:
            return
            
        date_str = date.strftime("%Y-%m-%d") # API Expected format for IRCTC1 V1
        
        # Bridge domain objects to manager expected format
        prefetch_items = []
        for route in top_routes:
            if not route.segments:
                continue
            
            # Prefetch for the first train segment
            seg = route.segments[0]
            if seg.train_number:
                # We need station codes. For now we assume they are passed or resolvable.
                # In production, Segment object carries station codes.
                prefetch_items.append({
                    "train_number": seg.train_number,
                    "from_station": getattr(seg, 'from_code', 'ST'), # Placeholder resolution
                    "to_station": getattr(seg, 'to_code', 'BVI'),
                    "date": date_str
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