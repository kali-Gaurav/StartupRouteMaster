"""
[DB Efficiency] apply_efficiency_indexes.py (TODO #22)

Creates composite indexes to optimize RAPTOR and Turbo lookups.
"""

import sqlite3
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def apply_indexes():
    raw_path = transit_db_path.replace("sqlite:///", "")
    print(f"Applying Efficiency Indexes on {raw_path}...")
    
    conn = sqlite3.connect(raw_path)
    try:
        # 1. RAPTOR Core: Finding next departure from a station
        print("Creating index: idx_station_schedule_lookup...")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_station_schedule_lookup ON station_schedule (station_id, day_of_week, departure)")
        
        # 2. RAPTOR Core: Scanning a trip forward
        print("Creating index: idx_train_path_scan...")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_train_path_scan ON train_path (trip_id, day_of_week, stop_seq)")
        
        # 3. ANALYZE to update query planner
        print("Running ANALYZE...")
        conn.execute("ANALYZE")
        
        conn.commit()
        print("🚀 Efficiency Indexes Applied & Analyzer Updated.")
        
    except Exception as e:
        print(f"Index Application Failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    apply_indexes()
