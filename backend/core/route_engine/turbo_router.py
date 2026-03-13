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
        # Store the session factory if possible, or just the reference
        self.db_factory = SessionLocal

    def _get_city_cluster(self, db, station_code: str) -> List[int]:
        """[4.1] Dynamic Cluster Resolution using numeric IDs."""
        query = """
            SELECT scm2.station_id 
            FROM stops s
            JOIN station_cluster_mapping scm1 ON s.id = scm1.station_id
            JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id
            WHERE s.code = :code
        """
        try:
            rows = db.execute(text(query), {"code": station_code.upper()}).fetchall()
            ids = [r[0] for r in rows]
            if ids: return ids
        except: pass
        
        # Fallback
        res = db.execute(text("SELECT id FROM stops WHERE code = :c"), {"c": station_code.upper()}).fetchone()
        return [res[0]] if res else []

    def _get_station_code(self, db, station_id: int) -> str:
        res = db.execute(text("SELECT code FROM stops WHERE id = :i"), {"i": station_id}).fetchone()
        return res[0] if res else str(station_id)

    def find_routes(self, source_code: str, dest_code: str, departure_date: datetime, limit: int = 15) -> List[Dict[str, Any]]:
        import gc
        gc.disable() # Subtask 5.3
        db = self.db_factory()
        try:
            src_ids = self._get_city_cluster(db, source_code)
            dst_ids = self._get_city_cluster(db, dest_code)
            
            day_mask = (1 << departure_date.weekday())
            all_routes = []

            # Resolve to codes for binary lookup
            src_codes = [self._get_station_code(db, sid) for sid in src_ids]
            dst_codes = [self._get_station_code(db, sid) for sid in dst_ids]

            # 1. Direct Search
            for src in src_codes:
                for dst in dst_codes:
                    direct = self._search_direct_binary(db, src, dst, day_mask, limit - len(all_routes))
                    all_routes.extend(direct)
                    if len(all_routes) >= limit: break
            
            # 2. 1-Transfer Search
            if len(all_routes) < limit:
                # [4.1] Use dynamic top 50 hubs from Task 1 analysis
                HUBS = [
                    'SDAH', 'KYN', 'HWH', 'MSB', 'DDU', 'BZA', 'TBM', 'ET', 'MS', 'CNB', 
                    'BRC', 'BSL', 'MSF', 'DDJ', 'ST', 'MBM', 'BNXR', 'GDY', 'PNBE', 'MPK', 
                    'CMP', 'STM', 'BWN', 'TLM', 'MKK', 'MN', 'MSC', 'NBK', 'PV', 'PZA', 
                    'SP', 'TBMS', 'PER', 'VGLJ', 'BDC', 'NDLS', 'PRYJ', 'GZB', 'NGP', 'LKO', 
                    'NH', 'KGP', 'GKP', 'PUNE', 'ARA', 'ASN', 'KPD', 'RTM', 'STA', 'BSB'
                ]
                transfer_routes = self._search_one_transfer_binary(db, src_codes, dst_codes, day_mask, limit - len(all_routes), HUBS)
                all_routes.extend(transfer_routes)
                
            return all_routes[:limit]
        finally:
            db.close()
            gc.enable() # Subtask 5.3

    def _unpack_trains(self, blob: bytes) -> Dict[int, Dict]:
        """[4.2] Unpack V3 Binary Struct (IHHBBH = 12 bytes)."""
        if not blob: return {}
        records = {}
        record_size = 12
        for i in range(0, len(blob), record_size):
            chunk = blob[i:i+record_size]
            if len(chunk) < record_size: break
            tid, dep, arr, mask, seq, dist = struct.unpack("IHHBBH", chunk)
            records[tid] = {
                'dep': dep, 'arr': arr, 'mask': mask, 'seq': seq, 'dist': dist
            }
        return records

    def _search_direct_binary(self, db, src: str, dst: str, mask: int, limit: int) -> List[Dict[str, Any]]:
        """Fastest binary intersection using V3 index."""
        try:
            res = db.execute(text(
                "SELECT station_code, transit_blob FROM station_transit_index_bin WHERE station_code IN (:src, :dst)"
            ), {"src": src, "dst": dst}).fetchall()
            
            if len(res) < 2: return []
            
            binary_map = {row[0]: row[1] for row in res}
            src_trains = self._unpack_trains(binary_map.get(src))
            dst_trains = self._unpack_trains(binary_map.get(dst))

            results = []
            common_trips = set(src_trains.keys()).intersection(dst_trains.keys())
            
            for tid in common_trips:
                s_data, d_data = src_trains[tid], dst_trains[tid]
                if (s_data['mask'] & mask) and s_data['seq'] < d_data['seq']:
                    results.append({
                        "type": "direct",
                        "train_no": str(tid),
                        "dep": self._min_to_time(s_data['dep']),
                        "arr": self._min_to_time(d_data['arr']),
                        "duration": (d_data['arr'] - s_data['dep']) % 1440,
                        "distance": float(d_data['dist'] - s_data['dist']),
                        "score": 100
                    })
            return sorted(results, key=lambda x: x['duration'])[:limit]
        except Exception as e:
            logger.error(f"Direct Binary Error: {e}")
            return []

    def _search_one_transfer_binary(self, db, src_codes: List[str], dst_codes: List[str], mask: int, limit: int, hubs: List[str]) -> List[Dict[str, Any]]:
        """[4.1-4.13] Refactored 1-transfer binary search with Metro Hub logic."""
        try:
            # [4.12] Use Hub Caching for performance
            codes_to_fetch = list(set(src_codes + dst_codes + hubs))
            
            # Fix: SQLite/SQLAlchemy IN clause requires individual placeholders
            placeholders = ", ".join([f":c{i}" for i in range(len(codes_to_fetch))])
            params = {f"c{i}": code for i, code in enumerate(codes_to_fetch)}
            
            query = f"SELECT station_code, transit_blob FROM station_transit_index_bin WHERE station_code IN ({placeholders})"
            res = db.execute(text(query), params).fetchall()
            
            data = {row[0]: self._unpack_trains(row[1]) for row in res}
            
            # [4.7] Fetch Metro Hub station mapping (stations in same cluster)
            # This allows transferring from NDLS to NZM if they share a cluster
            metro_map = {}
            hub_placeholders = ", ".join([f":h{i}" for i in range(len(hubs))])
            hub_params = {f"h{i}": code for i, code in enumerate(hubs)}
            
            cluster_query = f"""
                SELECT s1.code, s2.code 
                FROM station_cluster_mapping scm1
                JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id
                JOIN stops s1 ON scm1.station_id = s1.id
                JOIN stops s2 ON scm2.station_id = s2.id
                WHERE s1.code IN ({hub_placeholders})
            """
            metro_rows = db.execute(text(cluster_query), hub_params).fetchall()
            for r1, r2 in metro_rows:
                if r1 not in metro_map: metro_map[r1] = set()
                metro_map[r1].add(r2)

            results = []
            for h in hubs:
                # h is the arrival station of Leg 1
                h_arrival_trains = data.get(h)
                if not h_arrival_trains: continue
                
                # [4.7] Potential departure stations from this Metro Hub
                departure_hubs = metro_map.get(h, {h})
                
                for s in src_codes:
                    if h == s: continue
                    s_trains = data.get(s)
                    if not s_trains: continue
                    
                    # Leg 1: Source -> Hub (h)
                    t1_options = set(s_trains.keys()).intersection(h_arrival_trains.keys())
                    for tid1 in t1_options:
                        s_data, h1_data = s_trains[tid1], h_arrival_trains[tid1]
                        if not (s_data['mask'] & mask) or s_data['seq'] >= h1_data['seq']: continue
                        
                        arr_day = h1_data['arr'] // 1440
                        target_mask = ((mask << arr_day) | (mask >> (7 - arr_day))) & 0x7F if arr_day > 0 else mask

                        # Leg 2: Metro Hub (h_dep) -> Destination
                        for h_dep in departure_hubs:
                            h_departure_trains = data.get(h_dep)
                            if not h_departure_trains: continue
                            
                            for d in dst_codes:
                                if h_dep == d: continue
                                d_trains = data.get(d)
                                if not d_trains: continue
                                
                                t2_options = set(h_departure_trains.keys()).intersection(d_trains.keys())
                                for tid2 in t2_options:
                                    if tid1 == tid2: continue # [4.13] No collision
                                    
                                    h2_data, d_data = h_departure_trains[tid2], d_trains[tid2]
                                    if not (h2_data['mask'] & target_mask) or h2_data['seq'] >= d_data['seq']: continue
                                    
                                    # [4.4, 4.5] Connection timing
                                    # [4.10] Station change penalty
                                    transfer_penalty = 0
                                    if h != h_dep:
                                        transfer_penalty = 60 # 60 min penalty for changing station
                                    
                                    layover = (h2_data['dep'] - h1_data['arr']) % 1440
                                    if (45 + transfer_penalty) <= layover <= 720:
                                        results.append({
                                            "type": "1-transfer",
                                            "hub": h if h == h_dep else f"{h}->{h_dep}",
                                            "score": 80 - (layover / 15.0) - (20 if h != h_dep else 0),
                                            "legs": [
                                                {"train": str(tid1), "from": s, "to": h, "dep": self._min_to_time(s_data['dep']), "arr": self._min_to_time(h1_data['arr'])},
                                                {"train": str(tid2), "from": h_dep, "to": d, "dep": self._min_to_time(h2_data['dep']), "arr": self._min_to_time(d_data['arr'])}
                                            ]
                                        })
                                        if len(results) >= limit: return results
            return results
        except Exception as e:
            logger.error(f"Transfer Binary Error: {e}")
            return []

    def _min_to_time(self, minutes: int) -> str:
        m = minutes % 1440
        return f"{m // 60:02d}:{m % 60:02d}:00"

    def __del__(self):
        try: self.db.close()
        except: pass
