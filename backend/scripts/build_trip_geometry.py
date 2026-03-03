import sqlite3
import json
import zlib
import sys
import os
from datetime import datetime, time

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def time_to_minutes(t_str):
    if not t_str: return 0
    try:
        # Handle '14:30:00' or '14:30'
        parts = t_str.split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except: return 0

def build_trip_geometry_index():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Trip Geometry Index (Gap Analysis #1)...")
    
    try:
        # 1. Create the table
        conn.execute("DROP TABLE IF EXISTS trip_geometry_index")
        conn.execute("""
            CREATE TABLE trip_geometry_index (
                trip_id INTEGER PRIMARY KEY,
                geometry_blob BLOB  -- Compressed list of (stop_id, dist, time)
            )
        """)
        
        # 2. Fetch data from source (railway_data.db) 
        # We need the trip_id mapping from transit_graph.db first
        trips_mapping = {r['trip_id']: r['id'] for r in conn.execute("SELECT id, trip_id FROM trips").fetchall()}
        
        source_conn = sqlite3.connect('backend/database/railway_data.db')
        source_conn.row_factory = sqlite3.Row
        
        # We'll use train_routes which has distance_from_source and cumulative_travel_minutes
        print("  Extracting routes from source...")
        all_routes = source_conn.execute("""
            SELECT train_no, seq_no, station_code, distance_from_source, cumulative_travel_minutes 
            FROM train_routes 
            ORDER BY train_no, seq_no
        """).fetchall()
        
        # Map station_code to stop_id (internal)
        station_mapping = {r['code']: r['id'] for r in conn.execute("SELECT id, code FROM stops").fetchall()}
        
        from collections import defaultdict
        trip_data = defaultdict(list)
        
        for r in all_routes:
            t_no = str(r['train_no'])
            if t_no in trips_mapping and r['station_code'] in station_mapping:
                internal_trip_id = trips_mapping[t_no]
                internal_stop_id = station_mapping[r['station_code']]
                
                # Store (stop_id, cumulative_km, cumulative_min)
                trip_data[internal_trip_id].append((
                    internal_stop_id,
                    float(r['distance_from_source'] or 0),
                    int(r['cumulative_travel_minutes'] or 0)
                ))
        
        # 3. Compress and Insert
        print(f"  Compressing geometry for {len(trip_data)} trips...")
        insert_payload = []
        for trip_id, stops in trip_data.items():
            # Binary compression using zlib for efficiency
            binary_data = zlib.compress(json.dumps(stops).encode())
            insert_payload.append((trip_id, binary_data))
            
        conn.executemany("INSERT INTO trip_geometry_index VALUES (?, ?)", insert_payload)
        conn.commit()
        
        source_conn.close()
        print(f"🎉 Successfully indexed geometry for {len(insert_payload)} trips.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    build_trip_geometry_index()
