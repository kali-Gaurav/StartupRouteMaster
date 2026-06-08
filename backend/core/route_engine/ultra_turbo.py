import logging
import asyncio
import time
import json
import os
import sqlite3
from typing import List, Dict, Any, Optional, Set, Sequence
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor

from core.data_utils.structures import Route, RouteSegment
from database.config import Config
from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse

logger = logging.getLogger(__name__)

# Shared executor for heavy sync DB searches
_executor = ThreadPoolExecutor(max_workers=10)

# Legacy Terminal Mappings for Resilience
TERMINAL_MAP = {
    "BCT": ["MMCT", "BCT", "BDTS"],
    "CSTM": ["CSMT", "CSTM"],
    "MAS": ["MAS", "MS", "TBM"],
    "SBC": ["SBC", "YPR", "SMVB"]
}

def get_db_path():
    db_dir = Config.DB_DIR
    db_path = os.path.join(db_dir, "transit_graph.db")
    if not os.path.exists(db_path):
        db_path = os.path.join(Config.BASE_DIR, "database", "transit_graph.db")
    return db_path

class UltraTurboDirectEngine(BaseRoutingEngine):
    _hub_cache: Set[str] = set()
    _last_hub_refresh: float = 0

    @property
    def engine_id(self) -> str:
        return "ultra_turbo_direct"

    DAY_COLUMNS = {
        0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
        4: "friday", 5: "saturday", 6: "sunday"
    }

    def __init__(self):
        self.db_path = get_db_path()

    def _safe_int(self, val: Any, default: int = 0) -> int:
        if isinstance(val, int): return val
        try:
            return int(str(val))
        except (ValueError, TypeError):
            return default

    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        travel_date = request.departure_date.date()
        limit = request.limit
        start_ts = time.perf_counter()
        
        try:
            loop = asyncio.get_running_loop()
            routes = await asyncio.wait_for(
                loop.run_in_executor(_executor, self._find_routes_sync, request.source_code, request.destination_code, travel_date, limit),
                timeout=12.0 # Slightly higher internal timeout
            )
            
            latency_ms = (time.perf_counter() - start_ts) * 1000
            return RoutingResponse(
                engine_name=self.engine_id,
                routes=routes,
                latency_ms=latency_ms,
                yield_count=len(routes)
            )
        except Exception as e:
            logger.error(f"Ultra-Turbo Failure: {e}")
            return RoutingResponse(engine_name=self.engine_id, routes=[], latency_ms=0, yield_count=0)

    def _get_dynamic_hubs(self, conn) -> Set[str]:
        now = time.time()
        if not self._hub_cache or (now - self._last_hub_refresh > 3600):
            from core.engines.hubs import MEGA_HUBS, MAJOR_HUBS
            hubs = set(MEGA_HUBS | MAJOR_HUBS)
            try:
                dyn_q = "SELECT code FROM stops WHERE centrality_score > 0.02 OR is_major_junction = 1 LIMIT 100"
                for row in conn.execute(dyn_q).fetchall():
                    if row[0]: hubs.add(row[0])
                UltraTurboDirectEngine._hub_cache = hubs
                UltraTurboDirectEngine._last_hub_refresh = now
            except Exception: pass
        return self._hub_cache

    def _find_routes_sync(self, source_code: str, dest_code: str, travel_date: date, limit: int) -> List[Route]:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            src_ids = self._resolve_cluster_ids_sync(conn, source_code)
            dst_ids = self._resolve_cluster_ids_sync(conn, dest_code)
            
            if not src_ids or not dst_ids: return []

            hub_codes = self._get_dynamic_hubs(conn)
            hub_ids = []
            if hub_codes:
                hub_ids_q = f"SELECT id FROM stops WHERE code IN ({','.join(['?' for _ in hub_codes])})"
                hub_ids = [r[0] for r in conn.execute(hub_ids_q, list(hub_codes)).fetchall()]

            # 1. Primary Date
            routes = self._execute_search_core(conn, src_ids, dst_ids, hub_ids, travel_date, limit)
            
            # 2. Temporal Fallback (Yield Guard)
            if not routes:
                for offset in [7, -7, 14]:
                    fallback_date = travel_date + timedelta(days=offset)
                    routes = self._execute_search_core(conn, src_ids, dst_ids, hub_ids, fallback_date, limit)
                    if routes:
                        for r in routes: r.metadata["extrapolated"] = True
                        break
            return routes
        finally:
            if conn: conn.close()

    def _execute_search_core(self, conn, src_ids, dst_ids, hub_ids, travel_date, limit) -> List[Route]:
        direct = self._collect_direct_logic(conn, src_ids, dst_ids, travel_date, limit)
        transfers = []
        if len(direct) < 5:
            transfers = self._collect_1t_results(conn, src_ids, dst_ids, hub_ids, travel_date, limit)
        
        results = direct + transfers
        results.sort(key=lambda x: x.total_duration)
        return results[:limit]

    def _collect_direct_logic(self, conn, src_ids, dst_ids, travel_date, limit) -> List[Route]:
        day_name = self.DAY_COLUMNS.get(travel_date.weekday())
        db_date = travel_date.strftime("%Y%m%d")
        query = f"""
            SELECT 
                t.id as tid, t.trip_id as tno, t.service_id as tname,
                s1.stop_id as sid1, s2.stop_id as sid2,
                st1.code as code1, st2.code as code2,
                s1.departure_timestamp as ts1, s2.arrival_timestamp as ts2,
                s1.shape_dist_traveled as d1, s2.shape_dist_traveled as d2
            FROM trips t
            JOIN calendar c ON t.service_id = c.service_id
            JOIN stop_times s1 ON t.id = s1.trip_id
            JOIN stop_times s2 ON t.id = s2.trip_id
            JOIN stops st1 ON s1.stop_id = st1.id
            JOIN stops st2 ON s2.stop_id = st2.id
            WHERE s1.stop_id IN ({','.join('?' for _ in src_ids)})
              AND s2.stop_id IN ({','.join('?' for _ in dst_ids)})
              AND s1.stop_sequence < s2.stop_sequence
              AND ? BETWEEN c.start_date AND c.end_date
              AND c.{day_name} = 1
            LIMIT ?
        """
        params = src_ids + dst_ids + [db_date, limit]
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            rt = Route()
            dep_dt = datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts1'])
            arr_dt = datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts2'])
            if arr_dt < dep_dt: arr_dt += timedelta(days=1)
            rt.add_segment(RouteSegment(
                trip_id=self._safe_int(row['tid']), departure_stop_id=self._safe_int(row['sid1']), arrival_stop_id=self._safe_int(row['sid2']),
                departure_time=dep_dt, arrival_time=arr_dt,
                duration_minutes=(row['ts2'] - row['ts1']) // 60,
                distance_km=max(0.0, float((row['d2'] or 0.0) - (row['d1'] or 0.0))),
                train_number=str(row['tno']), train_name=str(row['tname']),
                departure_code=str(row['code1']), arrival_code=str(row['code2'])
            ))
            rt.metadata["engine"] = "ultra_turbo_direct"
            results.append(rt)
        return results

    def _collect_1t_results(self, conn, src_ids, dst_ids, hub_ids, travel_date, limit):
        if not hub_ids: return []
        day_name = self.DAY_COLUMNS.get(travel_date.weekday())
        query = f"""
            SELECT 
                t1.id as tid1, t1.trip_id as tno1, s1a.stop_id as sid1a, s1b.stop_id as sid1b,
                st1a.code as code1a, st1b.code as code1b, s1a.departure_timestamp as ts1a, s1b.arrival_timestamp as ts1b,
                t2.id as tid2, t2.trip_id as tno2, s2a.stop_id as sid2a, s2b.stop_id as sid2b,
                st2a.code as code2a, st2b.code as code2b, s2a.departure_timestamp as ts2a, s2b.arrival_timestamp as ts2b
            FROM trips t1
            JOIN calendar c1 ON t1.service_id = c1.service_id
            JOIN stop_times s1a ON t1.id = s1a.trip_id
            JOIN stop_times s1b ON t1.id = s1b.trip_id
            JOIN stops st1a ON s1a.stop_id = st1a.id
            JOIN stops st1b ON s1b.stop_id = st1b.id
            JOIN stop_times s2a ON s1b.stop_id = s2a.stop_id
            JOIN trips t2 ON s2a.trip_id = t2.id
            JOIN calendar c2 ON t2.service_id = c2.service_id
            JOIN stop_times s2b ON t2.id = s2b.trip_id
            JOIN stops st2a ON s2a.stop_id = st2a.id
            JOIN stops st2b ON s2b.stop_id = st2b.id
            WHERE s1a.stop_id IN ({','.join(['?' for _ in src_ids])})
              AND s2b.stop_id IN ({','.join(['?' for _ in dst_ids])})
              AND s1b.stop_id IN ({','.join(['?' for _ in hub_ids])})
              AND c1.{day_name} = 1 AND c2.{day_name} = 1
              AND s2a.departure_timestamp > s1b.arrival_timestamp + 1800
              AND s2a.departure_timestamp < s1b.arrival_timestamp + 21600
              AND s1b.stop_sequence > s1a.stop_sequence
              AND s2b.stop_sequence > s2a.stop_sequence
            LIMIT {limit}
        """
        params = src_ids + dst_ids + hub_ids
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            rt = Route()
            rt.add_segment(RouteSegment(
                trip_id=self._safe_int(row['tid1']), departure_stop_id=self._safe_int(row['sid1a']), arrival_stop_id=self._safe_int(row['sid1b']),
                departure_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts1a']),
                arrival_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts1b']),
                duration_minutes=(row['ts1b'] - row['ts1a']) // 60,
                train_number=str(row['tno1']), train_name="L1", departure_code=row['code1a'], arrival_code=row['code1b']
            ))
            rt.add_segment(RouteSegment(
                trip_id=self._safe_int(row['tid2']), departure_stop_id=self._safe_int(row['sid2a']), arrival_stop_id=self._safe_int(row['sid2b']),
                departure_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts2a']),
                arrival_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts2b']),
                duration_minutes=(row['ts2b'] - row['ts2a']) // 60,
                train_number=str(row['tno2']), train_name="L2", departure_code=row['code2a'], arrival_code=row['code2b']
            ))
            rt.metadata["engine"] = "ultra_turbo_hop"
            results.append(rt)
        return results

    def _resolve_cluster_ids_sync(self, conn, code: str) -> List[int]:
        from utils.station_utils import get_metro_group_codes
        code_u = code.upper().strip()
        codes = get_metro_group_codes(code_u)
        if not codes: codes = [code_u]
        
        # Inject legacy terminal mapping for Mumbai/Chennai/Bangalore
        if code_u in TERMINAL_MAP:
            for c in TERMINAL_MAP[code_u]:
                if c not in codes: codes.append(c)

        ids = set()
        try:
            q_stops = f"SELECT id FROM stops WHERE code IN ({','.join('?' for _ in codes)})"
            for r in conn.execute(q_stops, codes).fetchall():
                ids.add(r[0])
        except Exception: return []
        if not ids: return []
        try:
            q_clusters = f"SELECT scm2.station_id FROM station_cluster_mapping scm1 JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id WHERE scm1.station_id IN ({','.join(['?' for _ in ids])})"
            for r in conn.execute(q_clusters, list(ids)).fetchall():
                ids.add(r[0])
        except Exception: pass
        return list(ids)
