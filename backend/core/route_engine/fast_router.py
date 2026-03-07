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
        # Major Hubs for 2-transfer bridging
        self.major_hubs = [
            142, 257, 1, 10, 50, 100, 500, 1000 # Placeholder IDs for major junctions
        ]

    def find_routes(self, source_id: int, dest_id: int, date: datetime, constraints: RouteConstraints) -> List[Route]:
        max_transfers = constraints.max_transfers
        window_start = date
        window_end = date + timedelta(hours=24)
        
        all_found: List[Route] = []
        all_found.extend(self._find_direct(source_id, dest_id, window_start, window_end))
        
        if max_transfers >= 1:
            all_found.extend(self._find_1_transfer(source_id, dest_id, constraints, window_start, window_end))
            
        if max_transfers >= 2:
            # Task 3: Intelligent 2-Transfer Bridge
            all_found.extend(self._find_2_transfer_hub_bridge(source_id, dest_id, constraints, window_start, window_end))
            
        return self._deduplicate(all_found)

    def _find_direct(self, source_id: int, dest_id: int, start: datetime, end: datetime) -> List[Route]:
        routes = []
        deps = self.graph.get_departures_from_stop(source_id, start, 1440)
        station_sets = getattr(self.graph.snapshot, 'station_ids_by_trip', {})
        for dep_time, tid in deps:
            if dest_id in station_sets.get(tid, set()):
                segs = self._get_segments(tid, source_id, dest_id)
                if segs: routes.append(Route(segments=segs))
        return routes

    def _find_1_transfer(self, source_id: int, dest_id: int, constraints: RouteConstraints, start: datetime, end: datetime) -> List[Route]:
        routes = []
        source_deps = self.graph.get_departures_from_stop(source_id, start, 1440)
        dest_sched = self.graph.get_station_schedule(dest_id)
        dest_reach = {d['trip_id']: d['stop_seq'] for d in dest_sched}
        
        for dep_1, tid_1 in source_deps:
            path_1 = self.graph.get_train_path(tid_1)
            src_seq = next((p['stop_seq'] for p in path_1 if p['station_id'] == source_id), -1)
            if src_seq == -1: continue
            
            for pt in path_1:
                if pt['stop_seq'] <= src_seq: continue
                hub_id = pt['station_id']
                hub_deps = self.graph.get_departures_from_stop(hub_id, pt['arrival'] if isinstance(pt['arrival'], datetime) else dep_1, 720)
                for dep_2, tid_2 in hub_deps:
                    if tid_1 == tid_2: continue
                    if tid_2 in dest_reach:
                        s1 = self._get_segments(tid_1, source_id, hub_id)
                        s2 = self._get_segments(tid_2, hub_id, dest_id)
                        if s1 and s2:
                            wait = (s2[0].departure_time - s1[-1].arrival_time).total_seconds() / 60
                            if constraints.min_transfer_time <= wait <= constraints.max_layover_time:
                                tc = TransferConnection(hub_id, s1[-1].arrival_time, s2[0].departure_time, int(wait), "", 0.8, 0.8)
                                routes.append(Route(segments=s1+s2, transfers=[tc]))
        return routes

    def _find_2_transfer_hub_bridge(self, src_id: int, dst_id: int, constraints: RouteConstraints, start: datetime, end: datetime) -> List[Route]:
        """PGT -> Hub A -> Hub B -> KOTA"""
        routes = []
        # Simplified bridge logic: Find Hubs reachable from SRC and Hubs that can reach DST
        # This is a Tier 2 BFS
        src_hubs = self._get_reachable_hubs(src_id, start)
        dst_hubs = self._get_incoming_hubs(dst_id)
        
        for h1_id, info1 in src_hubs.items():
            for h2_id, info2 in dst_hubs.items():
                # Check Hub-to-Hub direct connection
                h1_deps = self.graph.get_departures_from_stop(h1_id, info1['arr_time'], 720)
                for dep_mid, tid_mid in h1_deps:
                    if tid_mid == info1['tid'] or tid_mid == info2.get('tid'): continue # No self-transfers
                    station_sets = getattr(self.graph.snapshot, 'station_ids_by_trip', {})
                    if h2_id in station_sets.get(tid_mid, set()):
                        # We found a 2-transfer path!
                        # s1: src->h1, s2: h1->h2, s3: h2->dst
                        s1 = self._get_segments(info1['tid'], src_id, h1_id)
                        s2 = self._get_segments(tid_mid, h1_id, h2_id)
                        s3 = self._get_segments(info2['tid'], h2_id, dst_id)
                        
                        if s1 and s2 and s3:
                            wait1 = (s2[0].departure_time - s1[-1].arrival_time).total_seconds() / 60
                            wait2 = (s3[0].departure_time - s2[-1].arrival_time).total_seconds() / 60
                            if 30 <= wait1 <= 480 and 30 <= wait2 <= 480:
                                tc1 = TransferConnection(h1_id, s1[-1].arrival_time, s2[0].departure_time, int(wait1), "", 0.8, 0.8)
                                tc2 = TransferConnection(h2_id, s2[-1].arrival_time, s3[0].departure_time, int(wait2), "", 0.8, 0.8)
                                routes.append(Route(segments=s1+s2+s3, transfers=[tc1, tc2]))
                                if len(routes) > 20: return routes
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
                    hubs[pt['station_id']] = {'tid': tid}
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
