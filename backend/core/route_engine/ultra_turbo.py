import logging
import asyncio
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy import text

from database.session import get_raw_transit_conn
from core.data_structures import Route, RouteSegment
from services.multi_layer_cache import multi_layer_cache, AvailabilityQuery

logger = logging.getLogger("ultra-turbo")

class FastSegment:
    """Subtask 1.8: Lightweight segment struct with object pooling."""
    __slots__ = (
        'trip_id', 'train_number', 'src_id', 'dst_id', 
        'dep_time', 'arr_time', 'duration', 'day_offset', 'fare'
    )
    _pool = []

    @classmethod
    def acquire(cls, **kwargs):
        if cls._pool:
            obj = cls._pool.pop()
            for k, v in kwargs.items():
                setattr(obj, k, v)
            return obj
        return cls(**kwargs)

    def release(self):
        self._pool.append(self)

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class UltraTurboDirectEngine:
    """
    Subtask 1.2 - 1.4: High-Performance Direct Route Fetcher.
    Bypasses ORM and uses raw SQL with indexing hints for sub-5ms performance.
    """

    def __init__(self):
        # Day name mapping for calendar table
        self.day_map = {
            0: "monday",
            1: "tuesday",
            2: "wednesday",
            3: "thursday",
            4: "friday",
            5: "saturday",
            6: "sunday"
        }

    async def find_routes(
        self, 
        source_code: str, 
        dest_code: str, 
        travel_date: date, 
        limit: int = 50
    ) -> List[Route]:
        """
        Subtask 1.6: Station Alias Pre-Resolution.
        Expands codes to clusters and resolves to numeric IDs for raw SQL.
        """
        start_ts = time.perf_counter()
        try:
            # Subtask 1.11: Timeout Circuit Breaker (150ms)
            return await asyncio.wait_for(
                self._find_routes_inner(source_code, dest_code, travel_date, limit, start_ts),
                timeout=0.150
            )
        except asyncio.TimeoutError:
            logger.warning(f"⏳ Ultra-Turbo Timed Out for {source_code}->{dest_code}. Falling back.")
            return []
        except Exception as e:
            logger.error(f"Ultra-Turbo Failure: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _find_routes_inner(
        self, 
        source_code: str, 
        dest_code: str, 
        travel_date: date, 
        limit: int,
        start_ts: float
    ) -> List[Route]:
        """
        Subtask 1.6: Station Alias Pre-Resolution.
        Expands codes to clusters and resolves to numeric IDs for raw SQL.
        """
        results = []
        # 1. Resolve Clusters & IDs
        async with get_raw_transit_conn() as conn:
            src_ids = await self._resolve_cluster_ids(conn, source_code)
            dst_ids = await self._resolve_cluster_ids(conn, dest_code)
            
            if not src_ids or not dst_ids: return []
            
            # 2. Execute Primary Query (Subtask 1.3: Generator)
            async for rt in self._execute_query(conn, src_ids, dst_ids, travel_date, limit):
                results.append(rt)
                if len(results) >= limit: break
            
            # 3. Subtask 1.5: Date Expansion Trigger
            if len(results) < 5:
                prev_day = travel_date - timedelta(days=1)
                next_day = travel_date + timedelta(days=1)
                
                # Note: For expansion, we consume generators one by one or concurrently
                # To keep it simple and safe for subtask 1.3:
                async def consume_gen(target_date, offset):
                    chunk = []
                    async for r in self._execute_query(conn, src_ids, dst_ids, target_date, limit, day_offset=offset):
                        chunk.append(r)
                        if len(chunk) >= limit: break
                    return chunk

                expanded = await asyncio.gather(
                    consume_gen(prev_day, -1),
                    consume_gen(next_day, 1)
                )
                for r_list in expanded: 
                    results.extend(r_list)
                    if len(results) >= limit: break
                
        latency = (time.perf_counter() - start_ts) * 1000
        logger.info(f"⚡ Ultra-Turbo: Found {len(results)} routes for {source_code}->{dest_code} in {latency:.2f}ms")
        return results[:limit]

    async def _resolve_cluster_ids(self, conn, code: Any) -> List[int]:
        """
        Subtask 1.5: Atomic Alias Resolution.
        Bypassing corrupted city_clusters table to ensure accuracy.
        """
        if isinstance(code, int):
            return [code]
            
        code_str = str(code).upper().strip()
        
        # Manual clean clusters for major cities
        MANUAL_CLUSTERS = {
            "PALAKKAD": ["PGT", "PGTN"],
            "PGT": ["PGT", "PGTN"],
            "DELHI": ["NDLS", "NZM", "DLI", "ANVT", "DEC"],
            "MUMBAI": ["BCT", "BDTS", "DR", "KYN", "PNVL", "CSTM"],
            "KOTA": ["KOTA"] # Isolation to fix the bug
        }
        
        codes = MANUAL_CLUSTERS.get(code_str, [code_str])
        
        query = "SELECT id FROM stops WHERE code IN (SELECT value FROM json_each(:codes_json))"
        try:
            async with conn.execute(query, {"codes_json": json.dumps(codes)}) as cursor:
                rows = await cursor.fetchall()
                return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"Alias Resolution Error: {e}")
            return []

    async def _execute_query(self, conn, src_ids: List[int], dst_ids: List[int], target_date: date, limit: int, day_offset: int = 0):
        day_name = self.day_map[target_date.weekday()]
        date_str = target_date.strftime("%Y-%m-%d")
        
        # Subtask 1.7: Pre-emptive Cancellation Set
        async with conn.execute(
            "SELECT train_no FROM cancelled_trains WHERE travel_date = ?", (date_str,)
        ) as cursor:
            cancelled_set = {str(r[0]) for r in await cursor.fetchall()}

        duration_sql = """
            ((CAST(substr(s2.arrival_time, 1, 2) AS INT) * 60 + CAST(substr(s2.arrival_time, 4, 2) AS INT)) - 
             (CAST(substr(s1.departure_time, 1, 2) AS INT) * 60 + CAST(substr(s1.departure_time, 4, 2) AS INT)))
        """
        duration_sql_safe = f"CASE WHEN {duration_sql} < 0 THEN {duration_sql} + 1440 ELSE {duration_sql} END"

        # [FIX] Better distance estimation: Average train speed 55 km/h
        distance_est_sql = f"({duration_sql_safe} * 0.916)" 

        # Subtask 1.6: Nonlinear Telescopic Piecewise Approximation
        estimated_fare_sql = f"""
            CASE 
                WHEN {distance_est_sql} < 100 THEN (60 + ({distance_est_sql} * 0.6))
                WHEN {distance_est_sql} < 500 THEN (150 + ({distance_est_sql} * 0.55))
                WHEN {distance_est_sql} < 1500 THEN (300 + ({distance_est_sql} * 0.50))
                ELSE (500 + ({distance_est_sql} * 0.45))
            END
        """

        query = f"""
            SELECT 
                t.id as trip_id,
                t.trip_id as train_number,
                s1.stop_id as src_id,
                s2.stop_id as dst_id,
                s1.departure_time,
                s2.arrival_time,
                ({duration_sql_safe}) as duration,
                ({distance_est_sql}) as distance,
                ({estimated_fare_sql}) as estimated_fare
            FROM stop_times s1 INDEXED BY idx_stop_times_stop_id
            JOIN stop_times s2 INDEXED BY idx_stop_times_trip_id ON s1.trip_id = s2.trip_id
            JOIN trips t ON s1.trip_id = t.id
            JOIN calendar c ON t.service_id = c.service_id
            WHERE s1.stop_id IN (SELECT value FROM json_each(:src_json))
              AND s2.stop_id IN (SELECT value FROM json_each(:dst_json))
              AND s1.stop_sequence < s2.stop_sequence
              AND c.{day_name} = 1
              AND :d_str BETWEEN c.start_date AND c.end_date
              AND NOT EXISTS (
                  SELECT 1 FROM calendar_dates cd 
                  WHERE cd.service_id = t.service_id 
                    AND cd.date = :d_str 
                    AND cd.exception_type = 2
              )
            LIMIT :limit
        """
        
        try:
            params = {
                "src_json": json.dumps(src_ids),
                "dst_json": json.dumps(dst_ids),
                "d_str": date_str,
                "limit": limit
            }
            async with conn.execute(query, params) as cursor:
                while True:
                    rows = await cursor.fetchmany(50)
                    if not rows: break
                    
                    for row in rows:
                        if row['train_number'] in cancelled_set:
                            continue

                        dur = row['duration']
                        if dur < 1 or dur > 2880: continue

                        rt = Route()
                        seg = RouteSegment(
                            trip_id=row['trip_id'],
                            train_number=row['train_number'],
                            departure_stop_id=row['src_id'],
                            arrival_stop_id=row['dst_id'],
                            departure_time=row['departure_time'],
                            arrival_time=row['arrival_time'],
                            duration_minutes=dur,
                            distance_km=float(row['distance']),
                            fare=float(row['estimated_fare'])
                        )
                        rt.add_segment(seg)
                        rt.metadata["engine"] = "ultra_turbo_direct"
                        rt.metadata["day_offset"] = day_offset
                        yield rt
        except Exception as e:
            logger.error(f"Ultra-Turbo Query Error: {e}")
