import sqlite3
import sys
import os

def verify_stop_bitmaps():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT trip_id, stop_mask FROM train_stop_bitmaps LIMIT 1").fetchone()
        if not row:
            print("❌ No data found")
            return
            
        trip_id, blob = row
        print(f"📊 Trip {trip_id} Stop Analysis:")
        
        # Check bits
        stops_found = []
        for i in range(128):
            byte_idx = i // 8
            bit_idx = i % 8
            if blob[byte_idx] & (1 << bit_idx):
                stops_found.append(i)
        
        print(f"  - Stops sequence IDs found in bitmask: {stops_found}")
        
        # Verify against actual table
        actual = conn.execute("SELECT stop_sequence FROM stop_times WHERE trip_id = ? ORDER BY stop_sequence", (trip_id,)).fetchall()
        actual_seqs = [r[0] for r in actual]
        print(f"  - Actual sequence IDs in stop_times: {actual_seqs}")
        
        if set(stops_found) == set(actual_seqs):
            print("🎉 SUCCESS: Stop-sequence bitmask is accurate.")
        else:
            print("❌ ERROR: Bitmask mismatch.")
            
    finally:
        conn.close()

if __name__ == "__main__":
    verify_stop_bitmaps()
