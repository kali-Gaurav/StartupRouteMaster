
import asyncio
import logging
import time as _time
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from sqlalchemy import and_, or_, create_engine, text, func
from sqlalchemy.orm import joinedload, sessionmaker
import os

from database.session import SessionTransit

from database.models import (
    Stop, Trip, StopTime, Calendar, CalendarDate, Route as RouteModel,
    Segment as SegmentModel, Transfer as TransferModel,
    StationHealthIndex
)
from core.data_structures import RouteSegment, TransferConnection
from .graph import TimeDependentGraph, StaticGraphSnapshot

logger = logging.getLogger(__name__)

def _to_time(val):
    if isinstance(val, time):
        return val
    if isinstance(val, datetime):
        return val.time()
    if isinstance(val, str):
        try:
            if '.' in val:
                val = val.split('.')[0]
            parts = [int(p) for p in val.split(':')]
            return time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)
        except Exception:
            return time(0, 0)
    return time(0, 0)

class MockStop:
    """Mock object that matches the expected Stop model interface"""
    id: int
    stop_id: str
    code: str
    name: str
    city: str
    state: str
    latitude: float = 0.0
    longitude: float = 0.0
    is_major_junction: bool = False

def _get_hour_buckets():
    return [[] for _ in range(24)]

class GraphBuilder:
    def __init__(self, executor: ThreadPoolExecutor, snapshot_manager=None):
        self.executor = executor
        self.snapshot_manager = snapshot_manager

    async def build_graph(self, date: datetime) -> TimeDependentGraph:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(self.executor, self._build_graph_sync, date)
        
        snapshot = StaticGraphSnapshot(
            date=date,
            _departures_data=data.get('_departures_data'),
            _departures_index=data.get('_departures_index'),
            _arrivals_data=data.get('_arrivals_data'),
            _arrivals_index=data.get('_arrivals_index'),
            _stop_id_map=data.get('_stop_id_map', {}),
            departures_by_stop={}, # Empty to save RAM
            arrivals_by_stop={},   # Empty to save RAM
            trip_segments=data['trip_segments'],
            transfer_graph=data['transfer_graph'],
            stop_cache=data['stop_cache'],
            station_schedule=data['station_schedule'],
            train_path=data['train_path'],
            route_patterns=data['route_patterns'],
            stop_index=data['stop_index'],
            station_time_index=data.get('station_time_index', {}),
            reliability_scores=data.get('reliability_scores', {}),
            station_ids_by_trip=data.get('station_ids_by_trip', {}),
            coordinate_matrix=data.get('coordinate_matrix'),
            stop_id_to_idx=data.get('stop_id_to_idx', {}),
            idx_to_stop_id=data.get('idx_to_stop_id', [])
        )
        return TimeDependentGraph(snapshot)

    def _get_active_service_ids(self, session, date: datetime) -> List[str]:
        target_date = date.date()
        target_date_str = date.strftime('%Y%m%d') # Format to GTFS YYYYMMDD
        weekday = date.strftime('%A').lower()
        
        # [FIX] Compare using string format or cast to match SQLite TEXT storage
        regular_services = session.query(Calendar.service_id).filter(
            and_(
                getattr(Calendar, weekday) == 1, # SQLite uses 1/0 for boolean
                Calendar.start_date <= target_date_str,
                Calendar.end_date >= target_date_str
            )
        ).all()
        
        if not regular_services:
            # Fallback for testing: pick first available date range from DB if target is outside
            logger.warning(f"No services found for {target_date_str}. Trying fallback to first available date range.")
            first_cal = session.query(Calendar).first()
            if first_cal:
                target_date_str = first_cal.start_date
                regular_services = session.query(Calendar.service_id).filter(
                    getattr(Calendar, weekday) == 1
                ).limit(500).all()

        active_set = {s[0] for s in regular_services}
        
        exceptions = session.query(CalendarDate.service_id, CalendarDate.exception_type).filter(
            CalendarDate.date == target_date
        ).all()
        
        for service_id, exc_type in exceptions:
            if exc_type == 1: active_set.add(service_id)
            elif exc_type == 2: active_set.discard(service_id)
                
        return list(active_set)

    def _get_service_bitmasks(self, session, service_ids: List[str]) -> Dict[str, int]:
        """Task 8: Calculate 7-bit mask for each service (Mon=1, Tue=2... Sun=64)."""
        bitmasks = {}
        if not service_ids: return {}
        
        # [FIX] Use raw SQL to avoid ORM 'id' column assumptions
        placeholders = ",".join([f"'{sid}'" for sid in service_ids])
        query = f"SELECT service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday FROM calendar WHERE service_id IN ({placeholders})"
        rows = session.execute(text(query)).fetchall()
        
        for row in rows:
            mask = 0
            # Indices: service_id=0, monday=1, tuesday=2, ... sunday=7
            if row[1]: mask |= 1
            if row[2]: mask |= 2
            if row[3]: mask |= 4
            if row[4]: mask |= 8
            if row[5]: mask |= 16
            if row[6]: mask |= 32
            if row[7]: mask |= 64
            bitmasks[row[0]] = mask
        return bitmasks

    def _build_graph_sync(self, date: datetime) -> Dict:
        session = SessionTransit()
        try:
            service_ids = self._get_active_service_ids(session, date)
            service_bitmasks = self._get_service_bitmasks(session, service_ids)
            logger.info(f"Building graph for {date.date()} with {len(service_ids)} active services")
            
            # ... rest of the setup ...
            departures = defaultdict(list)
            arrivals = defaultdict(list)
            trip_segments = defaultdict(list)
            transfer_graph = defaultdict(list)
            stop_cache = {}
            route_patterns = defaultdict(list)
            station_schedule = defaultdict(list)
            train_path = defaultdict(list)
            
            station_time_index = defaultdict(_get_hour_buckets)
            reliability_scores = self._get_reliability_scores(session)
            station_ids_by_trip = defaultdict(set)

            # 1. Load all stops
            stops_raw = session.execute(
                text("SELECT id, stop_id, code, name, city, state, latitude, longitude FROM stops").execution_options(yield_per=500)
            ) # Subtask 5.4
            for row in stops_raw:
                s = MockStop()
                s.id, s.stop_id, s.code, s.name, s.city, s.state = row[0], row[1], row[2], row[3], row[4], row[5]
                s.latitude, s.longitude = float(row[6] or 0.0), float(row[7] or 0.0)
                s.is_major_junction = False 
                stop_cache[int(s.id)] = s

            # 2. Query Segments (Include service_id for bitmasking)
            if not service_ids:
                segments_raw = []
            else:
                placeholders = ','.join([f"'{sid}'" for sid in service_ids])
                query = f"""
                    SELECT 
                        s.trip_id, s.source_stop_id, s.dest_station_id, 
                        s.departure_time, s.arrival_time, s.duration_minutes, s.distance_km, 
                        s.train_number, r.long_name as train_name, t.service_id 
                    FROM segments s 
                    JOIN trips t ON s.trip_id = t.id 
                    LEFT JOIN gtfs_routes r ON t.route_id = r.route_id 
                    WHERE t.service_id IN ({placeholders}) 
                    ORDER BY s.trip_id, s.departure_time
                """
                segments_raw = session.execute(text(query).execution_options(yield_per=500)) # Subtask 5.4
            
            logger.info("Processing segments with yield_per(500)...")

            trip_cumulative_offsets = defaultdict(int)
            trip_last_time = {}

            for row in segments_raw:
                tid = int(row[0])
                try:
                    sid_src, sid_dst = int(row[1]), int(row[2])
                except: continue
                
                dep_time, arr_time = _to_time(row[3]), _to_time(row[4])
                
                if tid in trip_last_time:
                    if dep_time < trip_last_time[tid]: trip_cumulative_offsets[tid] += 1
                
                current_offset = trip_cumulative_offsets[tid]
                dep_dt = datetime.combine(date.date() + timedelta(days=current_offset), dep_time)
                
                if arr_time < dep_time: 
                    trip_cumulative_offsets[tid] += 1
                
                arr_dt = datetime.combine(date.date() + timedelta(days=trip_cumulative_offsets[tid]), arr_time)
                trip_last_time[tid] = arr_time
                
                departures[sid_src].append((dep_dt, tid))
                arrivals[sid_dst].append((arr_dt, tid))
                
                station_time_index[sid_src][dep_dt.hour].append((dep_dt, tid))
                station_ids_by_trip[tid].add(sid_src)
                station_ids_by_trip[tid].add(sid_dst)
                
                # Fetch bitmask for Task 8
                sid_svc = row[9]
                mask = service_bitmasks.get(sid_svc, 127)
                
                seg = RouteSegment(
                    trip_id=tid, departure_stop_id=sid_src, arrival_stop_id=sid_dst,
                    departure_time=dep_dt, arrival_time=arr_dt,
                    duration_minutes=int(row[5] or 0), distance_km=float(row[6] or 0),
                    departure_code=stop_cache[sid_src].code if sid_src in stop_cache else str(sid_src),
                    arrival_code=stop_cache[sid_dst].code if sid_dst in stop_cache else str(sid_dst),
                    fare=0.0, 
                    train_number=str(row[7] or ""), train_name=str(row[8] or ""),
                    service_mask=mask
                )
                if seg.duration_minutes <= 0:
                    seg.duration_minutes = max(1, int((arr_dt - dep_dt).total_seconds() / 60))
                
                trip_segments[tid].append(seg)

            # 3. Build Route Patterns
            invalid_trips = [tid for tid, segs in trip_segments.items() if not segs or len(segs) < 1]
            for tid, segs in trip_segments.items():
                if tid not in invalid_trips:
                    pattern = [segs[0].departure_stop_id] + [s.arrival_stop_id for s in segs]
                    route_patterns[tuple(pattern)].append(tid)

            # 4. Transfers (Static + Dynamic 2km proximity)
            try:
                logger.info("Loading transfer graph with dynamic proximity (2km)...")
                # Pre-load from DB
                transfers = session.execute(
                    text("SELECT from_stop_id, to_stop_id, min_transfer_time, dist_meters FROM transfers").execution_options(yield_per=500)
                ).fetchall()
                for f_sid, t_sid, min_time, dist in transfers:
                    if f_sid in stop_cache and t_sid in stop_cache:
                        target = stop_cache[t_sid]
                        transfer_graph[f_sid].append(TransferConnection(
                            station_id=t_sid, arrival_time=datetime.min, departure_time=datetime.max,
                            duration_minutes=int(min_time or 15), station_name=target.name,
                            facilities_score=0.0, safety_score=50.0
                        ))
                
                # [NEW] Add dynamic transfers for any stations within 2km using Coordinate Matrix
                from scipy.spatial import KDTree
                # coords is already built at the end, but we need it here
                # Let's rebuild coordinates early
                all_ids = sorted(stop_cache.keys())
                coord_list = np.array([[stop_cache[sid].latitude, stop_cache[sid].longitude] for sid in all_ids])
                tree = KDTree(coord_list)
                
                # 2km is approx 0.018 degrees
                for i, sid in enumerate(all_ids):
                    # Find all within ~2km
                    indices = tree.query_ball_point(coord_list[i], 0.018)
                    for idx in indices:
                        neighbor_id = all_ids[idx]
                        if neighbor_id != sid:
                            target = stop_cache[neighbor_id]
                            # Simple 20 min walking estimate
                            transfer_graph[sid].append(TransferConnection(
                                station_id=neighbor_id, arrival_time=datetime.min, departure_time=datetime.max,
                                duration_minutes=20, station_name=target.name,
                                facilities_score=0.0, safety_score=50.0
                            ))
                
                logger.info(f"Transfer graph built with {sum(len(v) for v in transfer_graph.values())} edges.")
            except Exception as te: 
                logger.warning(f"Transfer error: {te}")

            # 5. Load station_schedule
            try:
                day = date.strftime('%A')
                p = ','.join([f"'{sid}'" for sid in service_ids])
                q = f"SELECT ss.station_id, ss.trip_id, ss.arrival, ss.departure, ss.stop_seq FROM station_schedule ss JOIN trips t ON ss.trip_id = t.id WHERE ss.day_of_week = '{day}' AND t.service_id IN ({p})"
                rows = session.execute(text(q).execution_options(yield_per=500))
                for r in rows:
                    si, ti = int(r[0]), int(r[1])
                    item = {'trip_id': ti, 'arrival': r[2], 'departure': r[3], 'stop_seq': int(r[4])}
                    station_schedule[si].append(item)
                    train_path[ti].append({'station_id': si, 'arrival': r[2], 'departure': r[3], 'stop_seq': int(r[4])})
            except Exception as e: logger.warning(f"Schedule error: {e}")

            # Optimization: Sort
            for sid in departures: departures[sid].sort(key=lambda x: x[0])
            for sid in arrivals: arrivals[sid].sort(key=lambda x: x[0])
            for sid in station_time_index:
                for h in range(24): station_time_index[sid][h].sort(key=lambda x: x[0])

            stop_index_map = {sid: idx for idx, sid in enumerate(sorted(stop_cache.keys()))}

            # Task 16.1: Coordinate Matrix
            num_stops = len(stop_cache)
            coords = np.zeros((num_stops, 2), dtype=np.float32)
            stop_id_to_idx = {}
            idx_to_stop_id = []
            for idx, sid in enumerate(sorted(stop_cache.keys())):
                stop = stop_cache[sid]
                # Task 17.2: Sanitize coords
                lat = float(stop.latitude or 0.0)
                lon = float(stop.longitude or 0.0)
                coords[idx] = [lat, lon]
                stop_id_to_idx[sid] = idx
                idx_to_stop_id.append(sid)

            # [Subtask 5.1] Memory Mapping Coordinate Matrix
            from .graph import MemMapManager
            mmap_path = MemMapManager.save_array("coordinate_matrix", coords)
            mapped_coords = MemMapManager.load_array("coordinate_matrix")
            logger.info(f"📍 Memory-mapped coordinate matrix to {mmap_path}")

            return {
                'departures_by_stop': departures, 'arrivals_by_stop': arrivals, 'trip_segments': trip_segments,
                'transfer_graph': transfer_graph, 'stop_cache': stop_cache, 'station_schedule': station_schedule,
                'train_path': train_path, 'route_patterns': route_patterns, 'stop_index': stop_index_map,
                'station_time_index': station_time_index, 'reliability_scores': reliability_scores,
                'station_ids_by_trip': station_ids_by_trip,
                'coordinate_matrix': mapped_coords,
                'stop_id_to_idx': stop_id_to_idx,
                'idx_to_stop_id': idx_to_stop_id
            }
        finally: session.close()

    def _get_reliability_scores(self, session) -> Dict[Tuple[int, int], float]:
        return {}
