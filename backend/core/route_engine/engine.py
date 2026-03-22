import asyncio
import logging
import os
import time as _time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

from sqlalchemy.orm import Session
from database.session import SessionTransit, engine_transit as engine
from database.models import (
    Trip as TripModel,
    Stop as StopModel,
    StopTime as StopTimeModel,
    Route as RouteModel,
    Calendar as CalendarModel
)

from .graph import TimeDependentGraph, StaticGraphSnapshot, RealtimeOverlay
from .builder import GraphBuilder
from .snapshot_manager import SnapshotManager
from .raptor import OptimizedRAPTOR, HybridRAPTOR
from .fast_router import FastPathRouter
from .hub import HubManager
from .constraints import RouteConstraints
from core.data_structures import Route
from .hybrid_engine import HybridRouteEngine
from .orchestrator import UnifiedRoutingOrchestrator
from services import multi_layer_cache

logger = logging.getLogger(__name__)

from core.providers import ServiceProvider, ServiceStatus
from core.container import container

class RailwayRouteEngine(ServiceProvider):
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RailwayRouteEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent double init from __new__ if already a ServiceProvider
        if hasattr(self, 'name') and self.name == "search": return
        super().__init__("search", version="3.0.0")
        
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.snapshot_manager = SnapshotManager()
        self.graph_builder = GraphBuilder(self.executor, self.snapshot_manager)
        
        # [Task 27.11] Centralized Overlay for entire system
        self.overlay = RealtimeOverlay()
        
        self.current_snapshot: Optional[StaticGraphSnapshot] = None
        self.current_graph: Optional[TimeDependentGraph] = None
        self.hybrid_engine = None
        self.hub_manager = None

    async def init(self):
        """IoC Lifecycle: Load Hybrid Engine, Hubs, and predictive snapshots."""
        print("DEBUG: [RailwayRouteEngine] IoC Init Starting")
        timetable_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "timetable.npz")
        self.hybrid_engine = HybridRouteEngine(timetable_path)
        
        self.hub_manager = HubManager(SessionTransit)
        try:
            self.hub_manager.initialize_hubs()
        except Exception as e:
            logger.error(f"Hub Initialization Failed: {e}")
            
        # Optional: Pre-load today's graph
        try:
            g = await self._get_current_graph(datetime.now())
            # [Task 27.18] Warmup call with correct arguments
            if g:
                for hub_id in [5533, 3099]: # NDLS, HWH
                    g.get_departures_from_stop(hub_id, datetime.now(), lookahead=240)
        except Exception as e:
            logger.warning(f"Predictive Warmup Failed: {e}")
        
        logger.info("🚂 IoC: RailwayRouteEngine (Search) Initialized.")

    async def fallback(self):
        """If full graph fails, we might still have Hybrid Kernel in shared memory."""
        await super().fallback()
        logger.warning("📉 IoC: Search engine in Degraded mode (Graph missing).")

    def is_loaded(self) -> bool:
        return self.current_graph is not None

    async def _get_current_graph(self, date: datetime) -> TimeDependentGraph:
        async with self._lock:
            if self.current_graph and self.current_snapshot.date.date() == date.date():
                # Ensure existing graph is linked to centralized overlay
                self.current_graph.overlay = self.overlay
                return self.current_graph
            
            snapshot = await self.snapshot_manager.load_snapshot(date)
            if not snapshot:
                logger.info(f"Engine: Building fresh graph snapshot for {date.date()}")
                self.current_graph = await self.graph_builder.build_graph(date)
                self.current_graph.overlay = self.overlay # Force link
                self.current_snapshot = self.current_graph.snapshot
                await self.snapshot_manager.save_snapshot(self.current_snapshot)
            else:
                logger.info(f"Engine: Loaded existing snapshot for {date.date()}")
                self.current_snapshot = snapshot
                self.current_graph = TimeDependentGraph(snapshot, overlay=self.overlay)
            
            # [Subtask 5.5] Trigger Predictive JIT Hydration
            asyncio.create_task(self._predictive_hydration(self.current_graph))
            
            return self.current_graph

    async def _predictive_hydration(self, graph: TimeDependentGraph):
        try:
            from core.hubs import MAJOR_HUBS
            logger.info("🧠 Predictive JIT: Hydrating major hub segments...")
            hub_ids = []
            for code in MAJOR_HUBS[:10]:
                for sid, stop in graph.stop_cache.items():
                    if stop.code == code:
                        hub_ids.append(sid)
                        break
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
        from utils.station_utils import resolve_stations
        res_db = db if db else SessionTransit()
        try:
            source_stop, dest_stop = resolve_stations(res_db, source_code, destination_code)
        finally:
            if not db: res_db.close()

        if not source_stop or not dest_stop: return []

        # 1. JIT Hierarchical Stitching
        from .stitcher import graph_stitcher
        try:
            stitched_data = await graph_stitcher.stitch_active_graph(source_stop.id, dest_stop.id)
            if stitched_data.size > 0:
                self.hybrid_engine.update_graph_jit(stitched_data)
        except Exception as e:
            logger.error(f"Stitching failed, using global fallback: {e}")
            self.hybrid_engine.reset_graph()

        # 2. Fast Hybrid Search
        logger.info(f"🚀 Performing high-speed hybrid search: {source_code} -> {destination_code}")
        try:
            raw_results = await self.hybrid_engine.find_routes(source_stop.id, dest_stop.id, departure_date, constraints)
        finally:
            self.hybrid_engine.reset_graph()
        
        if not raw_results:
            logger.warning("Hybrid engine found no paths, falling back to legacy RAPTOR.")
            graph = await self._get_current_graph(departure_date)
            raptor = OptimizedRAPTOR(max_transfers=constraints.max_transfers)
            return await raptor.find_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph)

        final_routes = []
        for res in raw_results:
            rt = Route(segments=res["path"])
            rt.score = res["score"]; rt.total_duration = res["duration_mins"]
            rt.total_cost = res["cost"]; rt.metadata = res["metadata"]
            final_routes.append(rt)
        return final_routes

    async def search_hub_routes(
        self,
        source_code: str,
        destination_code: str,
        departure_date: datetime,
        constraints: RouteConstraints,
        db: Optional[Session] = None
    ) -> List[Route]:
        from utils.station_utils import resolve_stations
        res_db = SessionTransit()
        try:
            source_stop, dest_stop = resolve_stations(res_db, source_code, destination_code)
        finally:
            res_db.close()

        if not source_stop or not dest_stop: return []
        graph = await self._get_current_graph(departure_date)
        raptor = OptimizedRAPTOR(max_transfers=1)
        return await raptor.find_one_transfer_hub_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph)

    async def rebuild_snapshot(self, date: datetime):
        async with self._lock:
            logger.info(f"Engine: Forcing rebuild for {date.date()}")
            self.current_graph = await self.graph_builder.build_graph(date)
            self.current_graph.overlay = self.overlay # Link overlay
            self.current_snapshot = self.current_graph.snapshot
            await self.snapshot_manager.save_snapshot(self.current_snapshot)
            
            from services.multi_layer_cache import multi_layer_cache
            multi_layer_cache.record_graph_metrics(
                nodes=len(self.current_snapshot.nodes), 
                edges=len(self.current_snapshot.edges), 
                rebuild_time=_time.time()
            )

    async def run_nightly_refresh(self):
        logger.info("📅 Starting Nightly Graph Refresh...")
        start_date = datetime.now()
        for i in range(7):
            target_date = start_date + timedelta(days=i)
            try:
                logger.info(f"  Pre-building snapshot for {target_date.date()}")
                new_graph = await self.graph_builder.build_graph(target_date)
                new_graph.overlay = self.overlay # Link overlay
                await self.snapshot_manager.save_snapshot(new_graph.snapshot)
                if i == 0:
                    async with self._lock:
                        self.current_graph = new_graph
                        self.current_snapshot = new_graph.snapshot
            except Exception as e:
                logger.error(f"  Failed to pre-build {target_date.date()}: {e}")
        logger.info("✅ Nightly Graph Refresh Complete.")

route_engine = RailwayRouteEngine()
container.register(route_engine)
