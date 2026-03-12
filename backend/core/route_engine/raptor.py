import asyncio
import logging
import time as _time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple
from sqlalchemy.orm import Session

from database import config
from database.session import SessionTransit
from database.models import Stop
from services.multi_layer_cache import multi_layer_cache, RouteQuery

# Logic to handle both absolute and package-relative imports
try:
    from ..routing.frequency_aware_range import get_frequency_aware_sizer
    from ...services.ml.reliability_model import get_reliability_model
except (ImportError, ValueError):
    # Fallback for script execution
    import sys
    import os
    backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if backend_path not in sys.path:
        sys.path.append(backend_path)
    from core.routing.frequency_aware_range import get_frequency_aware_sizer
    from services.ml.reliability_model import get_reliability_model

from core.data_structures import Route, RouteSegment, TransferConnection
from .constraints import RouteConstraints, Persona
from .graph import TimeDependentGraph, StaticGraphSnapshot
from .builder import GraphBuilder
from .hub import HubManager, HubConnectivityTable
from .snapshot_manager import SnapshotManager
from .transfer_intelligence import TransferIntelligenceManager
from .scoring import RouteScorer

logger = logging.getLogger(__name__)

class OptimizedRAPTOR:
    def __init__(self, max_transfers: int = 3, graph_builder=None, snapshot_manager=None):
        self.max_transfers = max_transfers
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.graph_builder = graph_builder or GraphBuilder(self.executor)
        self.snapshot_manager = snapshot_manager or SnapshotManager()
        self.transfer_intelligence_manager = TransferIntelligenceManager(SessionTransit)
        
        self.max_initial_departures = 100
        self.max_onward_departures = 50

    async def find_routes(self, source_stop_id: int, dest_stop_id: int,
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: Optional[TimeDependentGraph] = None) -> List[Route]:
        # [5.18] Low Yield Trigger: Check for direct routes first (lightweight)
        # For simplicity in this engine, we just use the existing thread pool logic
        return await asyncio.to_thread(self._find_routes_sync, source_stop_id, dest_stop_id, departure_date, constraints, graph)

    def _find_routes_sync(self, source_stop_id: int, dest_stop_id: int,
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: Optional[TimeDependentGraph] = None) -> List[Route]:
        if graph is None:
            from .snapshot_manager import SnapshotManager
            sm = SnapshotManager()
            import asyncio
            loop = asyncio.new_event_loop()
            snapshot = loop.run_until_complete(sm.load_snapshot(departure_date))
            loop.close()

            if snapshot:
                graph = TimeDependentGraph(snapshot=snapshot)
            else:
                return []

        # [5.18] Low Yield Detection: Check for direct routes first
        # We simulate a "direct" search by setting max_transfers=0 temporarily
        original_max = self.max_transfers
        self.max_transfers = 0
        direct_routes = self._search_single_departure_sync(graph, source_stop_id, dest_stop_id, departure_date, constraints)
        
        if len(direct_routes) < 3:
            # TRIGGER: Increase depth and lookahead
            logger.info(f"Low Yield detected for {source_stop_id}->{dest_stop_id}. Triggering Deep RAPTOR.")
            self.max_transfers = original_max if original_max > 0 else 2
            self.max_initial_departures = 200
            routes = self._search_single_departure_sync(graph, source_stop_id, dest_stop_id, departure_date, constraints)
        else:
            routes = direct_routes
            
        self.max_transfers = original_max # Reset

        # Batch scoring
        reliability = getattr(graph.snapshot, 'reliability_scores', {})
        for r in routes:
            if r.score == 0:
                r.score = r.total_duration

        routes.sort(key=lambda r: r.score)
        return routes[:constraints.max_results]

    def _search_single_departure_sync(self, graph: TimeDependentGraph, source_stop_id: int, dest_stop_id: int,
                                      departure_dt: datetime, constraints: RouteConstraints) -> List[Route]:
        routes_by_round = defaultdict(list)
        weekday_bit = 1 << departure_dt.weekday()

        # [5.1] Get initial departures from source
        source_departures = graph.get_departures_from_stop(source_stop_id, departure_dt, lookahead_minutes=720)
        
        # [5.12] Multi-round earliest arrival with strict Dominance
        # best_arrival[station] = earliest time seen so far across ANY round
        global_best_arrival = defaultdict(lambda: datetime.max)
        global_best_arrival[source_stop_id] = departure_dt

        # round_best_arrival[round][station]
        round_best_arrival = defaultdict(lambda: defaultdict(lambda: datetime.max))
        round_best_arrival[0][source_stop_id] = departure_dt

        for dep_time, trip_id in source_departures[:self.max_initial_departures]:
            segments = graph.get_trip_segments(trip_id)
            if not segments: continue
            
            start_idx = -1
            for idx, s in enumerate(segments):
                if s.departure_stop_id == source_stop_id and s.departure_time >= dep_time:
                    if not (s.service_mask & weekday_bit): break
                    start_idx = idx
                    break

            if start_idx == -1: continue

            current_segs = []
            for i in range(start_idx, len(segments)):
                seg = segments[i]
                current_segs.append(seg)
                
                arr_st = seg.arrival_stop_id
                # [5.12] Dominance: Only keep if better than global best
                if seg.arrival_time < global_best_arrival[arr_st]:
                    global_best_arrival[arr_st] = seg.arrival_time
                    round_best_arrival[0][arr_st] = seg.arrival_time
                    route = Route(segments=list(current_segs))
                    routes_by_round[0].append(route)

        # Process Rounds (Transfers)
        for r in range(1, self.max_transfers + 1):
            if not routes_by_round[r-1]: break
            
            # [5.12] Prune current round candidates: only keep the best arrival per station from the PREVIOUS round
            stations_to_explore = {}
            for rt in routes_by_round[r-1]:
                last_st = rt.segments[-1].arrival_stop_id
                if last_st not in stations_to_explore or rt.segments[-1].arrival_time < stations_to_explore[last_st].segments[-1].arrival_time:
                    stations_to_explore[last_st] = rt
            
            for pr in stations_to_explore.values():
                if pr.segments[-1].arrival_stop_id == dest_stop_id: continue
                
                new_found = self._process_route_transfers_sync(pr, graph, dest_stop_id, constraints, global_best_arrival, r)
                routes_by_round[r].extend(new_found)
            
            if not routes_by_round[r]: break

        all_results = []
        for r_idx in range(self.max_transfers + 1):
            for rt in routes_by_round[r_idx]:
                if rt.segments and rt.segments[-1].arrival_stop_id == dest_stop_id:
                    all_results.append(rt)

        return self._deduplicate_routes(all_results)

    def _process_route_transfers_sync(self, route: Route, graph: TimeDependentGraph,
                                      dest_stop_id: int, constraints: RouteConstraints,
                                      round_earliest: Dict[int, datetime], round_num: int) -> List[Route]:
        new_routes = []
        last_seg = route.segments[-1]
        weekday_bit = 1 << last_seg.arrival_time.weekday()

        # [5.11] Cycle detection
        visited_stations = {s.departure_stop_id for s in route.segments} | {s.arrival_stop_id for s in route.segments}
        visited_trips = {s.trip_id for s in route.segments}

        transfers = graph.get_transfers_from_stop(
            last_seg.arrival_stop_id,
            last_seg.arrival_time,
            min_transfer_time=45,
            incoming_trip_id=last_seg.trip_id
        )

        for tr in transfers:
            onward = graph.get_departures_from_stop(tr.station_id, tr.departure_time, lookahead_minutes=1440)

            for dep_t, trip_id in onward[:self.max_onward_departures]:
                if trip_id in visited_trips: continue 

                segments = graph.get_trip_segments(trip_id)
                start_idx = -1
                for idx, s in enumerate(segments):
                    if s.departure_stop_id == tr.station_id and s.departure_time >= dep_t:
                        if not (s.service_mask & weekday_bit): break
                        start_idx = idx
                        break
                if start_idx == -1: continue

                onward_segs = []
                for i in range(start_idx, len(segments)):
                    seg = segments[i]
                    # [5.11] Prevent revisiting stations
                    if seg.arrival_stop_id in visited_stations: continue
                    onward_segs.append(seg)

                    # [5.12] Multi-objective Dominance (simplified to time)
                    if seg.arrival_time < round_earliest[seg.arrival_stop_id]:
                        round_earliest[seg.arrival_stop_id] = seg.arrival_time
                        
                        new_rt = Route(segments=route.segments + list(onward_segs))
                        new_rt.transfers = route.transfers + [tr]

                        if seg.arrival_stop_id == dest_stop_id or round_num < self.max_transfers:
                            new_routes.append(new_rt)
        return new_routes
    async def find_one_transfer_hub_routes(self, source_stop_id: int, dest_stop_id: int,
                                         departure_date: datetime, constraints: RouteConstraints,
                                         db: Session) -> List[Route]:
        """
        Specialized search for one-transfer routes specifically passing through major hubs.
        [34.2] Hub-centric optimization.
        """
        # For now, we can use the general find_routes logic restricted to 1 transfer
        original_max = self.max_transfers
        self.max_transfers = 1
        try:
            return await self.find_routes(source_stop_id, dest_stop_id, departure_date, constraints)
        finally:
            self.max_transfers = original_max

    def _deduplicate_routes(self, routes: List[Route]) -> List[Route]:
        if not routes: return []
        
        from utils.algo_utils import find_pareto_frontier
        import numpy as np
        
        # [33.1] Define Multi-Objective Dimensions
        # Dimensions: [Arrival Timestamp, Final Score, Total Cost, Transfer Count]
        data = np.array([
            [
                r.segments[-1].arrival_time.timestamp() if r.segments else datetime.max.timestamp(),
                r.score,
                r.total_cost,
                len(r.transfers)
            ]
            for r in routes
        ], dtype=np.float64)
        
        # [33.2] Vectorized Pareto Filtering with more dimensions
        # This prevents a slow-cheap route from dominating a fast-expensive one.
        mask = find_pareto_frontier(data)
        pareto_routes = [routes[i] for i in range(len(routes)) if mask[i]]
        
        # [33.8] Analytics Logging
        logger.info(f"Pareto Pruning: {len(routes)} -> {len(pareto_routes)} optimal routes.")
        
        # 3. Path-based final deduplication (Keep only one per train-sequence)
        unique_map = {}
        for r in pareto_routes:
            # We use train_numbers + dep_times as the unique path key
            path_key = tuple((s.train_number or s.trip_id, s.departure_time.isoformat()) for s in r.segments)
            if path_key not in unique_map or r.score < unique_map[path_key].score:
                unique_map[path_key] = r
                
        return list(unique_map.values())

class HybridRAPTOR(OptimizedRAPTOR):
    def __init__(self, hub_manager, max_transfers=3):
        super().__init__(max_transfers)
        self.hub_manager = hub_manager
        self._hub_table = None

    def set_hub_table(self, table):
        self._hub_table = table

    async def find_routes(self, source_stop_id, dest_stop_id, departure_date, constraints, graph=None):
        return await super().find_routes(source_stop_id, dest_stop_id, departure_date, constraints, graph)
