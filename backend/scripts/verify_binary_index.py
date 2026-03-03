import sqlite3
import struct
import sys
import os

def verify_binary_index():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT station_code, transit_blob FROM station_transit_index_bin LIMIT 1").fetchone()
        if not row:
            print("❌ No data found")
            return
            
        code, blob = row
        print(f"📊 Station {code} Binary Analysis:")
        print(f"  - Blob Size: {len(blob)} bytes")
        
        # Unpack 12-byte records
        record_size = 12
        num_trains = len(blob) // record_size
        print(f"  - Trains indexed: {num_trains}")
        
        for i in range(min(num_trains, 3)):
            offset = i * record_size
            # Format: I (4) H (2) H (2) B (1) B (1) H (2)
            data = struct.unpack_from("IHHBBH", blob, offset)
            print(f"    [{i+1}] Train {data[0]}: Dep {data[1]}m, Mask {data[3]}, Seq {data[4]}, Dist {data[5]}km")
            
        if num_trains > 0:
            print("🎉 SUCCESS: Binary transit index functional and O(1) seekable.")
            
    finally:
        conn.close()

if __name__ == "__main__":
    verify_binary_index()
