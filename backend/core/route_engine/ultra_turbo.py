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

logger = logging.getLogger("ultra-turbo")

# This engine is designed for raw speed, so it uses its own connection logic.
def get_db_path():
    db_dir = Config.DB_DIR
    db_path = os.path.join(db_dir, "transit_graph.db")
    if not os.path.exists(db_path):
        # Fallback to legacy path
        db_path = os.path.join(Config.BASE_DIR, "database", "transit_graph.db")
    return db_path

class UltraTurboDirectEngine:
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

    async def find_routes(self, source_code: str, dest_code: str, travel_date: date, limit: int = 50) -> List[Route]:
        if os.getenv("DISABLE_ULTRA_TURBO") == "true": return []
        start_ts = time.perf_counter()
        try:
            # Use asyncio.to_thread to run the synchronous DB logic in a separate thread
            return await asyncio.wait_for(
                asyncio.to_thread(self._find_routes_sync, source_code, dest_code, travel_date, limit),
                timeout=5.0 
            )
        except asyncio.TimeoutError:
            logger.error("Ultra-Turbo search timed out.")
            return []
        except Exception as e:
            logger.error(f"Ultra-Turbo Failure: {e}", exc_info=True)
            return []

    def _find_routes_sync(self, source_code: str, dest_code: str, travel_date: date, limit: int) -> List[Route]:
        s_norm = source_code.upper().strip()
        d_norm = dest_code.upper().strip()
        if s_norm == d_norm: return []

        start_ts = time.perf_counter()
        
        try:
            # Each thread needs its own connection
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            src_ids = self._resolve_cluster_ids(conn, source_code)
            dst_ids = self._resolve_cluster_ids(conn, dest_code)
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

    def _resolve_cluster_ids(self, conn, code: str) -> List[int]:
        from utils.station_utils import get_metro_group_codes
        codes = get_metro_group_codes(code.upper().strip())
        
        ids = set()
        q_stops = f"SELECT id FROM stops WHERE code IN ({','.join('?' for _ in codes)})"
        for r in conn.execute(q_stops, codes).fetchall():
            ids.add(r[0])
            
        if not ids: return []
        
        q_clusters = f"""
            SELECT scm2.station_id 
            FROM station_cluster_mapping scm1 
            JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id 
            WHERE scm1.station_id IN ({','.join('?' for _ in ids)})
        """
        for r in conn.execute(q_clusters, list(ids)).fetchall():
            ids.add(r[0])
            
        return list(ids)

