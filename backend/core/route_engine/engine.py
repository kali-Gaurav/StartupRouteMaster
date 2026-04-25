import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, cast
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session
from database.session import SessionTransit
from .graph import TimeDependentGraph, StaticGraphSnapshot, RealtimeOverlay
from .builder import GraphBuilder
from .snapshot_manager import SnapshotManager
from .constraints import RouteConstraints
from core.data_structures import Route, Persona
from .orchestrator import UnifiedRoutingOrchestrator
from services import multi_layer_cache
from services.r2_sync_service import r2_sync

logger = logging.getLogger(__name__)

from core.providers import ServiceProvider
from core.container import container

class RailwayRouteEngine(ServiceProvider):
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RailwayRouteEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'name') and self.name == "search": return
        super().__init__("search", version="3.1.0")
        
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.snapshot_manager = SnapshotManager()
        self.graph_builder = GraphBuilder(self.executor, self.snapshot_manager)
        self.overlay = RealtimeOverlay()
        
        self.graph: Optional[TimeDependentGraph] = None
        self.graph_initialized = False
        
        # SWR Engine State Flags
        self.last_rebuild_status = "INIT"
        self._is_building = False
        
        self.orchestrator = UnifiedRoutingOrchestrator(self)

    async def init(self, date_override: Optional[datetime] = None, force_rebuild: bool = False):
        """IoC Lifecycle: Ensure graph is warm."""
        from core.providers import ServiceStatus
        if self.status == ServiceStatus.HEALTHY and not force_rebuild:
            return
            
        logger.info("🚂 [NEXUS:SEARCH] Initializing RailwayRouteEngine and pre-warming graph...")
        await self._get_current_graph(date_override or datetime.now(), force_rebuild=force_rebuild)
        self.graph_initialized = True
        self.status = ServiceStatus.HEALTHY
        logger.info("✅ [NEXUS:SEARCH] Route Engine is HOT and ready.")

    def is_loaded(self) -> bool:
        """Backward compatibility method for is_loaded() calls."""
        return self.graph_initialized

    async def shutdown(self):
        logger.info("Engine shutdown.")
        self.graph = None
        self.graph_initialized = False

    async def _background_build_and_swap(self, date: datetime, force_rebuild: bool = False):
        """[SWR Core] Background worker that builds the graph and performs an atomic swap."""
        if getattr(self, '_is_building', False):
            return
        
        self._is_building = True
        try:
            logger.info(f"🔄 [SWR] Background graph rebuild started for {date.date()}")
            
            # Fetch or build graph
            snapshot = await self.snapshot_manager.load_snapshot(date) if not force_rebuild else None
            is_nexus_grade = snapshot and hasattr(snapshot, '_trip_reachability_bitset') and \
                 getattr(snapshot, 'cluster_reachability', None) is not None
                 
            if not snapshot or not is_nexus_grade:
                logger.info(f"🔄 [SWR] Building fresh Nexus-Grade graph...")
                new_graph = await self.graph_builder.build_graph(date)
                if new_graph.snapshot:
                    asyncio.create_task(self.snapshot_manager.save_snapshot(new_graph.snapshot))
                    
                # [Nexus:Cloud] Background R2 Sync
                async def _sync_to_cloud():
                    await asyncio.sleep(10)
                    await r2_sync.upload_transit_db()
                    await r2_sync.upload_latest_snapshot()
                asyncio.create_task(_sync_to_cloud())
            else:
                new_graph = TimeDependentGraph(snapshot, overlay=self.overlay)
                
            # Atomic Swap (GIL makes reference assignment atomic)
            new_graph.overlay = self.overlay
            self.graph = new_graph
            
            self.last_rebuild_status = "READY_FRESH"
            logger.info(f"✅ [SWR] Background rebuild complete. Atomic swap successful.")
            
            asyncio.create_task(self._predictive_hydration(self.graph))
        except Exception as e:
            logger.error(f"❌ [SWR] Background rebuild failed: {e}")
            self.last_rebuild_status = "FAILED"
        finally:
            self._is_building = False

    async def _get_current_graph(self, date: datetime, force_rebuild: bool=False) -> Optional[TimeDependentGraph]:
        # Path 1: Fresh Graph exists in memory
        if self.graph and self.graph.snapshot and getattr(self.graph.snapshot, 'date', None) and self.graph.snapshot.date.date() == date.date() and not force_rebuild:
            self.graph.overlay = self.overlay
            self.last_rebuild_status = "READY_FRESH"
            return self.graph
            
        # Path 2: Stale Graph exists in memory (SWR Fallback)
        if self.graph and self.graph.snapshot:
            self.last_rebuild_status = "READY_STALE"
            if not getattr(self, '_is_building', False):
                asyncio.create_task(self._background_build_and_swap(date, force_rebuild))
            return self.graph
            
        # Path 3: Cold Start (Block only if absolutely nothing is available)
        async with self._lock:
            # Check if another request built it while we waited
            if self.graph: return self.graph
            
            # Try to load exactly what they want
            snapshot = await self.snapshot_manager.load_snapshot(date) if not force_rebuild else None
            
            # SWR Fallback: Try to load any available snapshot to avoid blocking
            if not snapshot:
                snapshot = await self.snapshot_manager.get_latest_snapshot_fallback()
                if snapshot:
                    self.graph = TimeDependentGraph(snapshot, overlay=self.overlay)
                    self.last_rebuild_status = "READY_STALE"
                    if not getattr(self, '_is_building', False):
                        asyncio.create_task(self._background_build_and_swap(date, force_rebuild))
                    return self.graph

            # Ultimate Slow Path: Block and build if no snapshots exist anywhere
            self.last_rebuild_status = "REBUILDING"
            await self._background_build_and_swap(date, force_rebuild)
            return self.graph

    async def _predictive_hydration(self, graph: TimeDependentGraph):
        try:
            from core.hubs import MAJOR_HUBS
            logger.info("🧠 Predictive JIT: Hydrating major hub segments...")
            hub_ids = [cast(int, stop.id) for code in list(MAJOR_HUBS)[:20] if (stop := graph.get_stop_by_code(code))]
            for hid in hub_ids:
                if graph.snapshot:
                    graph.get_departures_from_stop(hid, graph.snapshot.date, lookahead=1440)
                await asyncio.sleep(0.1)
            logger.info(f"✅ Predictive JIT: Hydrated {len(hub_ids)} hub clusters.")
        except Exception as e:
            logger.error(f"Predictive Hydration Error: {e}")

    async def search(
        self,
        source_code: str,
        destination_code: str,
        departure_date: datetime,
        constraints: RouteConstraints,
        db: Optional[Session] = None
    ) -> List[Route]:
        start_time = time.time()
        
        from utils.station_utils import resolve_stations
        res_db = db if db else SessionTransit()
        try:
            source_stop, dest_stop = resolve_stations(res_db, source_code, destination_code)
        finally:
            if not db: res_db.close()
        if not source_stop or not dest_stop: return []

        graph = await self._get_current_graph(departure_date)
        if not graph: return []

        logger.info(f"🚀 [SEARCH] Orchestrating High-Speed search for {source_code}->{destination_code}")
        
        # [Nexus Fix] Use the unified orchestrator search which handles phases and parallelism internally
        from .base import RoutingRequest
        req = RoutingRequest(
            source_code=source_code,
            destination_code=destination_code,
            departure_date=departure_date,
            constraints=constraints,
            limit=constraints.max_results,
            db_session=res_db
        )
        
        results = await self.orchestrator.search_all_tiers(req)
        
        logger.info(f"✅ Search Complete for {source_code}->{destination_code} in {(time.time() - start_time)*1000:.2f}ms. Returning {len(results)} routes.")
        return results

# ... (rest of the file remains the same)
# search_hub_routes, rebuild_snapshot, run_nightly_refresh
# ...

route_engine = RailwayRouteEngine()
container.register(route_engine)

def get_route_engine():
    return RailwayRouteEngine()
