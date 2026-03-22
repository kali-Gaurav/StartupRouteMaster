import logging
import asyncio
import time as _time
from datetime import datetime, timedelta
from typing import List, Optional, Any, Dict, Set, Tuple
import numpy as np

from core.data_structures import Route, RouteSegment, TransferConnection, ensure_datetime
from core.route_engine.constraints import RouteConstraints
from core.route_engine.graph import TimeDependentGraph
from core.frontier import FrontierManager, FrontierRoute

logger = logging.getLogger("tbr_router")

from .tbr_structures import trip_node_dtype, trip_edge_dtype

class SearchState:
    """Flyweight state object for TBR traversal."""
    __slots__ = ('trip_id', 'stop_id', 'arr_ts', 'dep_ts', 'round_num', 'parent', 'wait_mins', 'boarded_idx')
    
    def __init__(self):
        self.reset()

    def reset(self, tid=0, sid=0, arr=0, dep=0, round=0, parent=None, wait=0, b_idx=0):
        self.trip_id = tid
        self.stop_id = sid
        self.arr_ts = arr
        self.dep_ts = dep
        self.round_num = round
        self.parent = parent
        self.wait_mins = wait
        self.boarded_idx = b_idx

class TripBasedRouter:
    """
    Subtask 1.7: Trip-Based Routing (TBR) Engine Core.
    Explores contiguous trips rather than individual station departures.
    """
    _state_pool = [SearchState() for _ in range(10000)]
    
    @classmethod
    def _acquire_state(cls, **kwargs) -> SearchState:
        if cls._state_pool:
            state = cls._state_pool.pop()
            state.reset(**kwargs)
            return state
        return SearchState()

    @classmethod
    def _release_state(cls, state: SearchState):
        if len(cls._state_pool) < 20000:
            cls._state_pool.append(state)

    def __init__(self, max_transfers: int = 3):
        self.max_transfers = max_transfers
        self.frontier_manager = FrontierManager(max_routes_per_station=10)
        self.traversal_budget = 50000 
        self._nodes_explored = 0
        
        from .graph import MemMapManager
        import pickle
        import os
        
        backend_data = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
        try:
            self._edges = MemMapManager.load_array("tbr_edges")
            with open(os.path.join(backend_data, "tbr_edge_index.pkl"), "rb") as f:
                self._edge_index = pickle.load(f)
            if self._edges is not None:
                logger.info(f"🚄 TBR: Loaded {len(self._edges)} transfer edges.")
        except Exception as e:
            logger.warning(f"⚠️ TBR: Failed to load transfer graph: {e}")
            self._edges = None
            self._edge_index = {}

    async def find_routes(self, source_stop_id: int, dest_stop_id: int,
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: Optional[TimeDependentGraph] = None) -> List[Route]:
        if not graph: return []
        self._nodes_explored = 0
        start_time = _time.perf_counter()
        timeout_sec = (constraints.timeout_ms / 1000.0) if constraints.timeout_ms else 5.0
        
        def check_timeout():
            if _time.perf_counter() - start_time > timeout_sec:
                raise TimeoutError("TBR search timed out")

        try:
            results = await asyncio.to_thread(
                self._find_routes_sync, source_stop_id, dest_stop_id, 
                departure_date, constraints, graph, check_timeout
            )
            latency = (_time.perf_counter() - start_time) * 1000
            logger.info(f"🚀 TBR Yield: {len(results)} routes, Depth: {self._nodes_explored} nodes in {latency:.2f}ms.")
            return results
        except TimeoutError:
            logger.warning(f"⌛ TBR search timed out after {timeout_sec}s.")
            return []
        except Exception as e:
            logger.error(f"❌ TBR Search Error: {str(e)}", exc_info=True)
            return []

    def _find_routes_sync(self, source_stop_id: int, dest_stop_id: int,
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: TimeDependentGraph, check_timeout: Any) -> List[Route]:
        if not graph.snapshot: return []
        trip_nodes = getattr(graph.snapshot, 'tbr_trip_nodes', None)
        t_index = getattr(graph.snapshot, 'tbr_trip_index', {})
        s_index = getattr(graph.snapshot, 'tbr_stop_index', {}) 
        if trip_nodes is None or not t_index: return []

        from collections import deque
        from utils.station_utils import get_metro_group_codes
        
        src_stop = graph.stop_cache.get(source_stop_id)
        src_ids = {source_stop_id}
        if src_stop:
            for code in get_metro_group_codes(src_stop.code):
                s = graph.get_stop_by_code(code)
                if s: src_ids.add(s.id)

        dst_stop = graph.stop_cache.get(dest_stop_id)
        dst_ids = {dest_stop_id}
        if dst_stop:
            for code in get_metro_group_codes(dst_stop.code):
                d = graph.get_stop_by_code(code)
                if d: dst_ids.add(d.id)

        queue = deque()
        self.frontier_manager.reset()
        departure_ts = int(departure_date.timestamp())
        lookahead = constraints.range_minutes or 1440
        
        # [Task 1] Seed Queue with initial trips from ALL source group stations
        for sid in src_ids:
            deps = graph.get_departures_from_stop(sid, departure_date, lookahead)
            for dep_dt, tid in deps:
                check_timeout()
                if self._nodes_explored > self.traversal_budget: break
                
                t_info = t_index.get(tid)
                if not t_info: continue
                
                # Fast seq_idx lookup via precomputed stop index
                seq_idx = -1
                for stop_tid, stop_seq in s_index.get(sid, []):
                    if stop_tid == tid:
                        seq_idx = stop_seq; break
                if seq_idx == -1: continue
                
                self._nodes_explored += 1
                t_start, _ = t_info
                node = trip_nodes[t_start + seq_idx]
                
                state = self._acquire_state(
                    tid=tid, sid=sid, arr=node['arr_ts'], dep=node['dep_ts'],
                    round=0, parent=None, wait=(node['dep_ts'] - departure_ts) // 60,
                    b_idx=seq_idx
                )
                queue.append(state)

        found_search_routes = []
        for r in range(self.max_transfers + 1):
            if not queue: break
            round_size = len(queue)
            for _ in range(round_size):
                check_timeout()
                curr = queue.popleft()
                
                t_info = t_index.get(curr.trip_id)
                if not t_info: continue
                t_start, t_count = t_info
                
                # Scan stops in current trip
                for i in range(curr.boarded_idx + 1, t_count):
                    stop_node = trip_nodes[t_start + i]
                    curr_sid = int(stop_node['stop_id'])
                    
                    # 1. Goal Check (Task 27.15 Unified Groups)
                    if curr_sid in dst_ids:
                        goal_state = self._acquire_state(
                            tid=curr.trip_id, sid=curr_sid, 
                            arr=stop_node['arr_ts'], dep=stop_node['dep_ts'],
                            round=r, parent=curr, wait=curr.wait_mins, b_idx=i
                        )
                        found_search_routes.append(goal_state)
                        # Continue scanning for even better arrival times or transfers
                    
                    # 2. Dominance Pruning
                    arr_mins = (stop_node['arr_ts'] - departure_ts) // 60
                    f_route = FrontierRoute(
                        arrival_time=arr_mins + (r * 120), # Penalty for transfers
                        transfers=r, 
                        total_wait=curr.wait_mins, 
                        total_distance=0.0
                    )
                    
                    # Use epsilon for destination stations to allow more alternatives
                    eps = 15 if curr_sid in dst_ids else 0
                    if self.frontier_manager.is_dominated(curr_sid, f_route, epsilon_mins=eps): continue
                    
                    # 3. Transfer Search (O(1) Adjacency)
                    if r < self.max_transfers:
                        station_transfers = self._edge_index.get(curr.trip_id, {}).get(curr_sid)
                        if station_transfers:
                            e_start, e_count = station_transfers
                            for ei in range(e_start, e_start + e_count):
                                edge = self._edges[ei]
                                next_tid = int(edge['to_trip_id'])
                                nt_info = t_index.get(next_tid)
                                if not nt_info: continue
                                
                                # Fast seq_idx lookup for the new trip at this station
                                n_idx = -1
                                for nt_tid, nt_seq in s_index.get(curr_sid, []):
                                    if nt_tid == next_tid:
                                        n_idx = nt_seq; break
                                
                                if n_idx != -1:
                                    nt_start, _ = nt_info
                                    n_node = trip_nodes[nt_start + n_idx]
                                    next_state = self._acquire_state(
                                        tid=next_tid, sid=curr_sid,
                                        arr=n_node['arr_ts'], dep=n_node['dep_ts'],
                                        round=r+1, parent=curr, 
                                        wait=curr.wait_mins + int(edge['wait_time_mins']),
                                        b_idx=n_idx
                                    )
                                    queue.append(next_state)

        return [self._hydrate_tbr_route(sr, graph) for sr in found_search_routes]

    def _hydrate_tbr_route(self, state: SearchState, graph: TimeDependentGraph) -> Route:
        path = []
        curr = state
        while curr:
            path.append(curr); curr = curr.parent
        path.reverse()
        
        full_segments = []; transfers = []
        for i in range(len(path) - 1):
            board_state = path[i]; next_state = path[i+1]
            tid = board_state.trip_id
            
            # Robust Hydration: Reconstruct trip path from segments
            # Handles cases where the database segments are fragmented
            segs = graph.get_trip_segments(tid)
            if not segs:
                # Fallback: Create synthetic segment if missing from DB
                src_stop = graph.stop_cache.get(board_state.stop_id)
                dst_stop = graph.stop_cache.get(next_state.stop_id)
                synthetic = RouteSegment(
                    trip_id=tid, 
                    departure_stop_id=board_state.stop_id, 
                    arrival_stop_id=next_state.stop_id,
                    departure_time=graph.safe_fromtimestamp(board_state.dep_ts),
                    arrival_time=graph.safe_fromtimestamp(next_state.arr_ts),
                    duration_minutes=int((next_state.arr_ts - board_state.dep_ts)//60),
                    departure_code=src_stop.code if src_stop else str(board_state.stop_id),
                    arrival_code=dst_stop.code if dst_stop else str(next_state.stop_id),
                    train_number=f"TR-{tid}"
                )
                full_segments.append(synthetic)
            else:
                node_segs = []; started = False
                for s in segs:
                    if not started and s.departure_stop_id == board_state.stop_id: started = True
                    if started:
                        node_segs.append(s)
                        if s.arrival_stop_id == next_state.stop_id: break
                
                if not node_segs: # Segment mapping failed but trip exists
                     src_stop = graph.stop_cache.get(board_state.stop_id)
                     dst_stop = graph.stop_cache.get(next_state.stop_id)
                     node_segs = [RouteSegment(
                        trip_id=tid, departure_stop_id=board_state.stop_id, arrival_stop_id=next_state.stop_id,
                        departure_time=graph.safe_fromtimestamp(board_state.dep_ts),
                        arrival_time=graph.safe_fromtimestamp(next_state.arr_ts),
                        duration_minutes=int((next_state.arr_ts - board_state.dep_ts)//60),
                        departure_code=src_stop.code if src_stop else str(board_state.stop_id),
                        arrival_code=dst_stop.code if dst_stop else str(next_state.stop_id),
                        train_number=segs[0].train_number
                     )]
                full_segments.extend(node_segs)

            # Record transfer if not the last leg
            if i < len(path) - 2:
                next_leg = path[i+2]
                hub_stop = graph.stop_cache.get(next_state.stop_id)
                tc = TransferConnection(
                    station_id=next_state.stop_id, 
                    arrival_time=graph.safe_fromtimestamp(next_state.arr_ts),
                    departure_time=graph.safe_fromtimestamp(next_leg.dep_ts), 
                    duration_minutes=int((next_leg.dep_ts - next_state.arr_ts)//60),
                    station_name=hub_stop.name if hub_stop else f"Stop {next_state.stop_id}"
                )
                transfers.append(tc)

        rt = Route(segments=full_segments, transfers=transfers)
        rt.metadata["engine"] = "tbr_v2_advanced"
        return rt
