import sqlite3
import struct
import os
import sys
from datetime import datetime

# Setup path
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BACKEND_ROOT)

def to_min(t_str):
    if not t_str: return 0
    try:
        parts = t_str.split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except: return 0

def build_v3_index():
    db_path = os.path.join(BACKEND_ROOT, 'database', 'transit_graph.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("🚀 Rebuilding Binary Transit Index V3 (Subtasks 4.2, 4.8, 4.11)...")
    
    try:
        # 1. Create fresh table
        cursor.execute("DROP TABLE IF EXISTS station_transit_index_bin")
        cursor.execute("""
            CREATE TABLE station_transit_index_bin (
                station_code TEXT PRIMARY KEY,
                transit_blob BLOB 
            )
        """)

        # 2. Get Service Masks from Calendar
        # We need a bitmask for Mon-Sun (1, 2, 4, 8, 16, 32, 64)
        print("  Generating service masks...")
        cursor.execute("SELECT service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday FROM calendar")
        service_masks = {}
        for r in cursor.fetchall():
            mask = 0
            if r['monday']: mask |= 1
            if r['tuesday']: mask |= 2
            if r['wednesday']: mask |= 4
            if r['thursday']: mask |= 8
            if r['friday']: mask |= 16
            if r['saturday']: mask |= 32
            if r['sunday']: mask |= 64
            service_masks[r['service_id']] = mask

        # 3. Get Trip Details
        print("  Caching trip metadata...")
        cursor.execute("SELECT id, service_id FROM trips")
        trip_service = {r['id']: r['service_id'] for r in cursor.fetchall()}

        # 4. Process all stop_times
        print("  Processing stop_times into binary blobs...")
        # Struct: I(4) H(2) H(2) B(1) B(1) H(2) = 12 bytes
        # [TripID, DepMin, ArrMin, Mask, Seq, Dist]
        
        cursor.execute("""
            SELECT st.stop_id, s.code, st.trip_id, st.departure_time, st.arrival_time, st.stop_sequence, st.shape_dist_traveled
            FROM stop_times st
            JOIN stops s ON st.stop_id = s.id
            ORDER BY s.code
        """)
        
        current_code = None
        blob = bytearray()
        count = 0
        
        while True:
            row = cursor.fetchone()
            if row is None or row['code'] != current_code:
                # Save previous station
                if current_code and blob:
                    conn.execute("INSERT INTO station_transit_index_bin VALUES (?, ?)", (current_code, blob))
                    count += 1
                
                if row is None: break
                current_code = row['code']
                blob = bytearray()

            try:
                t_id = row['trip_id']
                s_id = trip_service.get(t_id)
                mask = service_masks.get(s_id, 0)
                
                dep_min = to_min(row['departure_time'])
                arr_min = to_min(row['arrival_time'])
                seq = min(255, row['stop_sequence'])
                dist = int(float(row['shape_dist_traveled'] or 0.0))
                
                # Format: IHHBBH (12 bytes)
                record = struct.pack("IHHBBH", t_id, dep_min, arr_min, mask, seq, dist)
                blob.extend(record)
            except Exception as e:
                continue

        conn.commit()
        print(f"✅ V3 Index Built: {count} stations indexed.")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    build_v3_index()
