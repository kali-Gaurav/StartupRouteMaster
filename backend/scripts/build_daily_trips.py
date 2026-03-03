import sqlite3
import json
import zlib
import sys
import os
from datetime import date, timedelta

# Ensure backend package is importable
sys.path.append(os.getcwd())

def build_daily_trips_index():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Inverse Calendar Lookup (Suggestion #17)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS daily_active_trips")
        conn.execute("""
            CREATE TABLE daily_active_trips (
                date TEXT PRIMARY KEY,
                active_trips_blob BLOB  -- Compressed list of trip_ids
            )
        """)
        
        # 2. Fetch all trip service patterns
        trips = conn.execute("""
            SELECT t.id, c.monday, c.tuesday, c.wednesday, c.thursday, c.friday, c.saturday, c.sunday
            FROM trips t JOIN calendar c ON t.service_id = c.service_id
        """).fetchall()
        
        # 3. Map trips to dates for the next 90 days
        print("  Calculating active trips for the next 90 days...")
        start_date = date.today()
        
        daily_map = defaultdict(list)
        for d_off in range(90):
            curr_date = start_date + timedelta(days=d_off)
            curr_date_str = curr_date.isoformat()
            day_name = curr_date.strftime('%A').lower()
            
            for t in trips:
                if t[day_name]:
                    daily_map[curr_date_str].append(t['id'])
                    
        # 4. Insert
        insert_data = []
        for d_str, t_ids in daily_map.items():
            blob = zlib.compress(json.dumps(t_ids).encode())
            insert_data.append((d_str, blob))
            
        conn.executemany("INSERT INTO daily_active_trips VALUES (?, ?)", insert_data)
        conn.commit()
        print(f"🎉 Successfully built inverse calendar for {len(insert_data)} days.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

from collections import defaultdict
if __name__ == "__main__":
    build_daily_trips_index()
