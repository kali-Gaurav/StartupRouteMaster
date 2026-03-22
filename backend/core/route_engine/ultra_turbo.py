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

    def __init__(self):
        self.day_map = {
            0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
            4: "friday", 5: "saturday", 6: "sunday"
        }

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
        async with get_raw_transit_conn() as conn:
            date_str = travel_date.strftime("%Y-%m-%d")
            
            async def get_cancelled():
                async with conn.execute("SELECT train_no FROM cancelled_trains WHERE travel_date = ?", (date_str,)) as c:
                    return {str(r[0]) for r in await c.fetchall()}

            async def get_station_meta():
                try:
                    res = await conn.execute("SELECT id, platform_count FROM stops WHERE code IN (?, ?)", (s_norm, d_norm))
                    return {r[0]: {"platforms": r[1]} for r in await res.fetchall()}
                except: return {}

            async with asyncio.TaskGroup() as tg:
                src_task = tg.create_task(self._resolve_cluster_ids(conn, source_code))
                dst_task = tg.create_task(self._resolve_cluster_ids(conn, dest_code))
                can_task = tg.create_task(get_cancelled())
                meta_task = tg.create_task(get_station_meta())

            src_ids = src_task.result()
            dst_ids = dst_task.result()
            cancelled_set = can_task.result()
            station_meta = meta_task.result()
            
            if not src_ids or not dst_ids: return []

            all_tasks = []
            async with asyncio.TaskGroup() as tg:
                all_tasks.append(tg.create_task(self._collect_day_results(conn, src_ids, dst_ids, travel_date, limit, cancelled_set, {}, 0)))
                all_tasks.append(tg.create_task(self._collect_1t_results(conn, src_ids, dst_ids, travel_date, limit // 2, cancelled_set, {})))
                # Restore 2T with limited scope if needed, but for now let's restore full 1T/Direct
                
            for t in all_tasks:
                try: results.extend(t.result())
                except: pass
        
        results.sort(key=lambda x: x.total_duration)
        logger.info(f"⚡ Ultra-Turbo: Found {len(results)} routes for {source_code}->{dest_code} in {(time.perf_counter()-start_ts)*1000:.2f}ms")
        return results[:limit]

    async def _resolve_cluster_ids(self, conn, code: Any) -> List[int]:
        if isinstance(code, int): return [code]
        c_str = str(code).upper().strip()
        from utils.station_utils import get_metro_group_codes
        codes = get_metro_group_codes(c_str)
        ids = set()
        for c in codes:
            async with conn.execute("SELECT id FROM stops WHERE code = ?", (c,)) as cursor:
                row = await cursor.fetchone()
                if row: 
                    sid = row[0]
                    ids.add(sid)
                    # Cluster mapping
                    async with conn.execute("SELECT scm2.station_id FROM station_cluster_mapping scm1 JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id WHERE scm1.station_id = ?", (sid,)) as c2:
                        for r in await c2.fetchall(): ids.add(r[0])
        return list(ids)

    async def _collect_day_results(self, conn, src_ids, dst_ids, target_date, limit, cancelled_set, fare_configs, offset):
        day_results = []
        async for rt in self._execute_query(conn, src_ids, dst_ids, target_date, limit, cancelled_set, offset):
            day_results.append(rt)
        return day_results

    async def _collect_1t_results(self, conn, src_ids, dst_ids, target_date, limit, cancelled_set, fare_configs):
        day_name = self.day_map[target_date.weekday()]
        db_date = target_date.strftime("%Y%m%d")
        query = f"""
            WITH leg1 AS (
                SELECT s1.trip_id as tid1, s1.stop_id as sid1, s2.stop_id as hub, s1.departure_timestamp as ts_dep1, s2.arrival_timestamp as ts_arr1, t.trip_id as tno1, sh.name as hub_name, s1.departure_time as dep1, s2.arrival_time as arr1, s1.shape_dist_traveled as d1, s2.shape_dist_traveled as d2
                FROM stop_times s1 JOIN stop_times s2 ON s1.trip_id = s2.trip_id JOIN stops sh ON s2.stop_id = sh.id JOIN trips t ON s1.trip_id = t.id JOIN calendar c ON t.service_id = c.service_id
                WHERE s1.stop_id IN (SELECT value FROM json_each(:src)) AND s1.stop_sequence < s2.stop_sequence AND c.{day_name} = 1 AND :db_date BETWEEN c.start_date AND c.end_date
            ),
            leg2 AS (
                SELECT s1.trip_id as tid2, s1.stop_id as hub, s2.stop_id as sid2, s1.departure_timestamp as ts_dep2, s2.arrival_timestamp as ts_arr2, t.trip_id as tno2, s1.departure_time as dep2, s2.arrival_time as arr2, s1.shape_dist_traveled as d1, s2.shape_dist_traveled as d2
                FROM stop_times s1 JOIN stop_times s2 ON s1.trip_id = s2.trip_id JOIN trips t ON s1.trip_id = t.id JOIN calendar c ON t.service_id = c.service_id
                WHERE s2.stop_id IN (SELECT value FROM json_each(:dst)) AND s1.stop_sequence < s2.stop_sequence AND c.{day_name} = 1 AND :db_date BETWEEN c.start_date AND c.end_date
            )
            SELECT l1.*, l2.* FROM leg1 l1 JOIN leg2 l2 ON l1.hub = l2.hub WHERE l1.tid1 != l2.tid2 AND l2.ts_dep2 > l1.ts_arr1 + 1800 AND l2.ts_dep2 < l1.ts_arr1 + 14400 LIMIT :limit
        """
        results = []
        try:
            async with conn.execute(query, {"src": json.dumps(src_ids), "dst": json.dumps(dst_ids), "db_date": db_date, "limit": limit}) as cursor:
                for row in await cursor.fetchall():
                    rt = Route()
                    def nt(s): return f"{int(s.split(':')[0])%24:02d}:{s.split(':')[1]}:{s.split(':')[2]}"
                    s1 = RouteSegment(
                        trip_id=int(row['tid1']), departure_stop_id=int(row['sid1']), 
                        arrival_stop_id=int(row['hub']), departure_time=nt(row['dep1']), 
                        arrival_time=nt(row['arr1']), duration_minutes=(row['ts_arr1']-row['ts_dep1'])//60, 
                        distance_km=max(0.0, float((row['d2'] or 0.0) - (row['d1'] or 0.0))), train_number=str(row['tno1'])
                    )
                    s2 = RouteSegment(
                        trip_id=int(row['tid2']), departure_stop_id=int(row['hub']), 
                        arrival_stop_id=int(row['sid2']), departure_time=nt(row['dep2']), 
                        arrival_time=nt(row['arr2']), duration_minutes=(row['ts_arr2']-row['ts_dep2'])//60, 
                        distance_km=max(0.0, float((row[20] or 0.0) - (row[19] or 0.0))), train_number=str(row['tno2'])
                    )
                    rt.add_segment(s1); rt.add_segment(s2)
                    rt.add_transfer(TransferConnection(int(row['hub']), s1.arrival_time, s2.departure_time, (row['ts_dep2']-row['ts_arr1'])//60, str(row['hub_name'])))
                    results.append(rt)
            return results
        except Exception as e:
            logger.error(f"1T Error: {e}")
            return []

    async def _collect_2t_results(self, conn, src_ids, dst_ids, target_date, limit, cancelled_set, fare_configs):
        return [] # Keep empty for now to avoid O(N^3)

    async def _execute_query(self, conn, src_ids, dst_ids, target_date, limit, cancelled_set, offset):
        day_name = self.day_map[target_date.weekday()]
        db_date = target_date.strftime("%Y%m%d")
        query = f"""
            SELECT t.id as tid, t.trip_id as tno, s1.stop_id as sid1, s2.stop_id as sid2, s1.departure_time as dep, s2.arrival_time as arr, s1.departure_timestamp as ts1, s2.arrival_timestamp as ts2, s1.shape_dist_traveled as d1, s2.shape_dist_traveled as d2
            FROM stop_times s1 JOIN stop_times s2 ON s1.trip_id = s2.trip_id JOIN trips t ON s1.trip_id = t.id JOIN calendar c ON t.service_id = c.service_id
            WHERE s1.stop_id IN (SELECT value FROM json_each(:src)) AND s2.stop_id IN (SELECT value FROM json_each(:dst)) AND s1.stop_sequence < s2.stop_sequence AND c.{day_name} = 1 AND :db_date BETWEEN c.start_date AND c.end_date LIMIT :limit
        """
        async with conn.execute(query, {"src": json.dumps(src_ids), "dst": json.dumps(dst_ids), "db_date": db_date, "limit": limit}) as cursor:
            async for row in cursor:
                rt = Route()
                def nt(s): return f"{int(s.split(':')[0])%24:02d}:{s.split(':')[1]}:{s.split(':')[2]}"
                rt.add_segment(RouteSegment(trip_id=int(row[0]), departure_stop_id=int(row[2]), arrival_stop_id=int(row[3]), departure_time=nt(row[4]), arrival_time=nt(row[5]), duration_minutes=(row[7]-row[6])//60, distance_km=max(0.0, float((row[9] or 0.0) - (row[8] or 0.0))), train_number=str(row[1])))
                rt.metadata["engine"] = "ultra_turbo_direct"; rt.metadata["day_offset"] = offset
                yield rt
