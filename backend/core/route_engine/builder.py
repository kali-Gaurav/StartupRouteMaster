
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

from core.data_utils.structures import RouteSegment, TransferConnection
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
        
        snapshot = StaticGraphSnapshot(date)
        snapshot._departures_data = data.get('_departures_data')
        snapshot._departures_index = data.get('_departures_index')
        snapshot._arrivals_data = data.get('_arrivals_data')
        snapshot._arrivals_index = data.get('_arrivals_index')
        snapshot._stop_id_map = data.get('_stop_id_map', {})
        snapshot.departures_by_stop = data.get('departures_by_stop', {})
        snapshot.arrivals_by_stop = data.get('arrivals_by_stop', {})
        snapshot.trip_segments = data['trip_segments']
        snapshot.transfer_graph = data['transfer_graph']
        snapshot.stop_cache = data['stop_cache']
        snapshot.station_schedule = data['station_schedule']
        snapshot.train_path = data['train_path']
        snapshot.route_patterns = data['route_patterns']
        snapshot.stop_index = data.get('stop_index', {})
        snapshot.station_time_index = data.get('station_time_index', {})
        snapshot.reliability_scores = data.get('reliability_scores', {})
        snapshot.station_ids_by_trip = data.get('station_ids_by_trip', {})
        snapshot.coordinate_matrix = data.get('coordinate_matrix')
        snapshot.stop_id_to_idx = data.get('stop_id_to_idx', {})
        snapshot.idx_to_stop_id = data.get('idx_to_stop_id', [])
        snapshot.tbr_trip_nodes = data.get('tbr_trip_nodes')
        snapshot.tbr_trip_index = data.get('tbr_trip_index', {})
        snapshot.tbr_stop_index = data.get('tbr_stop_index', {})
        snapshot._trip_id_map = data.get('_trip_id_map', {})
        snapshot.city_clusters = data.get('city_clusters', {})
        tbr_bundle = {
            'tbr_trip_nodes': data.get('tbr_trip_nodes'),
            'tbr_trip_index': data.get('tbr_trip_index'),
            'tbr_stop_index': data.get('tbr_stop_index')
        }
        snapshot.vectorize(tbr_data=tbr_bundle)
        return TimeDependentGraph(snapshot)

    def _get_active_service_ids(self, session, date: datetime) -> List[str]:
        from database.models import Calendar, CalendarDate
        target_date = date.date()
        target_date_str = date.strftime('%Y%m%d') # Standard format (No hyphens)
        weekday = date.strftime('%A').lower()
        
        # [Task 130 Resiliency] Use REPLACE to handle both 2024-01-01 and 20240101 formats in SQLite
        query = f"""
            SELECT service_id FROM calendar 
            WHERE {weekday} = 1 
            AND REPLACE(start_date, '-', '') <= :td
            AND REPLACE(end_date, '-', '') >= :td
        """
        regular_services = session.execute(text(query), {"td": target_date_str}).fetchall()
        if not regular_services:
            regular_services = session.query(Calendar.service_id).filter(
                getattr(Calendar, weekday).in_([1, True])
            ).limit(2000).all()
        active_set = {str(s[0]) for s in regular_services}
        exceptions = session.query(CalendarDate.service_id, CalendarDate.exception_type).filter(
            CalendarDate.date == target_date
        ).all()
        for service_id, exc_type in exceptions:
            if exc_type == 1: active_set.add(str(service_id))
            elif exc_type == 2: active_set.discard(str(service_id))
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
            bind = session.get_bind()
            bind_url = str(getattr(bind, "url", "unknown"))
            logger.info(f"🚄 [ELITE:BUILDER] Building Graph for {date.date()} | DB: {bind_url}")
            
            service_ids = self._get_active_service_ids(session, date)
            service_bitmasks = self._get_service_bitmasks(session, service_ids)
            logger.info(f"Found {len(service_ids)} active services.")
            
            # --- PHASE 1: Pre-allocate Large Structures ---
            from .tbr_structures import trip_node_dtype
            
            stop_cache = {}
            stop_id_to_idx = {}
            idx_to_stop_id = []
            city_clusters = defaultdict(list)
            
            # Fetch all stops first (Critical for indexing)
            stops_raw = session.execute(
                text("SELECT id, stop_id, code, name, city, state, latitude, longitude, is_major_junction FROM stops")
            )
            stops_list = list(stops_raw)
            for idx, row in enumerate(sorted(stops_list, key=lambda x: x[0])):
                sid = int(row[0])
                s = MockStop()
                s.id, s.stop_id, s.code, s.name, s.city, s.state = sid, row[1], row[2], row[3], row[4], row[5]
                s.latitude, s.longitude = float(row[6] or 0.0), float(row[7] or 0.0)
                s.is_major_junction = bool(row[8])
                stop_cache[sid] = s
                stop_id_to_idx[sid] = idx
                idx_to_stop_id.append(sid)
                if s.city:
                    city_key = s.city.lower().strip()
                    city_clusters[city_key].append(sid)
                    if sid in [5533, 1778, 3099]:
                        logger.info(f"DEBUG: Hub {s.code} added to cluster: {city_key}")
            
            logger.info(f"DEBUG: Total Clusters Formed: {len(city_clusters)}")
            
            BITSET_WORDS = (65536 // 64) + 1
            
            # --- PHASE 2: Fused SQL Processing ---
            if not service_ids: return {} 
            
            placeholder_names = [f"sid_{i}" for i in range(len(service_ids))]
            placeholders = {name: sid for name, sid in zip(placeholder_names, service_ids)}
            in_clause = ", ".join([f":{name}" for name in placeholder_names])
            
            # 1. Fetch Stop Times with Trip Meta
            query_stops = f"""
                SELECT st.trip_id, st.stop_id, st.arrival_timestamp, st.departure_timestamp, st.stop_sequence,
                       t.train_no
                FROM stop_times st
                JOIN trips t ON st.trip_id = t.id
                WHERE t.service_id IN ({in_clause})
                ORDER BY st.trip_id, st.stop_sequence
            """
            stop_times_raw = session.execute(text(query_stops).execution_options(yield_per=5000), placeholders)
            
            trip_nodes_temp = defaultdict(list)
            reach_bits_map = defaultdict(lambda: np.zeros(BITSET_WORDS, dtype=np.uint64))
            trip_stop_pos_map = defaultdict(dict)
            trip_meta = {} # Cache for train_number
            
            count = 0
            for row in stop_times_raw:
                if hasattr(row, '_mapping'):
                    r = row._mapping
                    tid, sid, arr_sec, dep_sec, seq = r['trip_id'], r['stop_id'], r['arrival_timestamp'], r['departure_timestamp'], r['stop_sequence']
                    tno = r['train_no']
                else:
                    tid, sid, arr_sec, dep_sec, seq = row[:5]
                    tno = row[5]
                trip_meta[tid] = tno
                
                count += 1
                # [Task 121: Elite Sequence Map]
                trip_stop_pos_map[tid][sid] = len(trip_nodes_temp[tid])
                trip_nodes_temp[tid].append((sid, arr_sec, dep_sec, seq))

            # [Task RO-012] Build Trip Reachability Bitset
            for tid, nodes in trip_nodes_temp.items():
                for sid, _, _, _ in nodes:
                    s_idx = stop_id_to_idx.get(sid)
                    if s_idx is not None:
                        reach_bits_map[tid][s_idx // 64] |= np.uint64(1) << np.uint64(s_idx % 64)

            logger.info(f"✅ [BUILDER] Done loading {count} stop_time rows into {len(trip_nodes_temp)} trips.")

            # --- PHASE 3: Vectorization & Reachability Construction ---
            total_nodes = sum(len(n) for n in trip_nodes_temp.values())
            tbr_trip_nodes = np.zeros(total_nodes, dtype=trip_node_dtype)
            tbr_trip_index = {}
            tbr_stop_index = defaultdict(list)
            
            tids_sorted = sorted(trip_nodes_temp.keys())
            reach_bits = np.zeros((len(tids_sorted), BITSET_WORDS), dtype=np.uint64)
            trip_id_to_idx = {tid: i for i, tid in enumerate(tids_sorted)}
            
            # [Task 146.2] Cluster Reachability Aggregator
            from .reachability import ClusterReachabilityMatrix
            from database.config import Config
            # Create stop_to_cluster reverse map for O(1) loop lookup
            stop_to_cluster = {}
            for cluster_name, sids in city_clusters.items():
                for sid in sids: stop_to_cluster[sid] = cluster_name
            
            # Map unique cluster names to indices for the matrix
            all_cluster_names = sorted(city_clusters.keys())
            cluster_name_to_idx = {name: i for i, name in enumerate(all_cluster_names)}
            cluster_matrix = ClusterReachabilityMatrix(date, cluster_name_to_idx)
            
            departures = defaultdict(list)
            arrivals = defaultdict(list)
            trip_segments = defaultdict(list)
            
            curr_off = 0
            base_timestamp = int(datetime.combine(date.date(), time(0)).timestamp())
            
            for tid in tids_sorted:
                nodes = sorted(trip_nodes_temp[tid], key=lambda x: x[3])
                t_count = len(nodes)
                tbr_trip_index[tid] = (curr_off, t_count)
                
                reach_idx = trip_id_to_idx[tid]
                reach_bits[reach_idx] = reach_bits_map[tid]
                
                # [Task 146.2] Capture cluster connectivity within this trip
                visited_clusters = []
                for node in nodes:
                    c_name = stop_to_cluster.get(node[0])
                    if c_name and (not visited_clusters or visited_clusters[-1] != c_name):
                        # Mark this cluster reachable from all PREVIOUS clusters in this trip
                        for prev_c in visited_clusters:
                            cluster_matrix.set_reachable(prev_c, c_name)
                        visited_clusters.append(c_name)
                
                # Pre-calculate all absolute arrival/departure times for the trip
                node_timestamps = []
                cum_days = 0
                last_arr_sec = -1
                for sid, arr_sec, dep_sec, seq in nodes:
                    if last_arr_sec != -1 and arr_sec < last_arr_sec:
                        cum_days += 1
                    eff_arr = arr_sec + (cum_days * 86400)
                    if dep_sec < arr_sec:
                         eff_dep = dep_sec + ((cum_days + 1) * 86400)
                    else:
                         eff_dep = dep_sec + (cum_days * 86400)
                    last_arr_sec = arr_sec
                    node_timestamps.append((base_timestamp + eff_arr, base_timestamp + eff_dep))

                # Now build nodes and segments
                for i, (sid, arr_sec, dep_sec, seq) in enumerate(nodes):
                    ts_arr, ts_dep = node_timestamps[i]
                    dt_arr = datetime.fromtimestamp(ts_arr)
                    dt_dep = datetime.fromtimestamp(ts_dep)
                    
                    tbr_trip_nodes[curr_off + i] = (sid, ts_arr, ts_dep)
                    tbr_stop_index[sid].append((tid, i))
                    
                    # RAPTOR Standard Collections
                    if i < t_count - 1:
                        departures[sid].append((dt_dep, tid))
                    if i > 0:
                        arrivals[sid].append((dt_arr, tid))
                        
                    # Pattern Generation Segments
                    if i < t_count - 1:
                        next_sid = nodes[i+1][0]
                        next_ts_arr = node_timestamps[i+1][0]
                        
                        trip_segments[tid].append(RouteSegment(
                            trip_id=tid,
                            departure_stop_id=sid,
                            arrival_stop_id=next_sid,
                            departure_time=dt_dep,
                            arrival_time=datetime.fromtimestamp(next_ts_arr),
                            train_number=trip_meta[tid],
                            stop_sequence=seq,
                            distance_km=0.0 # Standard fallback
                        ))
                    
                curr_off += t_count
            
            for sid in departures: departures[sid].sort(key=lambda x: x[0])
            for sid in arrivals: arrivals[sid].sort(key=lambda x: x[0])

            trip_nodes_temp.clear()
            reach_bits_map.clear()
            
            # [Task 146.3] Finalize multi-hop reachability
            cluster_matrix.compute_transitive_closure()
            
            # [Task 146.4] Persist Cluster Matrix
            cluster_matrix.save(Config.MEMMAP_DIR)
            logger.info(f"💾 [REACHABILITY] Saved Cluster Matrix for {date.date()} with {cluster_matrix.num_clusters} hubs.")

            # --- PHASE 4: Secondary Structures ---
            transfer_builder = TransferGraphBuilder(session)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            transfer_graph = loop.run_until_complete(transfer_builder.build_transfer_graph())
            loop.close()

            # Pass reach_bits directly to MemMap
            from .graph import MemMapManager
            ts = int(date.timestamp())
            MemMapManager.save_array(f"reach_{ts}", reach_bits)

            # Coordinate Matrix
            num_stops = len(stop_cache)
            coords = np.zeros((num_stops, 2), dtype=np.float32)
            SAFE_LAT, SAFE_LON = 20.5937, 78.9629
            for idx, sid in enumerate(idx_to_stop_id):
                stop = stop_cache[sid]
                lat, lon = float(stop.latitude or 0.0), float(stop.longitude or 0.0)
                if abs(lat) < 0.01 and abs(lon) < 0.01: lat, lon = SAFE_LAT, SAFE_LON
                coords[idx] = [lat, lon]
            
            MemMapManager.save_array("coordinate_matrix", coords)
            mapped_coords = MemMapManager.load_array("coordinate_matrix")


            return {
                'stop_cache': stop_cache,
                'departures_by_stop': departures,
                'arrivals_by_stop': arrivals,
                'transfer_graph': transfer_graph,
                'city_clusters': city_clusters,
                'tbr_trip_nodes': tbr_trip_nodes,
                'tbr_trip_index': tbr_trip_index,
                'tbr_stop_index': tbr_stop_index,
                '_trip_id_map': trip_id_to_idx,
                'stop_id_to_idx': stop_id_to_idx,
                'idx_to_stop_id': idx_to_stop_id,
                'coordinate_matrix': mapped_coords,
                'trip_stop_pos_map': trip_stop_pos_map,
                'trip_segments': dict(trip_segments),
                'reliability_scores': self._get_reliability_scores(session),
                'station_schedule': {}, 'train_path': {}, 'route_patterns': {}, 'station_time_index': {}, 'station_ids_by_trip': {}, 'hub_direct_adj': {}
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
