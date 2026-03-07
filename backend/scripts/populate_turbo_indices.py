import sqlite3
import json
import logging
import os
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("turbo_index")

def populate_turbo_indices():
    db_path = 'backend/database/transit_graph.db'
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Pre-fetch all fares into a map: trip_id -> {class: total_amt}
    logger.info("Caching fares for indexing (Summing segments)...")
    cursor.execute("SELECT trip_id, class_type, SUM(amount) FROM fares GROUP BY trip_id, class_type")
    fare_rows = cursor.fetchall()
    fare_lookup = defaultdict(dict)
    for tid, cls, total_amt in fare_rows:
        fare_lookup[tid][cls] = total_amt

    # 2. Get all stop times with station codes
    logger.info("Fetching stop times...")
    cursor.execute("""
        SELECT s.code, st.trip_id, st.departure_time, st.arrival_time, st.stop_sequence
        FROM stop_times st
        JOIN stops s ON st.stop_id = s.id
    """)
    rows = cursor.fetchall()
    
    station_map = defaultdict(dict)
    for row in rows:
        code, trip_id, dep, arr, seq = row
        # Get fares for this trip
        f3a = fare_lookup.get(trip_id, {}).get('3A', 0)
        fsl = fare_lookup.get(trip_id, {}).get('SL', 0)
        
        # New Format: [dep, arr, mask, seq, fare3a, fareSL]
        station_map[code][trip_id] = [str(dep), str(arr), 127, seq, f3a, fsl]

    # 3. Clean and Insert
    logger.info("Inserting into station_transit_index...")
    cursor.execute("DELETE FROM station_transit_index")
    insert_data = []
    for code, trains in station_map.items():
        insert_data.append((code, "", json.dumps(trains)))
    
    cursor.executemany(
        "INSERT INTO station_transit_index (station_code, station_name, trains_map) VALUES (?, ?, ?)",
        insert_data
    )
    
    conn.commit()
    conn.close()
    logger.info(f"Turbo indices populated with {len(insert_data)} stations.")

if __name__ == "__main__":
    populate_turbo_indices()
