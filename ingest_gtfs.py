import sqlite3
import pandas as pd
import os
import uuid
from datetime import datetime

db_path = 'backend/database/transit_graph.db'
gtfs_dir = 'gtfs'

def ingest_gtfs():
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Fix schema for route_shapes if it has UNIQUE(shape_id)
    print("Ensuring route_shapes schema is correct (no UNIQUE shape_id)...")
    cursor.execute("SELECT sql FROM sqlite_master WHERE name='route_shapes'")
    schema = cursor.fetchone()[0]
    if "UNIQUE (shape_id)" in schema:
        cursor.execute("DROP TABLE route_shapes")
        cursor.execute("""
            CREATE TABLE route_shapes (
                id VARCHAR(36) NOT NULL, 
                route_id INTEGER NOT NULL, 
                shape_id VARCHAR(100) NOT NULL, 
                geometry VARCHAR, 
                sequence INTEGER NOT NULL, 
                distance_traveled FLOAT NOT NULL, 
                created_at DATETIME, 
                PRIMARY KEY (id), 
                FOREIGN KEY(route_id) REFERENCES gtfs_routes (id)
            )
        """)
        conn.commit()

    # List of tables to clear
    tables_to_clear = [
        'agency', 'stops', 'gtfs_routes', 'calendar', 'calendar_dates', 
        'trips', 'stop_times', 'frequencies', 'transfers', 'route_shapes',
        'etl_metadata'
    ]

    print("Cleaning tables...")
    for table in tables_to_clear:
        try:
            cursor.execute(f"DELETE FROM {table}")
        except Exception as e:
            print(f"Warning: Could not clear {table}: {e}")
    conn.commit()

    # 1. Agency
    print("Ingesting agency.txt...")
    agency_df = pd.read_csv(os.path.join(gtfs_dir, 'agency.txt'))
    for _, row in agency_df.iterrows():
        cursor.execute(
            "INSERT INTO agency (agency_id, name, url, timezone, language) VALUES (?, ?, ?, ?, ?)",
            (str(row['agency_id']), row['agency_name'], row['agency_url'], row['agency_timezone'], str(row.get('agency_lang', 'en')))
        )

    # 2. Stops
    print("Ingesting stops.txt...")
    stops_df = pd.read_csv(os.path.join(gtfs_dir, 'stops.txt'))
    for _, row in stops_df.iterrows():
        # Using stop_timezone as city/state if available or empty
        city = ""
        if 'stop_timezone' in row and pd.notna(row['stop_timezone']):
            city = str(row['stop_timezone'])
        
        cursor.execute(
            "INSERT INTO stops (stop_id, code, name, latitude, longitude, city, state, data_quality_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(row['stop_id']), str(row.get('stop_code', row['stop_id'])), row['stop_name'], float(row['stop_lat']), float(row['stop_lon']), city, "", 0)
        )
    conn.commit()

    # 3. Routes
    print("Ingesting routes.txt...")
    routes_df = pd.read_csv(os.path.join(gtfs_dir, 'routes.txt'))
    for _, row in routes_df.iterrows():
        cursor.execute(
            "INSERT INTO gtfs_routes (route_id, short_name, long_name, route_type) VALUES (?, ?, ?, ?)",
            (str(row['route_id']), str(row.get('route_short_name', '')), str(row.get('route_long_name', '')), int(row['route_type']))
        )
    conn.commit()

    # 4. Calendar
    print("Ingesting calendar.txt...")
    if os.path.exists(os.path.join(gtfs_dir, 'calendar.txt')):
        calendar_df = pd.read_csv(os.path.join(gtfs_dir, 'calendar.txt'))
        for _, row in calendar_df.iterrows():
            cursor.execute(
                "INSERT INTO calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(row['service_id']), int(row['monday']), int(row['tuesday']), int(row['wednesday']), int(row['thursday']), int(row['friday']), int(row['saturday']), int(row['sunday']), str(row['start_date']), str(row['end_date']))
            )

    # 5. Trips
    print("Ingesting trips.txt...")
    trips_df = pd.read_csv(os.path.join(gtfs_dir, 'trips.txt'))
    for _, row in trips_df.iterrows():
        cursor.execute(
            "INSERT INTO trips (trip_id, route_id, service_id) VALUES (?, ?, ?)",
            (str(row['trip_id']), str(row['route_id']), str(row['service_id']))
        )
    conn.commit()

    # Cache IDs for performance in bulk inserts
    print("Caching internal IDs for mapping...")
    stop_id_map = {str(row[1]): row[0] for row in cursor.execute("SELECT id, stop_id FROM stops").fetchall()}
    trip_id_map = {str(row[1]): row[0] for row in cursor.execute("SELECT id, trip_id FROM trips").fetchall()}
    route_id_map = {str(row[1]): row[0] for row in cursor.execute("SELECT id, route_id FROM gtfs_routes").fetchall()}

    # 6. Stop Times
    print("Ingesting stop_times.txt...")
    total_stop_times = 0
    for chunk in pd.read_csv(os.path.join(gtfs_dir, 'stop_times.txt'), chunksize=20000):
        data_to_insert = []
        for _, row in chunk.iterrows():
            t_id = trip_id_map.get(str(row['trip_id']))
            s_id = stop_id_map.get(str(row['stop_id']))
            if t_id is not None and s_id is not None:
                data_to_insert.append((
                    t_id, s_id, str(row['arrival_time']), str(row['departure_time']), 
                    int(row['stop_sequence']), float(row.get('shape_dist_traveled', 0))
                ))
        
        cursor.executemany(
            "INSERT INTO stop_times (trip_id, stop_id, arrival_time, departure_time, stop_sequence, shape_dist_traveled) VALUES (?, ?, ?, ?, ?, ?)",
            data_to_insert
        )
        total_stop_times += len(data_to_insert)
    conn.commit()

    # 7. Shapes
    print("Ingesting shapes.txt...")
    if os.path.exists(os.path.join(gtfs_dir, 'shapes.txt')):
        shape_to_route_internal = {}
        for _, row in trips_df.iterrows():
            if 'shape_id' in row and pd.notna(row['shape_id']):
                s_id_str = str(row['shape_id'])
                if s_id_str.endswith('.0'): s_id_str = s_id_str[:-2]
                if s_id_str not in shape_to_route_internal:
                    r_id_str = str(row['route_id'])
                    if r_id_str.endswith('.0'): r_id_str = r_id_str[:-2]
                    r_id_internal = route_id_map.get(r_id_str)
                    if r_id_internal:
                        shape_to_route_internal[s_id_str] = r_id_internal

        for chunk in pd.read_csv(os.path.join(gtfs_dir, 'shapes.txt'), chunksize=20000):
            data_to_insert = []
            for _, row in chunk.iterrows():
                s_id_str = str(row['shape_id'])
                if s_id_str.endswith('.0'): s_id_str = s_id_str[:-2]
                r_id_internal = shape_to_route_internal.get(s_id_str)
                if r_id_internal:
                    geom = f"{row['shape_pt_lat']},{row['shape_pt_lon']}"
                    data_to_insert.append((
                        str(uuid.uuid4()), r_id_internal, s_id_str, geom, 
                        int(row['shape_pt_sequence']), float(row.get('shape_dist_traveled', 0)),
                        datetime.now().isoformat()
                    ))
            cursor.executemany(
                "INSERT INTO route_shapes (id, route_id, shape_id, geometry, sequence, distance_traveled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                data_to_insert
            )

    # 8. Feed Info (Into etl_metadata)
    print("Ingesting feed_info.txt into etl_metadata...")
    if os.path.exists(os.path.join(gtfs_dir, 'feed_info.txt')):
        feed_info_df = pd.read_csv(os.path.join(gtfs_dir, 'feed_info.txt'))
        if not feed_info_df.empty:
            row = feed_info_df.iloc[0]
            cursor.execute(
                "INSERT INTO etl_metadata (run_id, start_time, status, trips_synced, stop_times_synced, source_version, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), datetime.now().isoformat(), 'COMPLETED', len(trips_df), total_stop_times, str(row.get('feed_version', '1.0')), datetime.now().isoformat())
            )

    conn.commit()
    conn.close()
    print("GTFS Ingestion Complete with Feed Metadata!")

if __name__ == "__main__":
    ingest_gtfs()
