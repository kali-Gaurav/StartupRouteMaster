import sqlite3
import json
import sys
import os
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def build_hour_buckets():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Hour-Bucket Partitioning (Suggestion #13)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS station_hour_buckets")
        conn.execute("""
            CREATE TABLE station_hour_buckets (
                station_id INTEGER,
                hour INTEGER,
                trips_json TEXT,
                PRIMARY KEY (station_id, hour)
            )
        """)
        
        # 2. Extract departures grouped by hour
        print("  Extracting departures into buckets...")
        # We'll use the stop_times table
        rows = conn.execute("""
            SELECT stop_id, departure_time, trip_id 
            FROM stop_times
        """).fetchall()
        
        buckets = defaultdict(lambda: defaultdict(list))
        for r in rows:
            sid = r['stop_id']
            dep = r['departure_time']
            if not dep: continue
            
            # Extract hour: '14:30:00' -> 14
            hour = int(dep.split(':')[0])
            buckets[sid][hour].append({
                "t": r['trip_id'],
                "d": dep
            })
            
        # 3. Bulk Insert
        insert_data = []
        for sid, hr_map in buckets.items():
            for hr, trips in hr_map.items():
                insert_data.append((sid, hr, json.dumps(trips)))
                
        print(f"  Inserting {len(insert_data)} buckets...")
        conn.executemany("INSERT INTO station_hour_buckets VALUES (?, ?, ?)", insert_data)
        conn.commit()
        print("🎉 Successfully built hour-bucket index.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_hour_buckets()
