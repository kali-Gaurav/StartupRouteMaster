import sqlite3
import json
import zlib
import sys
import os
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.getcwd())

def build_direct_index():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Inverse Trip Index (Suggestion #14)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS direct_connectivity_index")
        conn.execute("""
            CREATE TABLE direct_connectivity_index (
                src_id INTEGER,
                dst_id INTEGER,
                trips_blob BLOB,
                PRIMARY KEY (src_id, dst_id)
            )
        """)
        
        # 2. Map all station pairs per trip
        print("  Mapping all reachable pairs from stop_times...")
        rows = conn.execute("SELECT trip_id, stop_id, stop_sequence FROM stop_times ORDER BY trip_id, stop_sequence").fetchall()
        
        trip_stops = defaultdict(list)
        for r in rows:
            trip_stops[r['trip_id']].append(r['stop_id'])
            
        pairs = defaultdict(list)
        for t_id, stops in trip_stops.items():
            for i in range(len(stops)):
                for j in range(i + 1, len(stops)):
                    src = stops[i]
                    dst = stops[j]
                    pairs[(src, dst)].append(t_id)
                    
        # 3. Bulk Insert
        print(f"  Inserting {len(pairs)} direct pairs...")
        insert_data = []
        for pair, t_ids in pairs.items():
            # Compress for efficiency
            blob = zlib.compress(json.dumps(t_ids).encode())
            insert_data.append((pair[0], pair[1], blob))
            
        conn.executemany("INSERT INTO direct_connectivity_index VALUES (?, ?, ?)", insert_data)
        conn.commit()
        print("🎉 Successfully built direct connectivity index.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_direct_index()
