import sqlite3
import struct
import sys
import os
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def build_stop_bitmaps():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Stop-Sequence Bitmaps (Suggestion #5)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS train_stop_bitmaps")
        conn.execute("""
            CREATE TABLE train_stop_bitmaps (
                trip_id INTEGER PRIMARY KEY,
                stop_mask BLOB  -- 128 bits = 16 bytes
            )
        """)
        
        # 2. Fetch stops for all trips
        print("  Extracting stop sequences...")
        rows = conn.execute("SELECT trip_id, stop_sequence FROM stop_times").fetchall()
        
        trip_stops = defaultdict(list)
        for r in rows:
            trip_stops[r['trip_id']].append(r['stop_sequence'])
            
        # 3. Build Bitmasks
        print(f"  Encoding masks for {len(trip_stops)} trips...")
        insert_data = []
        for trip_id, sequences in trip_stops.items():
            # 128-bit mask (16 bytes)
            mask = bytearray(16)
            for seq in sequences:
                if 0 <= seq < 128:
                    byte_idx = seq // 8
                    bit_idx = seq % 8
                    mask[byte_idx] |= (1 << bit_idx)
            
            insert_data.append((trip_id, mask))
            
        conn.executemany("INSERT INTO train_stop_bitmaps VALUES (?, ?)", insert_data)
        conn.commit()
        print(f"🎉 Successfully generated stop bitmasks for {len(insert_data)} trips.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_stop_bitmaps()
