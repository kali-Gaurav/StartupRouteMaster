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

from .graph import TimeDependentGraph, StaticGraphSnapshot
from .builder import GraphBuilder
from .snapshot_manager import SnapshotManager
from .raptor import OptimizedRAPTOR, HybridRAPTOR
from .fast_router import FastPathRouter
from .hub import HubManager
from .constraints import RouteConstraints
from core.data_structures import Route
from .hybrid_engine import HybridRouteEngine
from services import multi_layer_cache

logger = logging.getLogger(__name__)

class RailwayRouteEngine:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RailwayRouteEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.snapshot_manager = SnapshotManager()
        self.graph_builder = GraphBuilder(self.executor, self.snapshot_manager)
        self.hub_manager = HubManager(SessionTransit)
        self.current_snapshot: Optional[StaticGraphSnapshot] = None
        self.current_graph: Optional[TimeDependentGraph] = None
        
        # New High-Performance Hybrid Engine
        timetable_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "timetable.npz")
        self.hybrid_engine = HybridRouteEngine(timetable_path)
        self._initialized = True

    def is_loaded(self) -> bool:
        """Check if the graph is loaded and ready."""
        return self.current_graph is not None

    def get_total_routes_count(self) -> int:
        """Get total number of routes/patterns in the graph."""
        if not self.current_snapshot: return 0
        return len(self.current_snapshot.route_patterns)

    def get_total_trains_count(self) -> int:
        """Get total number of trips in the graph."""
        if not self.current_snapshot: return 0
        return len(self.current_snapshot.trip_segments)

    async def _get_current_graph(self, date: datetime) -> TimeDependentGraph:
        async with self._lock:
            if self.current_graph and self.current_snapshot.date.date() == date.date():
                return self.current_graph
            
            snapshot = await self.snapshot_manager.load_snapshot(date)
            if not snapshot:
                logger.info(f"Engine: Building fresh graph snapshot for {date.date()}")
                self.current_graph = await self.graph_builder.build_graph(date)
                self.current_snapshot = self.current_graph.snapshot
                await self.snapshot_manager.save_snapshot(self.current_snapshot)
            else:
                logger.info(f"Engine: Loaded existing snapshot for {date.date()}")
                self.current_snapshot = snapshot
                self.current_graph = TimeDependentGraph(snapshot)
            
            # [Subtask 5.5] Trigger Predictive JIT Hydration
            asyncio.create_task(self._predictive_hydration(self.current_graph))
            
            return self.current_graph

    async def _predictive_hydration(self, graph: TimeDependentGraph):
        """
        Subtask 5.5: Predictive JIT Hydration.
        Background task to hydrate high-frequency hubs/segments into RAM.
        """
        try:
            from core.route_engine.hubs import MAJOR_HUBS
            logger.info("🧠 Predictive JIT: Hydrating major hub segments...")
            
            # Identify stop IDs for major hubs
            hub_ids = []
            for code in MAJOR_HUBS[:10]: # Top 10 hubs only to save RAM
                for sid, stop in graph.stop_cache.items():
                    if stop.code == code:
                        hub_ids.append(sid)
                        break
            
            # Pre-fetch departures for these hubs
            for hid in hub_ids:
                # This populates the internal cache of segments for these stations
                graph.get_departures_from_stop(hid, graph.snapshot.date, lookahead_minutes=1440)
                await asyncio.sleep(0.1) # Jitter to avoid CPU spike
                
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

        if not source_stop or not dest_stop:
            return []

        # 1. JIT Hierarchical Stitching (Epic 3.6)
        from .stitcher import graph_stitcher
        try:
            stitched_data = await graph_stitcher.stitch_active_graph(source_stop.id, dest_stop.id)
            if stitched_data.size > 0:
                self.hybrid_engine.update_graph_jit(stitched_data)
        except Exception as e:
            logger.error(f"Stitching failed, using global fallback: {e}")
            self.hybrid_engine.reset_graph()

        # 2. Fast Hybrid Search (100x Speedup)
        logger.info(f"🚀 Performing high-speed hybrid search: {source_code} -> {destination_code}")
        try:
            raw_results = await self.hybrid_engine.find_routes(
                source_stop.id, dest_stop.id, departure_date, constraints
            )
        finally:
            # Always reset to global to prevent stale state in kernel
            self.hybrid_engine.reset_graph()
        
        if not raw_results:
            # Fallback to legacy RAPTOR if hybrid engine has no data or no paths
            logger.warning("Hybrid engine found no paths, falling back to legacy RAPTOR.")
            graph = await self._get_current_graph(departure_date)
            raptor = OptimizedRAPTOR(max_transfers=constraints.max_transfers)
            return await raptor.find_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph)

        # 2. Map processed results back to the standard Route object
        # The hybrid engine already scores and hydrates using RouteScorer
        final_routes = []
        for res in raw_results:
            # Reconstruct the existing Route object (Stage 2 Hydration)
            rt = Route(segments=res["path"])
            rt.score = res["score"]
            rt.total_duration = res["duration_mins"]
            rt.total_cost = res["cost"]
            rt.metadata = res["metadata"]
            final_routes.append(rt)
            
        return final_routes


    def _merge_and_deduplicate(self, routes: List[Route]) -> List[Route]:
        """
        Task 27: Universal Engine Deduplicator.
        Merges routes found by multiple engines into a single unique set.
        """
        if not routes: return []
        
        unique_map = {} # journey_hash -> Route
        
        for r in routes:
            if not r.segments: continue
            
            # Create a unique key for this journey: (trip_1, dep_1), (trip_2, dep_2)...
            journey_key = tuple((s.trip_id, s.departure_time.isoformat()) for s in r.segments)
            
            if journey_key not in unique_map:
                unique_map[journey_key] = r
            else:
                # If already exists, keep the one with the better score (lower is better)
                if r.score < unique_map[journey_key].score:
                    unique_map[journey_key] = r
                    
        # Return sorted list
        final_list = list(unique_map.values())
        final_list.sort(key=lambda x: x.score)
        return final_list

    async def search_hub_routes(
        self,
        source_code: str,
        destination_code: str,
        departure_date: datetime,
        constraints: RouteConstraints,
        db: Optional[Session] = None
    ) -> List[Route]:
        from utils.station_utils import resolve_stations
        
        # Always use SessionTransit for transit entities
        res_db = SessionTransit()
        try:
            source_stop, dest_stop = resolve_stations(res_db, source_code, destination_code)
        finally:
            res_db.close()

        if not source_stop or not dest_stop:
            return []

        graph = await self._get_current_graph(departure_date)
        
        raptor = OptimizedRAPTOR(max_transfers=1)
        routes = await raptor.find_one_transfer_hub_routes(
            source_stop.id, dest_stop.id, departure_date, constraints, graph
        )
        
        return routes

    async def rebuild_snapshot(self, date: datetime):
        """Force a rebuild of the graph snapshot."""
        async with self._lock:
            logger.info(f"Engine: Forcing rebuild for {date.date()}")
            self.current_graph = await self.graph_builder.build_graph(date)
            self.current_snapshot = self.current_graph.snapshot
            await self.snapshot_manager.save_snapshot(self.current_snapshot)
            
            # Task 11.9: Record metrics for the heartbeat
            from services.multi_layer_cache import multi_layer_cache
            nodes = len(self.current_snapshot.nodes)
            edges = len(self.current_snapshot.edges)
            multi_layer_cache.record_graph_metrics(
                nodes=nodes, 
                edges=edges, 
                rebuild_time=_time.time()
            )

    async def run_nightly_refresh(self):
        """
        [19.1] Automated Nightly Refresh (2 AM).
        [19.2] Pre-builds snapshots for next 7 days.
        """
        logger.info("📅 Starting Nightly Graph Refresh...")
        start_date = datetime.now()
        
        for i in range(7):
            target_date = start_date + timedelta(days=i)
            try:
                # [19.3] Atomic Swap: SnapshotManager.save_snapshot handles persistence
                logger.info(f"  Pre-building snapshot for {target_date.date()}")
                new_graph = await self.graph_builder.build_graph(target_date)
                await self.snapshot_manager.save_snapshot(new_graph.snapshot)
                
                # If it's today, update the current active graph
                if i == 0:
                    async with self._lock:
                        self.current_graph = new_graph
                        self.current_snapshot = new_graph.snapshot
            except Exception as e:
                logger.error(f"  Failed to pre-build {target_date.date()}: {e}")
        
        logger.info("✅ Nightly Graph Refresh Complete.")
