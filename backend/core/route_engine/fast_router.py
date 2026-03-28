import time
import logging
from typing import List, Dict, Tuple, Set, Union
from datetime import datetime, timedelta

from core.data_structures import Route, RouteSegment, TransferConnection
from .graph import TimeDependentGraph
from .constraints import RouteConstraints

logger = logging.getLogger(__name__)

class FastPathRouter:
    """
    10X PERFORMANCE BFS ROUTER.
    Uses pre-computed station_schedule and train_path for O(1) lookups.
    Now optimized for PURE DIRECT ROUTES, with transfers handled by TBR.
    """
    def __init__(self, graph: TimeDependentGraph):
        self.graph = graph

    def find_routes(self, source_ids: List[int], dest_ids: List[int], date: datetime, constraints: RouteConstraints) -> List[Route]:
        # FastPathRouter now exclusively focuses on direct routes,
        # leveraging the graph's efficient lookup capabilities.
        # Transfer routes are handled by the TBR engine via the Orchestrator.
        
        window_start = date
        window_end = date + timedelta(hours=24) # Search for 24 hours from departure_date
        
        all_found: List[Route] = []
        
        for s_id in source_ids:
            for d_id in dest_ids:
                all_found.extend(self._find_direct(s_id, d_id, window_start, window_end))
        
        return self._deduplicate(all_found)

    def _find_direct(self, source_id: int, dest_id: int, start: datetime, end: datetime) -> List[Route]:
        routes = []
        deps = self.graph.get_departures_from_stop(source_id, start, 1440) # 1440 minutes = 24 hours
        for dep_time, tid in deps:
            # Use O(1) bitset check for extreme performance instead of sets
            if self.graph.can_reach_destination(tid, dest_id):
                segs = self._get_segments(tid, source_id, dest_id)
                if segs:
                    rt = Route(segments=segs)
                    rt.metadata["engine"] = "fastpath_direct"
                    routes.append(rt)
        return routes

    def _get_segments(self, tid: int, sid_src: int, sid_dst: int) -> List[RouteSegment]:
        all_segs = self.graph.get_trip_segments(tid)
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
