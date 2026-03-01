import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from database.session import SessionLocal

logger = logging.getLogger(__name__)

class TurboRouter:
    """
    ULTRA Turbo Router using Key-based JSONB GIN indices in PostgreSQL.
    Exploits '?' operator for O(1) existence checks in station_transit_index.
    """

    def __init__(self):
        self.db = SessionLocal()

    def find_routes(
        self, 
        source_code: str, 
        dest_code: str, 
        departure_date: datetime,
        max_transfers: int = 1,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        start_time = time.time()
        source_code = source_code.upper()
        dest_code = dest_code.upper()
        
        day_idx = departure_date.weekday()
        day_mask = (1 << day_idx)

        logger.info(f"Ultra-Turbo Search: {source_code} -> {dest_code} (DayMask: {day_mask})")

        # 1. DIRECT ROUTES
        routes = self._search_direct(source_code, dest_code, day_mask, limit)
        
        # 2. 1-TRANSFER ROUTES
        if len(routes) < limit and max_transfers >= 1:
            routes.extend(self._search_one_transfer(source_code, dest_code, day_mask, limit - len(routes)))

        duration = (time.time() - start_time) * 1000
        logger.info(f"Ultra-Turbo Search finished in {duration:.2f}ms. Found {len(routes)} routes.")
        
        return routes

    def _search_direct(self, src: str, dst: str, mask: int, limit: int) -> List[Dict[str, Any]]:
        """Fastest key-intersection for direct trains."""
        sql = text("""
            WITH candidates AS (
                SELECT station_code, trains_map FROM station_transit_index WHERE station_code = :src
            ),
            matches AS (
                SELECT 
                    train_no,
                    (s.trains_map->train_no->>0) as dep_time,
                    (d.trains_map->train_no->>0) as arr_time,
                    (s.trains_map->train_no->>2)::int as s_mask,
                    (s.trains_map->train_no->>3)::int as s_seq,
                    (d.trains_map->train_no->>3)::int as d_seq
                FROM candidates s
                JOIN station_transit_index d ON d.station_code = :dst
                CROSS JOIN LATERAL jsonb_object_keys(s.trains_map) AS train_no
                WHERE d.trains_map ? train_no -- Key existence check (FAST)
            )
            SELECT * FROM matches
            WHERE s_seq < d_seq AND (s_mask & :mask) > 0
            ORDER BY dep_time ASC
            LIMIT :limit
        """)
        
        results = self.db.execute(sql, {"src": src, "dst": dst, "mask": mask, "limit": limit}).fetchall()
        
        routes = []
        for r in results:
            routes.append({
                "type": "direct",
                "train_no": r.train_no,
                "departure": r.dep_time,
                "arrival": r.arr_time,
                "transfers": 0,
                "legs": [{
                    "train_no": r.train_no,
                    "from": src,
                    "to": dst,
                    "dep": r.dep_time,
                    "arr": r.arr_time
                }]
            })
        return routes

    def _search_one_transfer(self, src: str, dst: str, mask: int, limit: int) -> List[Dict[str, Any]]:
        """Set intersection to find optimal interchange hubs."""
        sql = text("""
            WITH src_map AS (SELECT trains_map FROM station_transit_index WHERE station_code = :src),
                 dst_map AS (SELECT trains_map FROM station_transit_index WHERE station_code = :dst)
            SELECT 
                inter.station_code as interchange_code,
                inter.station_name as interchange_name,
                t1 as train1,
                (s.trains_map->t1->>1) as dep1,
                (inter.trains_map->t1->>0) as arr1,
                t2 as train2,
                (inter.trains_map->t2->>1) as dep2,
                (d.trains_map->t2->>0) as arr2
            FROM src_map s, dst_map d, station_transit_index inter
            CROSS JOIN LATERAL jsonb_object_keys(s.trains_map) t1
            CROSS JOIN LATERAL jsonb_object_keys(d.trains_map) t2
            WHERE inter.trains_map ? t1  -- Train 1 stops at Interchange
              AND inter.trains_map ? t2  -- Train 2 stops at Interchange
              AND inter.station_code NOT IN (:src, :dst)
              -- Sequence validation
              AND (s.trains_map->t1->>3)::int < (inter.trains_map->t1->>3)::int
              AND (inter.trains_map->t2->>3)::int < (d.trains_map->t2->>3)::int
              -- Day mask validation
              AND ((s.trains_map->t1->>2)::int & :mask) > 0
              AND ((inter.trains_map->t2->>2)::int & :mask) > 0
              -- Transfer buffer (Interchange dep2 > arr1)
              AND (inter.trains_map->t2->>1) > (inter.trains_map->t1->>0)
            LIMIT :limit
        """)
        
        results = self.db.execute(sql, {"src": src, "dst": dst, "mask": mask, "limit": limit}).fetchall()
        
        routes = []
        for r in results:
            routes.append({
                "type": "1-transfer",
                "interchange": r.interchange_code,
                "transfers": 1,
                "legs": [
                    {"train_no": r.train1, "from": src, "to": r.interchange_code, "dep": r.dep1, "arr": r.arr1},
                    {"train_no": r.train2, "from": r.interchange_code, "to": dst, "dep": r.dep2, "arr": r.arr2}
                ]
            })
        return routes

    def __del__(self):
        try:
            self.db.close()
        except:
            pass
