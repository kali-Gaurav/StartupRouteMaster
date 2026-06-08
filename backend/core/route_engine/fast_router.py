import time
import logging
import asyncio
from typing import List, Dict, Tuple, Set, Union, Optional
from datetime import datetime, timedelta

from core.data_utils.structures import Route, RouteSegment, TransferConnection, ensure_datetime
from .graph import TimeDependentGraph
from .constraints import RouteConstraints
from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse

logger = logging.getLogger(__name__)

class FastPathRouter(BaseRoutingEngine):
    @property
    def engine_id(self) -> str:
        return "fastpath_bfs"
    """
    10X PERFORMANCE BFS ROUTER.
    Uses pre-computed station_schedule and train_path for O(1) lookups.
    Now optimized for PURE DIRECT ROUTES, with transfers handled by TBR.
    """
    def __init__(self, graph: Optional[TimeDependentGraph] = None):
        self.graph: Optional[TimeDependentGraph] = graph

    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        graph = request.graph or self.graph
        if not graph:
            from .engine import route_engine
            graph = await route_engine._get_current_graph(request.departure_date)
            self.graph = graph
        if not graph:
            return RoutingResponse(engine_name=self.engine_id, routes=[], latency_ms=0.0, yield_count=0)
        return await asyncio.to_thread(self._find_routes_sync, request, graph)

    def _find_routes_sync(self, request: RoutingRequest, graph: TimeDependentGraph) -> RoutingResponse:
        # FastPathRouter: Hybrid Hub-Centric Search
        # 1. Direct Routes (Fastest)
        # 2. 2-Hub Transfers (Discovery)
        
        source_ids = request.src_cluster_ids
        dest_ids = request.dst_cluster_ids
        date = request.departure_date
        constraints = request.constraints
        
        start_time = time.perf_counter()
        window_start = date
        window_end = date + timedelta(hours=24)
        
        all_found: List[Route] = []
        
        # Phase 1: Direct
        for s_id in source_ids:
            for d_id in dest_ids:
                all_found.extend(self._find_direct(s_id, d_id, window_start, window_end, graph))
        
        # Phase 2: 2-Hub Transfer (Only if yield from Phase 1 is low or explicitly deep)
        if len(all_found) < 5 or getattr(constraints, 'search_depth', 'SHALLOW') != 'SHALLOW':
             from core.engines.hubs import MEGA_HUBS, MAJOR_HUBS, HUB_COORDINATES
             
             # Resolve local hubs
             src_hubs = [h for h in source_ids if (stop := graph.stop_cache.get(h)) and (stop.code in MEGA_HUBS or stop.code in MAJOR_HUBS)]
             dst_hubs = [h for h in dest_ids if (stop := graph.stop_cache.get(h)) and (stop.code in MEGA_HUBS or stop.code in MAJOR_HUBS)]
             
             if src_hubs and dst_hubs:
                  for s_hub in src_hubs:
                       for d_hub in dst_hubs:
                            # Use TBR-style lightweight expansion for hub connectivity
                            all_found.extend(self._find_2_hub_transfers(s_hub, d_hub, window_start, window_end, graph))

        unique_routes = self._deduplicate(all_found)
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        for r in unique_routes:
            if "engine" not in r.metadata:
                r.metadata["engine"] = self.engine_id
                
        return RoutingResponse(
            engine_name=self.engine_id,
            routes=unique_routes[:request.limit],
            latency_ms=latency_ms,
            yield_count=len(unique_routes)
        )

    def _find_2_hub_transfers(self, s_hub: int, d_hub: int, start: datetime, end: datetime, graph: TimeDependentGraph) -> List[Route]:
        # Implementation of 2-hub transfer search logic here
        # For now, we use a middle-hub lookup if any intermediary hub connects both
        from core.engines.hubs import MEGA_HUBS
        results = []
        # Find hubs that can be reached from s_hub AND can reach d_hub
        # This is a classic BFS-2
        deps = graph.get_departures_from_stop(s_hub, start, 1440)
        for dep_time, tid in deps:
             # Get all stops for this trip
             stops = graph.get_trip_segments(tid)
             for s in stops:
                  mid_hub = s.arrival_stop_id
                  mid_stop = graph.stop_cache.get(mid_hub)
                  if mid_stop and mid_stop.code in MEGA_HUBS and mid_hub != s_hub:
                       # Check if mid_hub connects to d_hub
                       arrival_time = s.arrival_time if isinstance(s.arrival_time, datetime) else ensure_datetime(s.arrival_time, reference=start)
                       connection_deps = graph.get_departures_from_stop(mid_hub, arrival_time + timedelta(minutes=30), 1440)
                       for c_dep_time, c_tid in connection_deps:
                            if graph.can_reach_destination(c_tid, d_hub):
                                 # Found a 2-train hub transfer!
                                 segs1 = self._get_segments(tid, s_hub, mid_hub, graph)
                                 segs2 = self._get_segments(c_tid, mid_hub, d_hub, graph)
                                 if segs1 and segs2:
                                      rt = Route(segments=segs1 + segs2)
                                      rt.metadata["engine"] = "fastpath_2hub"
                                      results.append(rt)
                                      if len(results) > 10: return results # Limit discovery
        return results

    def _find_direct(self, source_id: int, dest_id: int, start: datetime, end: datetime, graph: TimeDependentGraph) -> List[Route]:
        routes = []
        deps = graph.get_departures_from_stop(source_id, start, 1440)
        for dep_time, tid in deps:
            if graph.can_reach_destination(tid, dest_id):
                segs = self._get_segments(tid, source_id, dest_id, graph)
                if segs:
                    rt = Route(segments=segs)
                    rt.metadata["engine"] = "fastpath_direct"
                    routes.append(rt)
        return routes

    def _get_segments(self, tid: int, sid_src: int, sid_dst: int, graph: TimeDependentGraph) -> List[RouteSegment]:
        all_segs = graph.get_trip_segments(tid)
        res, started = [], False
        for s in all_segs:
            if s.departure_stop_id == sid_src: started = True
            if started:
                res.append(s)
                if s.arrival_stop_id == sid_dst: return res
        return []

    def _deduplicate(self, routes: List[Route]) -> List[Route]:
        seen = set()
        unique = []
        for r in routes:
            key = tuple(s.trip_id for s in r.segments)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
