import time
import logging
from typing import List, Dict, Tuple, Set
from collections import defaultdict
from datetime import datetime, timedelta

from core.data_structures import Route, RouteSegment, TransferConnection
from .graph import TimeDependentGraph
from .constraints import RouteConstraints
from database.config import Config

logger = logging.getLogger(__name__)

class FastPathRouter:
    """
    10X PERFORMANCE BFS ROUTER.
    Uses pre-computed station_schedule and train_path for O(1) lookups.
    """
    def __init__(self, graph: TimeDependentGraph):
        self.graph = graph
        self.major_hubs = []
        self._hubs_initialized = False

    def _ensure_hubs_initialized(self):
        if self._hubs_initialized: return
        
        if not self.graph or not self.graph.snapshot:
            logger.warning("FastPathRouter: Graph or Snapshot is None during hub init. Using fallback hubs.")
            self.major_hubs = [1, 10, 50, 100]
            self._hubs_initialized = True
            return

        # Resolve major hubs from snapshot
        try:
            from core.route_engine.hub import HubManager
            major_codes = set(HubManager.MAJOR_HUB_CODES)
            
            self.major_hubs = []
            for stop_id, stop in self.graph.stop_cache.items():
                if getattr(stop, 'is_major_junction', False) or stop.code in major_codes:
                    self.major_hubs.append(stop_id)
            
            logger.info(f"FastPathRouter: Initialized {len(self.major_hubs)} major hubs from snapshot.")
            self._hubs_initialized = True
        except Exception as e:
            logger.error(f"FastPathRouter: Hub init failed: {e}")
            self.major_hubs = [1, 10, 50, 100]
            self._hubs_initialized = True

    def find_routes(self, source_id: int, dest_id: int, date: datetime, constraints: RouteConstraints) -> List[Route]:
        self._ensure_hubs_initialized()
        
        # [Task 27.15] Metropolitan Group Expansion
        from utils.station_utils import get_metro_group_codes
        
        src_stop = self.graph.stop_cache.get(source_id)
        dst_stop = self.graph.stop_cache.get(dest_id)
        
        src_ids = {source_id}
        dst_ids = {dest_id}
        
        if src_stop:
            for code in get_metro_group_codes(src_stop.code):
                s = self.graph.get_stop_by_code(code)
                if s: src_ids.add(s.id)
        if dst_stop:
            for code in get_metro_group_codes(dst_stop.code):
                d = self.graph.get_stop_by_code(code)
                if d: dst_ids.add(d.id)

        # Fallback to city clusters if no metro group found or to complement it
        if self.graph and self.graph.snapshot:
            if src_stop and src_stop.city:
                for sid in self.graph.snapshot.city_clusters.get(src_stop.city.lower().strip(), []):
                    src_ids.add(sid)
            if dst_stop and dst_stop.city:
                for sid in self.graph.snapshot.city_clusters.get(dst_stop.city.lower().strip(), []):
                    dst_ids.add(sid)

        src_ids_list = list(src_ids)
        dst_ids_list = list(dst_ids)

        max_transfers = constraints.max_transfers
        window_start = date
        window_end = date + timedelta(hours=24)
        
        all_found: List[Route] = []
        # 1. Direct
        for s_id in src_ids_list:
            for d_id in dst_ids_list:
                all_found.extend(self._find_direct(s_id, d_id, window_start, window_end))
        
        # 2. 1-Transfer
        if max_transfers >= 1:
            for s_id in src_ids_list:
                all_found.extend(self._find_1_transfer(s_id, dst_ids_list, constraints, window_start, window_end))
            
        # 3. 2-Transfer Hub Bridge
        if max_transfers >= 2:
            for s_id in src_ids_list:
                all_found.extend(self._find_2_transfer_hub_bridge(s_id, dst_ids_list, constraints, window_start, window_end))
            
        return self._deduplicate(all_found)

    def _find_direct(self, source_id: int, dest_id: int, start: datetime, end: datetime) -> List[Route]:
        routes = []
        deps = self.graph.get_departures_from_stop(source_id, start, 1440)
        for dep_time, tid in deps:
            # Use O(1) bitset check for extreme performance instead of sets
            if self.graph.can_reach_destination(tid, dest_id):
                segs = self._get_segments(tid, source_id, dest_id)
                if segs:
                    rt = Route(segments=segs)
                    rt.metadata["engine"] = "fastpath_direct"
                    routes.append(rt)
        return routes

    def _find_1_transfer(self, source_id: int, dest_ids: List[int], constraints: RouteConstraints, start: datetime, end: datetime) -> List[Route]:
        routes = []
        source_deps = self.graph.get_departures_from_stop(source_id, start, 1440)
        
        from core.data_structures import ensure_datetime
        
        for dep_1, tid_1 in source_deps:
            path_1 = self.graph.get_train_path(tid_1)
            src_seq = next((p['stop_seq'] for p in path_1 if p['station_id'] == source_id), -1)
            if src_seq == -1: continue
            
            for pt in path_1:
                if pt['stop_seq'] <= src_seq: continue
                hub_id = pt['station_id']
                
                # Fetch departures from hub after Leg 1 arrival
                arr_1 = ensure_datetime(pt['arrival']) if pt['arrival'] else dep_1
                hub_deps = self.graph.get_departures_from_stop(hub_id, arr_1, 720)
                
                for dep_2, tid_2 in hub_deps:
                    if tid_1 == tid_2: continue
                    # [Task 8] Fast bitset check against ANY destination in cluster
                    for d_id in dest_ids:
                        if self.graph.can_reach_destination(tid_2, d_id):
                            # Potential 1-transfer route
                            s1 = self._get_segments(tid_1, source_id, hub_id)
                            s2 = self._get_segments(tid_2, hub_id, d_id)
                            if s1 and s2:
                                wait = (ensure_datetime(s2[0].departure_time) - ensure_datetime(s1[-1].arrival_time)).total_seconds() / 60
                                # [Task 6] Use station-size aware transfer time
                                min_tr_time = constraints.min_transfer_time
                                stop = self.graph.stop_cache.get(hub_id)
                                if stop and hasattr(stop, 'station_size'):
                                    size = getattr(stop, 'station_size')
                                    if size == 'major_hub': min_tr_time = 5
                                    elif size == 'large': min_tr_time = 10
                                    elif size == 'medium': min_tr_time = 15
                                    elif size == 'small': min_tr_time = 20
                                
                                if min_tr_time <= wait <= constraints.max_layover_time:
                                    tc = TransferConnection(hub_id, s1[-1].arrival_time, s2[0].departure_time, int(wait), "", 0.8, 0.8)
                                    rt = Route(segments=s1+s2, transfers=[tc])
                                    rt.metadata["engine"] = "fastpath_1t"
                                    routes.append(rt)
                                    if len(routes) >= 50: return routes
                            break # Found a destination for this tid_2
        return routes

    def _find_2_transfer_hub_bridge(self, src_id: int, dest_ids: List[int], constraints: RouteConstraints, start: datetime, end: datetime) -> List[Route]:
        """PGT -> Hub A -> Hub B -> KOTA"""
        routes = []
        # Find Hubs reachable from SRC
        src_hubs = self._get_reachable_hubs(src_id, start)
        # Find Hubs that can reach ANY DST in cluster
        dst_hubs = {}
        for d_id in dest_ids:
            dst_hubs.update(self._get_incoming_hubs(d_id))
        
        from core.data_structures import ensure_datetime
        
        for h1_id, info1 in src_hubs.items():
            for h2_id, info2 in dst_hubs.items():
                if h1_id == h2_id: continue
                
                # Leg 2: Hub 1 to Hub 2
                arr_1 = ensure_datetime(info1['arr_time'])
                h1_deps = self.graph.get_departures_from_stop(h1_id, arr_1, 720)
                
                for dep_mid, tid_mid in h1_deps:
                    if tid_mid == info1['tid'] or tid_mid == info2.get('tid'): continue 
                    
                    # [Task 8] Fast bitset check
                    if self.graph.can_reach_destination(tid_mid, h2_id):
                        # We found a 2-transfer bridge!
                        s1 = self._get_segments(info1['tid'], src_id, h1_id)
                        s2 = self._get_segments(tid_mid, h1_id, h2_id)
                        s3 = self._get_segments(info2['tid'], h2_id, info2['dst_id'])
                        
                        if s1 and s2 and s3:
                            wait1 = (ensure_datetime(s2[0].departure_time) - ensure_datetime(s1[-1].arrival_time)).total_seconds() / 60
                            wait2 = (ensure_datetime(s3[0].departure_time) - ensure_datetime(s2[-1].arrival_time)).total_seconds() / 60
                            
                            # [Task 6] Use station-size aware transfer time for both hubs
                            min_tr_time1 = 15
                            min_tr_time2 = 15
                            stop1 = self.graph.stop_cache.get(h1_id)
                            stop2 = self.graph.stop_cache.get(h2_id)
                            if stop1 and hasattr(stop1, 'station_size'):
                                size1 = getattr(stop1, 'station_size')
                                if size1 == 'major_hub': min_tr_time1 = 5
                                elif size1 == 'large': min_tr_time1 = 10
                                elif size1 == 'medium': min_tr_time1 = 15
                                elif size1 == 'small': min_tr_time1 = 20
                            if stop2 and hasattr(stop2, 'station_size'):
                                size2 = getattr(stop2, 'station_size')
                                if size2 == 'major_hub': min_tr_time2 = 5
                                elif size2 == 'large': min_tr_time2 = 10
                                elif size2 == 'medium': min_tr_time2 = 15
                                elif size2 == 'small': min_tr_time2 = 20
                            
                            if min_tr_time1 <= wait1 <= 720 and min_tr_time2 <= wait2 <= 720:
                                tc1 = TransferConnection(h1_id, s1[-1].arrival_time, s2[0].departure_time, int(wait1), "", 0.8, 0.8)
                                tc2 = TransferConnection(h2_id, s2[-1].arrival_time, s3[0].departure_time, int(wait2), "", 0.8, 0.8)
                                rt = Route(segments=s1+s2+s3, transfers=[tc1, tc2])
                                rt.metadata["engine"] = "fastpath_2t_bridge"
                                routes.append(rt)
                                if len(routes) >= 30: return routes
        return routes


    def _get_reachable_hubs(self, src_id: int, start: datetime) -> Dict:
        # Hubs reachable via 1 direct train from source
        hubs = {}
        deps = self.graph.get_departures_from_stop(src_id, start, 1440)
        for dep, tid in deps:
            path = self.graph.get_train_path(tid)
            for pt in path:
                if pt['station_id'] in self.major_hubs:
                    hubs[pt['station_id']] = {'tid': tid, 'arr_time': pt['arrival'] if isinstance(pt['arrival'], datetime) else dep}
        return hubs

    def _get_incoming_hubs(self, dst_id: int) -> Dict:
        hubs = {}
        sched = self.graph.get_station_schedule(dst_id)
        for item in sched:
            tid = item['trip_id']
            path = self.graph.get_train_path(tid)
            for pt in path:
                if pt['station_id'] in self.major_hubs and pt['stop_seq'] < item['stop_seq']:
                    # Include the final destination ID for route segment recovery
                    hubs[pt['station_id']] = {'tid': tid, 'dst_id': dst_id}
        return hubs

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
