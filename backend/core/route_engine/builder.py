import asyncio
import logging
import time as _time
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import and_, or_, create_engine, text, func
from sqlalchemy.orm import joinedload, sessionmaker
import os

from database.session import SessionLocal

from database.models import (
    Stop, Trip, StopTime, Calendar, CalendarDate, Route as RouteModel,
    Segment as SegmentModel, Transfer as TransferModel,
    StationHealthIndex
)
from .data_structures import RouteSegment, TransferConnection
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
            departures_by_stop=data['departures_by_stop'],
            arrivals_by_stop=data['arrivals_by_stop'],
            trip_segments=data['trip_segments'],
            transfer_graph=data['transfer_graph'],
            stop_cache=data['stop_cache'],
            station_schedule=data['station_schedule'],
            train_path=data['train_path'],
            route_patterns=data['route_patterns'],
            stop_index=data['stop_index'],
            station_time_index=data.get('station_time_index', {}),
            reliability_scores=data.get('reliability_scores', {}),
            station_ids_by_trip=data.get('station_ids_by_trip', {})
        )
        return TimeDependentGraph(snapshot)

    def _get_active_service_ids(self, session, date: datetime) -> List[str]:
        target_date = date.date()
        weekday = date.strftime('%A').lower()
        
        regular_services = session.query(Calendar.service_id).filter(
            and_(
                getattr(Calendar, weekday) == True,
                Calendar.start_date <= target_date,
                Calendar.end_date >= target_date
            )
        ).all()
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
        
        calendars = session.query(Calendar).filter(Calendar.service_id.in_(service_ids)).all()
        for cal in calendars:
            mask = 0
            if cal.monday: mask |= 1
            if cal.tuesday: mask |= 2
            if cal.wednesday: mask |= 4
            if cal.thursday: mask |= 8
            if cal.friday: mask |= 16
            if cal.saturday: mask |= 32
            if cal.sunday: mask |= 64
            bitmasks[cal.service_id] = mask
        return bitmasks

    def _build_graph_sync(self, date: datetime) -> Dict:
        session = SessionLocal()
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
            stops_raw = session.execute(text("SELECT id, stop_id, code, name, city, state, is_major_junction, latitude, longitude FROM stops")).fetchall()
            for row in stops_raw:
                s = MockStop()
                s.id, s.stop_id, s.code, s.name, s.city, s.state = row[0], row[1], row[2], row[3], row[4], row[5]
                s.is_major_junction, s.latitude, s.longitude = bool(row[6]), float(row[7] or 0.0), float(row[8] or 0.0)
                stop_cache[int(s.id)] = s

            # 2. Query Segments (Include service_id for bitmasking)
            if not service_ids:
                segments_raw = []
            else:
                placeholders = ','.join([f"'{sid}'" for sid in service_ids])
                query = f"""
                    SELECT 
                        s.trip_id, s.source_station_id, s.dest_station_id, 
                        s.departure_time, s.arrival_time, s.arrival_day_offset, 
                        s.duration_minutes, s.distance_km, s.cost,
                        t.trip_id as train_number, r.long_name as train_name,
                        t.service_id
                    FROM segments s
                    JOIN trips t ON CAST(s.trip_id AS INTEGER) = t.id
                    JOIN gtfs_routes r ON t.route_id = r.id
                    WHERE t.service_id IN ({placeholders})
                    ORDER BY s.trip_id, s.arrival_day_offset, s.departure_time
                    """
                segments_raw = session.execute(text(query)).fetchall()
            
            logger.info(f"Found {len(segments_raw)} segments.")

            trip_cumulative_offsets = defaultdict(int)
            trip_last_arrival_time = {}

            for row in segments_raw:
                tid = int(row[0])
                try:
                    sid_src, sid_dst = int(row[1]), int(row[2])
                except: continue
                
                dep_time, arr_time = _to_time(row[3]), _to_time(row[4])
                
                if tid in trip_last_arrival_time:
                    if dep_time < trip_last_arrival_time[tid]: trip_cumulative_offsets[tid] += 1
                
                current_offset = trip_cumulative_offsets[tid]
                dep_dt = datetime.combine(date.date() + timedelta(days=current_offset), dep_time)
                
                seg_arrival_offset = int(row[5] or 0)
                if arr_time < dep_time and seg_arrival_offset == 0: seg_arrival_offset = 1
                
                trip_cumulative_offsets[tid] += seg_arrival_offset
                arr_dt = datetime.combine(date.date() + timedelta(days=trip_cumulative_offsets[tid]), arr_time)
                trip_last_arrival_time[tid] = arr_time
                
                departures[sid_src].append((dep_dt, tid))
                arrivals[sid_dst].append((arr_dt, tid))
                
                station_time_index[sid_src][dep_dt.hour].append((dep_dt, tid))
                station_ids_by_trip[tid].add(sid_src)
                station_ids_by_trip[tid].add(sid_dst)
                
                # Fetch bitmask for Task 8
                sid = row[11]
                mask = service_bitmasks.get(sid, 127)
                
                seg = RouteSegment(
                    trip_id=tid, departure_stop_id=sid_src, arrival_stop_id=sid_dst,
                    departure_time=dep_dt, arrival_time=arr_dt,
                    duration_minutes=int(row[6] or 0), distance_km=float(row[7] or 0),
                    departure_code=stop_cache[sid_src].code if sid_src in stop_cache else str(sid_src),
                    arrival_code=stop_cache[sid_dst].code if sid_dst in stop_cache else str(sid_dst),
                    fare=float(row[8] or 0.0), train_number=str(row[9] or ""), train_name=str(row[10] or ""),
                    service_mask=mask
                )
                if seg.duration_minutes <= 0:
                    seg.duration_minutes = max(1, int((arr_dt - dep_dt).total_seconds() / 60))
                
                # IMPORTANT: Always add to trip_segments for Task 16 backward lookup
                trip_segments[tid].append(seg)

            # 3. Build Route Patterns
            invalid_trips = [tid for tid, segs in trip_segments.items() if not segs or len(segs) < 1]
            for tid, segs in trip_segments.items():
                if tid not in invalid_trips:
                    pattern = [segs[0].departure_stop_id] + [s.arrival_stop_id for s in segs]
                    route_patterns[tuple(pattern)].append(tid)
            
            if invalid_trips:
                logger.warning(f"TODO #10: Removing {len(invalid_trips)} unroutable trips.")
                for tid in invalid_trips:
                    if tid in trip_segments: del trip_segments[tid]
                    if tid in station_ids_by_trip: del station_ids_by_trip[tid]

            # 4. Transfers
            try:
                from .station_quality import StationQualityManager
                from database.config import Config
                transfers = session.query(TransferModel).all()
                for t in transfers:
                    f_sid, t_sid = int(t.from_stop_id), int(t.to_stop_id)
                    if f_sid in stop_cache and t_sid in stop_cache:
                        target = stop_cache[t_sid]
                        transfer_graph[f_sid].append(TransferConnection(
                            station_id=t_sid, arrival_time=datetime.min, departure_time=datetime.max,
                            duration_minutes=int(t.min_transfer_time or 15), station_name=target.name,
                            facilities_score=StationQualityManager.calculate_facility_score(getattr(target, 'facilities_json', {})),
                            safety_score=StationQualityManager.normalize_safety_score(getattr(target, 'safety_score', 50.0))
                        ))
                
                buf = Config.TRANSFER_WINDOW_MIN + Config.DELAY_BUFFER_MINUTES
                for sid in stop_cache:
                    if not any(tc.station_id == sid for tc in transfer_graph[sid]):
                        target = stop_cache[sid]
                        
                        # Phase 3: Real walking-time estimate based on platform count (TODO #25 & #26)
                        platform_count = getattr(target, 'platform_count', None) or 1
                        walking_time_minutes = min(15, max(5, int(platform_count * 1.5)))
                        total_transfer_time = buf + walking_time_minutes

                        transfer_graph[sid].append(TransferConnection(
                            station_id=sid, arrival_time=datetime.min, departure_time=datetime.max,
                            duration_minutes=total_transfer_time, station_name=target.name,
                            facilities_score=StationQualityManager.calculate_facility_score(getattr(target, 'facilities_json', {})),
                            safety_score=StationQualityManager.normalize_safety_score(getattr(target, 'safety_score', 50.0))
                        ))
                        
                        # Task 11: Cross-terminal Walking Transfers
                        from .clustering import StationClusterManager
                        cluster_manager = StationClusterManager(session)
                        nearby = cluster_manager.get_nearby_stations(sid)
                        for near_id, dist in nearby:
                            # 4km/h walking speed + buffer
                            walk_min = int((dist / 4.0) * 60) + 20 
                            near_stop = stop_cache.get(near_id)
                            if near_stop:
                                transfer_graph[sid].append(TransferConnection(
                                    station_id=near_id, arrival_time=datetime.min, departure_time=datetime.max,
                                    duration_minutes=walk_min, station_name=near_stop.name,
                                    facilities_score=0.0, safety_score=50.0
                                ))

            except Exception as te: logger.warning(f"Transfer error: {te}")

            # 5. Load station_schedule
            try:
                day = date.strftime('%A')
                p = ','.join([f"'{sid}'" for sid in service_ids])
                q = f"SELECT ss.station_id, ss.trip_id, ss.arrival, ss.departure, ss.stop_seq FROM station_schedule ss JOIN trips t ON ss.trip_id = t.id WHERE ss.day_of_week = '{day}' AND t.service_id IN ({p})"
                rows = session.execute(text(q)).fetchall()
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
            self._record_station_health(session, date, stop_cache, departures, arrivals)

            return {
                'departures_by_stop': departures, 'arrivals_by_stop': arrivals, 'trip_segments': trip_segments,
                'transfer_graph': transfer_graph, 'stop_cache': stop_cache, 'station_schedule': station_schedule,
                'train_path': train_path, 'route_patterns': route_patterns, 'stop_index': stop_index_map,
                'station_time_index': station_time_index, 'reliability_scores': reliability_scores,
                'station_ids_by_trip': station_ids_by_trip
            }
        finally: session.close()

    def _get_reliability_scores(self, session) -> Dict[Tuple[int, int], float]:
        from database.models import StationTrainHistory
        try:
            res = session.query(StationTrainHistory.trip_id, StationTrainHistory.station_id, func.count(StationTrainHistory.id), func.sum(func.case([(StationTrainHistory.delay_minutes <= 15, 1)], else_=0))).group_by(StationTrainHistory.trip_id, StationTrainHistory.station_id).all()
            return {(tid, sid): (on / total if total > 0 else 1.0) for tid, sid, total, on in res}
        except: return {}

    def _pre_build_audit(self, session, service_ids: List[str], count: int):
        if not service_ids: return
        try:
            p = ','.join([f"'{sid}'" for sid in service_ids])
            exp = session.execute(text(f"SELECT count(*) FROM trips WHERE service_id IN ({p})")).scalar()
            actual = session.execute(text(f"SELECT count(DISTINCT trip_id) FROM stop_times WHERE trip_id IN (SELECT id FROM trips WHERE service_id IN ({p}))")).scalar()
            logger.info(f"Audit: Expected {exp}, Found {actual} with stops.")
        except: pass

    def _record_station_health(self, session, dt: datetime, cache: Dict, deps: Dict, arrs: Dict):
        from sqlalchemy import delete
        target = dt.date()
        recs, zero = [], []
        for sid, stop in cache.items():
            dc, ac = len(deps.get(sid, [])), len(arrs.get(sid, []))
            if dc == 0: zero.append(getattr(stop, 'code', str(sid)))
            recs.append(StationHealthIndex(station_id=sid, date=target, dep_count=dc, arr_count=ac, health_score=(100.0 if dc > 0 else 0.0)))
        try:
            session.execute(delete(StationHealthIndex).where(StationHealthIndex.date == target))
            session.add_all(recs)
            session.commit()
            if zero: logger.warning(f"CRITICAL: {len(zero)} stations have 0 departures.")
        except: pass
