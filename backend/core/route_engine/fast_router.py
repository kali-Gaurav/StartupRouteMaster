import time
import logging
from typing import List, Dict, Tuple, Set
from collections import defaultdict
from datetime import datetime, timedelta

from .data_structures import Route, RouteSegment, TransferConnection
from .graph import TimeDependentGraph
from .constraints import RouteConstraints

logger = logging.getLogger(__name__)

class FastPathRouter:
    """
    Implements O(1) / Fast BFS routing using persistent train_path and station_schedule.
    Handles 0, 1, 2, and 3 transfers with significantly faster performance than RAPTOR.
    """
    def __init__(self, graph: TimeDependentGraph):
        self.graph = graph

    def find_routes(self, source_id: int, dest_id: int, date: datetime, constraints: RouteConstraints) -> List[Route]:
        max_transfers = constraints.max_transfers
        
        routes = []
        if max_transfers >= 0:
            routes.extend(self._find_direct(source_id, dest_id))
            
        if max_transfers >= 1 and len(routes) < 10:
            routes.extend(self._find_1_transfer(source_id, dest_id, constraints))
            
        if max_transfers >= 2 and len(routes) < 10:
            routes.extend(self._find_2_transfer(source_id, dest_id, constraints))
            
        if max_transfers >= 3 and len(routes) < 5:
             # 3 transfers is computationally heavier, but we can do a bounded search
             routes.extend(self._find_3_transfer(source_id, dest_id, constraints))
             
        # Deduplicate
        unique_routes = self._deduplicate(routes)
        return unique_routes

    def _get_segments(self, trip_id: int, from_stop: int, to_stop: int) -> List[RouteSegment]:
        segments = self.graph.get_trip_segments(trip_id)
        relevant = []
        started = False
        for seg in segments:
            if seg.departure_stop_id == from_stop:
                started = True
            if started:
                relevant.append(seg)
            if seg.arrival_stop_id == to_stop:
                break
        return relevant if (started and relevant and relevant[-1].arrival_stop_id == to_stop) else []

    def _find_direct(self, source_id: int, dest_id: int) -> List[Route]:
        direct_routes = []
        source_trains = self.graph.get_station_schedule(source_id)
        
        for st in source_trains:
            trip_id = st['trip_id']
            path = self.graph.get_train_path(trip_id)
            source_seq = st['stop_seq']
            
            for pt in path:
                if pt['station_id'] == dest_id and pt['stop_seq'] > source_seq:
                    segs = self._get_segments(trip_id, source_id, dest_id)
                    if segs:
                        direct_routes.append(Route(segments=segs))
                    break
        return direct_routes

    def _find_1_transfer(self, source_id: int, dest_id: int, constraints: RouteConstraints) -> List[Route]:
        routes = []
        # Precompute destination arriving trips and their stations
        dest_trains = self.graph.get_station_schedule(dest_id)
        
        # map: station_id -> list of (trip_id, arrival_at_dest_seq, dept_from_hub_seq)
        dest_reachability = defaultdict(list)
        for dt in dest_trains:
            trip_id = dt['trip_id']
            dest_seq = dt['stop_seq']
            path = self.graph.get_train_path(trip_id)
            for pt in path:
                if pt['stop_seq'] < dest_seq:
                    dest_reachability[pt['station_id']].append({
                        'trip_id': trip_id,
                        'hub_seq': pt['stop_seq'],
                        'dest_seq': dest_seq
                    })
                    
        source_trains = self.graph.get_station_schedule(source_id)
        for st in source_trains:
            trip_1 = st['trip_id']
            src_seq = st['stop_seq']
            path_1 = self.graph.get_train_path(trip_1)
            
            for pt_1 in path_1:
                if pt_1['stop_seq'] <= src_seq:
                    continue
                    
                hub_id = pt_1['station_id']
                if hub_id in dest_reachability:
                    for dt_info in dest_reachability[hub_id]:
                        trip_2 = dt_info['trip_id']
                        if trip_1 == trip_2: continue # Direct route
                        
                        segs_1 = self._get_segments(trip_1, source_id, hub_id)
                        segs_2 = self._get_segments(trip_2, hub_id, dest_id)
                        
                        if not segs_1 or not segs_2: continue
                        
                        arr_time = segs_1[-1].arrival_time
                        dep_time = segs_2[0].departure_time
                        
                        # Validate transfer
                        if arr_time < dep_time:
                            dur_mins = int((dep_time - arr_time).total_seconds() / 60)
                            if constraints.min_transfer_time <= dur_mins <= constraints.max_layover_time:
                                tc = TransferConnection(
                                    station_id=hub_id,
                                    arrival_time=arr_time,
                                    departure_time=dep_time,
                                    duration_minutes=dur_mins,
                                    station_name=self.graph.stop_cache.get(hub_id, type('obj', (object,), {'name': str(hub_id)})).name,
                                    facilities_score=0.8,
                                    safety_score=0.8
                                )
                                r = Route(
                                    segments=segs_1 + segs_2,
                                    transfers=[tc]
                                )
                                routes.append(r)
                                if len(routes) > constraints.max_results * 2:
                                    return routes
        return routes

    def _find_2_transfer(self, source_id: int, dest_id: int, constraints: RouteConstraints) -> List[Route]:
        routes = []
        dest_trains = self.graph.get_station_schedule(dest_id)
        dest_reachability = defaultdict(list)
        for dt in dest_trains:
            trip_id = dt['trip_id']
            dest_seq = dt['stop_seq']
            path = self.graph.get_train_path(trip_id)
            for pt in path:
                if pt['stop_seq'] < dest_seq:
                    dest_reachability[pt['station_id']].append({
                        'trip_id': trip_id,
                        'hub_seq': pt['stop_seq'],
                        'dest_seq': dest_seq
                    })
                    
        source_trains = self.graph.get_station_schedule(source_id)
        source_reachability = defaultdict(list)
        for st in source_trains:
            trip_id = st['trip_id']
            src_seq = st['stop_seq']
            path = self.graph.get_train_path(trip_id)
            for pt in path:
                if pt['stop_seq'] > src_seq:
                    source_reachability[pt['station_id']].append({
                        'trip_id': trip_id,
                        'src_seq': src_seq,
                        'hub_seq': pt['stop_seq']
                    })
        
        major_hubs = {s for s, stop in self.graph.stop_cache.items() if getattr(stop, 'is_hub', False) or getattr(stop, 'is_major', False)}
        if not major_hubs:
            major_hubs = set(list(source_reachability.keys())[:100])
            
        common_hubs_1 = set(source_reachability.keys()).intersection(major_hubs)
        common_hubs_2 = set(dest_reachability.keys()).intersection(major_hubs)
        
        for h1 in common_hubs_1:
            h1_trains = self.graph.get_station_schedule(h1)
            for ht in h1_trains:
                mid_trip = ht['trip_id']
                h1_seq = ht['stop_seq']
                mid_path = self.graph.get_train_path(mid_trip)
                for pt in mid_path:
                    if pt['stop_seq'] > h1_seq:
                        h2 = pt['station_id']
                        if h2 in common_hubs_2 and h1 != h2:
                            # Potential path: source -> h1 -> h2 -> dest
                            # We check time feasibility for mid_trip first
                            segs_2 = self._get_segments(mid_trip, h1, h2)
                            if not segs_2: continue
                            
                            mid_dep = segs_2[0].departure_time
                            mid_arr = segs_2[-1].arrival_time
                            
                            for s_info in source_reachability[h1][:3]:
                                trip_1 = s_info['trip_id']
                                if trip_1 == mid_trip: continue
                                segs_1 = self._get_segments(trip_1, source_id, h1)
                                if not segs_1: continue
                                
                                arr_1 = segs_1[-1].arrival_time
                                dur_1 = int((mid_dep - arr_1).total_seconds() / 60)
                                if not (constraints.min_transfer_time <= dur_1 <= constraints.max_layover_time):
                                    continue
                                    
                                for d_info in dest_reachability[h2][:3]:
                                    trip_3 = d_info['trip_id']
                                    if trip_3 == mid_trip or trip_3 == trip_1: continue
                                    segs_3 = self._get_segments(trip_3, h2, dest_id)
                                    if not segs_3: continue
                                    
                                    dep_3 = segs_3[0].departure_time
                                    dur_2 = int((dep_3 - mid_arr).total_seconds() / 60)
                                    if constraints.min_transfer_time <= dur_2 <= constraints.max_layover_time:
                                        tc1 = TransferConnection(
                                            station_id=h1, arrival_time=arr_1, departure_time=mid_dep, duration_minutes=dur_1,
                                            station_name=self.graph.stop_cache.get(h1, type('obj', (object,), {'name': str(h1)})).name,
                                            facilities_score=0.8, safety_score=0.8
                                        )
                                        tc2 = TransferConnection(
                                            station_id=h2, arrival_time=mid_arr, departure_time=dep_3, duration_minutes=dur_2,
                                            station_name=self.graph.stop_cache.get(h2, type('obj', (object,), {'name': str(h2)})).name,
                                            facilities_score=0.8, safety_score=0.8
                                        )
                                        routes.append(Route(segments=segs_1 + segs_2 + segs_3, transfers=[tc1, tc2]))
                                        if len(routes) > constraints.max_results: return routes
        return routes

    def _find_3_transfer(self, source_id: int, dest_id: int, constraints: RouteConstraints) -> List[Route]:
        # 3 transfers: source -> h1 -> h2 -> h3 -> dest
        # This is strictly restricted to HUB-TO-HUB paths for the middle legs
        routes = []
        major_hubs = [s for s, stop in self.graph.stop_cache.items() if getattr(stop, 'is_hub', False)]
        if len(major_hubs) < 2: return []

        dest_trains = self.graph.get_station_schedule(dest_id)
        dest_reachability = defaultdict(list)
        for dt in dest_trains:
            trip_id = dt['trip_id']
            path = self.graph.get_train_path(trip_id)
            for pt in path:
                if pt['stop_seq'] < dt['stop_seq']:
                    dest_reachability[pt['station_id']].append({'trip_id': trip_id, 'h_seq': pt['stop_seq']})

        source_trains = self.graph.get_station_schedule(source_id)
        source_reachability = defaultdict(list)
        for st in source_trains:
            trip_id = st['trip_id']
            path = self.graph.get_train_path(trip_id)
            for pt in path:
                if pt['stop_seq'] > st['stop_seq']:
                    source_reachability[pt['station_id']].append({'trip_id': trip_id, 'h_seq': pt['stop_seq']})

        # We only look for h1 -> h2 -> h3 where all are major hubs
        hubs_set = set(major_hubs)
        source_hubs = set(source_reachability.keys()).intersection(hubs_set)
        dest_hubs = set(dest_reachability.keys()).intersection(hubs_set)

        for h1 in source_hubs:
            h1_trains = self.graph.get_station_schedule(h1)
            for ht2 in h1_trains:
                trip_2 = ht2['trip_id']
                path_2 = self.graph.get_train_path(trip_2)
                for pt2 in path_2:
                    if pt2['stop_seq'] > ht2['stop_seq'] and pt2['station_id'] in hubs_set:
                        h2 = pt2['station_id']
                        if h1 == h2: continue
                        
                        h2_trains = self.graph.get_station_schedule(h2)
                        for ht3 in h2_trains:
                            trip_3 = ht3['trip_id']
                            if trip_3 == trip_2: continue
                            path_3 = self.graph.get_train_path(trip_3)
                            for pt3 in path_3:
                                if pt3['stop_seq'] > ht3['stop_seq'] and pt3['station_id'] in dest_hubs:
                                    h3 = pt3['station_id']
                                    if h3 == h2 or h3 == h1: continue
                                    
                                    # We have h1 -> h2 -> h3. Now find source -> h1 and h3 -> dest
                                    # To avoid huge complexity, just take the first valid match
                                    res = self._validate_3_hop(source_id, h1, h2, h3, dest_id, trip_2, trip_3, constraints, source_reachability, dest_reachability)
                                    if res:
                                        routes.append(res)
                                        if len(routes) >= 5: return routes
        return routes

    def _validate_3_hop(self, src, h1, h2, h3, dst, t2, t3, constraints, src_reach, dst_reach):
        segs_2 = self._get_segments(t2, h1, h2)
        segs_3 = self._get_segments(t3, h2, h3)
        if not segs_2 or not segs_3: return None
        
        # Check transfer t2 -> t3 at h2
        dur_2 = int((segs_3[0].departure_time - segs_2[-1].arrival_time).total_seconds() / 60)
        if not (constraints.min_transfer_time <= dur_2 <= constraints.max_layover_time): return None
        
        # Find trip 1 (src -> h1)
        for s_info in src_reach[h1][:2]:
            t1 = s_info['trip_id']
            if t1 == t2: continue
            segs_1 = self._get_segments(t1, src, h1)
            if not segs_1: continue
            dur_1 = int((segs_2[0].departure_time - segs_1[-1].arrival_time).total_seconds() / 60)
            if not (constraints.min_transfer_time <= dur_1 <= constraints.max_layover_time): continue
            
            # Find trip 4 (h3 -> dst)
            for d_info in dst_reach[h3][:2]:
                t4 = d_info['trip_id']
                if t4 == t3 or t4 == t2: continue
                segs_4 = self._get_segments(t4, h3, dst)
                if not segs_4: continue
                dur_3 = int((segs_4[0].departure_time - segs_3[-1].arrival_time).total_seconds() / 60)
                if constraints.min_transfer_time <= dur_3 <= constraints.max_layover_time:
                    # Success!
                    tcs = [
                        TransferConnection(h1, segs_1[-1].arrival_time, segs_2[0].departure_time, dur_1, self.graph.stop_cache[h1].name, 0.8, 0.8),
                        TransferConnection(h2, segs_2[-1].arrival_time, segs_3[0].departure_time, dur_2, self.graph.stop_cache[h2].name, 0.8, 0.8),
                        TransferConnection(h3, segs_3[-1].arrival_time, segs_4[0].departure_time, dur_3, self.graph.stop_cache[h3].name, 0.8, 0.8)
                    ]
                    return Route(segments=segs_1 + segs_2 + segs_3 + segs_4, transfers=tcs)
        return None

    def _deduplicate(self, routes: List[Route]) -> List[Route]:
        seen = set()
        unique = []
        for r in routes:
            if not r.segments: continue
            trips = tuple(seg.trip_id for seg in r.segments)
            if trips not in seen:
                seen.add(trips)
                r.total_duration = sum(s.duration_minutes for s in r.segments) + sum(t.duration_minutes for t in r.transfers)
                r.total_distance = sum(s.distance_km for s in r.segments)
                r.total_cost = sum(s.fare for s in r.segments)
                unique.append(r)
        unique.sort(key=lambda r: r.total_duration)
        return unique

