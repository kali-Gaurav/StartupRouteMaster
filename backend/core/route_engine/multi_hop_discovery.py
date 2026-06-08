import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Set, Any, Dict, Tuple, Optional
from dataclasses import dataclass
from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse
from core.data_utils.structures import Route, RouteSegment, TransferConnection
from collections import deque
from .exhaustive_direct import ExhaustiveDirectEngine

logger = logging.getLogger(__name__)

@dataclass(slots=True)
class DiscoveryPathNode:
    stop_id: int
    trip_id: int
    dep_ts: int
    arr_ts: int
    train_no: str
    train_name: str
    dep_code: str
    arr_code: str
    parent: Optional['DiscoveryPathNode'] = None

class MultiHopDiscoveryEngine(BaseRoutingEngine):
    """
    [Engineer 7-9 Task]
    Goal: Find deep-tier multi-hop routes (2-3 transfers).
    Strategy: Optimized BFS with Hub-Pruning and Memoization.
    """

    @property
    def engine_id(self) -> str:
        return "multi_hop_discovery"

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._mega_hubs_cache = None
        self._adj_cache = {} # Local search cache

    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        start_ts = datetime.now()
        import asyncio
        loop = asyncio.get_running_loop()
        
        # Clear local cache for new search
        self._adj_cache = {}
        limit = 100
        routes = await asyncio.wait_for(
            loop.run_in_executor(_executor, self._search_sync, request, limit),
            timeout=30.0
        )
        
        logger.info(f"🏁 [MULTI_HOP] Discovery complete. Found {len(routes)} routes.")
        return RoutingResponse(
            engine_name=self.engine_id,
            routes=routes,
            latency_ms=(datetime.now() - start_ts).total_seconds() * 1000,
            yield_count=len(routes)
        )

    def _search_sync(self, request: RoutingRequest, limit: int) -> List[Route]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            from .exhaustive_direct import ExhaustiveDirectEngine
            resolver = ExhaustiveDirectEngine(self.db_path)
            src_ids = resolver._resolve_terminal_ids(conn, request.source_code)
            dst_ids = resolver._resolve_terminal_ids(conn, request.destination_code)
            
            if not src_ids or not dst_ids: return []
            
            travel_date = request.departure_date.date()
            day_idx = travel_date.weekday()
            db_date_str = travel_date.strftime("%Y%m%d")
            
            if self._mega_hubs_cache is None:
                q_hubs = "SELECT id FROM stops WHERE centrality_score > 0.05 OR is_major_junction = 1 LIMIT 200"
                self._mega_hubs_cache = {r[0] for r in conn.execute(q_hubs).fetchall()}
            
            mega_hubs = self._mega_hubs_cache
            
            # [Optimization] BFS with Path-Backtracking (Lightweight)
            visited = {} # (stop_id, depth) -> min_arr_ts
            queue = deque()
            for sid in src_ids:
                queue.append((sid, None, 0, 0)) # curr_sid, parent_node, curr_arr_ts, depth
            
            logger.info(f"🔍 [MULTI_HOP] BFS Search Start")
            all_found_paths: List[DiscoveryPathNode] = []
            found_count = 0
            nodes_processed = 0
            
            while queue and found_count < limit and nodes_processed < 20000:
                curr_sid, parent, curr_ts, depth = queue.popleft()
                nodes_processed += 1
                
                if nodes_processed % 500 == 0:
                    logger.info(f"🔎 [MULTI_HOP:TRACE] Processed {nodes_processed} nodes. Current depth: {depth} Queue: {len(queue)}")
                
                # Goal Check
                if curr_sid in dst_ids:
                    logger.info(f"✨ [MULTI_HOP] Goal Found! Depth: {depth} at {curr_sid}")
                    all_found_paths.append(parent)
                    found_count += 1
                    if found_count >= limit: break
                    continue
                
                if depth >= 5: continue
                
                # Pruning: Only expand from mega-hubs or start stations
                if depth > 0 and curr_sid not in mega_hubs:
                    continue
                
                if (curr_sid, depth) in visited and visited[(curr_sid, depth)] <= curr_ts:
                    continue
                visited[(curr_sid, depth)] = curr_ts
                
                allowed_next = mega_hubs if depth > 0 else None
                adj = self._get_adjacencies_memoized(conn, curr_sid, day_idx, db_date_str, allowed_next, dst_ids)
                
                for next_sid, tid, dep_ts, arr_ts in adj:
                    # Pruning: Only consider connections within 30m to 12h
                    if depth > 0 and (dep_ts < curr_ts + 1800 or dep_ts > curr_ts + 43200):
                        continue
                    
                    # Cycle detection
                    is_cycle = False
                    p = parent
                    while p:
                        if p.stop_id == next_sid:
                            is_cycle = True
                            break
                        p = p.parent
                    if is_cycle: continue
                    
                    new_node = DiscoveryPathNode(
                        stop_id=next_sid, trip_id=tid, dep_ts=dep_ts, arr_ts=arr_ts,
                        train_no="", train_name="", # Deferred
                        dep_code="", arr_code="", # Deferred
                        parent=parent
                    )
                    queue.append((next_sid, new_node, arr_ts, depth + 1))
            
            logger.info(f"✨ [MULTI_HOP] BFS Complete. Found {len(all_found_paths)} potential paths. (Nodes: {nodes_processed})")
            
            # [Batch Hydration]
            routes = []
            if not all_found_paths: return []

            # 1. Collect all trip_ids and stop_ids for bulk hydration
            needed_trips = set()
            needed_stops = set(src_ids) | set(dst_ids)
            for path_end in all_found_paths:
                curr = path_end
                while curr:
                    needed_trips.add(curr.trip_id)
                    needed_stops.add(curr.stop_id)
                    curr = curr.parent
            
            # 2. Fetch train details
            trip_map = {}
            if needed_trips:
                q_trips = f"SELECT id, train_no, trip_id FROM trips WHERE id IN ({','.join(['?' for _ in needed_trips])})"
                for r in conn.execute(q_trips, list(needed_trips)).fetchall():
                    trip_map[r[0]] = (r[1], r[2])
            
            # 3. Fetch station codes
            stop_map = {}
            if needed_stops:
                q_stops = f"SELECT id, code FROM stops WHERE id IN ({','.join(['?' for _ in needed_stops])})"
                for r in conn.execute(q_stops, list(needed_stops)).fetchall():
                    stop_map[r[0]] = r[1]

            base_dt = datetime.combine(travel_date, datetime.min.time())
            for path_end in all_found_paths:
                rt_path = []
                curr = path_end
                while curr:
                    rt_path.append(curr)
                    curr = curr.parent
                rt_path.reverse()
                
                rt = Route()
                from core.data_utils.structures import TransferConnection
                prev_stop_id = list(src_ids)[0] # Approximation for display
                for i, node in enumerate(rt_path):
                    dep_dt = base_dt + timedelta(seconds=node.dep_ts)
                    arr_dt = base_dt + timedelta(seconds=node.arr_ts)
                    tno, tname = trip_map.get(node.trip_id, ("?", "?"))
                    
                    seg = RouteSegment(
                        trip_id=node.trip_id, departure_stop_id=0, arrival_stop_id=node.stop_id,
                        departure_time=dep_dt, arrival_time=arr_dt,
                        duration_minutes=(node.arr_ts - node.dep_ts) // 60,
                        train_number=str(tno), train_name=str(tname),
                        departure_code=stop_map.get(prev_stop_id, "?"), 
                        arrival_code=stop_map.get(node.stop_id, "?")
                    )
                    rt.add_segment(seg)
                    
                    if i < len(rt_path) - 1:
                        next_node = rt_path[i+1]
                        wait_mins = (next_node.dep_ts - node.arr_ts) // 60
                        rt.add_transfer(TransferConnection(
                            from_stop_id=node.stop_id, to_stop_id=node.stop_id,
                            duration_minutes=wait_mins,
                            arrival_time=arr_dt, departure_time=base_dt + timedelta(seconds=next_node.dep_ts)
                        ))
                    prev_stop_id = node.stop_id
                
                rt.total_duration = sum(s.duration_minutes for s in rt.segments) + \
                                   sum(t.duration_minutes for t in rt.transfers)
                rt.metadata["engine"] = f"multi_hop_{len(rt_path)}T" if len(rt_path) > 1 else "multi_hop_direct"
                routes.append(rt)
            
            return routes
        finally:
            conn.close()

    def _get_adjacencies_memoized(self, conn, stop_id: int, day_idx: int, db_date: str, hub_filter: Set[int], dst_ids: Set[int]):
        cache_key = (stop_id, day_idx)
        if cache_key not in self._adj_cache:
            day_col = ExhaustiveDirectEngine.DAY_COLUMNS[day_idx]
            
            # [Lightweight Query] No stops/trips joins here. BFS only needs structural data.
            q = f"""
                SELECT 
                    s2.stop_id as dst, s2.trip_id as tid,
                    s1.departure_timestamp as dep, s2.arrival_timestamp as arr
                FROM stop_times s1
                JOIN stop_times s2 ON s1.trip_id = s2.trip_id
                JOIN trips t ON s1.trip_id = t.id
                JOIN calendar c ON t.service_id = c.service_id
                WHERE s1.stop_id = ?
                  AND s2.stop_sequence > s1.stop_sequence
                  AND c.{day_col} = 1
                  AND ? BETWEEN c.start_date AND c.end_date
                ORDER BY s1.departure_timestamp ASC
                LIMIT 100
            """
            res = conn.execute(q, [stop_id, db_date]).fetchall()
            
            self._adj_cache[cache_key] = [
                (r['dst'], r['tid'], r['dep'], r['arr']) for r in res
            ]
            
        all_res = self._adj_cache[cache_key]
        
        if hub_filter is None:
            return all_res
        
        # Filter by hub or destination
        return [r for r in all_res if r[0] in (hub_filter or set()) or r[0] in (dst_ids or set())]
