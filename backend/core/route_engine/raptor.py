import asyncio
import logging
import time as _time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple

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
        if graph is None:
            snapshot = await self.snapshot_manager.load_snapshot(departure_date)
            if snapshot:
                graph = TimeDependentGraph(snapshot=snapshot)
            else:
                graph = await self.graph_builder.build_graph(departure_date)
        
        if not graph: return []

        # Multi-day Range-RAPTOR support
        if constraints.range_minutes > 0:
            half = constraints.range_minutes // 2
            departure_times = [departure_date + timedelta(minutes=m) for m in range(-half, half + 1, 30)]
            collected = []
            for dt in departure_times:
                res = await self._search_single_departure(graph, source_stop_id, dest_stop_id, dt, constraints)
                collected.extend(res)
            
            unique = self._deduplicate_routes(collected)
            unique.sort(key=lambda r: r.score)
            return unique[:constraints.max_results]

        routes = await self._search_single_departure(graph, source_stop_id, dest_stop_id, departure_date, constraints)
        
        # Scoring ensures persona weights are applied
        for r in routes:
            if r.score == 0:
                r.score = await RouteScorer.score_route(r, constraints, getattr(graph.snapshot, 'reliability_scores', {}))
                
        routes.sort(key=lambda r: r.score)
        return routes[:constraints.max_results]

    async def _search_single_departure(self, graph: TimeDependentGraph, source_stop_id: int, dest_stop_id: int,
                                      departure_dt: datetime, constraints: RouteConstraints) -> List[Route]:
        routes_by_round = defaultdict(list)
        weekday_bit = 1 << departure_dt.weekday()
        
        source_departures = graph.get_departures_from_stop(source_stop_id, departure_dt, lookahead_minutes=720)
        
        for dep_time, trip_id in source_departures[:self.max_initial_departures]:
            segments = graph.get_trip_segments(trip_id)
            if not segments: continue
            if not (segments[0].service_mask & weekday_bit): continue
                
            start_idx = -1
            for idx, s in enumerate(segments):
                if s.departure_stop_id == source_stop_id and s.departure_time >= dep_time:
                    start_idx = idx
                    break
            
            if start_idx == -1: continue
            
            current_segs = []
            for i in range(start_idx, len(segments)):
                seg = segments[i]
                current_segs.append(seg)
                
                if seg.arrival_stop_id == dest_stop_id:
                    route = Route(segments=list(current_segs))
                    route.score = await RouteScorer.score_route(route, constraints, getattr(graph.snapshot, 'reliability_scores', {}))
                    routes_by_round[0].append(route)
                
                routes_by_round[0].append(Route(segments=list(current_segs)))

        for r in range(1, self.max_transfers + 1):
            if not routes_by_round[r-1]: break
            prev_routes = sorted(routes_by_round[r-1], key=lambda x: x.total_duration)[:50]
            for pr in prev_routes:
                new_found = await self._process_route_transfers(pr, graph, dest_stop_id, constraints)
                routes_by_round[r].extend(new_found)

        all_results = []
        for round_idx, r_list in routes_by_round.items():
            for rt in r_list:
                if rt.segments and rt.segments[-1].arrival_stop_id == dest_stop_id:
                    all_results.append(rt)
        
        return self._deduplicate_routes(all_results)

    async def _process_route_transfers(self, route: Route, graph: TimeDependentGraph,
                                      dest_stop_id: int, constraints: RouteConstraints) -> List[Route]:
        new_routes = []
        last_seg = route.segments[-1]
        
        from utils.geo_utils import haversine_distance
        curr_stop = graph.stop_cache.get(last_seg.arrival_stop_id)
        dest_stop = graph.stop_cache.get(dest_stop_id)
        
        dist_to_dest = 0
        if curr_stop and dest_stop:
            dist_to_dest = haversine_distance(curr_stop.latitude, curr_stop.longitude, 
                                              dest_stop.latitude, dest_stop.longitude)

        from .buffer_logic import buffer_optimizer
        dynamic_buffer = buffer_optimizer.calculate_required_buffer(
            last_seg.arrival_stop_id, graph.stop_cache, last_seg.arrival_time
        )
        
        transfers = graph.get_transfers_from_stop(
            last_seg.arrival_stop_id, 
            last_seg.arrival_time, 
            dynamic_buffer,
            incoming_trip_id=last_seg.trip_id
        )
        
        for tr in transfers:
            tr_stop = graph.stop_cache.get(tr.station_id)
            if tr_stop and dest_stop:
                tr_dist_to_dest = haversine_distance(tr_stop.latitude, tr_stop.longitude, 
                                                     dest_stop.latitude, dest_stop.longitude)
                if tr_dist_to_dest > dist_to_dest + 100: continue

            onward = graph.get_departures_from_stop(tr.station_id, tr.departure_time)
            
            for dep_t, trip_id in onward[:self.max_onward_departures]:
                segments = graph.get_trip_segments(trip_id)
                start_idx = -1
                for idx, s in enumerate(segments):
                    if s.departure_stop_id == tr.station_id and s.departure_time >= dep_t:
                        if s.is_unconfirmed_allowed and constraints.persona != Persona.EMERGENCY: continue
                        start_idx = idx
                        break
                if start_idx == -1: continue
                
                onward_segs = []
                for i in range(start_idx, len(segments)):
                    seg = segments[i]
                    if seg.arrival_stop_id in route.visited_stations: continue
                    onward_segs.append(seg)
                    
                    new_rt = Route(segments=route.segments + list(onward_segs))
                    new_rt.transfers = route.transfers + [tr]
                    new_rt.total_cost = sum(s.fare for s in new_rt.segments)
                    
                    if seg.arrival_stop_id == dest_stop_id:
                        new_routes.append(new_rt)
                    elif len(new_rt.transfers) < self.max_transfers:
                        new_routes.append(new_rt)
        return new_routes

    def _deduplicate_routes(self, routes: List[Route]) -> List[Route]:
        if not routes: return []
        
        from utils.algo_utils import find_pareto_frontier
        import numpy as np
        
        # 1. Feature Extraction for Pareto (Duration, Score)
        # Using Score as second dimension because it includes Cost and Penalties
        data = np.array([
            [r.segments[-1].arrival_time.timestamp() if r.segments else datetime.max.timestamp(), r.score]
            for r in routes
        ], dtype=np.float64)
        
        # 2. Vectorized Pareto Filtering
        mask = find_pareto_frontier(data)
        pareto_routes = [routes[i] for i in range(len(routes)) if mask[i]]
        
        # 3. Path-based final deduplication (Keep only one per trip sequence)
        seen_trip_sequences = set()
        final_results = []
        for r in pareto_routes:
            trip_key = tuple(s.trip_id for s in r.segments)
            if trip_key not in seen_trip_sequences:
                final_results.append(r)
                seen_trip_sequences.add(trip_key)
                
        return final_results

class HybridRAPTOR(OptimizedRAPTOR):
    def __init__(self, hub_manager, max_transfers=3):
        super().__init__(max_transfers)
        self.hub_manager = hub_manager
        self._hub_table = None

    def set_hub_table(self, table):
        self._hub_table = table

    async def find_routes(self, source_stop_id, dest_stop_id, departure_date, constraints, graph=None):
        return await super().find_routes(source_stop_id, dest_stop_id, departure_date, constraints, graph)
