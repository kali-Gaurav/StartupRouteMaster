from dataclasses import dataclass
import asyncio
import logging
import time as _time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple, Union
from sqlalchemy.orm import Session

# Absolute imports for consistency
import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from core.data_structures import Route, RouteSegment, TransferConnection, Persona
from core.frontier import FrontierManager, FrontierRoute
from .constraints import RouteConstraints
from .graph import TimeDependentGraph, StaticGraphSnapshot
from core.routing.frequency_aware_range import get_frequency_aware_sizer

logger = logging.getLogger("raptor")

@dataclass(slots=True)
class SearchRoute:
    """Lightweight route representation for traversal."""
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    departure_time: datetime
    arrival_time: datetime
    round_num: int
    parent: Optional['SearchRoute'] = None
    transfer: Optional[TransferConnection] = None
    total_dist: float = 0.0
    total_wait: int = 0
    # [Task 4] Bloom-filter based cycle detection (bitmask)
    visited_bloom: int = 0

    def add_to_bloom(self, station_id: int):
        self.visited_bloom |= (1 << (station_id % 64))

    def has_cycle(self, station_id: int) -> bool:
        if not (self.visited_bloom & (1 << (station_id % 64))):
            return False
        curr = self
        while curr:
            if curr.to_stop_id == station_id or curr.from_stop_id == station_id:
                return True
            curr = curr.parent
        return False

class OptimizedRAPTOR:
    def __init__(self, max_transfers: int = 3):
        self.max_transfers = max_transfers
        self.frontier_manager = FrontierManager(max_routes_per_station=10) # Increased
        self.max_initial_departures = 500 # Increased
        self.max_onward_departures = 200 # Increased
        # [Task 27.12] Massive budget for full searching
        self.traversal_budget = 50000 
        self._nodes_explored = 0
        self._global_min_arrival_mins = float('inf')

    def _safe_fromtimestamp(self, ts: int) -> datetime:
        """[Task 27.11 Audit Fix] Safely handle timestamps for Windows compatibility."""
        try:
            # Handle both very small and very large timestamps
            # Windows max timestamp is around year 3000 (32535215999)
            capped_ts = min(32535215999, max(315532800, int(ts)))
            return datetime.fromtimestamp(capped_ts) # Safe floor 1980
        except (ValueError, OSError):
            return datetime(1980, 1, 1)

    async def find_routes(self, source_stop_id: int, dest_stop_id: int,
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: Optional[TimeDependentGraph] = None) -> List[Route]:
        self._nodes_explored = 0 
        self._global_min_arrival_mins = float('inf')
        
        # [Task 27.14] Distance-Aware Window Optimization
        if graph:
            s_stop = graph.stop_cache.get(source_stop_id)
            d_stop = graph.stop_cache.get(dest_stop_id)
            if s_stop and d_stop:
                # Simple Euclidean-ish distance check for window scaling
                dist = ((s_stop.latitude - d_stop.latitude)**2 + (s_stop.longitude - d_stop.longitude)**2)**0.5 * 111
                if dist < 50:
                    constraints.range_minutes = min(constraints.range_minutes or 1440, 240) # 4h max for terminal runs
                    logger.info(f"RAPTOR: Short-run detected ({dist:.1f}km). Window capped to 4h.")

        # [Task 9] Budget Watchdog
        start_time = _time.perf_counter()
        timeout_sec = (constraints.timeout_ms / 1000.0) if constraints.timeout_ms else 10.0 # Increased for audit
        
        def check_timeout():
            if _time.perf_counter() - start_time > timeout_sec:
                raise TimeoutError("RAPTOR search timed out")

        try:
            results = await asyncio.to_thread(self._find_routes_sync, source_stop_id, dest_stop_id, 
                                             departure_date, constraints, graph, check_timeout)
            # [Task 10] Depth Logging
            logger.info(f"RAPTOR Yield: {len(results)} routes, Traversal Depth: {self._nodes_explored} nodes.")
            return results
        except TimeoutError:
            logger.warning(f"RAPTOR search timed out. Returning partial results if available. Traversal Depth: {self._nodes_explored}")
            # If it timed out, the sync method might have been interrupted.
            # A more robust fix is to catch it inside the sync method to preserve the state.
            pass
        except Exception as e:
            logger.error(f"RAPTOR Search Error: {str(e)}")
            return []
        
        return []

    def _find_routes_sync(self, source_stop_id: int, dest_stop_id: int,
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: TimeDependentGraph, check_timeout: Any) -> List[Route]:
        if not graph: return []

        search_results = []
        try:
            # 1. Multi-Departure Search
            search_results = self._search_multi_departure_sync(graph, source_stop_id, dest_stop_id, departure_date, constraints, check_timeout)
        except TimeoutError:
            logger.warning("RAPTOR search loop timed out. Proceeding to hydrate available routes.")
            # We don't return here; we fall through to hydrate whatever is in routes_by_round

        # 2. Hydrate & Rank [Task 7]
        routes = [self._hydrate_route(sr, graph) for sr in search_results]
        routes = [r for r in routes if r and len(r.segments) > 0]
        
        if not routes: return []
        
        try:
            from services.ml.engine import MLMicroservice
            from database.session import SessionTransit
            ml_svc = MLMicroservice(SessionTransit)
            
            import nest_asyncio
            nest_asyncio.apply()
            
            async def score_routes():
                check_timeout()
                tasks = [ml_svc.get_route_reliability(r) for r in routes]
                return await asyncio.gather(*tasks)
            
            reliability_scores = asyncio.run(score_routes())
            for i, r in enumerate(routes):
                rel = reliability_scores[i]
                r.metadata["reliability_score"] = rel
                # [Task 7] Virtual Duration Scaling
                r.score = r.total_duration / max(0.1, rel)
        except Exception:
            for r in routes: r.score = r.total_duration + (len(r.transfers) * 120)

        routes.sort(key=lambda x: x.total_duration) # Requirement: Sort by travel time
        return routes[:constraints.max_results]

    def _search_multi_departure_sync(self, graph: TimeDependentGraph, source_stop_id: int, dest_stop_id: int,
                                      departure_dt: datetime, constraints: RouteConstraints, check_timeout: Any) -> List[SearchRoute]:
        """
        [Task 1a] Scan multi-departure window instead of single point.
        [Task 1b] Merge results from all departures in the window.
        """
        # [Analysis Only] Surge level detection
        from core.resource_monitor import resource_monitor, SurgeLevel
        level = resource_monitor.get_surge_level()
        if level != SurgeLevel.NORMAL:
            logger.info(f"📊 RAPTOR Surge Analysis: Level {level.name} detected. Budget: {self.traversal_budget}")

        routes_by_round = defaultdict(list)
        departure_ts = int(departure_dt.timestamp())
        self.frontier_manager.reset()

        # Round 0
        lookahead = constraints.range_minutes if constraints.range_minutes > 0 else 1440
        pattern_deps = graph.get_pattern_departures(source_stop_id, departure_dt, lookahead=lookahead)

        for pid, deps in pattern_deps.items():
            check_timeout()
            if self._nodes_explored > self.traversal_budget: break
            
            for dep_time, trip_id in deps:
                # [Task 8] Bitset Pruning - Only prune if it's the LAST possible round
                # and the trip doesn't reach the destination.
                # For round 0, we almost always want to explore for transfers.
                if self.max_transfers == 0:
                    if not graph.can_reach_destination(trip_id, dest_stop_id): continue
                
                # [Task 27.6] Overlay cancellation check
                if graph.overlay.is_cancelled(trip_id): continue

                self._nodes_explored += 1
                raw = graph.get_trip_segments_raw(trip_id)
                if raw is None: continue
                
                weekday_bit = 1 << dep_time.weekday()
                delay_secs = graph.overlay.get_trip_delay(trip_id) * 60
                dep_ts_int = int(dep_time.timestamp())
                start_found = False
                total_dist_m = 0
                
                for row in raw:
                    s_dep_sid, s_arr_sid = int(row[1]), int(row[2])
                    s_dep_ts, s_arr_ts = int(row[3]) + delay_secs, int(row[4]) + delay_secs
                    
                    if not start_found:
                        # [Audit Fix] Fuzzy match for timestamp to avoid precision jitter
                        if s_dep_sid == source_stop_id and abs(s_dep_ts - dep_ts_int) < 2:
                            if not (int(row[6]) & weekday_bit): break
                            start_found = True
                        else: continue

                    total_dist_m += int(row[5])
                    arr_mins = (s_arr_ts - departure_ts) // 60
                    wait_mins = (dep_ts_int - departure_ts) // 60
                    
                    # [Task 3] Frequency-Aware Sizing
                    f_size = get_frequency_aware_sizer(s_arr_sid, graph)
                    
                    if not self.frontier_manager.is_dominated(s_arr_sid, FrontierRoute(
                        arrival_time=arr_mins, transfers=0, total_wait=wait_mins, total_distance=total_dist_m / 1000.0
                    ), max_size=f_size):
                        sr = SearchRoute(trip_id=trip_id, from_stop_id=source_stop_id, to_stop_id=s_arr_sid,
                                         departure_time=dep_time, arrival_time=self._safe_fromtimestamp(s_arr_ts),
                                         round_num=0, total_dist=total_dist_m / 1000.0, total_wait=wait_mins)
                        sr.add_to_bloom(source_stop_id); sr.add_to_bloom(s_arr_sid)
                        routes_by_round[0].append(sr)
                        if s_arr_sid == dest_stop_id: self._global_min_arrival_mins = min(self._global_min_arrival_mins, arr_mins)

        # Onward Rounds
        for r in range(1, self.max_transfers + 1):
            if not routes_by_round[r-1]: break
            if self._nodes_explored > self.traversal_budget: break
            for psr in routes_by_round[r-1]:
                check_timeout()
                if psr.to_stop_id == dest_stop_id: continue
                new_found = self._process_transfers_sync(psr, graph, dest_stop_id, constraints, departure_dt, r, check_timeout)
                routes_by_round[r].extend(new_found)

        all_results = []
        for r_idx in range(self.max_transfers + 1):
            for sr in routes_by_round[r_idx]:
                if sr.to_stop_id == dest_stop_id: all_results.append(sr)
        return self._deduplicate_search_routes(all_results)

    def _process_transfers_sync(self, psr: SearchRoute, graph: TimeDependentGraph, dest_stop_id: int, 
                                 constraints: RouteConstraints, base_departure_dt: datetime, 
                                 round_num: int, check_timeout: Any) -> List[SearchRoute]:
        new_routes = []
        base_departure_ts = int(base_departure_dt.timestamp())
        min_tr = constraints.min_transfer_time or 15
        transfers = graph.get_transfers_from_stop(psr.to_stop_id, psr.arrival_time, min_transfer_time=min_tr, incoming_trip_id=psr.trip_id)

        for tr in transfers:
            # [Task 27.11 Audit Fix] Calculate actual earliest departure time 
            # instead of relying on tr.departure_time which might be a sentinel
            earliest_dep = psr.arrival_time + timedelta(minutes=tr.duration_minutes)
            
            lookahead = constraints.range_minutes if constraints.range_minutes > 0 else 1440
            onward = graph.get_pattern_departures(tr.station_id, earliest_dep, lookahead=lookahead)
            for pid, deps in onward.items():
                check_timeout()
                if self._nodes_explored > self.traversal_budget: break
                for dep_t, trip_id in deps[:self.max_onward_departures]:
                    if not graph.can_reach_destination(trip_id, dest_stop_id): continue
                    if graph.overlay.is_cancelled(trip_id): continue

                    self._nodes_explored += 1
                    raw = graph.get_trip_segments_raw(trip_id)
                    if raw is None: continue
                    weekday_bit = 1 << dep_t.weekday(); delay_secs = graph.overlay.get_trip_delay(trip_id) * 60
                    dep_ts_int = int(dep_t.timestamp()); start_found = False; dist_m = 0
                    for row in raw:
                        s_dep_sid, s_arr_sid = int(row[1]), int(row[2])
                        s_dep_ts, s_arr_ts = int(row[3]) + delay_secs, int(row[4]) + delay_secs
                        if not start_found:
                            if s_dep_sid == tr.station_id and abs(s_dep_ts - dep_ts_int) < 2:
                                if not (int(row[6]) & weekday_bit): break
                                start_found = True
                            else: continue
                        if psr.has_cycle(s_arr_sid): continue
                        dist_m += int(row[5])
                        total_dist = psr.total_dist + (dist_m / 1000.0)
                        total_wait = psr.total_wait + (dep_ts_int - int(psr.arrival_time.timestamp())) // 60
                        arr_mins = (s_arr_ts - base_departure_ts) // 60
                        if arr_mins > self._global_min_arrival_mins + 1440: continue
                        f_size = get_frequency_aware_sizer(s_arr_sid, graph)
                        if not self.frontier_manager.is_dominated(s_arr_sid, FrontierRoute(
                            arrival_time=arr_mins, transfers=round_num, total_wait=total_wait, total_distance=total_dist
                        ), max_size=f_size):
                            sr = SearchRoute(trip_id=trip_id, from_stop_id=tr.station_id, to_stop_id=s_arr_sid,
                                             departure_time=dep_t, arrival_time=self._safe_fromtimestamp(s_arr_ts),
                                             round_num=round_num, parent=psr, transfer=tr,
                                             total_dist=total_dist, total_wait=total_wait, visited_bloom=psr.visited_bloom)
                            sr.add_to_bloom(s_arr_sid); new_routes.append(sr)
                            if s_arr_sid == dest_stop_id: self._global_min_arrival_mins = min(self._global_min_arrival_mins, arr_mins)
        return new_routes

    def _hydrate_route(self, sr: SearchRoute, graph: TimeDependentGraph) -> Route:
        path = []; curr = sr
        while curr: path.append(curr); curr = curr.parent
        path.reverse(); full_segments = []; transfers = []
        for node in path:
            trip_segs = graph.get_trip_segments(node.trip_id)
            node_segs = []; started = False
            node_dep_ts = int(node.departure_time.timestamp())
            for s in trip_segs:
                if not started:
                    s_dep_ts = int(s.departure_time.timestamp())
                    if s.departure_stop_id == node.from_stop_id and abs(s_dep_ts - node_dep_ts) < 2: started = True
                if started:
                    node_segs.append(s)
                    if s.arrival_stop_id == node.to_stop_id: break
            full_segments.extend(node_segs)
            if node.transfer: transfers.append(node.transfer)
        rt = Route(segments=full_segments, transfers=transfers)
        rt.total_distance = sr.total_dist; rt.metadata["engine"] = "raptor_v2_window"
        return rt

    def _deduplicate_search_routes(self, routes: List[SearchRoute]) -> List[SearchRoute]:
        unique = {}
        for r in routes:
            p = []; c = r
            while c: p.append((c.trip_id, c.from_stop_id, c.to_stop_id)); c = c.parent
            k = tuple(reversed(p))
            if k not in unique or r.arrival_time < unique[k].arrival_time: unique[k] = r
        return list(unique.values())

class HybridRAPTOR(OptimizedRAPTOR):
    def __init__(self, hub_manager, max_transfers=3):
        super().__init__(max_transfers)
        self.hub_manager = hub_manager

    async def find_routes(self, source_stop_id, dest_stop_id, departure_date, constraints, graph=None):
        return await super().find_routes(source_stop_id, dest_stop_id, departure_date, constraints, graph)
