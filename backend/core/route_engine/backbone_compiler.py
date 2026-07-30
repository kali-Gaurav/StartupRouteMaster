
import sqlite3
import json
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Set

logger = logging.getLogger("nexus.backbone")

class BackboneCompiler:
    """
    [Task 175] Contraction Hierarchies: Pre-calculating Shortcuts.
    Generates a massive Hub-to-Hub connectivity index using a single database scan.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def compile(self, max_hubs: int = 1000):
        logger.info(f"🚀 Starting Backbone Compilation (Target: {max_hubs} Hubs)")
        
        # 0. Get Station Map
        self.cursor.execute("SELECT id, code FROM stops")
        station_map = {r[0]: r[1] for r in self.cursor.fetchall()}

        # 1. Identify Top Hubs (by frequency)
        self.cursor.execute("""
            SELECT stop_id, COUNT(*) as freq 
            FROM stop_times 
            GROUP BY stop_id 
            ORDER BY freq DESC 
            LIMIT ?
        """, (max_hubs,))
        hubs = [r[0] for r in self.cursor.fetchall()]
        hub_set = set(hubs)
        logger.info(f"📍 Selected {len(hubs)} Hubs.")

        # 2. Build Adjacency Matrix (Direct Trips)
        logger.info("⚡ Scanning segments for hub-to-hub direct connections...")
        # Note: 'segments' table already has duration_minutes and train_number
        self.cursor.execute("""
            SELECT s1.trip_id, s1.source_stop_id, s2.dest_station_id, 
                   s1.departure_time, s2.arrival_time, 
                   s2.duration_minutes, s2.distance_km,
                   s1.train_number as tno, t.service_id as tname
            FROM segments s1
            JOIN segments s2 ON s1.trip_id = s2.trip_id
            JOIN trips t ON s1.trip_id = t.id
            WHERE s1.source_stop_id IN ({})
              AND s2.dest_station_id IN ({})
              AND s2.arrival_time > s1.departure_time
        """.format(",".join(map(str, hubs)), ",".join(map(str, hubs))))

        connectivity = {} # (src, dst) -> List[TripInfo]
        
        count = 0
        for tid, src, dst, dep, arr, duration, dist, tno, tname in self.cursor.fetchall():
            if src == dst: continue
            pair = (src, dst)
            if pair not in connectivity: connectivity[pair] = []
            
            # Use total trip duration from s1.departure to s2.arrival
            # Wait! 'duration_minutes' in segments is per-segment.
            # I should calculate it from dep/arr strings if possible, or use a better query.
            # Actually, segments are A->B, B->C.
            # If I join s1 and s2 on trip_id, I'm finding paths A -> B -> ... -> C.
            # I need the TOTAL duration between s1.departure and s2.arrival.
            
            # Since both are GTFS format (HH:MM:SS), I'll parse them.
            def to_min(s):
                h, m, sc = map(int, s.split(':'))
                return h * 60 + m
            
            d_min = to_min(dep)
            a_min = to_min(arr)
            total_dur = a_min - d_min
            if total_dur < 0: total_dur += 1440 # Midnight crossover
            
            # Format: [tid, dep_time, arr_time, dist, tno, tname, scode, dcode, duration]
            connectivity[pair].append({
                "tid": int(tid),
                "dep": dep[:5], # HH:MM
                "arr": arr[:5],
                "dist": float(dist or 0),
                "duration": total_dur,
                "tno": str(tno),
                "tname": str(tname or ""),
                "scode": station_map.get(src, ""),
                "dcode": station_map.get(dst, "")
            })
            count += 1
            if count % 25000 == 0:
                logger.info(f"Fetched {count} connection slices...")

        # 3. Commit to Hub Connectivity Index
        logger.info(f"📦 Packaging {len(connectivity)} unique hub pairs to index...")
        self.cursor.execute("DELETE FROM hub_connectivity_index")
        
        batch = []
        for (src, dst), trips in connectivity.items():
            trips.sort(key=lambda x: x['dep'])
            json_data = json.dumps(trips[:20]) # Limit to top 20
            batch.append((int(src), int(dst), json_data))

        self.cursor.executemany("""
            INSERT INTO hub_connectivity_index (src_hub_id, dst_hub_id, trains_json)
            VALUES (?, ?, ?)
        """, batch)
        
        self.conn.commit()
        logger.info(f"✅ Backbone Compiled: {len(batch)} shortcuts injected.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    compiler = BackboneCompiler("backend/database/transit_graph.db")
    compiler.compile()
