"""
[Turbo Optimization] rebuild_transit_index.py
Upgraded with Incremental Support (Suggestion #24).
"""

import sqlite3
import json
import logging
import sys
import os
from typing import Optional, List

# Ensure backend package is importable
sys.path.append(os.getcwd())

from sqlalchemy import text
from database.session import engine_transit as engine
from database.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("index-builder")

def rebuild(dirty_trains: Optional[List[str]] = None):
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        if not dirty_trains:
            logger.info("Initializing station_transit_index (Full Rebuild)...")
            conn.execute("DROP TABLE IF EXISTS station_transit_index")
            conn.execute("CREATE TABLE station_transit_index (station_code TEXT PRIMARY KEY, station_name TEXT, trains_map TEXT)")
        else:
            logger.info(f"Incremental Rebuild for {len(dirty_trains)} trains...")

        # 1. Extract data
        # We need: station -> {train_no: [dep, arr, day_mask, seq, dist, fare]}
        query = """
            SELECT s.code, s.name, t.trip_id as train_no, st.departure_time, st.arrival_time, 
                   st.stop_sequence, seg.distance_km, seg.cost,
                   c.monday, c.tuesday, c.wednesday, c.thursday, c.friday, c.saturday, c.sunday
            FROM stops s
            JOIN stop_times st ON s.id = st.stop_id
            JOIN trips t ON st.trip_id = t.id
            JOIN calendar c ON t.service_id = c.service_id
            LEFT JOIN segments seg ON t.id = seg.trip_id AND s.id = seg.source_station_id
        """
        
        if dirty_trains:
            # Only fetch rows for specific trains
            query += f" WHERE t.trip_id IN ({','.join([f'?' for _ in dirty_trains])})"
            rows = conn.execute(query, dirty_trains).fetchall()
        else:
            rows = conn.execute(query).fetchall()

        from collections import defaultdict
        station_maps = defaultdict(dict)
        station_names = {}

        for r in rows:
            code = r['code']
            station_names[code] = r['name']
            
            # Calculate day mask
            mask = 0
            days = [r['monday'], r['tuesday'], r['wednesday'], r['thursday'], r['friday'], r['saturday'], r['sunday']]
            for i, val in enumerate(days):
                if val: mask |= (1 << i)
            
            station_maps[code][r['train_no']] = [
                str(r['departure_time']),
                str(r['arrival_time']),
                mask,
                r['stop_sequence'],
                float(r['distance_km'] or 0),
                float(r['cost'] or 0)
            ]

        # 2. Insert/Update
        insert_data = []
        for code, t_map in station_maps.items():
            if dirty_trains:
                # Incremental: Fetch existing, merge, then update
                existing = conn.execute("SELECT trains_map FROM station_transit_index WHERE station_code = ?", (code,)).fetchone()
                if existing:
                    merged = json.loads(existing[0])
                    merged.update(t_map)
                    t_map = merged
            
            insert_data.append((code, station_names[code], json.dumps(t_map)))

        print(f"  Updating {len(insert_data)} stations...")
        conn.executemany("INSERT OR REPLACE INTO station_transit_index VALUES (?, ?, ?)", insert_data)
        conn.commit()
        logger.info("🚀 Transit Index update successful.")
        
    finally:
        conn.close()

if __name__ == "__main__":
    rebuild()
