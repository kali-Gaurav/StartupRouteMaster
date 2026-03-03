import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from database.session import SessionTransit as SessionLocal
from database.config import Config

logger = logging.getLogger(__name__)

class TurboRouter:
    """
    ULTRA Turbo Router adapted for SQLite.
    Uses json_each() for station-centric index lookups.
    """

    def __init__(self):
        self.db = SessionLocal()

    def find_routes(
        self, 
        source_code: str, 
        dest_code: str, 
        departure_date: datetime,
        max_transfers: int = 1,
        limit: int = 15,
        time_window_hours: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        start_time = time.time()
        source_code = source_code.upper()
        dest_code = dest_code.upper()
        
        day_idx = departure_date.weekday()
        day_mask = (1 << day_idx)

        if time_window_hours is not None:
            half = max(0, int(time_window_hours * 60) // 2)
        else:
            window_minutes = getattr(Config, "TURBO_TIME_WINDOW_MINUTES", 720)
            half = max(0, int(window_minutes) // 2)
            
        start_dt = departure_date - timedelta(minutes=half)
        end_dt = departure_date + timedelta(minutes=half)
        dep_start = start_dt.strftime("%H:%M")
        dep_end = end_dt.strftime("%H:%M")

        logger.info(
            "SQLite Turbo Search: %s -> %s (DayMask=%s, window=%s-%s)",
            source_code,
            dest_code,
            day_mask,
            dep_start,
            dep_end,
        )

        # 1. DIRECT ROUTES
        routes = self._search_direct(source_code, dest_code, day_mask, dep_start, dep_end, limit)
        
        # 2. 1-TRANSFER ROUTES
        if len(routes) < limit and max_transfers >= 1:
            routes.extend(
                self._search_one_transfer(
                    source_code,
                    dest_code,
                    day_mask,
                    dep_start,
                    dep_end,
                    limit - len(routes),
                )
            )

        duration = (time.time() - start_time) * 1000
        logger.info(f"SQLite Turbo Search finished in {duration:.2f}ms. Found {len(routes)} routes.")
        return routes

    def _search_direct(self, src: str, dst: str, mask: int, dep_start: str, dep_end: str, limit: int) -> List[Dict[str, Any]]:
        """Direct trains search using SQLite json_each."""
        sql = text("""
            SELECT 
                s_item.key as train_no,
                json_extract(s_item.value, '$[0]') as dep_time,
                json_extract(d_item.value, '$[0]') as arr_time,
                CAST(json_extract(s_item.value, '$[2]') AS INTEGER) as s_mask,
                CAST(json_extract(s_item.value, '$[3]') AS INTEGER) as s_seq,
                CAST(json_extract(d_item.value, '$[3]') AS INTEGER) as d_seq,
                CAST(json_extract(s_item.value, '$[4]') AS REAL) as distance,
                CAST(json_extract(s_item.value, '$[5]') AS REAL) as fare
            FROM station_transit_index s, 
                 station_transit_index d,
                 json_each(s.trains_map) as s_item,
                 json_each(d.trains_map) as d_item
            WHERE s.station_code = :src 
              AND d.station_code = :dst
              AND s_item.key = d_item.key -- Same train
              AND s_seq < d_seq -- Direction validation
              AND (s_mask & :mask) > 0 -- Day of week
              AND dep_time BETWEEN :dep_start AND :dep_end
            ORDER BY dep_time ASC
            LIMIT :limit
        """)
        
        try:
            results = self.db.execute(
                sql,
                {"src": src, "dst": dst, "mask": mask, "dep_start": dep_start, "dep_end": dep_end, "limit": limit},
            ).fetchall()
        except Exception as e:
            logger.error(f"Turbo direct search failed: {e}")
            return []
        
        routes = []
        for r in results:
            routes.append({
                "type": "direct", "train_no": r.train_no, "departure": r.dep_time, "arrival": r.arr_time, "transfers": 0,
                "distance_km": r.distance, "fare": r.fare,
                "legs": [{"train_no": r.train_no, "from": src, "to": dst, "dep": r.dep_time, "arr": r.arr_time, "distance_km": r.distance, "fare": r.fare}]
            })
        return routes

    def _search_one_transfer(self, src: str, dst: str, mask: int, dep_start: str, dep_end: str, limit: int) -> List[Dict[str, Any]]:
        return []

    def __del__(self):
        try:
            self.db.close()
        except:
            pass
