import sqlite3
import hashlib
import sys
import os
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.getcwd())

def build_path_hashes():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Route Fingerprint Hashes (Suggestion #15)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS trip_path_hashes")
        conn.execute("""
            CREATE TABLE trip_path_hashes (
                trip_id INTEGER PRIMARY KEY,
                path_hash TEXT
            )
        """)
        
        # 2. Extract paths
        print("  Extracting station sequences...")
        rows = conn.execute("SELECT trip_id, stop_id FROM stop_times ORDER BY trip_id, stop_sequence").fetchall()
        
        trip_paths = defaultdict(list)
        for r in rows:
            trip_paths[r['trip_id']].append(str(r['stop_id']))
            
        # 3. Hash and Insert
        insert_data = []
        for trip_id, stops in trip_paths.items():
            path_str = ",".join(stops)
            path_hash = hashlib.sha256(path_str.encode()).hexdigest()[:16]
            insert_data.append((trip_id, path_hash))
            
        conn.executemany("INSERT INTO trip_path_hashes VALUES (?, ?)", insert_data)
        conn.commit()
        
        # 4. Show redundancy
        unique_hashes = len(set(h for _, h in insert_data))
        print(f"🎉 Successfully hashed {len(insert_data)} trips.")
        print(f"📊 Found {unique_hashes} unique paths (Redundancy: {len(insert_data) - unique_hashes} identical routes).")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_path_hashes()
