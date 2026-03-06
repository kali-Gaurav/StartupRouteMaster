import asyncio
import logging
import time as _time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

from sqlalchemy.orm import Session
from database.session import SessionLocal, engine_transit as engine
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
from .data_structures import Route
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
        
        res_db = db if db else SessionLocal()
        try:
            source_stop, dest_stop = resolve_stations(res_db, source_code, destination_code)
        finally:
            if not db: res_db.close()

        if not source_stop or not dest_stop:
            return []

        graph = await self._get_current_graph(departure_date)
        
        # Task 22: Level 0 - Direct Pre-computation
        from .direct_index import get_direct_manager
        from database.session import SessionTransit
        t_db = SessionTransit()
        direct_manager = get_direct_manager(t_db)
        direct_trip_ids = direct_manager.get_direct_trips(source_stop.id, dest_stop.id)
        t_db.close()
        
        direct_routes = []
        if direct_trip_ids:
            print(f"DEBUG: Found {len(direct_trip_ids)} candidate trips in direct index.")
            # Task 8: Check bitmask for these direct trips
            weekday_bit = 1 << departure_date.weekday()
            for tid in direct_trip_ids:
                segments = graph.get_trip_segments(tid)
                if not segments: 
                    print(f"DEBUG: Trip {tid} has no segments in graph.")
                    continue
                if not (segments[0].service_mask & weekday_bit):
                    continue
                
                # Filter specific segments for this OD pair
                route_segs = []
                started = False
                for s in segments:
                    if s.departure_stop_id == source_stop.id: started = True
                    if started:
                        route_segs.append(s)
                        if s.arrival_stop_id == dest_stop.id: break
                
                if route_segs and route_segs[-1].arrival_stop_id == dest_stop_id:
                    print(f"DEBUG: Trip {tid} successfully forms a direct route.")
                    # 1. Add the normal direct route
                    rt = Route(segments=route_segs)
                    raptor_scorer = OptimizedRAPTOR()
                    rt.score = await raptor_scorer._score_with_reliability(rt, constraints, graph)
                    direct_routes.append(rt)
                    
                    # 2. Task 16: Check for earlier major stations on this SAME trip
                    trip_segs = graph.get_trip_segments(tid)
                    print(f"DEBUG: Trip {tid} has {len(trip_segs)} total segments.")
                    
                    # Find our current source index in the full trip
                    current_src_idx = -1
                    for idx, s in enumerate(trip_segs):
                        if s.departure_stop_id == source_stop.id:
                            current_src_idx = idx
                            break
                    
                    print(f"DEBUG: current_src_idx={current_src_idx}")
                    if current_src_idx > 0:
                        # Look at every segment starting before our current source
                        for i in range(current_src_idx):
                            prev_stop_id = trip_segs[i].departure_stop_id
                            prev_stop = graph.stop_cache.get(prev_stop_id)
                            
                            if prev_stop and getattr(prev_stop, 'is_major_junction', False):
                                print(f"DEBUG: Found major junction {prev_stop.code} at index {i}")
                                # We found a major junction! Create the virtual route.
                                # It's segments from 'i' all the way to 'current_src_idx + len(route_segs)'
                                v_segs = trip_segs[i : current_src_idx + len(route_segs)]
                                
                                if v_segs and v_segs[-1].arrival_stop_id == dest_stop.id:
                                    print(f"DEBUG: Successfully created virtual route for Task 16.")
                                    v_rt = Route(segments=v_segs)
                                    v_rt.score = await raptor_scorer._score_with_reliability(v_rt, constraints, graph)
                                    
                                    if not hasattr(v_rt, 'metadata') or v_rt.metadata is None:
                                        v_rt.metadata = {}
                                    v_rt.metadata["boarding_point_trick"] = True
                                    v_rt.metadata["suggested_boarding_code"] = prev_stop.code
                                    direct_routes.append(v_rt)
                                    break

        # 1. RAPTOR Search
        raptor = OptimizedRAPTOR(max_transfers=constraints.max_transfers)
        routes = await raptor.find_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph)
        
        # Combine and Deduplicate
        final_list = self._merge_and_deduplicate(direct_routes + routes)
        return final_list

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
