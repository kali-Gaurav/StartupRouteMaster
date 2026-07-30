import sqlite3
import struct
import sys
import os
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def time_to_min(t_str):
    if not t_str: return 0
    try:
        parts = t_str.split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except: return 0

def build_delta_times():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Delta-Encoded Stop Times (Suggestion #3)...")
    
    try:
        conn.execute("DROP TABLE IF EXISTS trip_delta_times")
        conn.execute("CREATE TABLE trip_delta_times (trip_id INTEGER PRIMARY KEY, deltas_blob BLOB)")
        
        # We need the source data to correctly calculate day-offsets
        source_conn = sqlite3.connect('backend/database/railway_data.db')
        source_conn.row_factory = sqlite3.Row
        
        # Mapping of internal trip_id to train_no
        trip_map = {r[0]: r[1] for r in conn.execute("SELECT id, trip_id FROM trips").fetchall()}
        
        print("  Extracting routes with day offsets from source...")
        # Use train_routes as it has day_offset
        routes = source_conn.execute("""
            SELECT train_no, seq_no, arrival_time, day_offset 
            FROM train_routes 
            ORDER BY train_no, seq_no
        """).fetchall()
        
        train_data = defaultdict(list)
        for r in routes:
            minutes = time_to_min(r['arrival_time']) + (r['day_offset'] * 1440)
            train_data[str(r['train_no'])].append(minutes)
            
        # Reverse map internal IDs
        internal_trip_data = {}
        # Invert the map: train_no -> internal_id
        inv_map = {v: k for k, v in trip_map.items()}
        for t_no, times in train_data.items():
            if t_no in inv_map:
                internal_trip_data[inv_map[t_no]] = times

        print(f"  Encoding deltas for {len(internal_trip_data)} trips...")
        insert_data = []
        for trip_id, times in internal_trip_data.items():
            start_time = times[0]
            # Ensure all deltas are positive
            deltas = [max(0, t - start_time) for t in times]
            blob = struct.pack(f"{len(deltas)}H", *deltas)
            insert_data.append((trip_id, blob))
            
        conn.executemany("INSERT INTO trip_delta_times VALUES (?, ?)", insert_data)
        conn.commit()
        print(f"🎉 Successfully delta-encoded {len(insert_data)} trips.")
        
        source_conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    build_delta_times()
