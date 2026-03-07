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
        from database.session import SessionTransit
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
            
            return self.current_graph

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

        # 1. Fast Hybrid Search (100x Speedup)
        # Using the CSA kernel to find optimal paths first
        logger.info(f"🚀 Performing high-speed hybrid search: {source_code} -> {destination_code}")
        raw_results = await self.hybrid_engine.find_routes(
            source_stop.id, dest_stop.id, departure_date, constraints
        )
        
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
        from database.session import SessionTransit
        
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
