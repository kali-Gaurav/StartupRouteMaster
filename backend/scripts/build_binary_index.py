import sqlite3
import struct
import sys
import os
import json
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

def build_binary_transit_index():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Binary Station Transit Index (Suggestion #4)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS station_transit_index_bin")
        conn.execute("""
            CREATE TABLE station_transit_index_bin (
                station_code TEXT PRIMARY KEY,
                transit_blob BLOB  -- Sequence of 12-byte records
            )
        """)
        
        # 2. Fetch existing JSON data
        print("  Converting JSON maps to Binary...")
        rows = conn.execute("SELECT station_code, trains_map FROM station_transit_index").fetchall()
        
        insert_data = []
        for r in rows:
            code = r['station_code']
            trains = json.loads(r['trains_map'])
            
            # Binary structure for EACH train:
            # TrainID (4B integer) | DepMin (2B) | ArrMin (2B) | Mask (1B) | Seq (1B) | Dist (2B)
            # Total: 12 bytes per train.
            
            blob = bytearray()
            for t_no, details in trains.items():
                # details: [dep, arr, mask, seq, dist, fare]
                try:
                    # Compact representation
                    t_id = int(t_no) 
                    dep_min = time_to_min(details[0])
                    arr_min = time_to_min(details[1])
                    mask = int(details[2])
                    seq = int(details[3])
                    dist = int(float(details[4]))
                    
                    # Pack: I=unsigned int (4), H=unsigned short (2), B=unsigned char (1)
                    # Format: I H H B B H (4 + 2 + 2 + 1 + 1 + 2 = 12 bytes)
                    record = struct.pack("IHHBBH", t_id, dep_min, arr_min, mask, seq, dist)
                    blob.extend(record)
                except ValueError:
                    # Skip trains with non-numeric IDs for this binary optimization
                    continue
            
            if blob:
                insert_data.append((code, blob))
                
        conn.executemany("INSERT INTO station_transit_index_bin VALUES (?, ?)", insert_data)
        conn.commit()
        print(f"🎉 Successfully converted {len(insert_data)} stations to Binary Index.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    build_binary_transit_index()
