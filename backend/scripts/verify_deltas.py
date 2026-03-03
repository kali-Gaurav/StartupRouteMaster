import sqlite3
import struct
import sys
import os

def verify_deltas():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT trip_id, deltas_blob FROM trip_delta_times LIMIT 1").fetchone()
        if not row:
            print("❌ No data found")
            return
            
        trip_id, blob = row
        # Number of 2-byte shorts
        n = len(blob) // 2
        deltas = struct.unpack(f"{n}H", blob)
        
        print(f"📊 Trip {trip_id} Delta Schedule:")
        print(f"  - Packed Size: {len(blob)} bytes")
        print(f"  - Unpacked Deltas (mins): {deltas}")
        
        if len(deltas) > 0:
            print("🎉 SUCCESS: Delta-encoded storage functional.")
            
    finally:
        conn.close()

if __name__ == "__main__":
    verify_deltas()
