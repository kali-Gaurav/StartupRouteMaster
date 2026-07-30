import pandas as pd
import sqlite3
import os
import sys
import logging
from datetime import datetime, time
import json

# Ensure backend package is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.config import Config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("GTFS-Importer")

GTFS_DIR = "gtfs"
DB_URL = Config.GET_SQLALCHEMY_URL("transit", is_async=False)
DB_PATH = DB_URL.replace("sqlite:///", "")

def norm_id(val):
    """Robust ID normalization: strip, convert float to int string, etc."""
    if pd.isna(val): return None
    try:
        s = str(val).strip()
        if s.endswith('.0'):
            s = s[:-2]
        # Remove leading zeros ONLY if it's purely numeric to match trips table '1'
        if s.isdigit():
            return str(int(s))
        return s
    except: return str(val).strip()

def run_importer():
    logger.info(f"🚀 Starting GTFS Master Import into {DB_PATH}...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. DROP AND REBUILD CORE TABLES
        logger.info("🧹 Purging corrupted tables...")
        cursor.execute("DROP TABLE IF EXISTS segments")
        cursor.execute("DROP TABLE IF EXISTS stop_times")
        cursor.execute("DROP TABLE IF EXISTS trips")
        cursor.execute("DROP TABLE IF EXISTS stops")
        cursor.execute("DROP TABLE IF EXISTS gtfs_routes")
        cursor.execute("DROP TABLE IF EXISTS calendar")
        cursor.execute("DROP TABLE IF EXISTS city_clusters")

        # Re-create tables
        cursor.execute("""
            CREATE TABLE stops (
                id INTEGER PRIMARY KEY,
                stop_id TEXT UNIQUE,
                code TEXT,
                name TEXT,
                city TEXT,
                state TEXT,
                latitude FLOAT,
                longitude FLOAT,
                data_quality_score INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE gtfs_routes (
                id INTEGER PRIMARY KEY,
                route_id TEXT UNIQUE,
                short_name TEXT,
                long_name TEXT,
                route_type INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE calendar (
                service_id TEXT PRIMARY KEY,
                monday INTEGER, tuesday INTEGER, wednesday INTEGER, thursday INTEGER,
                friday INTEGER, saturday INTEGER, sunday INTEGER,
                start_date TEXT, end_date TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE trips (
                id INTEGER PRIMARY KEY,
                trip_id TEXT UNIQUE,
                route_id TEXT,
                service_id TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE stop_times (
                id INTEGER PRIMARY KEY,
                trip_id INTEGER,
                stop_id INTEGER,
                arrival_time TEXT,
                departure_time TEXT,
                stop_sequence INTEGER,
                shape_dist_traveled FLOAT
            )
        """)
        cursor.execute("""
            CREATE TABLE segments (
                id TEXT PRIMARY KEY,
                trip_id INTEGER,
                source_stop_id INTEGER,
                dest_station_id INTEGER,
                departure_time TEXT,
                arrival_time TEXT,
                duration_minutes INTEGER,
                distance_km FLOAT,
                train_number TEXT,
                data_quality_score INTEGER DEFAULT 0
            )
        """)

        # 2. IMPORT DATA
        logger.info("📥 Importing stops.txt...")
        stops_df = pd.read_csv(os.path.join(GTFS_DIR, "stops.txt"), dtype=str)
        stops_df['stop_id_norm'] = stops_df['stop_id'].apply(lambda x: str(x).strip())
        stops_df['stop_code'] = stops_df['stop_code'].fillna(stops_df['stop_id'])
        stops_data = stops_df[['stop_id_norm', 'stop_code', 'stop_name', 'stop_lat', 'stop_lon']].values.tolist()
        cursor.executemany("INSERT INTO stops (stop_id, code, name, latitude, longitude) VALUES (?, ?, ?, ?, ?)", stops_data)

        logger.info("📥 Importing routes.txt...")
        routes_df = pd.read_csv(os.path.join(GTFS_DIR, "routes.txt"), dtype=str)
        routes_data = routes_df[['route_id', 'route_short_name', 'route_long_name', 'route_type']].values.tolist()
        cursor.executemany("INSERT INTO gtfs_routes (route_id, short_name, long_name, route_type) VALUES (?, ?, ?, ?)", routes_data)

        logger.info("📥 Importing calendar.txt...")
        cal_df = pd.read_csv(os.path.join(GTFS_DIR, "calendar.txt"))
        cursor.executemany("INSERT INTO calendar VALUES (?,?,?,?,?,?,?,?,?,?)", cal_df.values.tolist())

        logger.info("📥 Importing trips.txt...")
        trips_df = pd.read_csv(os.path.join(GTFS_DIR, "trips.txt"), dtype=str)
        trips_df['trip_id_norm'] = trips_df['trip_id'].apply(norm_id)
        trips_data = trips_df[['trip_id_norm', 'route_id', 'service_id']].values.tolist()
        cursor.executemany("INSERT INTO trips (trip_id, route_id, service_id) VALUES (?, ?, ?)", trips_data)

        conn.commit() # Save trips so we can build the map

        logger.info("📥 Importing stop_times.txt (Using normalized mapping)...")
        trip_map = {str(row[1]): row[0] for row in cursor.execute("SELECT id, trip_id FROM trips").fetchall()}
        stop_map = {str(row[1]): row[0] for row in cursor.execute("SELECT stop_id, id FROM stops").fetchall()}
        
        # Stream read to handle ID normalization line by line
        st_df = pd.read_csv(os.path.join(GTFS_DIR, "stop_times.txt"), dtype=str)
        st_df['trip_id_norm'] = st_df['trip_id'].apply(norm_id)
        st_df['stop_id_norm'] = st_df['stop_id'].apply(lambda x: str(x).strip())
        st_df['stop_sequence'] = pd.to_numeric(st_df['stop_sequence'])
        
        st_df = st_df.sort_values(['trip_id_norm', 'stop_sequence'])
        
        st_batch = []
        seg_batch = []
        last_trip_id = None
        prev_row = None
        
        count = 0
        total = len(st_df)
        
        logger.info(f"🛠️ Processing {total} stop time rows...")
        for row in st_df.itertuples():
            tid_pk = trip_map.get(str(row.trip_id_norm))
            sid_pk = stop_map.get(str(row.stop_id_norm))
            
            if not tid_pk:
                # logger.warning(f"Trip ID {row.trip_id_norm} not found in trips table")
                continue
            if not sid_pk:
                # logger.warning(f"Stop ID {row.stop_id_norm} not found in stops table")
                continue
            
            dist = getattr(row, 'shape_dist_traveled', '0')
            try: dist = float(dist)
            except: dist = 0.0
            
            st_batch.append((tid_pk, sid_pk, row.arrival_time, row.departure_time, int(str(row.stop_sequence)), dist))
            
            if last_trip_id == row.trip_id_norm and prev_row is not None:
                try:
                    h1, m1, _ = map(int, str(prev_row.departure_time).split(':'))
                    h2, m2, _ = map(int, str(row.arrival_time).split(':'))
                    dur = (h2*60+m2) - (h1*60+m1)
                    if dur < 0: dur += 1440
                    
                    prev_dist = getattr(prev_row, 'shape_dist_traveled', '0')
                    try: prev_dist = float(prev_dist)
                    except: prev_dist = 0.0
                    
                    seg_dist = dist - prev_dist
                    
                    seg_batch.append((
                        f"{tid_pk}_{str(prev_row.stop_sequence)}_{str(row.stop_sequence)}",
                        tid_pk, stop_map.get(str(prev_row.stop_id_norm)), sid_pk,
                        prev_row.departure_time, row.arrival_time,
                        dur, round(max(0, seg_dist), 3), str(row.trip_id_norm), 100
                    ))
                except: pass
            
            last_trip_id = row.trip_id_norm
            prev_row = row

            if len(st_batch) >= 10000:
                cursor.executemany("INSERT INTO stop_times (trip_id, stop_id, arrival_time, departure_time, stop_sequence, shape_dist_traveled) VALUES (?,?,?,?,?,?)", st_batch)
                st_batch = []
            if len(seg_batch) >= 10000:
                cursor.executemany("INSERT INTO segments (id, trip_id, source_stop_id, dest_station_id, departure_time, arrival_time, duration_minutes, distance_km, train_number, data_quality_score) VALUES (?,?,?,?,?,?,?,?,?,?)", seg_batch)
                seg_batch = []
            
            count += 1
            if count % 50000 == 0:
                logger.info(f"  Processed {count}/{total} rows...")

        if st_batch:
            cursor.executemany("INSERT INTO stop_times (trip_id, stop_id, arrival_time, departure_time, stop_sequence, shape_dist_traveled) VALUES (?,?,?,?,?,?)", st_batch)
        if seg_batch:
            cursor.executemany("INSERT INTO segments (id, trip_id, source_stop_id, dest_station_id, departure_time, arrival_time, duration_minutes, distance_km, train_number, data_quality_score) VALUES (?,?,?,?,?,?,?,?,?,?)", seg_batch)

        logger.info("⚡ Building indices...")
        cursor.execute("CREATE INDEX idx_st_trip ON stop_times(trip_id)")
        cursor.execute("CREATE INDEX idx_st_stop ON stop_times(stop_id)")
        cursor.execute("CREATE INDEX idx_seg_src ON segments(source_stop_id)")
        cursor.execute("CREATE INDEX idx_seg_dst ON segments(dest_station_id)")

        conn.commit()
        logger.info("🎉 GTFS Master Import Success!")

    except Exception as e:
        logger.error(f"❌ ETL Failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_importer()
