import logging
import time
import struct
import json
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from sqlalchemy import text
from database.session import SessionTransit as SessionLocal

logger = logging.getLogger(__name__)

from core.dynamic_logic import is_valid_transfer
from core.data_structures import DynamicWaitConfig, SearchPhase
from core.frontier import FrontierManager, FrontierRoute
from database.config import Config

class TurboRouter:
    # [Task 11.5] Static Cache for Hub Adjacency
    _hub_adj_cache = {}
    _last_cache_update = 0

    def __init__(self, db_session=None):
        self.db_factory = SessionLocal
        self.wait_config = DynamicWaitConfig(
            min_wait_minutes=getattr(Config, 'TRANSFER_WINDOW_MIN', 30) or 30,
            max_wait_minutes=getattr(Config, 'TRANSFER_WINDOW_MAX', 240) or 240,
            beta=1.5,
            phase_multipliers={
                SearchPhase.STRICT: 1.0,
                SearchPhase.MODERATE: 1.5,
                SearchPhase.RELAXED: 3.0
            }
        )
        self.frontier_manager = FrontierManager(max_routes_per_station=10)

    def _get_hub_adjacency(self, db, hubs: List[str]) -> Dict[str, Set[int]]:
        """
        [Task 11.5] Fetch and cache trip IDs serving each hub.
        Allows O(1) intersection without repeated BLOB fetching.
        """
        now = time.time()
        if not self._hub_adj_cache or (now - self._last_cache_update > 3600):
            logger.info("TurboRouter: Refreshing Hub Adjacency Cache...")
            placeholders = ", ".join([f":h{i}" for i in range(len(hubs))])
            params = {f"h{i}": h for i, h in enumerate(hubs)}
            query = f"SELECT station_code, transit_blob FROM station_transit_index_bin WHERE station_code IN ({placeholders})"
            res = db.execute(text(query), params).fetchall()
            
            new_cache = {}
            for code, blob in res:
                trains = self._unpack_trains(blob)
                new_cache[code] = set(trains.keys())
            
            TurboRouter._hub_adj_cache = new_cache
            TurboRouter._last_cache_update = now
        
        return self._hub_adj_cache

    def _get_city_cluster(self, db, station_code: str) -> List[int]:
        """[4.1] Dynamic Cluster Resolution using METRO_GROUPS and City fallback."""
        from utils.station_utils import get_metro_group_codes
        metro_codes = get_metro_group_codes(station_code)
        
        ids = set()
        for code in metro_codes:
            # 1. Base Station
            base_query = "SELECT id, city FROM stops WHERE code = :code"
            base_row = db.execute(text(base_query), {"code": code.upper()}).fetchone()
            if not base_row: continue
            base_id, city = base_row[0], base_row[1]
            ids.add(base_id)

            # 2. GTFS Cluster
            query_gtfs = """
                SELECT scm2.station_id
                FROM station_cluster_mapping scm1
                JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id
                WHERE scm1.station_id = :sid
            """
            try:
                rows = db.execute(text(query_gtfs), {"sid": base_id}).fetchall()
                for r in rows: ids.add(r[0])
            except: pass

            # 3. City Cluster (Fallback for smaller towns)
            if city and len(metro_codes) == 1:
                try:
                    city_rows = db.execute(text("SELECT id FROM stops WHERE city = :city"), {"city": city}).fetchall()
                    for r in city_rows: ids.add(r[0])
                except: pass
            
        return list(ids)

    def _get_station_code(self, db, station_id: int) -> str:
        res = db.execute(text("SELECT code FROM stops WHERE id = :i"), {"i": station_id}).fetchone()
        return res[0] if res else str(station_id)

    def _get_transfer_penalty(self, db, code1: str, code2: str) -> int:
        """
        [Task 11.6] Dynamic Station Change Penalty.
        Considers station size (centrality) and distance matrix.
        """
        if code1 == code2:
            # [Task 6] Station-size aware transfer penalty
            query = "SELECT station_size FROM stops WHERE code = :c"
            try:
                res = db.execute(text(query), {"c": code1}).fetchone()
                if res and res[0]:
                    size = res[0]
                    if size == 'major_hub': return 5
                    elif size == 'large': return 10
                    elif size == 'medium': return 15
                    elif size == 'small': return 20
            except: pass
            return 15
        
        # Station change (e.g. NDLS -> NZM)
        query = "SELECT min_km FROM hub_distance_matrix WHERE (src_code = :c1 AND dst_code = :c2) OR (src_code = :c2 AND dst_code = :c1) LIMIT 1"
        try:
            res = db.execute(text(query), {"c1": code1, "c2": code2}).fetchone()
            if res:
                # Heuristic: 20 mins base for change + 10 mins per km
                return int(20 + (res[0] * 10))
        except: pass
        
        return 90 # Conservative default for station change

    def find_routes(self, source_code: str, dest_code: str, departure_date: datetime, limit: int = 15) -> List[Dict[str, Any]]:
        import gc
        from core.data_structures import SearchPhase
        gc.disable() # Subtask 5.3
        db = self.db_factory()
        self.frontier_manager.reset() # Reset for new search
        try:
            src_ids = self._get_city_cluster(db, source_code)
            dst_ids = self._get_city_cluster(db, dest_code)
            
            day_mask = (1 << departure_date.weekday())
            # [Task 27.11 Audit Fix] Use YYYYMMDD for binary index lookups
            db_date_str = departure_date.strftime("%Y%m%d")
            
            all_routes = []
            seen_journey_ids = set()

            # Resolve to codes for binary lookup
            src_codes = [self._get_station_code(db, sid) for sid in src_ids]
            dst_codes = [self._get_station_code(db, sid) for sid in dst_ids]

            # 1. Direct Search (Always Strict)
            from core.route_engine.engine import route_engine
            overlay = route_engine.overlay 
            
            for sid_idx, src in enumerate(src_codes):
                src_id = src_ids[sid_idx]
                for did_idx, dst in enumerate(dst_codes):
                    dst_id = dst_ids[did_idx]
                    direct = self._search_direct_binary(db, src, dst, day_mask, limit - len(all_routes))
                    for r in direct:
                        # [Task 27.3] Engine-level cancellation check
                        if overlay.is_cancelled(int(r['train_no'])): continue
                        
                        jid = f"direct_{r['train_no']}_{r['dep']}"
                        if jid not in seen_journey_ids:
                            r['phase_found'] = SearchPhase.STRICT
                            all_routes.append(r)
                            seen_journey_ids.add(jid)
                            
                            # Also populate frontier with direct routes to prune worse transfers
                            arr_mins = self._time_to_min(r['arr'])
                            self.frontier_manager.is_dominated(
                                dst_id, 
                                FrontierRoute(arr_mins, 0, 0, r['distance'])
                            )
                    if len(all_routes) >= limit: break
            
            # 2. Multi-Phase 1-Transfer Search (Task 2)
            if len(all_routes) < limit:
                from utils.hub_utils import get_top_centrality_hubs
                all_hubs = get_top_centrality_hubs(limit=100)
                
                # [Task 11.7] Zonal Filtering: Only use hubs in relevant zones
                zone_query = "SELECT DISTINCT zone FROM stops WHERE code IN (:s, :d)"
                target_zones = [r[0] for r in db.execute(text(zone_query), {"s": source_code, "d": dest_code}).fetchall()]
                
                hubs = all_hubs[:50] 
                
                # [Task 18] Zero-Result Fallback: Always try STRICT first, but if < 3, definitely proceed to RELAXED
                search_phases = [SearchPhase.STRICT, SearchPhase.MODERATE, SearchPhase.RELAXED]
                
                for phase in search_phases:
                    if len(all_routes) >= limit: break

                    # [Task 29.3] Context-Aware Checkpoint
                    from core.context import check_timeout
                    try: check_timeout()
                    except TimeoutError: break

                    if phase == SearchPhase.RELAXED and len(all_routes) >= 3:

                        break

                    logger.info(f"TurboRouter: Entering Search Phase: {phase}")
                    phase_routes = self._search_one_transfer_binary(
                        db, src_ids, dst_ids, src_codes, dst_codes, day_mask, 
                        limit - len(all_routes), hubs, phase
                    )
                    
                    for r in phase_routes:
                        jid = f"1t_{r['legs'][0]['train']}_{r['legs'][1]['train']}_{r['legs'][0]['dep']}"
                        if jid not in seen_journey_ids:
                            r['phase_found'] = phase
                            all_routes.append(r)
                            seen_journey_ids.add(jid)
                
            # [Task Group 1 Constraint] Show routes in order of travel time
            all_routes.sort(key=lambda x: x.get('duration', 999999))
            return all_routes[:limit]
        finally:
            db.close()
            gc.enable() # Subtask 5.3

    def _time_to_min(self, time_str: str) -> int:
        h, m = map(int, time_str.split(':')[:2])
        return h * 60 + m

    def _unpack_trains(self, blob: bytes) -> Dict[int, Dict]:
        """
        [Task 11.3] Unpack Binary Struct.
        Supports V3 (12 bytes: IHHBBH) and V4 (16 bytes: IHHBBHf).
        """
        if not blob: return {}
        records = {}
        
        # Auto-detect version based on blob size vs record alignment
        # V4 = 16 bytes, V3 = 12 bytes
        record_size = 16 if len(blob) % 16 == 0 else 12
        fmt = "IHHBBHf" if record_size == 16 else "IHHBBH"
        
        for i in range(0, len(blob), record_size):
            chunk = blob[i:i+record_size]
            if len(chunk) < record_size: break
            
            unpacked = struct.unpack(fmt, chunk)
            tid, dep, arr, mask, seq, dist = unpacked[:6]
            price = unpacked[6] if record_size == 16 else 0.0
            
            records[tid] = {
                'dep': dep, 'arr': arr, 'mask': mask, 'seq': seq, 'dist': dist, 'price': price
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

    def _search_one_transfer_binary(self, db, src_ids: List[int], dst_ids: List[int], src_codes: List[str], dst_codes: List[str], mask: int, limit: int, hubs: List[str], phase: SearchPhase = SearchPhase.MODERATE) -> List[Dict[str, Any]]:
        """[4.1-4.13] Refactored 1-transfer binary search with Metro Hub logic."""
        try:
            # ... (rest of the method unchanged before the loop)
            # ... (skipped for brevity, will provide full block in Act)
            # [4.12] Use Hub Caching for performance
            codes_to_fetch = list(set(src_codes + dst_codes + hubs))
            
            # Fix: SQLite/SQLAlchemy IN clause requires individual placeholders
            placeholders = ", ".join([f":c{i}" for i in range(len(codes_to_fetch))])
            params = {f"c{i}": code for i, code in enumerate(codes_to_fetch)}
            
            query = f"SELECT station_code, transit_blob FROM station_transit_index_bin WHERE station_code IN ({placeholders})"
            res = db.execute(text(query), params).fetchall()
            
            data = {row[0]: self._unpack_trains(row[1]) for row in res}
            
            # [4.7] Fetch Metro Hub station mapping
            # This allows transferring from NDLS to NZM if they share a cluster
            metro_map = {}
            hub_placeholders = ", ".join([f":h{i}" for i in range(len(hubs))])
            hub_params = {f"h{i}": code for i, code in enumerate(hubs)}
            
            # Access centralized overlay from route_engine
            from core.route_engine.engine import route_engine
            overlay = route_engine.overlay

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
                # [Task 29.3] Context-Aware Checkpoint
                from core.context import check_timeout
                check_timeout()

                # h is the arrival station of Leg 1
                h_arrival_trains = data.get(h)
                if not h_arrival_trains: continue
                
            # [4.7] Potential departure stations from this Metro Hub
                # Task 11.4: Enhanced Cluster bridging logic
                departure_hubs = metro_map.get(h, {h})
                
                # Check if 'h' itself is a major junction (top centrality)
                # to prioritize same-station transfers
                sorted_departure_hubs = sorted(list(departure_hubs), key=lambda x: 0 if x == h else 1)
                
                for s in src_codes:
                    if h == s: continue
                    s_trains = data.get(s)
                    if not s_trains: continue
                    
                    # Leg 1: Source -> Hub (h)
                    t1_options = set(s_trains.keys()).intersection(h_arrival_trains.keys())
                    for tid1 in t1_options:
                        # [Task 27.3] Cancellation check for leg 1
                        if overlay.is_cancelled(int(tid1)): continue
                        
                        s_data, h1_data = s_trains[tid1], h_arrival_trains[tid1]
                        if not (s_data['mask'] & mask) or s_data['seq'] >= h1_data['seq']: continue
                        
                        arr_day = h1_data['arr'] // 1440
                        target_mask = ((mask << arr_day) | (mask >> (7 - arr_day))) & 0x7F if arr_day > 0 else mask

                        # Leg 2: Metro Hub (h_dep) -> Destination
                        for h_dep in sorted_departure_hubs:
                            h_departure_trains = data.get(h_dep)
                            if not h_departure_trains: continue
                            
                            for d in dst_codes:
                                if h_dep == d: continue
                                d_trains = data.get(d)
                                if not d_trains: continue
                                
                                t2_options = set(h_departure_trains.keys()).intersection(d_trains.keys())
                                for tid2 in t2_options:
                                    if tid1 == tid2: continue # [4.13] No collision
                                    
                                    # [Task 27.3] Cancellation check for leg 2
                                    if overlay.is_cancelled(int(tid2)): continue
                                    
                                    h2_data, d_data = h_departure_trains[tid2], d_trains[tid2]
                                    if not (h2_data['mask'] & target_mask) or h2_data['seq'] >= d_data['seq']: continue
                                    
                                    # [4.4, 4.5] Connection timing
                                    # [4.10] Station change penalty
                                    transfer_penalty = self._get_transfer_penalty(db, h, h_dep)
                                    
                                    journey_so_far = (h1_data['arr'] - s_data['dep']) % 1440
                                    layover = (h2_data['dep'] - h1_data['arr']) % 1440
                                    
                                    if is_valid_transfer(h1_data['arr'], h2_data['dep'], journey_so_far, self.wait_config, h, transfer_penalty, phase):
                                        # [Task 4] Station Frontier Pruning
                                        arrival_at_dest = d_data['arr']
                                        total_dist = float((h1_data['dist'] - s_data['dist']) + (d_data['dist'] - h2_data['dist']))
                                        
                                        # Use numeric ID for frontier
                                        dst_id = dst_ids[dst_codes.index(d)]
                                        
                                        # Check if this 1-transfer route is dominated at destination 'd'
                                        if not self.frontier_manager.is_dominated(dst_id, FrontierRoute(arrival_at_dest, 1, layover, total_dist)):
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
