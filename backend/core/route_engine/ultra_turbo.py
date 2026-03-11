import logging
import asyncio
import time
import json
import os
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
        # [3.17] Feature Toggle
        if os.getenv("DISABLE_ULTRA_TURBO") == "true":
            return []

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
        [3.7, 3.11, 3.13] Optimized Direct Route Engine.
        """
        # [3.13] Same Station Protection
        if source_code.upper().strip() == dest_code.upper().strip():
            return []

        results = []
        # 1. Resolve Clusters & IDs
        async with get_raw_transit_conn() as conn:
            src_ids = await self._resolve_cluster_ids(conn, source_code)
            dst_ids = await self._resolve_cluster_ids(conn, dest_code)
            
            if not src_ids or not dst_ids: return []
            
            # 2. Execute Primary Query
            async for rt in self._execute_query(conn, src_ids, dst_ids, travel_date, limit):
                # [3.11] Simple Scoring: 100 - (Duration / 10) - (10 if low speed)
                dur = rt.total_duration
                dist = rt.total_distance
                speed = (dist / (dur / 60.0)) if dur > 0 else 0
                
                score = 100 - (dur / 15.0)
                if speed < 40: score -= 20 # Penalty for slow local trains
                rt.score = max(10, round(score, 2))
                
                results.append(rt)
                if len(results) >= limit: break
            
            # 3. Date Expansion Trigger
            if len(results) < 5:
                prev_day = travel_date - timedelta(days=1)
                next_day = travel_date + timedelta(days=1)
                
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
        
        # [3.7] Sort by score (Fastest/Optimal)
        results.sort(key=lambda x: x.score, reverse=True)
                
        latency = (time.perf_counter() - start_ts) * 1000
        logger.info(f"⚡ Ultra-Turbo: Found {len(results)} routes for {source_code}->{dest_code} in {latency:.2f}ms")
        return results[:limit]

    async def _resolve_cluster_ids(self, conn, code: Any) -> List[int]:
        """
        [3.2] Dynamic Cluster-to-ID Resolution.
        Uses Task 1.10 Geographical Clusters.
        """
        if isinstance(code, int):
            return [code]
            
        code_str = str(code).upper().strip()
        
        # 1. Find if this code belongs to a cluster
        # 2. Get all station IDs in that same cluster
        query = """
            SELECT scm2.station_id 
            FROM stops s
            JOIN station_cluster_mapping scm1 ON s.id = scm1.station_id
            JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id
            WHERE s.code = :code
        """
        try:
            async with conn.execute(query, {"code": code_str}) as cursor:
                rows = await cursor.fetchall()
                ids = [r[0] for r in rows]
                if ids:
                    return ids
        except Exception as e:
            logger.error(f"Dynamic Cluster Resolution Error: {e}")
            
        # Fallback: Just the station itself
        try:
            async with conn.execute("SELECT id FROM stops WHERE code = ?", (code_str,)) as cursor:
                row = await cursor.fetchone()
                return [row[0]] if row else []
        except:
            return []

    async def _execute_query(self, conn, src_ids: List[int], dst_ids: List[int], target_date: date, limit: int, day_offset: int = 0):
        day_name = self.day_map[target_date.weekday()]
        date_str = target_date.strftime("%Y-%m-%d")
        
        # Subtask 1.7: Pre-emptive Cancellation Set
        async with conn.execute(
            "SELECT train_no FROM cancelled_trains WHERE travel_date = ?", (date_str,)
        ) as cursor:
            cancelled_set = {str(r[0]) for r in await cursor.fetchall()}

        query = f"""
            SELECT 
                t.id as trip_id,
                t.trip_id as train_number,
                s1.stop_id as src_id,
                s2.stop_id as dst_id,
                s1.departure_time,
                s2.arrival_time,
                s1.platform_code as src_platform,
                s2.platform_code as dst_platform,
                s1.departure_timestamp,
                s2.arrival_timestamp,
                s1.shape_dist_traveled as src_dist,
                s2.shape_dist_traveled as dst_dist
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
            # [3.18] SQL Execution Telemetry
            q_start = time.perf_counter()
            async with conn.execute(query, params) as cursor:
                q_lat = (time.perf_counter() - q_start) * 1000
                logger.debug(f"SQL Latency: {q_lat:.2f}ms")
                
                while True:
                    rows = await cursor.fetchmany(50)
                    if not rows: break
                    
                    for row in rows:
                        if row['train_number'] in cancelled_set:
                            continue

                        # [3.4] O(1) Distance & Duration Calculation
                        dist = float(row['dst_dist'] or 0.0) - float(row['src_dist'] or 0.0)
                        
                        # [3.3] Midnight Rollover Logic for Duration
                        dep_ts = row['departure_timestamp']
                        arr_ts = row['arrival_timestamp']
                        dur_sec = arr_ts - dep_ts
                        if dur_sec < 0: dur_sec += 86400 # 24h rollover
                        dur = dur_sec // 60
                        
                        # [3.8] Filter extreme/invalid durations
                        if dur < 1 or dur > 4320: continue 

                        rt = Route()
                        
                        def norm_time(t_str):
                            if not t_str: return "00:00:00"
                            parts = t_str.split(':')
                            h = int(parts[0]) % 24
                            return f"{h:02d}:{parts[1]}:{parts[2]}"

                        seg = RouteSegment(
                            trip_id=row['trip_id'],
                            train_number=row['train_number'],
                            departure_stop_id=row['src_id'],
                            arrival_stop_id=row['dst_id'],
                            departure_time=norm_time(row['departure_time']),
                            arrival_time=norm_time(row['arrival_time']),
                            duration_minutes=int(dur),
                            distance_km=max(0.0, float(dist)),
                            fare=0.0
                        )
                        # [3.12] Platform Hydration
                        seg.metadata["platform"] = row['src_platform']
                        seg.metadata["dest_platform"] = row['dst_platform']
                        
                        rt.add_segment(seg)
                        rt.metadata["engine"] = "ultra_turbo_direct"
                        rt.metadata["day_offset"] = day_offset
                        yield rt
        except Exception as e:
            logger.error(f"Ultra-Turbo Query Error: {e}")
