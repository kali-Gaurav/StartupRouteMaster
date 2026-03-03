"""
[Turbo Optimization] rebuild_transit_index.py

Populates the station_transit_index table in SQLite for high-speed
direct and 1-transfer lookups.
"""

import sqlite3
import json
import logging
import sys
import os
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlalchemy import text
from database.session import engine_transit as engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("index-builder")

def rebuild():
    conn = engine.raw_connection()
    try:
        # 1. Create table
        logger.info("Initializing station_transit_index table...")
        conn.execute("DROP TABLE IF EXISTS station_transit_index")
        conn.execute("""
            CREATE TABLE station_transit_index (
                station_code TEXT PRIMARY KEY,
                station_name TEXT,
                trains_map TEXT -- JSON string: {train_no: [arr, dep, mask, seq, distance, fare]}
            )
        """)
        
        # 2. Extract and Aggregate data
        logger.info("Extracting data from stop_times, trips and segments...")
        # We need distance and fare from segments table
        query = """
            SELECT t.trip_id, s.code, st.arrival_time, st.departure_time, st.stop_sequence, t.service_id,
                   COALESCE(seg.distance_km, 0) as distance, COALESCE(seg.cost, 0) as fare
            FROM trips t
            JOIN stop_times st ON t.id = st.trip_id
            JOIN stops s ON st.stop_id = s.id
            LEFT JOIN segments seg ON (seg.trip_id = t.id AND seg.source_station_id = st.stop_id)
        """
        rows = conn.execute(query).fetchall()
        
        # station_code -> {train_no: [arr, dep, mask, seq, dist, fare]}
        index_data = defaultdict(dict)
        for r in rows:
            tno, scode, arr, dep, seq, sid, dist, fare = r[0], r[1], str(r[2]), str(r[3]), r[4], r[5], r[6], r[7]
            mask = 127 if "DAILY" in sid else 127 # Simple mapping
            index_data[scode][tno] = [arr, dep, mask, seq, dist, fare]
            
        # 3. Insert into index
        logger.info(f"Inserting indexed data for {len(index_data)} stations...")
        insert_data = []
        for scode, tmap in index_data.items():
            insert_data.append((scode, scode, json.dumps(tmap)))
            
        conn.executemany("INSERT INTO station_transit_index VALUES (?, ?, ?)", insert_data)
        conn.commit()
        logger.info("🚀 Transit Index rebuilt with distance/fare support.")
        
    finally:
        conn.close()

if __name__ == "__main__":
    rebuild()
