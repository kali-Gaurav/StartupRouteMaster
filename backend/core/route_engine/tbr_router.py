import logging
import asyncio
import time as _time
import heapq
import os
import pickle
import math
import numpy as np
from collections import defaultdict
from datetime import datetime
from typing import List, Optional, Any, Dict, Set, Tuple, Union, cast

from core.data_structures import Route, RouteSegment, TransferConnection, ensure_datetime
from core.route_engine.constraints import RouteConstraints
from core.route_engine.graph import TimeDependentGraph, MemMapManager
from core.frontier import FrontierManager, FrontierRoute
from utils.station_utils import get_metro_group_codes
from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse

logger = logging.getLogger("tbr_router")

# [Issue 14] Constants for strict routing
MAX_COMPRESSED_SEGMENTS = 10
MAX_TRANSFERS_LIMIT = 5

MIN_TRANSFER_BUFFER_SEC = 900 # 15 minutes default
AVG_TRAIN_SPEED_KMPH = 60

class SearchState:
    """[Issue 5] Thread-safe state object (no pooling)."""
    __slots__ = ('trip_id', 'stop_id', 'arr_ts', 'dep_ts', 'round_num', 'parent', 'wait_mins', 'boarded_idx')
    
    def __init__(self, tid=0, sid=0, arr=0, dep=0, round_num=0, parent=None, wait=0, b_idx=0):
        self.trip_id = tid
        self.stop_id = sid
        self.arr_ts = arr
        self.dep_ts = dep
        self.round_num = round_num
        self.parent = parent
        self.wait_mins = wait
        self.boarded_idx = b_idx

def haversine(lat1, lon1, lat2, lon2):
    """[Issue 1] Real distance for heuristic."""
    R = 6371 # km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class TripBasedRouter(BaseRoutingEngine):
    @property
    def engine_id(self) -> str:
        return "tbr_v4_a_star"
    """
    Subtask 1.7: Trip-Based Routing (TBR) Engine Core (V4 A* Optimized).
    """
    def __init__(self, max_transfers: int = 3):
        self.max_transfers = max_transfers
        self.frontier_manager = FrontierManager(max_routes_per_station=60)
        self.traversal_budget = 800000 
        self._nodes_explored = 0
        
        from database.config import Config
        data_dir = Config.DATA_DIR
        try:
            self._edges = MemMapManager.load_array("tbr_edges")
            self._edge_index_mmap = MemMapManager.load_array("tbr_edge_index")
            
            lookup_map_path = os.path.join(data_dir, "tbr_edge_lookup_map.pkl")
            trip_stops_map_path = os.path.join(data_dir, "tbr_trip_to_stops_map.pkl")
            if os.path.exists(lookup_map_path):
                with open(lookup_map_path, "rb") as f:
                    self._edge_lookup_map = pickle.load(f)
            else:
                self._edge_lookup_map = {}
                
            if os.path.exists(trip_stops_map_path):
                with open(trip_stops_map_path, "rb") as f:
                    self._trip_to_stops_map = pickle.load(f)
            else:
                self._trip_to_stops_map = {}
                
            if self._edges is not None and self._edge_index_mmap is not None:
                logger.info(f"🚄 TBR: Loaded {len(self._edges)} transfer edges and {len(self._edge_index_mmap)} index entries from {data_dir}")
        except Exception as e:
            logger.warning(f"⚠️ TBR: Failed to load transfer graph: {e}")
            self._edges = None
            self._edge_index_mmap = None
            self._edge_lookup_map = {}
            self._trip_to_stops_map = {}

    async def get_graph(self, date: datetime):
        from .engine import route_engine
        return await route_engine._get_current_graph(date)

    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        source_stop_id = request.src_cluster_ids
        dest_stop_id = request.dst_cluster_ids
        departure_date = request.departure_date
        constraints = request.constraints
        graph = request.graph
        limit = request.limit
        load_more = request.metadata.get("load_more", False)

        if not graph: 
            graph = await self.get_graph(departure_date)
        if graph is None:
            return RoutingResponse(
                engine_name=self.engine_id,
                routes=[],
                latency_ms=0.0,
                yield_count=0,
                triage_status="FAILED",
                metadata={"error": "GRAPH_UNAVAILABLE"},
            )
            
        # [Gap 3] Adaptive Search Budget based on distance
        s_id = source_stop_id[0] if isinstance(source_stop_id, list) else source_stop_id
        d_id = dest_stop_id[0] if isinstance(dest_stop_id, list) else dest_stop_id
        src_stop = graph.stop_cache.get(int(s_id))
        dst_stop = graph.stop_cache.get(int(d_id))
        
        # [Nexus Upgrade] Expanded Base Budget for High-Performance Local SSD
        # Since we migrated to C-Drive/LocalSSD, we can afford 4x more node explorations
        depth_map = {"SHALLOW": 100000, "MEDIUM": 250000, "DEEP": 600000}
        requested_depth = getattr(constraints, 'search_depth', 'SHALLOW')
        base_budget = depth_map.get(requested_depth, 100000)
        
        if load_more:
             base_budget *= 2 # Extra boost for load more requests
        
        if src_stop is not None and dst_stop is not None:
            dist = haversine(src_stop.latitude, src_stop.longitude, dst_stop.latitude, dst_stop.longitude)
            # Scale budget: Long journeys need MUCH deeper searches (up to 2,000,000 nodes for Cross-Country)
            distance_multiplier = min(5.0, max(1.0, dist / 400.0)) 
            self.traversal_budget = int(base_budget * distance_multiplier)
            logger.info(f"🚀 [TBR:NEXUS] Adaptive Budget scaled to {self.traversal_budget} (Depth: {requested_depth}, Mode: {'Deep' if load_more else 'Fast'})")
        else:
            self.traversal_budget = base_budget

        self._nodes_explored = 0
        start_time = _time.perf_counter()
        timeout_sec = (constraints.timeout_ms / 1000.0) if constraints.timeout_ms else 10.0
        
        def check_timeout():
            if _time.perf_counter() - start_time > timeout_sec:
                raise TimeoutError("TBR search timed out")

        try:
            results = await asyncio.to_thread(
                self._find_routes_sync, source_stop_id, dest_stop_id, 
                departure_date, constraints, graph, check_timeout, load_more
            )
            latency_ms = (_time.perf_counter() - start_time) * 1000
            
            final_routes = results[:limit]
            
            logger.info(f"TBR Final: {len(final_routes)} routes in {latency_ms:.2f}ms. (Load More: {load_more})")
            
            return RoutingResponse(
                engine_name=self.engine_id,
                routes=final_routes,
                latency_ms=latency_ms,
                yield_count=len(final_routes),
                metadata={"nodes_explored": self._nodes_explored}
            )
            
        except (TimeoutError, asyncio.TimeoutError):
            logger.warning(f"TBR search timed out after {timeout_sec}s.")
            return RoutingResponse(
                engine_name=self.engine_id, 
                routes=[], 
                latency_ms=(_time.perf_counter() - start_time) * 1000, 
                yield_count=0, 
                triage_status="FAILED",
                metadata={"error": "TIMEOUT"}
            )
        except Exception as e:
            logger.error(f"TBR Search Error: {str(e)}", exc_info=True)
            return RoutingResponse(
                engine_name=self.engine_id, 
                routes=[], 
                latency_ms=(_time.perf_counter() - start_time) * 1000, 
                yield_count=0, 
                triage_status="FAILED",
                metadata={"error": str(e)}
            )

    def _find_routes_sync(self, source_id: Union[int, List[int]], dest_id: Union[int, List[int]],
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: TimeDependentGraph, check_timeout: Any,
                         load_more: bool = False) -> List[Route]:
        if not graph.snapshot: return []
        trip_nodes = getattr(graph.snapshot, 'tbr_trip_nodes', None)
        t_index = getattr(graph.snapshot, 'tbr_trip_index', {})
        if trip_nodes is None or not t_index: return []

        if isinstance(source_id, list):
            src_ids = set(source_id)
        else:
            src_ids = {source_id}
            src_stop = graph.stop_cache.get(int(source_id))
            if src_stop:
                for code in get_metro_group_codes(src_stop.code):
                    s = graph.get_stop_by_code(code)
                    if s: src_ids.add(int(cast(Any, s.id)))

        if isinstance(dest_id, list):
            dst_ids = set(dest_id)
        else:
            dst_ids = {dest_id}
            dst_stop = graph.stop_cache.get(int(dest_id))
            if dst_stop:
                for code in get_metro_group_codes(dst_stop.code):
                    d = graph.get_stop_by_code(code)
                    if d: dst_ids.add(int(cast(Any, d.id)))

        # 1. Local Caches and Variables
        _reach_cache = {}
        bridge_sids = set()
        if constraints and getattr(constraints, 'metadata', None):
                bridges = constraints.metadata.get("cross_cluster_bridges", {})
                for hc in bridges.get("src_hubs", []) + bridges.get("dst_hubs", []):
                  h_stop = graph.get_stop_by_code(hc)
                  if h_stop: bridge_sids.add(int(cast(Any, h_stop.id)))
        
        delay_lookup = {}
        # [Yield Fix] Store multiple labels per stop/round with Diversity tracking
        # [Yield Fix] Variety tracking per (stop, round)
        variety_labels = defaultdict(lambda: defaultdict(list))
        # best_arrival[stop_id][round_num] = absolute best time found so far
        best_arrival = defaultdict(lambda: defaultdict(lambda: float('inf')))
        # [Task 42.6] best_cost[stop_id][round_num]
        best_cost = defaultdict(lambda: defaultdict(lambda: float('inf')))
        
        self.cost_fn = self.calculate_generalized_cost
        self.constraints = constraints
        
        # [Task 42.1] Define Quotas for diverse transfer-counts (Generation 12.1 High Yield Overhaul)
        quotas = {0: 300, 1: 200, 2: 100, 3: 50, 4: 30, 5: 20}
        if load_more:
            quotas = {0: 500, 1: 300, 2: 200, 3: 100, 4: 60, 5: 40}
        
        # [Yield Modification] Massive slack and pareto limits for maximum 2, 3 transfer yields
        slack_sec = 86400 if load_more else 43200 # 24h or 12h slack
        max_labels_per_stop = 35 if load_more else 25 # Increased Pareto yield limit
        
        # 2. Closure Functions
        def get_delay(tid):
            if tid not in delay_lookup:
                delay_lookup[tid] = graph.overlay.get_trip_delay(tid) * 60
            return delay_lookup[tid]

        def can_reach_goal_or_hub(tid):
            if tid not in _reach_cache:
                # [Task 146] Dual-Bitset Pruning (Intelligence)
                # 1. Can we reach any of the destination stops?
                at_goal = any(graph.can_reach_destination(tid, d_id) for d_id in dst_ids)
                if at_goal:
                     _reach_cache[tid] = True
                else:
                     # 2. Relaxed constraint: if it has ANY precomputed outgoing transfers, it's valid
                     has_tbr_transfers = (tid in _trip_to_stops_map)
                     _reach_cache[tid] = has_tbr_transfers or graph.can_reach_any_hub(tid)
            
            return _reach_cache.get(tid, False)

        # [Nexus Elite: Fast Heuristic] Manhattan-Euclidean Approximation (Task 121)
        # Using fixed degree-to-meter constants for India (Lat ~20N)
        DEG_TO_KM_Y = 111.1
        DEG_TO_KM_X = 104.4 # Approx scaled for cos(20 deg)
        _h_cache = {}

        def get_heuristic(curr_sid: int, goal_sids: Set[int]) -> int:
            if curr_sid in _h_cache: return _h_cache[curr_sid]
            
            snapshot = cast(Any, graph.snapshot)
            c_mat = getattr(snapshot, 'coordinate_matrix', None) if snapshot is not None else None
            if c_mat is None: 
                # Fallback to legacy stop_cache if matrix missing
                _h_cache[curr_sid] = 0
                return 0
            
            sid_idx = snapshot.stop_id_to_idx.get(curr_sid) if snapshot is not None else None
            if sid_idx is None: 
                _h_cache[curr_sid] = 0
                return 0
            
            curr_y, curr_x = c_mat[sid_idx]
            min_km = 999999.0
            
            for d_id in goal_sids:
                did_idx = snapshot.stop_id_to_idx.get(d_id) if snapshot is not None else None
                if did_idx is None: continue
                dy, dx = c_mat[did_idx]
                # Manhattan-Euclidean (Faster than Haversine for A* search)
                km = abs(curr_y - dy) * DEG_TO_KM_Y + abs(curr_x - dx) * DEG_TO_KM_X
                if km < min_km: min_km = km
                
            h_mins = int(min_km / 0.75) # 0.75 km/min admissible estimate
            _h_cache[curr_sid] = h_mins * 60 # Return in seconds for A*
            return _h_cache[curr_sid]

        # 3. Hot Loop Local References
        _edge_index_mmap = self._edge_index_mmap
        _edge_lookup_map = self._edge_lookup_map
        _trip_to_stops_map = self._trip_to_stops_map
        _edges_arr = self._edges
        _tbr_nodes = trip_nodes
        _tbr_idx = t_index
        # [Task 12.1] Sync transfer limit with constraints
        _transfers_limit = getattr(constraints, 'max_transfers', MAX_TRANSFERS_LIMIT)
        _min_buffer = MIN_TRANSFER_BUFFER_SEC
        departure_ts = int(departure_date.timestamp())

        # O(1) Trip-Stop lookup (Task 121: Elite Migration)
        # We now use the snapshot's pre-computed trip mapping where possible
        s_lookup = getattr(graph.snapshot, '_trip_to_pid', {})

        # Seed Queue
        pq = []
        range_min = (constraints.range_minutes or 1440) * (2 if load_more else 1)
        logger.info(f"🔍 TBR: Starting A* v4 Search (Yield Optimized) for {source_id} -> {dest_id}")
        seen_initial_trips = set()
        filtered_by_reach = 0
        total_deps = 0
        skipped_idx = 0; skipped_seq = 0; pq_pushed = 0
        for sid in src_ids:
            deps = graph.get_departures_from_stop(sid, departure_date, range_min)
            for dep_dt, tid in deps:
                total_deps += 1
                if tid in seen_initial_trips: continue
                seen_initial_trips.add(tid)
                
                t_info = _tbr_idx.get(tid)
                if not t_info: 
                    skipped_idx += 1
                    continue
                # [Task 121: Sequence Resolution Fix]
                seq_idx = graph.get_stop_sequence_in_trip(tid, sid)
                if seq_idx == -1: 
                    skipped_seq += 1
                    continue
                
                t_start, _ = t_info
                node = _tbr_nodes[t_start + seq_idx]
                delay_secs = get_delay(tid)
                adj_arr = int(node['arr_ts']) + delay_secs
                adj_dep = int(node['dep_ts']) + delay_secs

                if not can_reach_goal_or_hub(tid): 
                    filtered_by_reach += 1
                    continue
                
                state = SearchState(
                    tid=tid, sid=sid, arr=adj_arr, dep=adj_dep,
                    round_num=0, parent=None, wait=(adj_dep - departure_ts) // 60,
                    b_idx=seq_idx
                )
                h = get_heuristic(sid, dst_ids)
                heapq.heappush(pq, (adj_arr + h, id(state), state))
                pq_pushed += 1

        logger.info(f"🚀 [TBR:NEXUS] Seeded {len(pq)} initial states. (Total: {total_deps}, Pushed: {pq_pushed}, SkipIdx: {skipped_idx}, SkipSeq: {skipped_seq}, ReachFilter: {filtered_by_reach})")

        found_search_routes = []
        # [Nexus: Goal-Based Discovery] (Task 121)
        # Fast Initial Search = 250 routes, Deep discovery = 1000 routes
        target_yield = 250 if not load_more else 1000
        best_time_final = float('inf')
        pruned_time = 0; pruned_dominance = 0; found_goals = 0
        goals_by_tier = defaultdict(int)

        while pq:
            if self._nodes_explored > self.traversal_budget: break
            # Goal Stop Condition (Relaxed for Yield Diversity)
            if not load_more and found_goals >= target_yield:
                # Don't break if we lack diversity in transfer tiers
                if goals_by_tier[1] >= quotas.get(1, 10) // 2 and goals_by_tier[2] >= quotas.get(2, 5) // 2:
                     break
                if found_goals >= target_yield * 4: # Hard safety net if it finds hundreds of 0-T routes
                     break
            # Hard limit for security against infinite loops in complex hubs
            if found_goals >= 3000: break 
            
            check_timeout()
            _, _, curr = heapq.heappop(pq)
            
            # Relaxed best_time exit: Be very generous to allow for slow multi-transfer options
            if curr.arr_ts > best_time_final + (slack_sec * 3): break 
            if curr.round_num > _transfers_limit: continue
            
            t_info = _tbr_idx.get(curr.trip_id)
            if not t_info: continue
            t_start, t_count = t_info
            delay_secs = get_delay(curr.trip_id)

            # 2. Optimized Loop: Only check destinations and high-impact hubs
            pid = graph.snapshot._trip_to_pid.get(curr.trip_id)
            
            interesting_indices = set()
            for d_id in dst_ids:
                idx = graph.get_stop_sequence_in_trip(curr.trip_id, d_id)
                if idx > curr.boarded_idx: interesting_indices.add(idx)
                
            # [Subtask 146.4] Force explicitly scanning cross-cluster bridge hubs to guide search
            for b_id in bridge_sids:
                idx = graph.get_stop_sequence_in_trip(curr.trip_id, b_id)
                if idx > curr.boarded_idx: interesting_indices.add(idx)
            
            # Efficiently find all stops on this trip that have outbound transfers
            trip_transfer_stops = _trip_to_stops_map.get(curr.trip_id, {})
            for sid in trip_transfer_stops.keys():
                idx = graph.get_stop_sequence_in_trip(curr.trip_id, sid)
                if idx > curr.boarded_idx:
                    interesting_indices.add(idx)
            
            # Fallback: add periodic stops to ensure we don't miss anything 
            for i in range(curr.boarded_idx + 5, t_count, 5):
                interesting_indices.add(i)
            
            for i in sorted(list(interesting_indices)):
                stop_node = _tbr_nodes[t_start + i]
                curr_sid = int(stop_node['stop_id'])
                current_arr_ts = int(stop_node['arr_ts']) + delay_secs
                self._nodes_explored += 1
                 # --- [Nexus: Cost-Aware Pareto Pruning] ---
                is_dom = False
                prev_rid = curr.round_num
                
                # Estimate distance so far
                dist_km = (curr.wait_mins * 0.5) + (curr.round_num * 100) 
                
                # [McRAPTOR] Estimate fare and comfort for TBR
                fare = 175.0 + (max(0, dist_km - 100) * 1.2)
                train_num = snapshot.trip_to_train.get(curr.trip_id, "")
                comfort = 0.5 
                if any(p in train_num for p in ["VANDE", "RAJ", "SHT", "DUR"]): comfort += 0.3
                
                current_cost = self.calculate_generalized_cost(
                    current_arr_ts, curr.round_num, curr.wait_mins, 
                    dist_km, fare, comfort, 1.0, constraints
                )

                # 1. Global Dominance
                for r in range(prev_rid + 1):
                    # [Yield Fix] High Multiplier for massive diversity
                    dominance_factor = 5.0 if curr.round_num >= 2 else 3.0
                    if current_cost > best_cost[curr_sid][r] * dominance_factor: 
                        is_dom = True; break
                
                if not is_dom:
                    # 2. Local Variety
                    round_vars = variety_labels[curr_sid][curr.round_num]
                    if any(current_cost >= ex * 1.05 for ex in round_vars):
                        is_dom = True
                
                if is_dom:
                    pruned_dominance += 1; continue
                
                # 3. Update Pareto Frontier
                round_vars = variety_labels[curr_sid][curr.round_num]
                best_cost[curr_sid][curr.round_num] = min(best_cost[curr_sid][curr.round_num], current_cost)
                best_arrival[curr_sid][curr.round_num] = min(best_arrival[curr_sid][curr.round_num], current_arr_ts)
                round_vars.append(current_cost)
                round_vars.sort()
                variety_labels[curr_sid][curr.round_num] = round_vars[:max_labels_per_stop]

                # --- Create state and check goal ---
                alight_state = SearchState(
                    tid=curr.trip_id, sid=curr_sid, 
                    arr=current_arr_ts, dep=int(stop_node['dep_ts']) + delay_secs,
                    round_num=curr.round_num, parent=curr, wait=curr.wait_mins, b_idx=i
                )
                
                if curr_sid in dst_ids:
                    found_search_routes.append(alight_state)
                    found_goals += 1
                    goals_by_tier[curr.round_num] += 1
                    best_time_final = min(best_time_final, current_arr_ts)
                
                # 5. Inter-Station & Leg-based Transfer Expansion
                if curr.round_num < _transfers_limit:
                    index_pos_in_mmap = _edge_lookup_map.get((curr.trip_id, curr_sid))
                    
                    if index_pos_in_mmap is not None and _edge_index_mmap is not None and _edges_arr is not None:
                        index_entry = _edge_index_mmap[index_pos_in_mmap]
                        e_start = index_entry['offset']
                        e_count = index_entry['count']
                        
                        for edge in _edges_arr[e_start : e_start + e_count]:
                            next_tid = int(edge['to_trip_id'])
                            if not can_reach_goal_or_hub(next_tid): continue

                            nt_info = _tbr_idx.get(next_tid)
                            if not nt_info: continue
                            
                            n_idx = graph.get_stop_sequence_in_trip(next_tid, curr_sid)
                            if n_idx == -1: continue
                            
                            next_delay = get_delay(next_tid)
                            nt_start, _ = nt_info
                            n_node = _tbr_nodes[nt_start + n_idx]
                            
                            min_buffer_eff = max(_min_buffer, int(edge['wait_time_mins']) * 60)
                            adj_next_dep = int(n_node['dep_ts']) + next_delay
                            if adj_next_dep < current_arr_ts + min_buffer_eff:
                                pruned_time += 1; continue

                            next_state = SearchState(
                                tid=next_tid, sid=curr_sid,
                                arr=int(n_node['arr_ts']) + next_delay, dep=adj_next_dep,
                                round_num=curr.round_num + 1, parent=alight_state, 
                                wait=curr.wait_mins + (min_buffer_eff // 60),
                                b_idx=n_idx
                            )
                            h = get_heuristic(curr_sid, dst_ids)
                            heapq.heappush(pq, (next_state.arr_ts + h, id(next_state), next_state))

        logger.info(f"📊 TBR Stats: {found_goals} goals, {self._nodes_explored} nodes, PRUNED(time:{pruned_time}, dom:{pruned_dominance})")
        logger.info(f"📊 Goals by tier: {dict(goals_by_tier)}")
        
        # Hydrate and Tiered Quota Filtering
        hydrated = []
        src_hydrate_id = source_id[0] if isinstance(source_id, list) else source_id
        dst_hydrate_id = dest_id[0] if isinstance(dest_id, list) else dest_id
        for sr in found_search_routes:
            rt = self._hydrate_tbr_route(sr, graph, int(src_hydrate_id), int(dst_hydrate_id))
            if rt: hydrated.append(rt)
            
        if not hydrated:
            return []
            
        # Group by transfer count for quota admission
        by_transfers = defaultdict(list)
        for r in hydrated:
            by_transfers[len(r.transfers)].append(r)
            
        final_results = []
        best_overall_duration = min(r.total_duration for r in hydrated)
        
        for t_count in sorted(by_transfers.keys()):
            tier_routes = sorted(by_transfers[t_count], key=lambda x: x.total_duration)
            quota = quotas.get(t_count, 5)
            admitted = 0
            for r in tier_routes:
                if admitted >= quota: break
                
                # Broad sanity filter
                if r.total_duration > best_overall_duration + (slack_sec // 60) * 2:
                    continue
                
                final_results.append(r)
                admitted += 1

        # Final Deduplication by trip sequence
        unique_final_list = []
        seen_paths = set()
        for r in sorted(final_results, key=lambda x: x.total_duration):
            path_key = tuple((s.trip_id, s.departure_stop_id, s.arrival_stop_id) for s in r.segments)
            if path_key not in seen_paths:
                unique_final_list.append(r)
                seen_paths.add(path_key)

        return unique_final_list

    def _hydrate_tbr_route(self, state: SearchState, graph: TimeDependentGraph, src_id: int, dst_id: int) -> Optional[Route]:
        chain = []
        curr = state
        while curr:
            chain.append(curr); curr = curr.parent
        chain.reverse()
        
        legs = []
        i = 0
        while i < len(chain):
            curr_leg_start = chain[i]
            j = i + 1
            curr_leg_end = None
            while j < len(chain):
                if chain[j].trip_id == curr_leg_start.trip_id:
                    curr_leg_end = chain[j]
                    j += 1
                else: break
            
            if curr_leg_end:
                legs.append((curr_leg_start, curr_leg_end))
                i = j
            else:
                i += 1
            
        if not legs: return None
            
        compressed_segs = []
        for l_start, l_end in legs:
            src_stop = graph.stop_cache.get(l_start.stop_id)
            dst_stop = graph.stop_cache.get(l_end.stop_id)
            train_no = "TR-UNKNOWN"
            try:
                base_segs = graph.get_trip_segments(l_start.trip_id)
                if base_segs: train_no = base_segs[0].train_number
            except: pass

            seg = RouteSegment(
                trip_id=l_start.trip_id,
                departure_stop_id=l_start.stop_id,
                arrival_stop_id=l_end.stop_id,
                departure_time=graph.safe_fromtimestamp(l_start.dep_ts),
                arrival_time=graph.safe_fromtimestamp(l_end.arr_ts),
                duration_minutes=int((l_end.arr_ts - l_start.dep_ts)//60) if l_end.arr_ts >= l_start.dep_ts else int((l_end.arr_ts + 86400 - l_start.dep_ts)//60),
                departure_code=src_stop.code if src_stop else str(l_start.stop_id),
                arrival_code=dst_stop.code if dst_stop else str(l_end.stop_id),
                train_number=train_no
            )
            compressed_segs.append(seg)
            
        transfers = []
        for i in range(len(compressed_segs) - 1):
            s1, s2 = compressed_segs[i], compressed_segs[i+1]
            hub_stop = graph.stop_cache.get(s1.arrival_stop_id)
            duration_minutes = int((s2.departure_time - s1.arrival_time).total_seconds() // 60)
            if duration_minutes < 0:
                duration_minutes += 1440
                
            tc = TransferConnection(
                station_id=s1.arrival_stop_id,
                station_code=hub_stop.code if hub_stop else str(s1.arrival_stop_id),
                arrival_time=s1.arrival_time,
                departure_time=s2.departure_time,
                duration_minutes=duration_minutes,
                station_name=hub_stop.name if hub_stop else f"Stop {s1.arrival_stop_id}",
                facilities_score=0.0,
                safety_score=0.0,
                platform_from=None,
                platform_to=None,
                is_multi_station=False,
                transfer_type="TRANSFER"
            )
            transfers.append(tc)

        rt = Route(
            segments=compressed_segs, transfers=transfers,
            total_duration=int((compressed_segs[-1].arrival_time - compressed_segs[0].departure_time).total_seconds() // 60)
        )
        rt.metadata["engine"] = "tbr_v4_a_star"    # TBR-specific override removed to use unified BaseRoutingEngine.calculate_generalized_cost
        return rt

    # TBR-specific override removed to use unified BaseRoutingEngine.calculate_generalized_cost
