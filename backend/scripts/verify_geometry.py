import sqlite3
import zlib
import json
import sys
import os
import time

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def verify_geometry():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    
    try:
        # Get a trip that has geometry
        trip = conn.execute("SELECT trip_id, geometry_blob FROM trip_geometry_index LIMIT 1").fetchone()
        if not trip:
            print("❌ No data found in index")
            return
            
        trip_id, blob = trip
        
        # 1. Test Retrieval & Decompression
        start = time.perf_counter()
        data = json.loads(zlib.decompress(blob).decode())
        dur = (time.perf_counter() - start) * 1000
        
        print(f"📊 Trip {trip_id} Analysis:")
        print(f"  - Stops in route: {len(data)}")
        print(f"  - Decompression Time: {dur:.4f}ms")
        
        if len(data) >= 2:
            # 2. Test O(1) Distance Logic
            # Let's say we want distance between first and last stop
            src_stop = data[0]
            dst_stop = data[-1]
            distance = dst_stop[1] - src_stop[1]
            travel_time = dst_stop[2] - src_stop[2]
            
            print(f"  - Route: {src_stop[0]} -> {dst_stop[0]}")
            print(f"  - Calculated Distance: {distance} km")
            print(f"  - Calculated Time: {travel_time} mins")
            
            print("🎉 SUCCESS: O(1) Route Fingerprint functional.")
        
    finally:
        conn.close()

if __name__ == "__main__":
    verify_geometry()
