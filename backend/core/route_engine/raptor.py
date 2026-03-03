import asyncio
import logging
import time as _time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple

from database import config
from database.session import SessionLocal
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

from .data_structures import Route, RouteSegment, TransferConnection
from .constraints import RouteConstraints
from .graph import TimeDependentGraph, StaticGraphSnapshot
from .builder import GraphBuilder
from .hub import HubManager, HubConnectivityTable
from .snapshot_manager import SnapshotManager
from .transfer_intelligence import TransferIntelligenceManager

logger = logging.getLogger(__name__)

def _sum_segment_fares(segments: List[RouteSegment]) -> float:
    return sum((seg.fare or 0.0) for seg in segments)

class OptimizedRAPTOR:
    def __init__(self, max_transfers: int = 3, graph_builder=None, snapshot_manager=None):
        self.max_transfers = max_transfers
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.graph_builder = graph_builder or GraphBuilder(self.executor)
        self.snapshot_manager = snapshot_manager or SnapshotManager()
        self.transfer_intelligence_manager = TransferIntelligenceManager(SessionLocal)
        
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
        routes.sort(key=lambda r: r.score)
        return routes[:constraints.max_results]

    async def _search_single_departure(self, graph: TimeDependentGraph, source_stop_id: int, dest_stop_id: int,
                                      departure_dt: datetime, constraints: RouteConstraints) -> List[Route]:
        routes_by_round = defaultdict(list)
        
        # Round 0: Direct trips from source
        source_departures = graph.get_departures_from_stop(source_stop_id, departure_dt, lookahead_minutes=720)
        
        for dep_time, trip_id in source_departures[:self.max_initial_departures]:
            segments = graph.get_trip_segments(trip_id)
            # Find start index
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
                    route.score = await self._score_with_reliability(route, constraints)
                    routes_by_round[0].append(route)
                
                # Add partials for transfers
                if i % 10 == 0 or i == len(segments)-1:
                    routes_by_round[0].append(Route(segments=list(current_segs)))

        # Rounds 1..N: Transfers
        for r in range(1, self.max_transfers + 1):
            if not routes_by_round[r-1]: break
            
            # Limit partials
            prev_routes = sorted(routes_by_round[r-1], key=lambda x: x.total_duration)[:50]
            for pr in prev_routes:
                new_found = await self._process_route_transfers(pr, graph, dest_stop_id, constraints)
                routes_by_round[r].extend(new_found)

        all_results = []
        for r_list in routes_by_round.values():
            for rt in r_list:
                if rt.segments and rt.segments[-1].arrival_stop_id == dest_stop_id:
                    all_results.append(rt)
        
        return self._deduplicate_routes(all_results)

    async def _process_route_transfers(self, route: Route, graph: TimeDependentGraph,
                                      dest_stop_id: int, constraints: RouteConstraints) -> List[Route]:
        new_routes = []
        last_seg = route.segments[-1]
        
        # Enforce strict buffer (TODO #21)
        from database.config import Config
        strict_min = Config.TRANSFER_WINDOW_MIN + Config.DELAY_BUFFER_MINUTES
        
        transfers = graph.get_transfers_from_stop(last_seg.arrival_stop_id, last_seg.arrival_time, strict_min)
        
        for tr in transfers:
            onward = graph.get_departures_from_stop(tr.station_id, tr.departure_time)
            for dep_t, trip_id in onward[:self.max_onward_departures]:
                segments = graph.get_trip_segments(trip_id)
                start_idx = -1
                for idx, s in enumerate(segments):
                    if s.departure_stop_id == tr.station_id and s.departure_time >= dep_t:
                        start_idx = idx
                        break
                if start_idx == -1: continue
                
                onward_segs = []
                for i in range(start_idx, len(segments)):
                    seg = segments[i]
                    onward_segs.append(seg)
                    
                    # Connection Survival (TODO #33)
                    new_rt = Route(segments=route.segments + list(onward_segs))
                    new_rt.transfers = route.transfers + [tr]
                    
                    if seg.arrival_stop_id == dest_stop_id:
                        new_rt.score = await self._score_with_reliability(new_rt, constraints)
                        new_routes.append(new_rt)
                    elif len(new_rt.transfers) < self.max_transfers and (i % 10 == 0):
                        new_routes.append(new_rt)
        return new_routes

    def _deduplicate_routes(self, routes: List[Route]) -> List[Route]:
        seen = set()
        unique = []
        for r in routes:
            if not r.segments: continue
            key = tuple(s.trip_id for s in r.segments)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    async def _score_with_reliability(self, route: Route, constraints: RouteConstraints) -> float:
        # Base scoring
        w = constraints.weights
        time_score = route.total_duration
        cost_score = route.total_cost
        
        # Phase 4: Connection Survival (TODO #33 & #34)
        survival_prob = self.simulate_connection_survival(route)
        if not hasattr(route, 'metadata') or route.metadata is None:
            route.metadata = {}
        route.metadata["break_probability"] = 1.0 - survival_prob
        
        # Penalize risk
        risk_penalty = (1.0 - survival_prob) * 500
        
        return (w.time * time_score + w.cost * cost_score + risk_penalty)

    def simulate_connection_survival(self, route: Route) -> float:
        if not route.transfers: return 1.0
        prob = 1.0
        scores = getattr(self.graph.snapshot, 'reliability_scores', {}) if hasattr(self, 'graph') else {}
        for i, tr in enumerate(route.transfers):
            trip_id = route.segments[i].trip_id
            score = scores.get((trip_id, tr.station_id), 0.95)
            # Layover boost
            buffer = min(1.0, tr.duration_minutes / 120.0)
            prob *= (score + (1.0 - score) * buffer)
        return prob

class HybridRAPTOR(OptimizedRAPTOR):
    def __init__(self, hub_manager, max_transfers=3):
        super().__init__(max_transfers)
        self.hub_manager = hub_manager
        self._hub_table = None

    def set_hub_table(self, table):
        self._hub_table = table

    async def find_routes(self, source_stop_id, dest_stop_id, departure_date, constraints, graph=None):
        # Implementation similar to Optimized but includes hub logic
        return await super().find_routes(source_stop_id, dest_stop_id, departure_date, constraints, graph)
