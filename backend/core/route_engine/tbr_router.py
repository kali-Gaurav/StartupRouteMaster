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
from typing import List, Optional, Any, Dict, Set, Tuple

from core.data_structures import Route, RouteSegment, TransferConnection, ensure_datetime
from core.route_engine.constraints import RouteConstraints
from core.route_engine.graph import TimeDependentGraph, MemMapManager
from core.frontier import FrontierManager, FrontierRoute
from utils.station_utils import get_metro_group_codes

logger = logging.getLogger("tbr_router")

# [Issue 14] Constants for strict routing
MAX_COMPRESSED_SEGMENTS = 10
MAX_TRANSFERS_LIMIT = 3
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

class TripBasedRouter:
    """
    Subtask 1.7: Trip-Based Routing (TBR) Engine Core (V4 A* Optimized).
    """
    def __init__(self, max_transfers: int = 3):
        self.max_transfers = max_transfers
        self.frontier_manager = FrontierManager(max_routes_per_station=10)
        self.traversal_budget = 50000 
        self._nodes_explored = 0
        
        backend_data = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
        try:
            self._edges = MemMapManager.load_array("tbr_edges")
            index_path = os.path.join(backend_data, "tbr_edge_index.pkl")
            if os.path.exists(index_path):
                with open(index_path, "rb") as f:
                    self._edge_index = pickle.load(f)
            else:
                self._edge_index = {}
                
            if self._edges is not None:
                logger.info(f"🚄 TBR: Loaded {len(self._edges)} transfer edges.")
        except Exception as e:
            logger.warning(f"⚠️ TBR: Failed to load transfer graph: {e}")
            self._edges = None
            self._edge_index = {}

    def get_graph(self, date: datetime):
        from .engine import route_engine
        return route_engine._get_current_graph(date)

    async def find_routes(self, source_stop_id: Union[int, List[int]], dest_stop_id: Union[int, List[int]],
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: Optional[TimeDependentGraph] = None,
                         load_more: bool = False) -> List[Route]:
        if not graph: 
            graph = await self.get_graph(departure_date)
            
        # [Gap 3] Adaptive Search Budget based on distance
        s_id = source_stop_id[0] if isinstance(source_stop_id, list) else source_stop_id
        d_id = dest_stop_id[0] if isinstance(dest_stop_id, list) else dest_stop_id
        src_stop = graph.stop_cache.get(s_id)
        dst_stop = graph.stop_cache.get(d_id)
        
        base_budget = 50000 if not load_more else 100000
        if src_stop and dst_stop:
            dist = haversine(src_stop.latitude, src_stop.longitude, dst_stop.latitude, dst_stop.longitude)
            # Scale budget: 1 extra node for every 10 meters of distance, capped at 4x
            distance_multiplier = min(4.0, max(1.0, dist / 500.0)) 
            self.traversal_budget = int(base_budget * distance_multiplier)
            logger.debug(f"TBR: Adaptive Budget set to {self.traversal_budget} (Dist: {dist:.1f}km)")
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
            latency = (_time.perf_counter() - start_time) * 1000
            logger.info(f"TBR Final: {len(results)} routes in {latency:.2f}ms. (Load More: {load_more})")
            return results
        except (TimeoutError, asyncio.TimeoutError):
            logger.warning(f"TBR search timed out after {timeout_sec}s.")
            return []
        except Exception as e:
            logger.error(f"TBR Search Error: {str(e)}", exc_info=True)
            return []

    def _find_routes_sync(self, source_id: Union[int, List[int]], dest_id: Union[int, List[int]],
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: TimeDependentGraph, check_timeout: Any,
                         load_more: bool = False) -> List[Route]:
        if not graph.snapshot: return []
        trip_nodes = getattr(graph.snapshot, 'tbr_trip_nodes', None)
        t_index = getattr(graph.snapshot, 'tbr_trip_index', {})
        s_index = getattr(graph.snapshot, 'tbr_stop_index', {}) 
        if trip_nodes is None or not t_index: return []

        if isinstance(source_id, list):
            src_ids = set(source_id)
        else:
            src_stop = graph.stop_cache.get(source_id)
            src_ids = {source_id}
            if src_stop:
                for code in get_metro_group_codes(src_stop.code):
                    s = graph.get_stop_by_code(code)
                    if s: src_ids.add(s.id)

        if isinstance(dest_id, list):
            dst_ids = set(dest_id)
        else:
            dst_stop = graph.stop_cache.get(dest_id)
            dst_ids = {dest_id}
            if dst_stop:
                for code in get_metro_group_codes(dst_stop.code):
                    d = graph.get_stop_by_code(code)
                    if d: dst_ids.add(d.id)

        # 1. Local Caches and Variables
        local_stop_cache = {sid: graph.stop_cache.get(sid) for sid in dst_ids}
        _reach_cache = {}
        delay_lookup = {}
        # [Yield Fix] Store multiple labels per stop/round
        # best_labels[stop_id][round_num] = list of arrival_times
        best_labels = defaultdict(lambda: defaultdict(list))
        pq = []
        
        slack_sec = 28800 if load_more else 14400 # 8h or 4h slack
        max_labels_per_bin = 10 if load_more else 5
        
        # 2. Closure Functions
        def get_delay(tid):
            if tid not in delay_lookup:
                delay_lookup[tid] = graph.overlay.get_trip_delay(tid) * 60
            return delay_lookup[tid]

        def can_reach(tid):
            if tid not in _reach_cache:
                _reach_cache[tid] = any(graph.can_reach_destination(tid, d_id) for d_id in dst_ids)
            return _reach_cache[tid]

        _h_cache = {}
        def get_heuristic(curr_sid, goal_sids):
            if curr_sid in _h_cache: return _h_cache[curr_sid]
            c_stop = graph.stop_cache.get(curr_sid)
            if not c_stop: 
                _h_cache[curr_sid] = 0
                return 0
            min_h = float('inf')
            c_lat, c_lon = c_stop.latitude, c_stop.longitude
            for g_id in goal_sids:
                g_stop = local_stop_cache.get(g_id) or graph.stop_cache.get(g_id)
                if not g_stop: continue
                dist_km = haversine(c_lat, c_lon, g_stop.latitude, g_stop.longitude)
                time_sec = (dist_km / AVG_TRAIN_SPEED_KMPH) * 3600
                min_h = min(min_h, time_sec)
            val = 0 if min_h == float('inf') else int(min_h)
            _h_cache[curr_sid] = val
            return val

        # 3. Hot Loop Local References
        _edge_idx = self._edge_index
        _edges_arr = self._edges
        _tbr_nodes = trip_nodes
        _tbr_idx = t_index
        _transfers_limit = MAX_TRANSFERS_LIMIT
        _min_buffer = MIN_TRANSFER_BUFFER_SEC
        departure_ts = int(departure_date.timestamp())

        # O(1) Trip-Stop lookup
        s_lookup = {}
        for sid_key, trip_list in s_index.items():
            if sid_key in src_ids or sid_key in _edge_idx or sid_key in dst_ids: 
                s_lookup[sid_key] = {tid: seq for tid, seq in trip_list}

        # Seed Queue
        range_min = (constraints.range_minutes or 1440) * (2 if load_more else 1)
        logger.info(f"🔍 TBR: Starting A* v4 Search (Yield Optimized) for {source_id} -> {dest_id}")
        seen_initial_trips = set()
        seen_initial_trips = set()
        for sid in src_ids:
            deps = graph.get_departures_from_stop(sid, departure_date, range_min)
            for dep_dt, tid in deps:
                if tid in seen_initial_trips: continue
                seen_initial_trips.add(tid)
                
                t_info = _tbr_idx.get(tid)
                if not t_info: continue
                seq_idx = s_lookup.get(sid, {}).get(tid, -1)
                if seq_idx == -1: continue
                
                t_start, _ = t_info
                node = _tbr_nodes[t_start + seq_idx]
                delay_secs = get_delay(tid)
                adj_arr = int(node['arr_ts']) + delay_secs
                adj_dep = int(node['dep_ts']) + delay_secs

                if not can_reach(tid): continue

                state = SearchState(
                    tid=tid, sid=sid, arr=adj_arr, dep=adj_dep,
                    round_num=0, parent=None, wait=(adj_dep - departure_ts) // 60,
                    b_idx=seq_idx
                )
                h = get_heuristic(sid, dst_ids)
                heapq.heappush(pq, (adj_arr + h, id(state), state))

        found_search_routes = []
        # Increase internal candidate limit to ensure we get enough multi-transfer routes
        internal_search_limit = 1000 
        best_time_final = float('inf')
        pruned_time = 0; pruned_dominance = 0; found_goals = 0

        # Track goals per tier to ensure diversity
        goals_by_tier = defaultdict(int)

        while pq:
            if self._nodes_explored > self.traversal_budget: break
            # Stop if we have enough routes in all required tiers or we hit a huge total
            if found_goals >= internal_search_limit: break
            if all(goals_by_tier[t] >= 50 for t in range(4)) and found_goals >= 200: break
            
            check_timeout()
            _, _, curr = heapq.heappop(pq)
            
            # Relaxed best_time exit: Be very generous to allow for slow multi-transfer options
            if curr.arr_ts > best_time_final + (slack_sec * 3): break 
            if curr.round_num > _transfers_limit: continue
            
            t_info = _tbr_idx.get(curr.trip_id)
            if not t_info: continue
            t_start, t_count = t_info
            delay_secs = get_delay(curr.trip_id)

            for i in range(curr.boarded_idx + 1, t_count):
                stop_node = _tbr_nodes[t_start + i]
                curr_sid = int(stop_node['stop_id'])
                current_arr_ts = int(stop_node['arr_ts']) + delay_secs
                self._nodes_explored += 1
                
                # [Yield Fix] Relaxed Dominance: 
                # Prune ONLY if we are much slower than a route with FEWER or EQUAL transfers.
                is_dom = False
                for r_num in range(curr.round_num + 1):
                    bin_labels = best_labels[curr_sid][r_num]
                    if bin_labels:
                        min_arr = min(bin_labels)
                        # More slack for cross-tier dominance
                        eff_slack = slack_sec if r_num == curr.round_num else (slack_sec * 2)
                        if current_arr_ts > min_arr + eff_slack:
                            is_dom = True; break
                        # If same tier, allow multiple but cap density
                        if r_num == curr.round_num and len(bin_labels) >= max_labels_per_bin:
                            if current_arr_ts >= max(bin_labels):
                                is_dom = True; break
                
                if is_dom:
                    pruned_dominance += 1; continue
                
                best_labels[curr_sid][curr.round_num].append(current_arr_ts)
                
                # [Yield Fix] Correctly link alighting state in the chain
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
                
                if curr.round_num < _transfers_limit:
                    station_transfers = _edge_idx.get(curr.trip_id, {}).get(curr_sid)
                    if station_transfers:
                        e_start, e_count = station_transfers
                        for edge in _edges_arr[e_start : e_start + e_count]:
                            next_tid = int(edge['to_trip_id'])
                            if not can_reach(next_tid): continue

                            nt_info = _tbr_idx.get(next_tid)
                            if not nt_info: continue
                            n_idx = s_lookup.get(curr_sid, {}).get(next_tid, -1)
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
        for sr in found_search_routes:
            rt = self._hydrate_tbr_route(sr, graph, source_id, dest_id)
            if rt: hydrated.append(rt)
            
        # [Quota Fix] Specific targets: 0-T (All), 1-T (15), 2-T (10), 3-T (5)
        quotas = {0: 999, 1: 15, 2: 10, 3: 5}
        if load_more:
            quotas = {0: 999, 1: 30, 2: 20, 3: 10}

        # Group by transfer count
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
                
                # Broad sanity filter: Don't show routes that are massively slower than best
                # Use slack_sec to allow for sub-optimal but valid options
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
        
        # logger.debug(f"Hydrating chain: {len(chain)} nodes")
        
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
                # Fallback: if single node leg (should rarely happen in TBR)
                # legs.append((curr_leg_start, curr_leg_start))
                i += 1
            
        if not legs: 
            logger.debug("Hydration failed: No legs found")
            return None
            
        if len(legs) < (state.round_num + 1):
            logger.debug(f"Hydration anomaly: Found {len(legs)} legs for round {state.round_num}")

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
            tc = TransferConnection(
                station_id=s1.arrival_stop_id,
                arrival_time=s1.arrival_time,
                departure_time=s2.departure_time,
                duration_minutes=int((s2.departure_time - s1.arrival_time).total_seconds() // 60),
                station_name=hub_stop.name if hub_stop else f"Stop {s1.arrival_stop_id}"
            )
            transfers.append(tc)

        rt = Route(
            segments=compressed_segs, transfers=transfers,
            total_duration=int((compressed_segs[-1].arrival_time - compressed_segs[0].departure_time).total_seconds() // 60)
        )
        rt.metadata["engine"] = "tbr_v4_a_star"
        return rt
