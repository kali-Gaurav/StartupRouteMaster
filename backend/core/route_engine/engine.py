import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
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
        
        self.orchestrator = UnifiedRoutingOrchestrator(self)

    async def init(self, date_override: Optional[datetime] = None, force_rebuild: bool = False):
        logger.info("🚂 [NEXUS:SEARCH] Initializing RailwayRouteEngine and pre-warming graph...")
        await self._get_current_graph(date_override or datetime.now(), force_rebuild=force_rebuild)
        self.graph_initialized = True
        logger.info("✅ [NEXUS:SEARCH] Route Engine is HOT and ready.")

    async def shutdown(self):
        logger.info("Engine shutdown.")
        self.graph = None
        self.graph_initialized = False

    async def _get_current_graph(self, date: datetime, force_rebuild: bool=False) -> Optional[TimeDependentGraph]:
        async with self._lock:
            if self.graph and self.graph.snapshot.date.date() == date.date() and not force_rebuild:
                self.graph.overlay = self.overlay
                return self.graph
            
            snapshot = await self.snapshot_manager.load_snapshot(date) if not force_rebuild else None
            is_nexus_grade = snapshot and hasattr(snapshot, '_trip_reachability_bitset') and snapshot._trip_reachability_bitset is not None
            
            if not snapshot or not is_nexus_grade:
                logger.info(f"Engine: Building fresh Nexus-Grade graph for {date.date()}")
                self.graph = await self.graph_builder.build_graph(date)
            else:
                logger.info(f"Engine: Loaded existing Nexus-Grade snapshot for {date.date()}")
                self.graph = TimeDependentGraph(snapshot, overlay=self.overlay)
            
            if self.graph:
                self.graph.overlay = self.overlay
                asyncio.create_task(self._predictive_hydration(self.graph))
            
            return self.graph

    async def _predictive_hydration(self, graph: TimeDependentGraph):
        try:
            from core.hubs import MAJOR_HUBS
            logger.info("🧠 Predictive JIT: Hydrating major hub segments...")
            hub_ids = [stop.id for code in list(MAJOR_HUBS)[:20] if (stop := graph.get_stop_by_code(code))]
            for hid in hub_ids:
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

        logger.info(f"🚀 [SEARCH] Phase 1: High-Speed search for {source_code}->{destination_code}")
        
        phase1_engines = ["UltraTurbo", "TBR"]
        fast_results = await self.orchestrator.run_search_phase(
            phase1_engines, source_code, destination_code, departure_date, constraints, source_stop, dest_stop, graph
        )
        
        logger.info(f"📊 [SEARCH] Phase 1 yielded {len(fast_results)} unique routes.")
        
        DEFAULT_MIN_YIELD = 15
        if len(fast_results) < DEFAULT_MIN_YIELD:
            logger.warning(f"📉 [SEARCH] Low yield ({len(fast_results)}), triggering Phase 2: RAPTOR Deep Search.")
            
            raptor_results = await self.orchestrator.run_search_phase(
                ["RAPTOR"], source_code, destination_code, departure_date, constraints, source_stop, dest_stop, graph
            )
            
            existing_jids = {r.journey_id for r in fast_results}
            for route in raptor_results:
                if route.journey_id not in existing_jids:
                    fast_results.append(route)
            logger.info(f"📊 [SEARCH] Phase 2 expanded yield to {len(fast_results)} routes.")

        final_results = fast_results
        if constraints.persona in (Persona.BUDGET, Persona.ECONOMY):
            final_results.sort(key=lambda x: (x.total_cost or 99999, x.total_duration or 99999))
        else:
            final_results.sort(key=lambda x: x.score or 0, reverse=True)
            
        await self.orchestrator.hydration_pipeline.execute(final_results, constraints, graph, res_db)
        
        logger.info(f"✅ Search Complete for {source_code}->{destination_code} in {(time.time() - start_time)*1000:.2f}ms. Returning {len(final_results)} routes.")
        return final_results[:constraints.max_results]

# ... (rest of the file remains the same)
# search_hub_routes, rebuild_snapshot, run_nightly_refresh
# ...

route_engine = RailwayRouteEngine()
container.register(route_engine)
