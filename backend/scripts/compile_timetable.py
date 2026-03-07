import sqlite3
import numpy as np
import os
import logging
from datetime import datetime, time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("timetable_compiler")

def time_to_seconds(t_str):
    """Convert HH:MM:SS to seconds from midnight."""
    try:
        # Handle string TIME format from SQLite
        t_str = str(t_str).split('.')[0]
        parts = t_str.split(':')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + (int(parts[2]) if len(parts) > 2 else 0)
    except:
        return 0

def compile_timetable():
    db_path = 'backend/database/transit_graph.db'
    output_path = 'backend/data/timetable.npz'
    
    if not os.path.exists('backend/data'):
        os.makedirs('backend/data')

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    logger.info("Fetching segments and stops for CSA compilation...")
    
    # 1. Map stops to indices
    cur.execute("SELECT id FROM stops ORDER BY id")
    stop_ids = np.array([row[0] for row in cur.fetchall()], dtype=np.int32)
    stop_to_idx = {sid: i for i, sid in enumerate(stop_ids)}
    
    # 2. Fetch all segments
    cur.execute("""
        SELECT source_station_id, dest_station_id, departure_time, arrival_time, trip_id 
        FROM segments
    """)
    rows = cur.fetchall()
    logger.info(f"Processing {len(rows)} connections...")

    connections = []
    for src_id, dst_id, dep_t, arr_t, tid in rows:
        try:
            # We convert everything to integers for the NumPy kernel
            # dep_stop_idx, arr_stop_idx, dep_seconds, arr_seconds, trip_id
            dep_sec = time_to_seconds(dep_t)
            arr_sec = time_to_seconds(arr_t)
            
            # Handle cross-midnight trips
            if arr_sec < dep_sec:
                arr_sec += 86400 # +24 hours
                
            connections.append([
                stop_to_idx[int(src_id)],
                stop_to_idx[int(dst_id)],
                dep_sec,
                arr_sec,
                int(tid)
            ])
        except:
            continue

    # 3. CRITICAL: Sort by departure time for CSA
    logger.info("Sorting connections by departure time...")
    connections_array = np.array(connections, dtype=np.int32)
    # Sort by the 3rd column (dep_sec)
    sorted_indices = np.argsort(connections_array[:, 2])
    sorted_connections = connections_array[sorted_indices]

    # 4. Save
    logger.info(f"Saving compiled timetable to {output_path}...")
    np.savez_compressed(output_path, connections=sorted_connections, stop_ids=stop_ids)
    
    conn.close()
    logger.info("Timetable compilation complete.")

if __name__ == "__main__":
    compile_timetable()
