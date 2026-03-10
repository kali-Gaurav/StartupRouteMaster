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

    def _get_city_cluster(self, db, station_code: str) -> List[str]:
        """Expand a station code into all stations in its city cluster."""
        try:
            row = db.execute(text("""
                SELECT station_codes_json FROM city_clusters 
                WHERE station_codes_json LIKE :like_code
            """), {"like_code": f'%"{station_code}"%'}).fetchone()
            if row:
                return json.loads(row[0])
        except Exception as e:
            logger.error(f"Cluster lookup failed: {e}")
        return [station_code]

    def find_routes(self, source_code: str, dest_code: str, departure_date: datetime, limit: int = 15) -> List[Dict[str, Any]]:
        # Task 3.11: Thread-safe session management
        db = self.db_factory()
        try:
            src_cluster = self._get_city_cluster(db, source_code.upper())
            dst_cluster = self._get_city_cluster(db, dest_code.upper())
            
            day_mask = (1 << departure_date.weekday())
            all_routes = []

            # 1. Direct Search (Binary Optimized)
            for src in src_cluster:
                for dst in dst_cluster:
                    if len(all_routes) >= limit: break
                    direct = self._search_direct_binary(db, src, dst, day_mask, limit - len(all_routes))
                    all_routes.extend(direct)
            
            # 2. 1-Transfer Search (Binary Optimized)
            if len(all_routes) < 5:
                transfer_routes = self._search_one_transfer_binary(db, source_code.upper(), dest_code.upper(), day_mask, limit - len(all_routes))
                all_routes.extend(transfer_routes)
                
            return all_routes[:limit]
        finally:
            db.close()

    def _search_direct_binary(self, db, src: str, dst: str, mask: int, limit: int) -> List[Dict[str, Any]]:
        """Fastest binary intersection for direct routes."""
        try:
            res = db.execute(text(
                "SELECT station_code, trains_binary FROM station_transit_index WHERE station_code IN (:src, :dst)"
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
                        "train_no": tid,
                        "dep": self._min_to_time(s_data['dep']),
                        "arr": self._min_to_time(d_data['arr']),
                        "fare": float(d_data['f3a'] or 1500.0)
                    })
            return results[:limit]
        except: return []

    def _search_one_transfer_binary(self, db, src: str, dst: str, mask: int, limit: int) -> List[Dict[str, Any]]:
        """Binary intersection via pre-defined Hubs (Strategic Junctions)."""
        HUBS = [
            'NDLS', 'BCT', 'MS', 'HWH', 'KGP', 'ET', 'NGP', 'BSL', 'DR', 'KYN', 'PNVL', 
            'STA', 'JBP', 'PUNE', 'ADI', 'MAS', 'SBC', 'SC', 'BRC', 'RTM', 'KOTA', 
            'AGC', 'VGLJ', 'CNB', 'LKO', 'BSB', 'GAYA', 'MGS', 'BPL', 'GTL', 'SRR', 'TCR'
        ]
        
        try:
            placeholders = ",".join([f"'{h}'" for h in HUBS])
            res = db.execute(text(f"""
                SELECT station_code, trains_binary 
                FROM station_transit_index 
                WHERE station_code IN (:src, :dst, {placeholders})
            """), {"src": src, "dst": dst}).fetchall()
            
            data = {row[0]: self._unpack_trains(row[1]) for row in res}
            src_trains = data.get(src, {})
            dst_trains = data.get(dst, {})
            
            results = []
            for hub_code in HUBS:
                if hub_code == source_code or hub_code == dest_code:
                    continue # Task 3.1.1: Prevent obvious loops
                
                hub_trains = data.get(hub_code)
                if not hub_trains: continue
                
                t1_options = set(src_trains.keys()).intersection(hub_trains.keys())
                t2_options = set(hub_trains.keys()).intersection(dst_trains.keys())
                
                for tid1 in t1_options:
                    s_data, h1_data = src_trains[tid1], hub_trains[tid1]
                    if not (s_data['mask'] & mask) or s_data['seq'] >= h1_data['seq']: continue
                    
                    # Task 3.4: Handle next-day bitmask for long-distance arrivals
                    arrival_day_offset = h1_data['arr'] // 1440
                    target_mask = mask
                    if arrival_day_offset > 0:
                        target_mask = ((mask << arrival_day_offset) | (mask >> (7 - arrival_day_offset))) & 0x7F

                    for tid2 in t2_options:
                        if tid1 == tid2: continue # Prevent same-train loop
                        
                        h2_data, d_data = hub_trains[tid2], dst_trains[tid2]
                        if not (h2_data['mask'] & target_mask) or h2_data['seq'] >= d_data['seq']: continue
                        
                        # Task 3.2: Minimum Connection Time logic
                        if h2_data['dep'] > h1_data['arr'] + 45: 
                            results.append({
                                "type": "1-transfer",
                                "hub": hub_code,
                                "legs": [
                                    {"train": tid1, "from": src, "to": hub_code, "dep": self._min_to_time(s_data['dep']), "arr": self._min_to_time(h1_data['arr'])},
                                    {"train": tid2, "from": hub_code, "to": dst, "dep": self._min_to_time(h2_data['dep']), "arr": self._min_to_time(d_data['arr'])}
                                ],
                                "total_fare": float(h1_data['f3a'] + d_data['f3a'])
                            })
                            if len(results) >= limit: return results
            return results
        except: return []

    def _unpack_trains(self, blob: bytes) -> Dict[int, Dict]:
        """Unpack the 18-byte binary format (v3)."""
        if not blob: return {}
        try:
            num_trains = struct.unpack_from("<H", blob, 0)[0]
            trains = {}
            offset = 2
            for _ in range(num_trains):
                # IHHBBII = 18 bytes
                tid, dep, arr, mask, seq, f3a, fsl = struct.unpack_from("<IHHBBII", blob, offset)
                trains[tid] = {'dep': dep, 'arr': arr, 'mask': mask, 'seq': seq, 'f3a': f3a, 'fsl': fsl}
                offset += 18
            return trains
        except: return {}

    def _min_to_time(self, minutes: int) -> str:
        return f"{minutes // 60:02d}:{minutes % 60:02d}:00"

    def __del__(self):
        try: self.db.close()
        except: pass
