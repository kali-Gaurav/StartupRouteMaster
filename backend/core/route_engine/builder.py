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
from .transfer_graph_builder import TransferGraphBuilder

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
            h = parts[0] % 24
            return time(h, parts[1], parts[2] if len(parts) > 2 else 0)
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
            departures_by_stop=data.get('departures_by_stop', {}),
            arrivals_by_stop=data.get('arrivals_by_stop', {}),
            trip_segments=data['trip_segments'],
            transfer_graph=data['transfer_graph'],
            stop_cache=data['stop_cache'],
            station_schedule=data['station_schedule'],
            train_path=data['train_path'],
            route_patterns=data['route_patterns'],
            stop_index=data.get('stop_index', {}),
            station_time_index=data.get('station_time_index', {}),
            reliability_scores=data.get('reliability_scores', {}),
            station_ids_by_trip=data.get('station_ids_by_trip', {}),
            coordinate_matrix=data.get('coordinate_matrix'),
            stop_id_to_idx=data.get('stop_id_to_idx', {}),
            idx_to_stop_id=data.get('idx_to_stop_id', []),
            tbr_trip_nodes=data.get('tbr_trip_nodes'),
            tbr_trip_index=data.get('tbr_trip_index', {}),
            tbr_stop_index=data.get('tbr_stop_index', {})
        )
        tbr_bundle = {
            'tbr_trip_nodes': data.get('tbr_trip_nodes'),
            'tbr_trip_index': data.get('tbr_trip_index'),
            'tbr_stop_index': data.get('tbr_stop_index')
        }
        snapshot.vectorize(tbr_data=tbr_bundle)
        return TimeDependentGraph(snapshot)

    def _get_active_service_ids(self, session, date: datetime) -> List[str]:
        target_date = date.date()
        target_date_str = date.strftime('%Y%m%d') 
        weekday = date.strftime('%A').lower()
        regular_services = session.query(Calendar.service_id).filter(
            and_(
                getattr(Calendar, weekday) == True, 
                Calendar.start_date <= target_date_str,
                Calendar.end_date >= target_date_str
            )
        ).all()
        if not regular_services:
            regular_services = session.query(Calendar.service_id).filter(
                getattr(Calendar, weekday).in_([1, True])
            ).limit(2000).all()
        active_set = {s[0] for s in regular_services}
        exceptions = session.query(CalendarDate.service_id, CalendarDate.exception_type).filter(
            CalendarDate.date == target_date
        ).all()
        for service_id, exc_type in exceptions:
            if exc_type == 1: active_set.add(service_id)
            elif exc_type == 2: active_set.discard(service_id)
        return list(active_set)

    def _get_service_bitmasks(self, session, service_ids: List[str]) -> Dict[str, int]:
        bitmasks = {}
        if not service_ids: return {}
        placeholders = {f"sid_{i}": sid for i, sid in enumerate(service_ids)}
        in_clause = ", ".join([f":sid_{i}" for i in range(len(service_ids))])
        query = f"SELECT service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday FROM calendar WHERE service_id IN ({in_clause})"
        rows = session.execute(text(query), placeholders).fetchall()
        for i, row in enumerate(rows):
            if i < 2: logger.info(f"DEBUG: Bitmask Row: {row} | Size: {len(row)}")
            if len(row) < 8:
                logger.warning(f"Unexpected row size in bitmasks: {len(row)} at index {i}. Row: {row}")
                continue
            mask = 0
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
            # [Task 130 Diagnostic]
            bind_url = str(session.get_bind().url)
            logger.info(f"🚄 Building Graph for {date.date()} | DB: {bind_url}")
            self.is_postgresql = "postgresql" in bind_url
            
            service_ids = self._get_active_service_ids(session, date)
            service_bitmasks = self._get_service_bitmasks(session, service_ids)
            logger.info(f"Found {len(service_ids)} active services.")
            
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
            city_clusters = defaultdict(list)
            stop_to_city = {}
            hub_direct_adj = defaultdict(set)
            
            stops_raw = session.execute(
                text("SELECT id, stop_id, code, name, city, state, latitude, longitude, is_major_junction FROM stops")
            )
            # Fetch all to avoid cursor issues with logging len
            stops_list = list(stops_raw)
            logger.info(f"Processing stops and city clusters (Task 14)... Found {len(stops_list)} rows.")
            
            for row in stops_list:
                s = MockStop()
                s.id, s.stop_id, s.code, s.name, s.city, s.state = row[0], row[1], row[2], row[3], row[4], row[5]
                s.latitude, s.longitude = float(row[6] or 0.0), float(row[7] or 0.0)
                s.is_major_junction = bool(row[8])
                stop_cache[int(s.id)] = s
                if s.city:
                    normalized_city = s.city.lower().strip()
                    city_clusters[normalized_city].append(s.id)
                    stop_to_city[s.id] = normalized_city
            
            if not service_ids:
                segments_raw = []
                stop_times_raw = []
            else:
                placeholders = {f"sid_{i}": sid for i, sid in enumerate(service_ids)}
                in_clause = ", ".join([f":sid_{i}" for i in range(len(service_ids))])
                
                # [Task 130] Dynamic Dialect Selection (SQLite vs Postgres)
                self.is_postgresql = "postgresql" in str(session.get_bind().url)
                src_col = "source_stop_id"
                dst_col = "dest_station_id"
                
                # 1. Fetch Segments for metadata
                query_segs = f"""
                    SELECT 
                        s.trip_id, s.{src_col}, s.{dst_col}, 
                        s.departure_time, s.arrival_time, s.duration_minutes, s.distance_km, 
                        s.train_number, 
                        r.long_name as train_name, t.service_id 
                    FROM segments s 
                    JOIN trips t ON s.trip_id = t.id 
                    LEFT JOIN gtfs_routes r ON t.route_id = r.id 
                    WHERE t.service_id IN ({in_clause}) 
                    ORDER BY s.trip_id, s.departure_time
                """
                segments_raw = session.execute(text(query_segs).execution_options(yield_per=1000), placeholders)
                
                # 2. [OPTIMIZED] Fetch Stop Times using Integer Timestamps
                query_stops = f"""
                    SELECT st.trip_id, st.stop_id, st.arrival_timestamp, st.departure_timestamp, st.stop_sequence, t.service_id
                    FROM stop_times st
                    JOIN trips t ON st.trip_id = t.id
                    WHERE t.service_id IN ({in_clause})
                    ORDER BY st.trip_id, st.stop_sequence
                """
                stop_times_raw = session.execute(text(query_stops).execution_options(yield_per=2000), placeholders)
            
            logger.info(f"Processing segments metadata (Raw Count target: {len(service_ids)} services)...")
            try:
                logger.info(f"Segment columns: {segments_raw.keys()}")
            except:
                logger.info("Segment columns: UNKNOWN (not a Result object)")
            
            count = 0
            for row in segments_raw:
                try:
                    count += 1
                    # [Task 130] Handle Row objects (SQLAlchemy 2.0) or tuples robustly
                    if hasattr(row, '_mapping'):
                        r = row._mapping
                        tid = r['trip_id']
                        sid_src = r[src_col]
                        sid_dst = r[dst_col] 
                        svc_id = r['service_id']
                        train_num = r['train_number']
                        train_name = r.get('train_name', '')
                        dep_raw = r['departure_time']
                        arr_raw = r['arrival_time']
                        dist_km = r['distance_km']
                        dur_min = r['duration_minutes']
                    else:
                        tid = int(row[0])
                        sid_src, sid_dst = int(row[1]), int(row[2])
                        dep_raw = row[3]
                        arr_raw = row[4]
                        dur_min = int(row[5] or 0)
                        dist_km = float(row[6] or 0)
                        train_num = str(row[7] or "")
                        train_name = str(row[8] or "")
                        svc_id = row[9] if len(row) > 9 else None

                    # Parse times properly
                    dep_time = _to_time(dep_raw)
                    arr_time = _to_time(arr_raw)
                    
                    dep_dt = datetime.combine(date.date(), dep_time)
                    arr_dt = datetime.combine(date.date(), arr_time)
                    if arr_time < dep_time:
                        arr_dt += timedelta(days=1)

                    mask = service_bitmasks.get(svc_id, 127)
                    
                    # Ensure stop exists in cache
                    if sid_src not in stop_cache or sid_dst not in stop_cache:
                        if count < 5: logger.warning(f"Stop missing for segment: {sid_src} -> {sid_dst}")
                        continue

                    seg = RouteSegment(
                        trip_id=tid, 
                        departure_stop_id=sid_src, 
                        arrival_stop_id=sid_dst,
                        departure_time=dep_dt, 
                        arrival_time=arr_dt,
                        duration_minutes=dur_min, 
                        distance_km=dist_km,
                        departure_code=stop_cache[sid_src].code,
                        arrival_code=stop_cache[sid_dst].code,
                        fare=0.0, 
                        train_number=train_num, 
                        train_name=train_name,
                        service_mask=mask, 
                        stop_sequence=0
                    )
                    trip_segments[tid].append(seg)
                except Exception as e:
                    if count < 20: logger.error(f"Row {count} failed: {e} | Row: {row}")
                    continue
            
            logger.info(f"✅ Processed {count} segment rows. Populated {len(trip_segments)} trips.")
            if len(trip_segments) == 0:
                logger.error("❌ CRITICAL: No trip segments were populated! Search will fail.")

            logger.info("Building full trip sequences from stop_times...")
            trip_nodes_temp = defaultdict(list)
            
            # Optimization: Pre-define time conversion
            def sec_to_time(s):
                if s is None: return time(0,0)
                return time((int(s) // 3600) % 24, (int(s) // 60) % 60, int(s) % 60)

            for row in stop_times_raw:
                try:
                    if hasattr(row, '_mapping'):
                        r = row._mapping
                        tid = r['trip_id']
                        sid = r['stop_id']
                        arr_sec = r['arrival_timestamp']
                        dep_sec = r['departure_timestamp']
                        seq = r['stop_sequence']
                    else:
                        tid, sid, arr_sec, dep_sec, seq = row[:5]
                    
                    arr_t = sec_to_time(arr_sec)
                    dep_t = sec_to_time(dep_sec)
                    
                    trip_nodes_temp[tid].append({
                        'sid': int(sid), 'arr': arr_t, 'dep': dep_t, 'seq': seq
                    })
                except Exception as e:
                    continue

            for tid, nodes in trip_nodes_temp.items():
                nodes.sort(key=lambda x: x['seq'])
                trip_last_time_dt = None
                cumulative_days = 0
                
                # Fix trip segments and populate departures/arrivals
                for i in range(len(nodes)):
                    node = nodes[i]
                    sid = node['sid']
                    arr_time, dep_time = node['arr'], node['dep']
                    
                    if trip_last_time_dt and arr_time < trip_last_time_dt:
                        cumulative_days += 1
                    
                    actual_arr_dt = datetime.combine(date.date() + timedelta(days=cumulative_days), arr_time)
                    if dep_time < arr_time: 
                        cumulative_days += 1
                    actual_dep_dt = datetime.combine(date.date() + timedelta(days=cumulative_days), dep_time)
                    trip_last_time_dt = dep_time
                    
                    node['arr_dt'] = actual_arr_dt
                    node['dep_dt'] = actual_dep_dt
                    
                    if i < len(nodes) - 1:
                        departures[sid].append((actual_dep_dt, tid))
                        station_time_index[sid][actual_dep_dt.hour].append((actual_dep_dt, tid))
                    if i > 0:
                        arrivals[sid].append((actual_arr_dt, tid))
                    
                    station_ids_by_trip[tid].add(sid)

            # Sort departures and arrivals for bisect_left optimization
            for sid in departures:
                departures[sid].sort(key=lambda x: x[0])
            for sid in arrivals:
                arrivals[sid].sort(key=lambda x: x[0])

            # 3. Transfer Graph Generation (Audit: Integrated Step)
            logger.info("Building full transfer graph (Audit Step)...")

            # We wrap the async call in a sync bridge since we are in an executor
            import asyncio
            transfer_builder = TransferGraphBuilder(session)
            # Create a temporary loop if needed or just use run_until_complete logic
            # Since we are already in a thread, this is safe
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            transfer_graph = loop.run_until_complete(transfer_builder.build_transfer_graph())
            loop.close()

            # [Task 121: Elite Connectivity] Pre-compute TBR Edges (Nexus)
            from .tbr_edge_builder import TBREdgeBuilder
            
            # Route Patterns
            for tid, nodes in trip_nodes_temp.items():
                if len(nodes) > 1:
                    pattern = tuple(n['sid'] for n in nodes)
                    route_patterns[pattern].append(tid)

            # Coordinate Matrix & Stop Index
            num_stops = len(stop_cache)
            coords = np.zeros((num_stops, 2), dtype=np.float32)
            stop_id_to_idx = {}
            idx_to_stop_id = []
            SAFE_LAT, SAFE_LON = 20.5937, 78.9629
            for idx, sid in enumerate(sorted(stop_cache.keys())):
                stop = stop_cache[sid]
                lat, lon = float(stop.latitude or 0.0), float(stop.longitude or 0.0)
                if abs(lat) < 0.01 and abs(lon) < 0.01: lat, lon = SAFE_LAT, SAFE_LON
                coords[idx] = [lat, lon]
                stop_id_to_idx[sid] = idx
                idx_to_stop_id.append(sid)
            stop_index_map = stop_id_to_idx

            from .graph import MemMapManager
            mmap_res = MemMapManager.save_array("coordinate_matrix", coords)
            mapped_coords = MemMapManager.load_array("coordinate_matrix")

            # TBR Indexing
            from .tbr_structures import trip_node_dtype
            logger.info("🚄 Building TBR Vectorized Trip Sequences (Task 2 Alignment)...")
            total_trip_nodes = sum(len(nodes) for nodes in trip_nodes_temp.values())
            tbr_trip_nodes = np.zeros(total_trip_nodes, dtype=trip_node_dtype)
            tbr_trip_index = {}
            tbr_stop_index = defaultdict(list)
            current_node_offset = 0
            
            for tid, nodes in trip_nodes_temp.items():
                t_count = len(nodes)
                tbr_trip_index[tid] = (current_node_offset, t_count)
                for i, node in enumerate(nodes):
                    node_idx = current_node_offset + i
                    tbr_trip_nodes[node_idx] = (
                        node['sid'], 
                        int(node['arr_dt'].timestamp()), 
                        int(node['dep_dt'].timestamp())
                    )
                    tbr_stop_index[node['sid']].append((tid, i))
                current_node_offset += t_count

            # Create a temporary snapshot for the builder to use
            temp_snapshot = StaticGraphSnapshot(
                date=date,
                tbr_trip_nodes=tbr_trip_nodes,
                tbr_trip_index=tbr_trip_index
            )
            tbr_edge_builder = TBREdgeBuilder()
            tbr_edge_builder.build_tbr_edges(temp_snapshot)

            return {
                'departures_by_stop': departures, 'arrivals_by_stop': arrivals, 'trip_segments': trip_segments,
                'transfer_graph': transfer_graph, 'stop_cache': stop_cache, 'station_schedule': station_schedule,
                'train_path': train_path, 'route_patterns': route_patterns, 'stop_index': stop_index_map,
                'station_time_index': station_time_index, 'reliability_scores': reliability_scores,
                'station_ids_by_trip': station_ids_by_trip, 'coordinate_matrix': mapped_coords,
                'stop_id_to_idx': stop_id_to_idx, 'idx_to_stop_id': idx_to_stop_id,
                'city_clusters': city_clusters, 'hub_direct_adj': hub_direct_adj,
                'tbr_trip_nodes': tbr_trip_nodes, 'tbr_trip_index': tbr_trip_index, 'tbr_stop_index': tbr_stop_index
            }
        finally: session.close()

    def _get_reliability_scores(self, session) -> Dict[Tuple[int, int], float]:
        """
        [Task 173] Fetch pre-calculated reliability scores from the database.
        Scores are per (from_stop_id, to_stop_id) pair.
        """
        scores = {}
        try:
            # [Nexus Fix] Ensure table exists before querying
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS reliability_scores (
                    from_stop_id INTEGER,
                    to_stop_id INTEGER,
                    score REAL,
                    PRIMARY KEY (from_stop_id, to_stop_id)
                )
            """))
            session.commit()
            
            reliability_raw = session.execute(text("SELECT from_stop_id, to_stop_id, score FROM reliability_scores")).fetchall()
            for row in reliability_raw:
                from_id, to_id, score = int(row[0]), int(row[1]), float(row[2])
                scores[(from_id, to_id)] = score
            logger.info(f"Loaded {len(scores)} reliability scores.")
        except Exception as e:
            logger.warning(f"Failed to load reliability scores: {e}. Falling back to default (1.0).")
        return scores
