import logging
import time
import struct
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import text
from database.session import SessionTransit as SessionLocal

logger = logging.getLogger(__name__)

class TurboRouter:
    def __init__(self, db_session=None):
        self.db = db_session if db_session else SessionLocal()

    def _get_city_cluster(self, station_code: str) -> List[str]:
        """Expand a station code into all stations in its city cluster."""
        try:
            row = self.db.execute(text("""
                SELECT station_codes_json FROM city_clusters 
                WHERE station_codes_json LIKE :like_code
            """), {"like_code": f'%"{station_code}"%'}).fetchone()
            if row:
                return json.loads(row[0])
        except Exception as e:
            logger.error(f"Cluster lookup failed: {e}")
        return [station_code]

    def find_routes(self, source_code: str, dest_code: str, departure_date: datetime, limit: int = 15) -> List[Dict[str, Any]]:
        # Suggestion #6: City-Cluster Adjacency Integration
        src_cluster = self._get_city_cluster(source_code.upper())
        dst_cluster = self._get_city_cluster(dest_code.upper())
        
        day_mask = (1 << departure_date.weekday())
        all_routes = []

        # Try all combinations in the clusters
        for src in src_cluster:
            for dst in dst_cluster:
                if len(all_routes) >= limit: break
                
                # Check Backbone first (Suggestion #4 & #8)
                hub_routes = self._search_hub_backbone(src, dst)
                if hub_routes:
                    all_routes.extend(hub_routes)
                    continue

                # Fallback to standard Direct
                direct = self._search_direct(src, dst, day_mask, limit - len(all_routes))
                all_routes.extend(direct)
        
        if len(all_routes) < 3:
            logger.info(f"Triggering 1-Transfer for clusters...")
            transfer_routes = self._search_one_transfer(source_code.upper(), dest_code.upper(), day_mask, limit - len(all_routes))
            all_routes.extend(transfer_routes)
            
        return all_routes[:limit]

    def _search_hub_backbone(self, src: str, dst: str) -> List[Dict[str, Any]]:
        """O(1) lookup via hub_transit_index."""
        try:
            row = self.db.execute(text("""
                SELECT trains_json FROM hub_transit_index 
                WHERE src_hub = :src AND dst_hub = :dst
            """), {"src": src, "dst": dst}).fetchone()
            
            if row:
                trains = json.loads(row[0])
                return [{"type": "direct_backbone", "train_no": t['t'], "dep": t['d'], "arr": t['a']} for t in trains]
        except: pass
        return []

    def _search_direct(self, src: str, dst: str, mask: int, limit: int) -> List[Dict[str, Any]]:
        # Modified to use the original station_transit_index for compatibility, 
        # but in production, we decode the struct.pack blobs.
        sql = text("""
            SELECT 
                s_item.key as train_no,
                json_extract(s_item.value, '$[0]') as dep_time,
                json_extract(d_item.value, '$[0]') as arr_time,
                CAST(json_extract(s_item.value, '$[3]') AS INTEGER) as s_seq,
                CAST(json_extract(d_item.value, '$[3]') AS INTEGER) as d_seq
            FROM station_transit_index s, station_transit_index d,
                 json_each(s.trains_map) as s_item,
                 json_each(d.trains_map) as d_item
            WHERE s.station_code = :src AND d.station_code = :dst
              AND s_item.key = d_item.key
              AND s_seq < d_seq
              AND (CAST(json_extract(s_item.value, '$[2]') AS INTEGER) & :mask) > 0
            LIMIT :limit
        """)
        try:
            results = self.db.execute(sql, {"src": src, "dst": dst, "mask": mask, "limit": limit}).fetchall()
            return [{"type": "direct", "train_no": r[0], "dep": r[1], "arr": r[2]} for r in results]
        except: return []

    def _search_one_transfer(self, src: str, dst: str, mask: int, limit: int) -> List[Dict[str, Any]]:
        # Using pre-calculated neighbor flags or direct query
        sql = text("""
            SELECT 
                s_item.key as t1, h_item1.key as t1_h,
                json_extract(s_item.value, '$[0]') as t1_dep,
                json_extract(h_item1.value, '$[0]') as t1_arr,
                h.station_code as hub,
                h_item2.key as t2,
                json_extract(h_item2.value, '$[0]') as t2_dep,
                json_extract(d_item.value, '$[0]') as t2_arr
            FROM station_transit_index s,
                 station_transit_index h,
                 station_transit_index d,
                 json_each(s.trains_map) as s_item,
                 json_each(h.trains_map) as h_item1,
                 json_each(h.trains_map) as h_item2,
                 json_each(d.trains_map) as d_item
            WHERE s.station_code = :src AND d.station_code = :dst
              AND s_item.key = h_item1.key 
              AND h_item2.key = d_item.key 
              AND s.station_code != h.station_code AND d.station_code != h.station_code
              AND t2_dep > t1_arr
              AND (CAST(json_extract(s_item.value, '$[2]') AS INTEGER) & :mask) > 0
              AND (CAST(json_extract(h_item2.value, '$[2]') AS INTEGER) & :mask) > 0
            LIMIT :limit
        """)
        try:
            res = self.db.execute(sql, {"src": src, "dst": dst, "mask": mask, "limit": limit}).fetchall()
            return [{
                "type": "1-transfer",
                "hub": r.hub,
                "legs": [
                    {"train": r.t1, "from": src, "to": r.hub, "dep": r.t1_dep, "arr": r.t1_arr},
                    {"train": r.t2, "from": r.hub, "to": dst, "dep": r.t2_dep, "arr": r.t2_arr}
                ]
            } for r in res]
        except: return []

    def __del__(self):
        try: self.db.close()
        except: pass
