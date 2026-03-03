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

    async def search_routes(
        self,
        source_code: str,
        destination_code: str,
        departure_date: datetime,
        constraints: RouteConstraints,
        db: Optional[Session] = None
    ) -> List[Route]:
        from utils.station_utils import resolve_stations
        
        # Use provided transit_db or fallback
        res_db = db if db else SessionLocal()
        try:
            source_stop, dest_stop = resolve_stations(res_db, source_code, destination_code)
        finally:
            if not db: res_db.close()

        if not source_stop or not dest_stop:
            return []

        graph = await self._get_current_graph(departure_date)
        
        # 1. RAPTOR Search
        raptor = OptimizedRAPTOR(max_transfers=constraints.max_transfers)
        routes = await raptor.find_routes(source_stop.id, dest_stop.id, departure_date, constraints, graph)
        
        return routes

    async def rebuild_snapshot(self, date: datetime):
        """Force a rebuild of the graph snapshot."""
        async with self._lock:
            logger.info(f"Engine: Forcing rebuild for {date.date()}")
            self.current_graph = await self.graph_builder.build_graph(date)
            self.current_snapshot = self.current_graph.snapshot
            await self.snapshot_manager.save_snapshot(self.current_snapshot)
