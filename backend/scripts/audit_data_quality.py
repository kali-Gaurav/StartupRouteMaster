import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("data_audit")

def audit_data():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print("\n>>> Data Quality Audit <<<")

    # 1. Trips with < 2 stops
    cur.execute("""
        SELECT trip_id, COUNT(*) as stop_count 
        FROM stop_times 
        GROUP BY trip_id 
        HAVING stop_count < 2
    """)
    short_trips = cur.fetchall()
    print(f"  Short Trips (< 2 stops): {len(short_trips)}")

    # 2. Stations with invalid coordinates
    cur.execute("""
        SELECT code, name, latitude, longitude 
        FROM stops 
        WHERE latitude = 0.0 OR longitude = 0.0 
           OR latitude IS NULL OR longitude IS NULL
    """)
    invalid_coords = cur.fetchall()
    print(f"  Stations with invalid coordinates: {len(invalid_coords)}")

    # 3. Segments with invalid distance
    cur.execute("""
        SELECT COUNT(*) 
        FROM segments 
        WHERE distance_km <= 0 AND source_station_id != dest_station_id
    """)
    invalid_dist = cur.fetchone()[0]
    print(f"  Segments with invalid distance: {invalid_dist}")

    # 4. Temporal inconsistency
    # Note: departure_time and arrival_time are stored as strings in stop_times or TIME in segments
    # This check is complex in SQL without a parser, but we can check if duration is negative
    cur.execute("""
        SELECT COUNT(*) 
        FROM segments 
        WHERE duration_minutes < 0
    """)
    negative_duration = cur.fetchone()[0]
    print(f"  Segments with negative duration: {negative_duration}")

    # 5. Trips with no segments
    cur.execute("""
        SELECT COUNT(*) 
        FROM trips t
        WHERE NOT EXISTS (SELECT 1 FROM segments s WHERE s.trip_id = t.id)
    """)
    orphan_trips = cur.fetchone()[0]
    print(f"  Orphan Trips (no segments): {orphan_trips}")

    conn.close()

if __name__ == "__main__":
    audit_data()
