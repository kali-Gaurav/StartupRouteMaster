import sqlite3
import json
import struct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("binary_migration")

def time_to_minutes(t_str):
    try:
        t_str = t_str.split('.')[0]
        parts = t_str.split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except:
        return 0

def migrate_to_binary():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    logger.info("Starting binary migration (v3 - 4-byte Fares)...")
    cursor.execute("SELECT station_code, trains_map FROM station_transit_index WHERE trains_map IS NOT NULL")
    rows = cursor.fetchall()
    
    total = len(rows)
    logger.info(f"Processing {total} stations...")

    updates = []
    for s_code, trains_map_json in rows:
        try:
            trains_map = json.loads(trains_map_json)
            num_trains = len(trains_map)
            blob = struct.pack("<H", num_trains)
            
            for trip_id_str, data in trains_map.items():
                try:
                    trip_id = int(trip_id_str)
                except ValueError: continue

                dep_min = time_to_minutes(data[0])
                arr_min = time_to_minutes(data[1])
                mask = int(data[2])
                seq = int(data[3])
                fare3a = int(float(data[4])) if len(data) > 4 else 0
                fareSL = int(float(data[5])) if len(data) > 5 else 0
                
                # Changed to I (4 bytes) for fares: IHHBBII = 18 bytes
                blob += struct.pack("<IHHBBII", trip_id, dep_min, arr_min, mask, seq, fare3a, fareSL)
            
            updates.append((blob, s_code))
        except Exception as e:
            logger.error(f"Error packing station {s_code}: {e}")

    logger.info(f"Updating {len(updates)} stations in database...")
    cursor.executemany("UPDATE station_transit_index SET trains_binary = ? WHERE station_code = ?", updates)
    conn.commit()
    conn.close()
    logger.info("Binary migration v3 complete.")

if __name__ == "__main__":
    migrate_to_binary()
