import logging
import asyncio
import time
import json
import os
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, date, timedelta
from sqlalchemy import text

from database.session import get_raw_transit_conn
from core.data_structures import Route, RouteSegment, TransferConnection
from core.pricing.fare_calculator import calculate_fare

logger = logging.getLogger("ultra-turbo")

class UltraTurboDirectEngine:
    """
    Subtask 1.2 - 1.4: High-Performance Direct Route Fetcher.
    Bypasses ORM and uses raw SQL with indexing hints for sub-5ms performance.
    """
    _conn_semaphore = asyncio.Semaphore(10)
    
    # [Gap 18] Static Safe Column Mapping
    DAY_COLUMNS = {
        0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
        4: "friday", 5: "saturday", 6: "sunday"
    }

    def __init__(self):
        pass # Mapping moved to class level for efficiency

    async def find_routes(self, source_code: str, dest_code: str, travel_date: date, limit: int = 50) -> List[Route]:
        if os.getenv("DISABLE_ULTRA_TURBO") == "true": return []
        start_ts = time.perf_counter()
        try:
            return await asyncio.wait_for(
                self._find_routes_inner(source_code, dest_code, travel_date, limit, start_ts),
                timeout=2.0 
            )
        except Exception as e:
            logger.error(f"Ultra-Turbo Failure: {e}")
            return []

    async def _find_routes_inner(self, source_code: Any, dest_code: Any, travel_date: date, limit: int, start_ts: float) -> List[Route]:
        s_norm = str(source_code).upper().strip()
        d_norm = str(dest_code).upper().strip()
        if s_norm == d_norm: return []

        results = []
        # [Gap 9] Concurrency Fix: Use sequential setup to avoid aiosqlite locking on single conn
        async with get_raw_transit_conn() as conn:
            date_str = travel_date.strftime("%Y-%m-%d")
            
            # 1. Resolve Clusters
            src_ids = await self._resolve_cluster_ids(conn, source_code)
            dst_ids = await self._resolve_cluster_ids(conn, dest_code)
            if not src_ids or not dst_ids: return []

            # 2. Get Metadata & Cancellations
            # Task 7: Combine cancelled_trains with calendar_dates (exception_type=2)
            cancelled = set()
            try:
                async with conn.execute("SELECT train_no FROM cancelled_trains WHERE travel_date = :dt", {"dt": date_str}) as c:
                    rows = await c.fetchall()
                    for r in rows: cancelled.add(str(r[0]))
                
                query_gtfs_exceptions = """
                    SELECT t.trip_id 
                    FROM calendar_dates cd
                    JOIN trips t ON cd.service_id = t.service_id
                    WHERE cd.date = :dt AND cd.exception_type = 2
                """
                async with conn.execute(query_gtfs_exceptions, {"dt": date_str}) as c:
                    for r in await c.fetchall(): cancelled.add(str(r[0]))
            except Exception as e:
                logger.warning(f"UltraTurbo metadata fetch failed: {e}")

            # 3. Parallel Execution of Search Queries
            # Since these are read-only queries on the same connection, aiosqlite *might* serialize them safely,
            # but it's safer to run them sequentially or use a pool. 
            # However, for speed, we want parallel. But `conn` is single.
            # We'll run them sequentially to guarantee safety against "database is locked".
            # The queries are sub-millisecond anyway.
            
            # [Gap 11] Remove arbitrary limit division
            # Direct routes are cheap, get as many as needed.
            direct_results = await self._collect_day_results(conn, src_ids, dst_ids, travel_date, limit, cancelled, {}, 0)
            results.extend(direct_results)
            
            # 1-Transfer: Fill the rest of the limit
            remaining = limit - len(results)
            if remaining > 0:
                t1_results = await self._collect_1t_results(conn, src_ids, dst_ids, travel_date, remaining, cancelled, {})
                results.extend(t1_results)
                
        results.sort(key=lambda x: x.total_duration)
        logger.info(f"⚡ Ultra-Turbo: Found {len(results)} routes for {source_code}->{dest_code} in {(time.perf_counter()-start_ts)*1000:.2f}ms")
        return results[:limit]

    async def _resolve_cluster_ids(self, conn, code: Any) -> List[int]:
        if isinstance(code, int): return [code]
        c_str = str(code).upper().strip()
        from utils.station_utils import get_metro_group_codes
        codes = get_metro_group_codes(c_str)
        
        ids = set()
        # 1. Resolve stop IDs for all codes in group
        q_stops = "SELECT id FROM stops WHERE code IN (SELECT value FROM json_each(:codes))"
        async with conn.execute(q_stops, {"codes": json.dumps(codes)}) as cursor:
            rows = await cursor.fetchall()
            for r in rows: ids.add(r[0])
            
        if not ids: return []
        
        # 2. Resolve cluster mappings for all IDs found
        q_clusters = """
            SELECT scm2.station_id 
            FROM station_cluster_mapping scm1 
            JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id 
            WHERE scm1.station_id IN (SELECT value FROM json_each(:sids))
        """
        async with conn.execute(q_clusters, {"sids": json.dumps(list(ids))}) as cursor:
            rows = await cursor.fetchall()
            for r in rows: ids.add(r[0])
            
        return list(ids)

    async def _collect_day_results(self, conn, src_ids, dst_ids, target_date, limit, cancelled_set, fare_configs, offset):
        day_results = []
        async for rt in self._execute_query(conn, src_ids, dst_ids, target_date, limit, cancelled_set, offset):
            day_results.append(rt)
        return day_results

    async def _collect_1t_results(self, conn, src_ids, dst_ids, target_date, limit, cancelled_set, fare_configs):
        day_idx = target_date.weekday()
        if day_idx not in self.DAY_COLUMNS: return []
        day_name = self.DAY_COLUMNS[day_idx]
            
        db_date = target_date.strftime("%Y%m%d")
        # [Gap 12] Add ORDER BY for determinism
        next_day_idx = (day_idx + 1) % 7
        next_day_name = self.DAY_COLUMNS[next_day_idx]
        tomorrow_db_date = (target_date + timedelta(days=1)).strftime("%Y%m%d")

        query = f"""
            WITH leg1 AS (
                SELECT s1.trip_id as tid1, s1.stop_id as sid1, s2.stop_id as hub, s1.departure_timestamp as ts_dep1, s2.arrival_timestamp as ts_arr1, 
                       t.trip_id as tno1, t.service_id as tname1, sh.name as hub_name, sh.code as hub_code, st1.code as code1,
                       s1.departure_time as dep1, s2.arrival_time as arr1, s1.shape_dist_traveled as d1, s2.shape_dist_traveled as d2
                FROM stop_times s1 
                JOIN stop_times s2 ON s1.trip_id = s2.trip_id 
                JOIN stops sh ON s2.stop_id = sh.id 
                JOIN stops st1 ON s1.stop_id = st1.id
                JOIN trips t ON s1.trip_id = t.id 
                JOIN calendar c ON t.service_id = c.service_id
                WHERE s1.stop_id IN (SELECT value FROM json_each(:src)) 
                  AND s1.stop_sequence < s2.stop_sequence 
                  AND c.{day_name} = 1 
                  AND :db_date BETWEEN c.start_date AND c.end_date
            ),
            leg2 AS (
                SELECT s1.trip_id as tid2, s1.stop_id as hub, s2.stop_id as sid2, s1.departure_timestamp as ts_dep2, s2.arrival_timestamp as ts_arr2, 
                       t.trip_id as tno2, t.service_id as tname2, st2.code as code2,
                       s1.departure_time as dep2, s2.arrival_time as arr2, s1.shape_dist_traveled as d1, s2.shape_dist_traveled as d2,
                       0 as day_adj
                FROM stop_times s1 
                JOIN stop_times s2 ON s1.trip_id = s2.trip_id 
                JOIN stops st2 ON s2.stop_id = st2.id
                JOIN trips t ON s1.trip_id = t.id 
                JOIN calendar c ON t.service_id = c.service_id
                WHERE s2.stop_id IN (SELECT value FROM json_each(:dst)) 
                  AND s1.stop_sequence < s2.stop_sequence 
                  AND c.{day_name} = 1 
                  AND :db_date BETWEEN c.start_date AND c.end_date
                
                UNION ALL
                
                SELECT s1.trip_id as tid2, s1.stop_id as hub, s2.stop_id as sid2, s1.departure_timestamp as ts_dep2, s2.arrival_timestamp as ts_arr2, 
                       t.trip_id as tno2, t.service_id as tname2, st2.code as code2,
                       s1.departure_time as dep2, s2.arrival_time as arr2, s1.shape_dist_traveled as d1, s2.shape_dist_traveled as d2,
                       86400 as day_adj
                FROM stop_times s1 
                JOIN stop_times s2 ON s1.trip_id = s2.trip_id 
                JOIN stops st2 ON s2.stop_id = st2.id
                JOIN trips t ON s1.trip_id = t.id 
                JOIN calendar c ON t.service_id = c.service_id
                WHERE s2.stop_id IN (SELECT value FROM json_each(:dst)) 
                  AND s1.stop_sequence < s2.stop_sequence 
                  AND c.{next_day_name} = 1 
                  AND :tm_date BETWEEN c.start_date AND c.end_date
            )
            SELECT l1.*, l2.* FROM leg1 l1 
            JOIN leg2 l2 ON l1.hub = l2.hub 
            WHERE l1.tid1 != l2.tid2 
              AND (l2.ts_dep2 + l2.day_adj) > l1.ts_arr1 + 1800 
              AND (l2.ts_dep2 + l2.day_adj) < l1.ts_arr1 + 28800 
              AND (l2.ts_arr2 + l2.day_adj - l1.ts_dep1) > 3600
            ORDER BY (l2.ts_arr2 + l2.day_adj - l1.ts_dep1) ASC
            LIMIT :limit
        """
        results = []
        try:
            async with conn.execute(query, {
                "src": json.dumps(src_ids), 
                "dst": json.dumps(dst_ids), 
                "db_date": db_date, 
                "tm_date": tomorrow_db_date,
                "dt_iso": target_date.date(),
                "tm_dt_iso": (target_date + timedelta(days=1)).date(),
                "limit": limit
            }) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    if str(row['tno1']) in cancelled_set or str(row['tno2']) in cancelled_set: continue
                    rt = Route()
                    def nt(s): 
                        h, m, sc = map(int, s.split(':'))
                        extra_days = h // 24
                        return datetime.combine(target_date.date(), time(h % 24, m, sc)) + timedelta(days=extra_days)
                    
                    s1_dep = nt(row['dep1'])
                    s1_arr = nt(row['arr1'])
                    s1 = RouteSegment(
                        trip_id=int(row['tid1']), departure_stop_id=int(row['sid1']), 
                        arrival_stop_id=int(row['hub']), departure_time=s1_dep, 
                        arrival_time=s1_arr, duration_minutes=(row['ts_arr1']-row['ts_dep1'])//60, 
                        distance_km=max(0.0, float((row['d2'] or 0.0) - (row['d1'] or 0.0))), 
                        train_number=str(row['tno1']), train_name=str(row['tname1']),
                        departure_code=str(row['code1']), arrival_code=str(row['hub_code'])
                    )
                    
                    dep2_dt = nt(row['dep2'])
                    arr2_dt = nt(row['arr2'])
                    if row['day_adj'] > 0:
                        dep2_dt += timedelta(days=1)
                        arr2_dt += timedelta(days=1)
                        
                    s2 = RouteSegment(
                        trip_id=int(row['tid2']), departure_stop_id=int(row['hub']), 
                        arrival_stop_id=int(row['sid2']), departure_time=dep2_dt, 
                        arrival_time=arr2_dt, duration_minutes=(row['ts_arr2']-row['ts_dep2'])//60, 
                        distance_km=max(0.0, float((row['d2:1'] or 0.0) - (row['d1:1'] or 0.0))), 
                        train_number=str(row['tno2']), train_name=str(row['tname2']),
                        departure_code=str(row['hub_code']), arrival_code=str(row['code2'])
                    )
                    rt.add_segment(s1); rt.add_segment(s2)
                    rt.add_transfer(TransferConnection(
                        station_id=int(row['hub']), 
                        station_code=str(row['hub_code']),
                        arrival_time=s1_arr, 
                        departure_time=dep2_dt, 
                        duration_minutes=(row['ts_dep2'] + row['day_adj'] - row['ts_arr1'])//60, 
                        station_name=str(row['hub_name'])
                    ))
                    rt.total_duration = (row['ts_arr2'] + row['day_adj'] - row['ts_dep1']) // 60
                    rt.metadata["engine"] = "ultra_turbo_1t"
                    results.append(rt)
            return results
        except Exception as e:
            logger.error(f"1T Error: {e}")
            return []

    async def _collect_2t_results(self, conn, src_ids, dst_ids, target_date, limit, cancelled_set, fare_configs):
        return [] # Keep empty for now to avoid O(N^3)

    async def _execute_query(self, conn, src_ids, dst_ids, target_date, limit, cancelled_set, offset):
        day_idx = target_date.weekday()
        if day_idx not in self.DAY_COLUMNS: return
        day_name = self.DAY_COLUMNS[day_idx]
        
        db_date = target_date.strftime("%Y%m%d")
        # [Gap 14] JOIN with stops to get station codes
        query = f"""
            SELECT t.id as tid, t.trip_id as tno, t.service_id as tname, 
                   s1.stop_id as sid1, s2.stop_id as sid2, 
                   st1.code as code1, st2.code as code2,
                   s1.departure_time as dep, s2.arrival_time as arr, 
                   s1.departure_timestamp as ts1, s2.arrival_timestamp as ts2, 
                   s1.shape_dist_traveled as d1, s2.shape_dist_traveled as d2
            FROM stop_times s1 
            JOIN stop_times s2 ON s1.trip_id = s2.trip_id 
            JOIN stops st1 ON s1.stop_id = st1.id
            JOIN stops st2 ON s2.stop_id = st2.id
            JOIN trips t ON s1.trip_id = t.id 
            JOIN calendar c ON t.service_id = c.service_id
            WHERE s1.stop_id IN (SELECT value FROM json_each(:src)) 
              AND s2.stop_id IN (SELECT value FROM json_each(:dst)) 
              AND s1.stop_sequence < s2.stop_sequence 
              -- [Task 7] Calendar logic with exceptions
              AND :db_date BETWEEN c.start_date AND c.end_date
              AND NOT EXISTS (SELECT 1 FROM calendar_dates cd WHERE cd.service_id = t.service_id AND cd.date = :dt_iso AND cd.exception_type = 2)
              AND (c.{day_name} = 1 OR EXISTS (SELECT 1 FROM calendar_dates cd WHERE cd.service_id = t.service_id AND cd.date = :dt_iso AND cd.exception_type = 1))
              AND (s2.arrival_timestamp - s1.departure_timestamp) > 1800
            ORDER BY (s2.arrival_timestamp - s1.departure_timestamp) ASC
            LIMIT :limit
        """
        async with conn.execute(query, {
            "src": json.dumps(src_ids), 
            "dst": json.dumps(dst_ids), 
            "db_date": db_date, 
            "dt_iso": target_date.date(),
            "limit": limit
        }) as cursor:
            async for row in cursor:
                if str(row['tno']) in cancelled_set: continue
                # [Task 14] Reverse Direction Check - ensured by s1.stop_sequence < s2.stop_sequence
                # If we need to filter for A->B->A patterns, this is done by Orchestrator or Route.has_cycle
                
                rt = Route()
                def nt(s): return f"{int(s.split(':')[0])%24:02d}:{s.split(':')[1]}:{s.split(':')[2]}"
                rt.add_segment(RouteSegment(
                    trip_id=int(row['tid']), 
                    departure_stop_id=int(row['sid1']), 
                    arrival_stop_id=int(row['sid2']), 
                    departure_time=nt(row['dep']), 
                    arrival_time=nt(row['arr']), 
                    duration_minutes=(row['ts2']-row['ts1'])//60, 
                    distance_km=max(0.0, float((row['d2'] or 0.0) - (row['d1'] or 0.0))), 
                    train_number=str(row['tno']),
                    train_name=str(row['tname']),
                    departure_code=str(row['code1']),
                    arrival_code=str(row['code2'])
                ))
                rt.metadata["engine"] = "ultra_turbo_direct"; rt.metadata["day_offset"] = offset
                yield rt
