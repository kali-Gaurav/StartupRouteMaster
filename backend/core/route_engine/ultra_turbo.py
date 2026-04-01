import logging
import asyncio
import time
import json
import os
import sqlite3
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, date, timedelta

from core.data_structures import Route, RouteSegment
from database.config import Config
from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse

logger = logging.getLogger("ultra-turbo")

# This engine is designed for raw speed, so it uses its own connection logic.
def get_db_path():
    db_dir = Config.DB_DIR
    db_path = os.path.join(db_dir, "transit_graph.db")
    if not os.path.exists(db_path):
        # Fallback to legacy path
        db_path = os.path.join(Config.BASE_DIR, "database", "transit_graph.db")
    return db_path

class UltraTurboDirectEngine(BaseRoutingEngine):
    @property
    def engine_id(self) -> str:
        return "ultra_turbo_direct"
    """
    Subtask 1.2 - 1.4: High-Performance Direct Route Fetcher.
    Bypasses ORM and uses raw SQL for sub-5ms performance.
    REFACTORED to use a thread-safe synchronous DB connection to prevent asyncio deadlocks.
    """
    DAY_COLUMNS = {
        0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
        4: "friday", 5: "saturday", 6: "sunday"
    }

    def __init__(self):
        self.db_path = get_db_path()

    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        source_code = request.source_code
        dest_code = request.destination_code
        travel_date = request.departure_date.date()
        limit = request.limit
        
        start_ts = time.perf_counter()
        
        if os.getenv("DISABLE_ULTRA_TURBO") == "true": 
            return RoutingResponse(engine_name=self.engine_id, routes=[], latency_ms=0, yield_count=0)
            
        try:
            # Use asyncio.to_thread to run the synchronous DB logic in a separate thread
            routes = await asyncio.wait_for(
                asyncio.to_thread(self._find_routes_sync, source_code, dest_code, travel_date, limit),
                timeout=5.0 
            )
            
            latency_ms = (time.perf_counter() - start_ts) * 1000
            for r in routes:
                r.metadata["engine"] = self.engine_id
                
            return RoutingResponse(
                engine_name=self.engine_id,
                routes=routes,
                latency_ms=latency_ms,
                yield_count=len(routes)
            )
        except asyncio.TimeoutError:
            logger.error("Ultra-Turbo search timed out.")
            return RoutingResponse(
                engine_name=self.engine_id, 
                routes=[], 
                latency_ms=(time.perf_counter() - start_ts) * 1000, 
                yield_count=0,
                triage_status="FAILED",
                metadata={"error": "TIMEOUT"}
            )
        except Exception as e:
            logger.error(f"Ultra-Turbo Failure: {e}", exc_info=True)
            return RoutingResponse(
                engine_name=self.engine_id, 
                routes=[], 
                latency_ms=(time.perf_counter() - start_ts) * 1000, 
                yield_count=0,
                triage_status="FAILED",
                metadata={"error": str(e)}
            )
    def _find_routes_sync(self, source_code: str, dest_code: str, travel_date: date, limit: int) -> List[Route]:
        s_norm = source_code.upper().strip()
        d_norm = dest_code.upper().strip()
        if s_norm == d_norm: return []

        start_ts = time.perf_counter()
        
        try:
            # Each thread needs its own connection
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            src_ids = self._resolve_cluster_ids_sync(conn, source_code)
            dst_ids = self._resolve_cluster_ids_sync(conn, dest_code)
            if not src_ids or not dst_ids: return []

            cancelled = set()
            try:
                date_str = travel_date.strftime("%Y-%m-%d")
                for r in conn.execute("SELECT train_no FROM cancelled_trains WHERE travel_date = ?", (date_str,)).fetchall():
                    cancelled.add(str(r[0]))
            except Exception: pass
            
            day_idx = travel_date.weekday()
            day_name = self.DAY_COLUMNS.get(day_idx)
            if not day_name: return []

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
                ORDER BY (s2.arrival_timestamp - s1.departure_timestamp) ASC
                LIMIT ?
            """
            
            params = src_ids + dst_ids + [db_date, limit * 2]
            rows = conn.execute(query, params).fetchall()
            
            results = []
            for row in rows:
                if str(row['tno']) in cancelled: continue
                
                rt = Route()
                dep_dt = datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts1'])
                arr_dt = datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts2'])
                if arr_dt < dep_dt: arr_dt += timedelta(days=1)

                rt.add_segment(RouteSegment(
                    trip_id=int(row['tid']), 
                    departure_stop_id=int(row['sid1']), 
                    arrival_stop_id=int(row['sid2']), 
                    departure_time=dep_dt, 
                    arrival_time=arr_dt, 
                    duration_minutes=(row['ts2'] - row['ts1']) // 60, 
                    distance_km=max(0.0, float((row['d2'] or 0.0) - (row['d1'] or 0.0))), 
                    train_number=str(row['tno']),
                    train_name=str(row['tname']),
                    departure_code=str(row['code1']),
                    arrival_code=str(row['code2'])
                ))
                rt.metadata["engine"] = "ultra_turbo_direct"
                results.append(rt)

            results.sort(key=lambda x: x.total_duration)
            logger.info(f"⚡ Ultra-Turbo SYNC: Found {len(results)} direct routes for {source_code}->{dest_code} in {(time.perf_counter()-start_ts)*1000:.2f}ms")
            return results[:limit]

        finally:
            if 'conn' in locals() and conn:
                conn.close()

    async def _resolve_cluster_ids(self, conn: Any, code: str) -> List[int]:
        """Async version for Orchestrator/Async callers."""
        from utils.station_utils import get_metro_group_codes
        codes = get_metro_group_codes(code.upper().strip())
        
        from sqlalchemy import text
        from database.session import AsyncSession
        is_session = isinstance(conn, AsyncSession)

        ids = set()
        q_stops = f"SELECT id FROM stops WHERE code IN ({','.join('?' for _ in codes)})"
        
        if is_session:
            # SQLAlchemy uses :params or ? depending on driver, but text() helps
            # Using ? for sqlite, but for postgres we might need :p1, :p2
            # Let's unify with positional ? if allowed or just use simple string if safe (internal use)
            # Actually, let's use SQLAlchemy text and mapping
            q_stops_sa = f"SELECT id FROM stops WHERE code IN ({','.join([':c'+str(i) for i in range(len(codes))])})"
            params = {f"c{i}": c for i, c in enumerate(codes)}
            res = await conn.execute(text(q_stops_sa), params)
            for r in res.fetchall():
                ids.add(r[0])
        else:
            # aiosqlite or similar
            cursor = await conn.execute(q_stops, codes)
            for r in await cursor.fetchall():
                ids.add(r[0])
            
        if not ids: return []
        
        q_clusters = f"""
            SELECT scm2.station_id 
            FROM station_cluster_mapping scm1 
            JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id 
            WHERE scm1.station_id IN ({','.join(['?' for _ in ids])})
        """
        if is_session:
            q_clusters_sa = f"""
                SELECT scm2.station_id 
                FROM station_cluster_mapping scm1 
                JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id 
                WHERE scm1.station_id IN ({','.join([':s'+str(i) for i in range(len(ids))])})
            """
            params_cl = {f"s{i}": sid for i, sid in enumerate(ids)}
            try:
                res = await conn.execute(text(q_clusters_sa), params_cl)
                for r in res.fetchall():
                    ids.add(r[0])
            except: pass # Table might not exist
        else:
            try:
                cursor = await conn.execute(q_clusters, list(ids))
                for r in await cursor.fetchall():
                    ids.add(r[0])
            except: pass
            
        return list(ids)

    async def _collect_day_results(self, conn, src_ids, dst_ids, travel_date, limit, cancelled, memo, depth=0):
        # Direct search logic refactored from _find_routes_sync
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        day_name = days[travel_date.weekday()]
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
            WHERE s1.stop_id IN ({','.join(['?' for _ in src_ids])})
              AND s2.stop_id IN ({','.join(['?' for _ in dst_ids])})
              AND s1.stop_sequence < s2.stop_sequence
              AND ? BETWEEN c.start_date AND c.end_date
              AND c.{day_name} = 1
            ORDER BY (s2.arrival_timestamp - s1.departure_timestamp) ASC
            LIMIT ?
        """
        
        from database.session import AsyncSession
        from sqlalchemy import text
        is_session = isinstance(conn, AsyncSession)
        
        if is_session:
            # Re-map placeholders for SQLAlchemy
            q_sa = query.replace("?", ":p") # Placeholder fix logic needed for list
            # Simplify: use positional if possible, but SQLAlchemy prefers named
            p_map = {}
            for i, sid in enumerate(src_ids): p_map[f"s{i}"] = sid
            for i, did in enumerate(dst_ids): p_map[f"d{i}"] = did
            p_map["date"] = db_date
            p_map["limit"] = limit
            
            q_sa = f"""
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
                WHERE s1.stop_id IN ({','.join([':s'+str(i) for i in range(len(src_ids))])})
                  AND s2.stop_id IN ({','.join([':d'+str(i) for i in range(len(dst_ids))])})
                  AND s1.stop_sequence < s2.stop_sequence
                  AND :date BETWEEN c.start_date AND c.end_date
                  AND c.{day_name} = 1
                ORDER BY (s2.arrival_timestamp - s1.departure_timestamp) ASC
                LIMIT :limit
            """
            res = await conn.execute(text(q_sa), p_map)
            rows = res.fetchall()
        else:
            params = src_ids + dst_ids + [db_date, limit]
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            # row is tuple if aiosqlite, so we use indices
            # tid=0, tno=1, tname=2, sid1=3, sid2=4, code1=5, code2=6, ts1=7, ts2=8, d1=9, d2=10
            tno = str(row[1]) if is_session else str(row['tno'])
            if int(tno) in cancelled: continue
            
            rt = Route()
            ts1 = row[7] if is_session else row['ts1']
            ts2 = row[8] if is_session else row['ts2']
            sid1 = row[3] if is_session else row['sid1']
            sid2 = row[4] if is_session else row['sid2']
            code1 = row[5] if is_session else row['code1']
            code2 = row[6] if is_session else row['code2']
            tid = row[0] if is_session else row['tid']
            d1 = row[9] if is_session else row['d1']
            d2 = row[10] if is_session else row['d2']
            tname = row[2] if is_session else row['tname']

            dep_dt = datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=ts1)
            arr_dt = datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=ts2)
            if arr_dt < dep_dt: arr_dt += timedelta(days=1)

            rt.add_segment(RouteSegment(
                trip_id=int(tid), departure_stop_id=int(sid1), arrival_stop_id=int(sid2),
                departure_time=dep_dt, arrival_time=arr_dt,
                duration_minutes=(ts2 - ts1) // 60,
                distance_km=float((d2 or 0) - (d1 or 0)),
                train_number=tno, train_name=str(tname),
                departure_code=code1, arrival_code=code2
            ))
            rt.metadata["engine"] = "ultra_turbo"
            results.append(rt)
        return results

    def _collect_1t_results(self, conn, src_ids, dst_ids, travel_date, limit, cancelled):
        """
        [Task 51.3] Hub Greedy Join: Discover 1-transfer routes in <100ms.
        Principle: Join (Src -> Hub) and (Hub -> Dst) via SQL.
        """
        from core.hubs import MEGA_HUBS, MAJOR_HUBS
        all_hubs = list(MEGA_HUBS | MAJOR_HUBS)
        
        # 1. Resolve Hub IDs
        hub_ids_q = f"SELECT id FROM stops WHERE code IN ({','.join(['?' for _ in all_hubs])})"
        hub_ids = [r[0] for r in conn.execute(hub_ids_q, all_hubs).fetchall()]
        if not hub_ids: return []

        day_name = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][travel_date.weekday()]
        
        # 2. Optimized Join Query
        # Join Leg 1 and Leg 2 where Leg 1 ends at a Hub and Leg 2 starts at that same Hub.
        # Ensure Leg 2 departs after Leg 1 arrives + minimum transfer buffer.
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
              AND s2a.departure_timestamp > s1b.arrival_timestamp + 1800 -- Min 30m transfer
              AND s2a.departure_timestamp < s1b.arrival_timestamp + 21600 -- Max 6h wait
              AND s1b.stop_sequence > s1a.stop_sequence
              AND s2b.stop_sequence > s2a.stop_sequence
            LIMIT {limit}
        """
        
        params = src_ids + dst_ids + hub_ids
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            rt = Route()
            # Leg 1
            rt.add_segment(RouteSegment(
                trip_id=int(row['tid1']), departure_stop_id=int(row['sid1a']), arrival_stop_id=int(row['sid1b']),
                departure_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts1a']),
                arrival_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts1b']),
                duration_minutes=(row['ts1b'] - row['ts1a']) // 60,
                train_number=str(row['tno1']), train_name="L1", departure_code=row['code1a'], arrival_code=row['code1b']
            ))
            # Leg 2
            rt.add_segment(RouteSegment(
                trip_id=int(row['tid2']), departure_stop_id=int(row['sid2a']), arrival_stop_id=int(row['sid2b']),
                departure_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts2a']),
                arrival_time=datetime.combine(travel_date, datetime.min.time()) + timedelta(seconds=row['ts2b']),
                duration_minutes=(row['ts2b'] - row['ts2a']) // 60,
                train_number=str(row['tno2']), train_name="L2", departure_code=row['code2a'], arrival_code=row['code2b']
            ))
            rt.metadata["engine"] = "ultra_turbo_hop"
            results.append(rt)
        return results

    def _resolve_cluster_ids_sync(self, conn, code: str) -> List[int]:
        """Keep original sync version for internal threads."""
        from utils.station_utils import get_metro_group_codes
        codes = get_metro_group_codes(code.upper().strip())
        
        ids = set()
        q_stops = f"SELECT id FROM stops WHERE code IN ({','.join('?' for _ in codes)})"
        try:
            for r in conn.execute(q_stops, codes).fetchall():
                ids.add(r[0])
        except Exception: return [] # Table or connection issues
            
        if not ids: return []
        
        q_clusters = f"""
            SELECT scm2.station_id 
            FROM station_cluster_mapping scm1 
            JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id 
            WHERE scm1.station_id IN ({','.join('?' for _ in ids)})
        """
        try:
            for r in conn.execute(q_clusters, list(ids)).fetchall():
                ids.add(r[0])
        except Exception: pass # Table might not exist
            
        return list(ids)

    def __del__(self):
        pass

