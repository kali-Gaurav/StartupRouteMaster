import sqlite3
import logging
from datetime import datetime, timedelta, date
from typing import List, Set, Any
from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse
from core.data_utils.structures import Route, RouteSegment

logger = logging.getLogger(__name__)

class ExhaustiveDirectEngine(BaseRoutingEngine):
    """
    [Engineer 1-3 Task] 
    Goal: 100% Exhaustive search for all direct trains.
    Constraint: NO filters, ALL possible calendar dates within window.
    """
    
    @property
    def engine_id(self) -> str:
        return "exhaustive_direct"

    DAY_COLUMNS = {
        0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
        4: "friday", 5: "saturday", 6: "sunday"
    }

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _resolve_terminal_ids(self, conn, code: str) -> List[int]:
        # [Engineer 3 Task] Terminal Mapping (BCT -> MMCT, BDTS, etc.)
        from utils.station_utils import get_metro_group_codes
        from .ultra_turbo import TERMINAL_MAP
        
        code_u = code.upper().strip()
        codes = get_metro_group_codes(code_u)
        if not codes: codes = [code_u]
        
        # Merge Terminal Mappings
        if code_u in TERMINAL_MAP:
            for c in TERMINAL_MAP[code_u]:
                if c not in codes: codes.append(c)

        # Get IDs
        ids = set()
        q = f"SELECT id FROM stops WHERE code IN ({','.join('?' for _ in codes)})"
        for r in conn.execute(q, codes).fetchall():
            ids.add(r[0])
            
        # Cluster Expansion (Deep Discovery)
        try:
            q_cl = f"SELECT scm2.station_id FROM station_cluster_mapping scm1 JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id WHERE scm1.station_id IN ({','.join(['?' for _ in ids])})"
            for r in conn.execute(q_cl, list(ids)).fetchall():
                ids.add(r[0])
        except: pass
        return list(ids)

    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        # [Engineer 2 Task] Exhaustive Search Implementation
        start_ts = datetime.now()
        travel_date = request.departure_date.date()
        
        # Run in thread for SQLite blocking
        import asyncio
        loop = asyncio.get_running_loop()
        routes = await loop.run_in_executor(None, self._search_sync, request.source_code, request.destination_code, travel_date)
        
        return RoutingResponse(
            engine_name=self.engine_id,
            routes=routes,
            latency_ms=(datetime.now() - start_ts).total_seconds() * 1000,
            yield_count=len(routes)
        )

    def _search_sync(self, src_code: str, dst_code: str, travel_date: date) -> List[Route]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            src_ids = self._resolve_terminal_ids(conn, src_code)
            dst_ids = self._resolve_terminal_ids(conn, dst_code)
            if not src_ids or not dst_ids: return []

            day_name = self.DAY_COLUMNS.get(travel_date.weekday())
            db_date = travel_date.strftime("%Y%m%d")
            
            # [Engineer 1 Task] Optimized Query for 100% Coverage
            # We join calendar to ensure train is running on THIS date
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
                ORDER BY s1.departure_timestamp ASC
            """
            params = src_ids + dst_ids + [db_date]
            rows = conn.execute(query, params).fetchall()
            
            routes = []
            for row in rows:
                rt = Route()
                dep_dt = datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts1'])
                arr_dt = datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts2'])
                if arr_dt < dep_dt: arr_dt += timedelta(days=1)
                
                rt.add_segment(RouteSegment(
                    trip_id=row['tid'], departure_stop_id=row['sid1'], arrival_stop_id=row['sid2'],
                    departure_time=dep_dt, arrival_time=arr_dt,
                    duration_minutes=(row['ts2'] - row['ts1']) // 60,
                    distance_km=max(0.0, float((row['d2'] or 0.0) - (row['d1'] or 0.0))),
                    train_number=str(row['tno']), train_name=str(row['tname']),
                    departure_code=str(row['code1']), arrival_code=str(row['code2'])
                ))
                rt.metadata["engine"] = self.engine_id
                routes.append(rt)
            return routes
        finally:
            conn.close()
