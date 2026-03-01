import asyncio
import logging
import time as _time
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import and_, or_, create_engine
from sqlalchemy.orm import joinedload, sessionmaker
import os

from database.session import SessionLocal

from database.models import (
    Stop, Trip, StopTime, Calendar, Route as RouteModel,
    Segment as SegmentModel, Transfer as TransferModel
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
            # Handle HH:MM:SS.ffffff
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
            stop_index=data['stop_index']
        )
        return TimeDependentGraph(snapshot)

    def _get_active_service_ids(self, session, date: datetime) -> List[str]:
        target_date = date.date()
        weekday = date.strftime('%A').lower()
        try:
            # Use only True for boolean comparison to satisfy Postgres
            regular_services = session.query(Calendar.service_id).filter(
                and_(
                    getattr(Calendar, weekday) == True,
                    Calendar.start_date <= target_date,
                    Calendar.end_date >= target_date
                )
            ).all()
            return [s[0] for s in regular_services]
        except Exception as e:
            logger.debug(f"First service ID query failed: {e}, trying string fallback")
            target_date_str = target_date.isoformat()
            regular_services = session.query(Calendar.service_id).filter(
                and_(
                    getattr(Calendar, weekday) == True,
                    Calendar.start_date <= target_date_str,
                    Calendar.end_date >= target_date_str
                )
            ).all()
            return [s[0] for s in regular_services]

    def _build_graph_sync(self, date: datetime) -> Dict:
        session = SessionLocal()
        try:
            from sqlalchemy import text
            
            service_ids = self._get_active_service_ids(session, date)
            logger.info(f"Building graph for {date.date()} with {len(service_ids)} active services")

            departures = defaultdict(list)
            arrivals = defaultdict(list)
            trip_segments = defaultdict(list)
            transfer_graph = defaultdict(list)
            stop_cache = {}
            route_patterns = defaultdict(list)
            station_schedule = defaultdict(list)
            train_path = defaultdict(list)

            # 1. Load all stops (Raw SQL for speed)
            stops_raw = session.execute(text("SELECT id, stop_id, code, name, city, state, is_major_junction, latitude, longitude FROM stops")).fetchall()
            for row in stops_raw:
                s = MockStop()
                s.id = row[0]
                s.stop_id = row[1]
                s.code = row[2]
                s.name = row[3]
                s.city = row[4]
                s.state = row[5]
                s.is_major_junction = bool(row[6])
                s.latitude = float(row[7] or 0.0)
                s.longitude = float(row[8] or 0.0)
                stop_cache[int(s.id)] = s

            # 2. Query Segments - Raw SQL for extreme performance
            if not service_ids:
                logger.warning("No active services found for this date.")
                segments_raw = []
            else:
                # Format IN clause
                placeholders = ','.join([f"'{sid}'" for sid in service_ids])
                query = f"""
                    SELECT 
                        s.trip_id, s.source_station_id, s.dest_station_id, 
                        s.departure_time, s.arrival_time, s.arrival_day_offset, 
                        s.duration_minutes, s.distance_km, s.cost,
                        t.trip_id as train_number, r.long_name as train_name
                    FROM segments s
                    JOIN trips t ON s.trip_id = t.id
                    JOIN gtfs_routes r ON t.route_id = r.id
                    WHERE t.service_id IN ({placeholders})
                    ORDER BY s.trip_id, s.arrival_day_offset, s.departure_time
                    """

                segments_raw = session.execute(text(query)).fetchall()
            
            logger.info(f"Found {len(segments_raw)} segments (Raw SQL)")

            # Track cumulative offset per trip to handle multi-day journeys correctly
            trip_cumulative_offsets = defaultdict(int)
            trip_last_arrival_time = {}

            for row in segments_raw:
                tid = int(row[0])
                try:
                    sid_src = int(row[1])
                    sid_dst = int(row[2])
                except (ValueError, TypeError):
                    continue
                
                # Raw SQLite returns times as strings 'HH:MM:SS'
                dep_time = _to_time(row[3])
                arr_time = _to_time(row[4])
                
                # Logic to handle day rollover within a trip
                if tid in trip_last_arrival_time:
                    # If this departure time is earlier than the last arrival time, 
                    # it MUST be on a subsequent day.
                    if dep_time < trip_last_arrival_time[tid]:
                        trip_cumulative_offsets[tid] += 1
                
                current_offset = trip_cumulative_offsets[tid]
                dep_dt = datetime.combine(date.date() + timedelta(days=current_offset), dep_time)
                
                # Segment-specific arrival offset (relative to its own departure)
                seg_arrival_offset = int(row[5] or 0)
                # If arrival time < departure time, it's at least +1 day automatically
                if arr_time < dep_time and seg_arrival_offset == 0:
                    seg_arrival_offset = 1
                
                # Update cumulative offset if segment spans midnight
                trip_cumulative_offsets[tid] += seg_arrival_offset
                arr_dt = datetime.combine(date.date() + timedelta(days=trip_cumulative_offsets[tid]), arr_time)
                
                # Remember this arrival for the next segment in the trip
                trip_last_arrival_time[tid] = arr_time
                
                # Index departure/arrival
                departures[sid_src].append((dep_dt, tid))
                arrivals[sid_dst].append((arr_dt, tid))
                
                seg = RouteSegment(
                    trip_id=tid,
                    departure_stop_id=sid_src,
                    arrival_stop_id=sid_dst,
                    departure_time=dep_dt,
                    arrival_time=arr_dt,
                    duration_minutes=int(row[6] or 0),
                    distance_km=float(row[7] or 0),
                    departure_code=stop_cache[sid_src].code if sid_src in stop_cache else str(sid_src),
                    arrival_code=stop_cache[sid_dst].code if sid_dst in stop_cache else str(sid_dst),
                    fare=float(row[8] or 0.0),
                    train_number=str(row[9] or ""),
                    train_name=str(row[10] or "")
                )
                if seg.duration_minutes <= 0:
                    seg.duration_minutes = max(1, int((arr_dt - dep_dt).total_seconds() / 60))
                
                trip_segments[tid].append(seg)

            # 3. Build Route Patterns
            for tid, segs in trip_segments.items():
                if segs:
                    pattern = [segs[0].departure_stop_id] + [s.arrival_stop_id for s in segs]
                    route_patterns[tuple(pattern)].append(tid)

            # 4. Transfers (Phase 4: Automatic Same-Station Transfers)
            try:
                # First, load existing transfers from DB
                transfers = session.query(TransferModel).all()
                for t in transfers:
                    from_sid = int(t.from_stop_id)
                    to_sid = int(t.to_stop_id)
                    if from_sid in stop_cache and to_sid in stop_cache:
                        tc = TransferConnection(
                            station_id=to_sid,
                            arrival_time=datetime.min,
                            departure_time=datetime.max,
                            duration_minutes=int(t.min_transfer_time or 15),
                            station_name=stop_cache[to_sid].name,
                            facilities_score=0.0,
                            safety_score=0.0
                        )
                        transfer_graph[from_sid].append(tc)
                
                # Second, automatically generate same-station transfers for all active stops
                # This ensures RAPTOR can always "transfer" between different trips at the same stop.
                for sid in stop_cache:
                    # Only add if not already present to avoid duplicates
                    if not any(tc.station_id == sid for tc in transfer_graph[sid]):
                        tc = TransferConnection(
                            station_id=sid,
                            arrival_time=datetime.min,
                            departure_time=datetime.max,
                            duration_minutes=15, # Default 15 mins for same-station transfer
                            station_name=stop_cache[sid].name,
                            facilities_score=5.0, # Neutral/Standard
                            safety_score=5.0
                        )
                        transfer_graph[sid].append(tc)
                logger.info(f"Generated {len(stop_cache)} same-station transfers.")

            except Exception as te:
                logger.warning(f"Transfer generation failed: {te}")

            # 5. Load station_schedule and train_path (Phase 10)
            try:
                day_of_week = date.strftime('%A')
                query_schedule = f"SELECT station_id, trip_id, arrival, departure, stop_seq FROM station_schedule WHERE day_of_week = '{day_of_week}'"
                schedule_rows = session.execute(text(query_schedule)).fetchall()
                for row in schedule_rows:
                    station_schedule[int(row[0])].append({
                        'trip_id': int(row[1]),
                        'arrival': row[2],
                        'departure': row[3],
                        'stop_seq': int(row[4])
                    })
                    train_path[int(row[1])].append({
                        'station_id': int(row[0]),
                        'arrival': row[2],
                        'departure': row[3],
                        'stop_seq': int(row[4])
                    })
                logger.info(f"Loaded {len(schedule_rows)} station_schedule entries.")
            except Exception as e:
                logger.warning(f"Failed to load station_schedule: {e}")

            all_stop_ids = sorted(stop_cache.keys())
            stop_index_map = {sid: idx for idx, sid in enumerate(all_stop_ids)}

            # Optimization 1: Sort departures and arrivals by time for efficient binary search
            for sid in departures:
                departures[sid].sort(key=lambda x: x[0])
            for sid in arrivals:
                arrivals[sid].sort(key=lambda x: x[0])

            logger.info(f"Graph build complete: {len(stop_cache)} stops, {len(trip_segments)} trips indexed")

            return {
                'departures_by_stop': departures,
                'arrivals_by_stop': arrivals,
                'trip_segments': trip_segments,
                'transfer_graph': transfer_graph,
                'stop_cache': stop_cache,
                'station_schedule': station_schedule,
                'train_path': train_path,
                'route_patterns': route_patterns,
                'stop_index': stop_index_map
            }
        finally:
            session.close()
