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
from .constraints import RouteConstraints, Persona
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
        
        # Scoring ensures persona weights are applied
        for r in routes:
            if r.score == 0:
                r.score = await self._score_with_reliability(r, constraints, graph)
                
        routes.sort(key=lambda r: r.score)
        return routes[:constraints.max_results]

    async def _search_single_departure(self, graph: TimeDependentGraph, source_stop_id: int, dest_stop_id: int,
                                      departure_dt: datetime, constraints: RouteConstraints) -> List[Route]:
        routes_by_round = defaultdict(list)
        
        # Task 8: Day-of-week bitmask (Mon=1, Tue=2... Sun=64)
        weekday_bit = 1 << departure_dt.weekday()
        
        # Round 0: Direct trips from source
        source_departures = graph.get_departures_from_stop(source_stop_id, departure_dt, lookahead_minutes=720)
        
        for dep_time, trip_id in source_departures[:self.max_initial_departures]:
            segments = graph.get_trip_segments(trip_id)
            if not segments: continue
            
            # Task 8: Bitmask check
            if not (segments[0].service_mask & weekday_bit):
                continue
                
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
                    route.score = await self._score_with_reliability(route, constraints, graph)
                    routes_by_round[0].append(route)
                
                # Add partials for transfers (Task 14 / Round 1 Expansion)
                routes_by_round[0].append(Route(segments=list(current_segs)))
        
        print(f"DEBUG: Round 0 found {len(routes_by_round[0])} partial/complete routes.")

        # Rounds 1..N: Transfers
        for r in range(1, self.max_transfers + 1):
            if not routes_by_round[r-1]: 
                print(f"DEBUG: Round {r-1} empty, stopping.")
                break
            
            # Limit partials
            prev_routes = sorted(routes_by_round[r-1], key=lambda x: x.total_duration)[:50]
            print(f"DEBUG: Round {r} expanding {len(prev_routes)} previous routes.")
            for pr in prev_routes:
                new_found = await self._process_route_transfers(pr, graph, dest_stop_id, constraints)
                if new_found:
                    print(f"DEBUG: Round {r} found {len(new_found)} new routes from a partial.")
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
        
        # Task 10: Directional Consistency Check
        from utils.geo_utils import haversine_distance
        curr_stop = graph.stop_cache.get(last_seg.arrival_stop_id)
        dest_stop = graph.stop_cache.get(dest_stop_id)
        
        dist_to_dest = 0
        if curr_stop and dest_stop:
            dist_to_dest = haversine_distance(curr_stop.latitude, curr_stop.longitude, 
                                              dest_stop.latitude, dest_stop.longitude)

        # Task 7: Layover Buffer Optimization
        from .buffer_logic import buffer_optimizer
        dynamic_buffer = buffer_optimizer.calculate_required_buffer(
            last_seg.arrival_stop_id, graph.stop_cache, last_seg.arrival_time
        )
        
        transfers = graph.get_transfers_from_stop(
            last_seg.arrival_stop_id, 
            last_seg.arrival_time, 
            dynamic_buffer,
            incoming_trip_id=last_seg.trip_id # Task 13
        )
        print(f"DEBUG: last_seg.arrival_time={last_seg.arrival_time}, dynamic_buffer={dynamic_buffer}, transfers_found={len(transfers)}")
        
        for tr in transfers:
            # Task 14: Circular Route Prevention
            # We allow tr.station_id if it's the SAME as last_seg.arrival_stop_id (normal transfer),
            # but we block it if it's any OTHER station already visited.
            # Actually, visited_stations includes last_seg.arrival_stop_id. 
            # We should check if tr.station_id is in visited_stations AND is not the current stop.
            # OR better: block if the NEXT segment arrival is already visited.
            pass # Check moved inside onward loop for precision

            # Task 10: Check if transfer station moves us significantly away from destination
            tr_stop = graph.stop_cache.get(tr.station_id)
            if tr_stop and dest_stop:
                tr_dist_to_dest = haversine_distance(tr_stop.latitude, tr_stop.longitude, 
                                                     dest_stop.latitude, dest_stop.longitude)
                if tr_dist_to_dest > dist_to_dest + 100:
                    print(f"DEBUG: Pruning zig-zag at {tr_stop.name}")
                    continue

            onward = graph.get_departures_from_stop(tr.station_id, tr.departure_time)
            
            # Task 13: Rake Linkage Check
            from .rake_linkage import RakeLinkageManager
            rl_manager = RakeLinkageManager()

            for dep_t, trip_id in onward[:self.max_onward_departures]:
                # Task 13: If same rake, bypass transfer window and add bonus
                is_in_seat = rl_manager.is_same_rake(last_seg.trip_id, trip_id, tr.station_id)
                
                segments = graph.get_trip_segments(trip_id)
                start_idx = -1
                for idx, s in enumerate(segments):
                    if s.departure_stop_id == tr.station_id and s.departure_time >= dep_t:
                        # Task 3: Partial GN Compromise Check
                        # If segment requires GN/unconfirmed but persona is not EMERGENCY, block it.
                        if s.is_unconfirmed_allowed and constraints.persona != Persona.EMERGENCY:
                            continue
                        start_idx = idx
                        break
                if start_idx == -1: continue
                
                onward_segs = []
                for i in range(start_idx, len(segments)):
                    seg = segments[i]
                    
                    # Task 14: Circular Route Prevention
                    if seg.arrival_stop_id in route.visited_stations:
                        print(f"DEBUG: Pruning cycle at station {seg.arrival_stop_id}")
                        continue
                        
                    onward_segs.append(seg)
                    
                    new_rt = Route(segments=route.segments + list(onward_segs))
                    new_rt.transfers = route.transfers + [tr]
                    
                    # Recompute total cost to ensure it sums all leg fares (Task 5)
                    new_rt.total_cost = sum(s.fare for s in new_rt.segments)
                    
                    # Task 12: Flag walking transfers in metadata
                    if tr.station_id != last_seg.arrival_stop_id:
                        if not hasattr(new_rt, 'metadata') or new_rt.metadata is None:
                            new_rt.metadata = {}
                        if "walking_transfers" not in new_rt.metadata:
                            new_rt.metadata["walking_transfers"] = []
                        new_rt.metadata["walking_transfers"].append({
                            "from": last_seg.arrival_stop_id,
                            "to": tr.station_id,
                            "minutes": tr.duration_minutes
                        })
                    
                    if seg.arrival_stop_id == dest_stop_id:
                        new_rt.score = await self._score_with_reliability(new_rt, constraints, graph)
                        new_routes.append(new_rt)
                    elif len(new_rt.transfers) < self.max_transfers:
                        new_routes.append(new_rt)
        return new_routes

    async def find_one_transfer_hub_routes(self, source_stop_id: int, dest_stop_id: int,
                                         departure_date: datetime, constraints: RouteConstraints,
                                         graph: TimeDependentGraph) -> List[Route]:
        """
        Task 34.1: Graph-based search for 1-transfer hub routes.
        Task 34.5: Enforces minimum 2-hour buffer at hub.
        """
        from .hub import HubManager
        hub_manager = HubManager(SessionLocal)
        hub_manager.initialize_hubs()
        
        # 1. Round 0: Direct trips from source to any Hub
        # We collect all routes from source that reach a Hub
        source_to_hubs = []
        source_departures = graph.get_departures_from_stop(source_stop_id, departure_date, lookahead_minutes=720)
        
        for dep_time, trip_id in source_departures[:self.max_initial_departures]:
            segments = graph.get_trip_segments(trip_id)
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
                
                # Check if this stop is a Hub
                if hub_manager.is_hub(seg.arrival_stop_id):
                    route = Route(segments=list(current_segs))
                    source_to_hubs.append(route)

        # 2. Round 1: From each Hub to Destination
        hub_alternatives = []
        # Enforce Task 34.5: 2-hour buffer (120 mins)
        buffer_min = 120 
        
        for leg1 in source_to_hubs:
            hub_id = leg1.segments[-1].arrival_stop_id
            hub_arrival = leg1.segments[-1].arrival_time
            
            # Search departures from hub to destination with buffer
            onward_departures = graph.get_departures_from_stop(hub_id, hub_arrival + timedelta(minutes=buffer_min))
            
            for onward_dep_time, onward_trip_id in onward_departures[:self.max_onward_departures]:
                onward_segments = graph.get_trip_segments(onward_trip_id)
                start_idx = -1
                for idx, s in enumerate(onward_segments):
                    if s.departure_stop_id == hub_id and s.departure_time >= onward_dep_time:
                        start_idx = idx
                        break
                
                if start_idx == -1: continue
                
                current_onward = []
                for i in range(start_idx, len(onward_segments)):
                    s = onward_segments[i]
                    current_onward.append(s)
                    
                    if s.arrival_stop_id == dest_stop_id:
                        # Success! Found a hub-based 1-transfer route
                        combined_route = Route(segments=leg1.segments + list(current_onward))
                        
                        # Task 34.8: Platform Numbering (extract from Stop/StopTime if available)
                        arrival_platform = getattr(s, 'platform', None) or "N/A"
                        
                        # Record transfer info for metadata
                        tr = TransferConnection(
                            station_id=hub_id,
                            station_name="HUB", # We'll fill this later or use stop code
                            arrival_time=hub_arrival,
                            departure_time=s.departure_time,
                            duration_minutes=int((s.departure_time - hub_arrival).total_seconds() / 60),
                            facilities_score=5.0,
                            safety_score=5.0
                        )
                        combined_route.transfers = [tr]
                        # Attach platform info to metadata
                        if not hasattr(combined_route, 'metadata') or combined_route.metadata is None:
                            combined_route.metadata = {}
                        combined_route.metadata["platforms"] = {
                            "hub_arrival": getattr(leg1.segments[-1], 'platform', "N/A"),
                            "hub_departure": getattr(s, 'platform', "N/A")
                        }
                        
                        hub_alternatives.append(combined_route)
                        break # Only need best from this trip

        return self._deduplicate_routes(hub_alternatives)

    def _deduplicate_routes(self, routes: List[Route]) -> List[Route]:
        """
        Task 9 & Task 28: Dominance Filtering (Pareto Optimality).
        Removes routes that are strictly inferior to others across all dimensions.
        """
        if not routes: return []
        
        # Sort by arrival time primarily to process faster routes first
        routes.sort(key=lambda r: r.segments[-1].arrival_time if r.segments else datetime.max)
        
        pareto_frontier = []
        seen_trip_sequences = set()
        
        for r in routes:
            if not r.segments: continue
            
            # 1. Hashing for identical paths
            trip_key = tuple(s.trip_id for s in r.segments)
            if trip_key in seen_trip_sequences:
                continue
            
            # 2. Pareto Dominance Check (Task 28)
            is_dominated = False
            for p in pareto_frontier:
                # p dominates r if p is better or equal in ALL aspects and strictly better in one.
                # In our engine, 'score' already aggregates time, cost, transfers, and penalties.
                
                # Dim 1: Total Duration (Arrival Time)
                p_arr = p.segments[-1].arrival_time
                r_arr = r.segments[-1].arrival_time
                
                # Dim 2: Score (aggregated persona preference)
                if p_arr <= r_arr and p.score <= r.score:
                    # If p is faster AND has better score, r is dominated.
                    if p_arr < r_arr or p.score < r.score:
                        is_dominated = True
                        break
                    # If exactly equal, r is redundant
                    is_dominated = True
                    break
            
            if not is_dominated:
                # Keep r
                pareto_frontier.append(r)
                seen_trip_sequences.add(trip_key)
                
        return pareto_frontier

    async def _score_with_reliability(self, route: Route, constraints: RouteConstraints, graph: TimeDependentGraph) -> float:
        # Base scoring
        w = constraints.weights
        time_score = route.total_duration
        cost_score = route.total_cost
        
        # Task 15: Availability Heuristic (Confirmation Chance)
        from services.ml.availability_heuristic import availability_heuristic
        cnf_prob = availability_heuristic.get_route_availability_score(route.segments)
        
        # Phase 4: Connection Survival (TODO #33 & #34)
        survival_prob = self.simulate_connection_survival(route, graph)
        
        if not hasattr(route, 'metadata') or route.metadata is None:
            route.metadata = {}
        
        route.metadata["break_probability"] = 1.0 - survival_prob
        route.metadata["predicted_cnf_probability"] = cnf_prob
        
        # Use average probability per leg to avoid bias against multi-leg routes
        avg_cnf_prob = cnf_prob ** (1.0 / len(route.segments)) if route.segments else 1.0
        
        # Combined Risk Score
        availability_penalty = (1.0 - avg_cnf_prob) * 1000
        connection_penalty = (1.0 - survival_prob) * 500
        
        # Task 3: Partial GN Compromise (EMERGENCY ONLY)
        gn_penalty = 0
        if constraints.persona == Persona.EMERGENCY:
            for seg in route.segments:
                if seg.is_unconfirmed_allowed and seg.duration_minutes < 150:
                    # Small penalty for comfort, but allow the route to survive
                    gn_penalty += 200 
                elif seg.is_unconfirmed_allowed:
                    # Too long for GN, major penalty
                    gn_penalty += 5000
        
        # Task 1: Persona-based transfer penalty
        transfer_count_penalty = len(route.transfers) * w.transfer
        
        # Task 4: Night-Transfer Penalty
        night_penalty = 0
        if constraints.persona != Persona.EMERGENCY:
            for tr in route.transfers:
                # Night window: 23:30 to 05:00
                h = tr.arrival_time.hour
                m = tr.arrival_time.minute
                if (h == 23 and m >= 30) or (h < 5):
                    night_penalty += 1000 # Massive 16-hour penalty
                
                h_dep = tr.departure_time.hour
                if h_dep < 5:
                    night_penalty += 500
        
        # Task 6: Pantry Car Priority
        pantry_bonus = 0
        if route.total_duration > 600: # Journeys > 10 hours
            for seg in route.segments:
                if seg.has_pantry:
                    # Subtracting 60 mins from 'perceived' time per pantry leg
                    pantry_bonus -= 60 
        
        return (w.time * time_score + w.cost * cost_score + availability_penalty + connection_penalty + transfer_count_penalty + gn_penalty + night_penalty + pantry_bonus)

    def simulate_connection_survival(self, route: Route, graph: TimeDependentGraph) -> float:
        if not route.transfers: return 1.0
        prob = 1.0
        scores = getattr(graph.snapshot, 'reliability_scores', {})
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
