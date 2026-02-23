import sqlite3
import os
from datetime import datetime, date, time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
RAILWAY_DATA_DB = "backend/database/railway_data.db"
TRANSIT_GRAPH_DB = "backend/database/transit_graph.db"

def migrate():
    if not os.path.exists(RAILWAY_DATA_DB):
        logger.error(f"Source DB {RAILWAY_DATA_DB} not found!")
        return

    # Connect to both databases
    source_conn = sqlite3.connect(RAILWAY_DATA_DB)
    target_conn = sqlite3.connect(TRANSIT_GRAPH_DB)
    
    source_conn.row_factory = sqlite3.Row
    
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()

    try:
        # 1. Migrate Agency
        logger.info("Migrating Agency...")
        target_cursor.execute("INSERT OR IGNORE INTO agency (id, agency_id, name, url, timezone) VALUES (1, 'IR', 'Indian Railways', 'http://www.indianrail.gov.in', 'Asia/Kolkata')")
        
        # 2. Migrate Stops
        logger.info("Migrating Stops...")
        source_cursor.execute("SELECT * FROM stations_master")
        stations = source_cursor.fetchall()
        for s in stations:
            target_cursor.execute("""
                INSERT OR IGNORE INTO stops (stop_id, code, name, city, state, latitude, longitude, location_type, safety_score, is_major_junction, facilities_json, wheelchair_accessible)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, 50.0, 0, '{}', 0)
            """, (s['station_code'], s['station_code'], s['station_name'], s['city'], s['state'], s['latitude'] or 0.0, s['longitude'] or 0.0))
        
        # 3. Create a default Route for each Train
        logger.info("Migrating Routes and Trips...")
        source_cursor.execute("SELECT * FROM trains_master")
        trains = source_cursor.fetchall()
        for t in trains:
            # Create GTFS Route for each train (or group them if needed, but 1-to-1 is safer for rail)
            route_id_str = f"R_{t['train_no']}"
            target_cursor.execute("""
                INSERT OR IGNORE INTO gtfs_routes (route_id, agency_id, short_name, long_name, route_type)
                VALUES (?, 1, ?, ?, 2)
            """, (route_id_str, str(t['train_no']), t['train_name']))
            
            # Get internal route id
            target_cursor.execute("SELECT id FROM gtfs_routes WHERE route_id = ?", (route_id_str,))
            row = target_cursor.fetchone()
            if not row: continue
            route_internal_id = row[0]
            
            # Create Calendar entry for service_id
            service_id = f"S_{t['train_no']}"
            # Extract days from train_running_days
            source_cursor.execute("SELECT * FROM train_running_days WHERE train_no = ?", (t['train_no'],))
            days = source_cursor.fetchone()
            if days:
                target_cursor.execute("""
                    INSERT OR IGNORE INTO calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, '2025-01-01', '2026-12-31')
                """, (service_id, days['mon'], days['tue'], days['wed'], days['thu'], days['fri'], days['sat'], days['sun']))
            else:
                target_cursor.execute("""
                    INSERT OR IGNORE INTO calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                    VALUES (?, 1, 1, 1, 1, 1, 1, 1, '2025-01-01', '2026-12-31')
                """, (service_id,))

            # Create Trip
            target_cursor.execute("""
                INSERT OR IGNORE INTO trips (trip_id, route_id, service_id, headsign, bike_allowed, wheelchair_accessible)
                VALUES (?, ?, ?, ?, 0, 0)
            """, (str(t['train_no']), route_internal_id, service_id, t['destination_station']))
            
        # 4. Migrate StopTimes
        logger.info("Migrating StopTimes (this may take a while)...")
        source_cursor.execute("SELECT * FROM train_schedule")
        schedule = source_cursor.fetchall()
        
        # Map stop_id (code) to internal stops.id
        target_cursor.execute("SELECT id, stop_id FROM stops")
        stop_map = {row[1]: row[0] for row in target_cursor.fetchall()}
        
        # Map trip_id (train_number) to internal trips.id
        target_cursor.execute("SELECT id, trip_id FROM trips")
        trip_map = {row[1]: row[0] for row in target_cursor.fetchall()}
        
        count = 0
        batch = []
        for row in schedule:
            trip_internal_id = trip_map.get(str(row['train_no']))
            stop_internal_id = stop_map.get(row['station_code'])
            
            if trip_internal_id and stop_internal_id:
                # Format times HH:MM:SS
                arr = row['arrival_time']
                dep = row['departure_time']
                
                batch.append((trip_internal_id, stop_internal_id, arr, dep, row['seq_no'], 0.0, 0, 0))
                count += 1
                
                if len(batch) >= 1000:
                    target_cursor.executemany("""
                        INSERT OR IGNORE INTO stop_times (trip_id, stop_id, arrival_time, departure_time, stop_sequence, cost, pickup_type, drop_off_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    batch = []
                    if count % 10000 == 0:
                        logger.info(f"  Processed {count} stop times...")

        if batch:
            target_cursor.executemany("""
                INSERT OR IGNORE INTO stop_times (trip_id, stop_id, arrival_time, departure_time, stop_sequence, cost, pickup_type, drop_off_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)

        target_conn.commit()
        logger.info(f"Migration complete! Total stop times: {count}")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        target_conn.rollback()
    finally:
        source_conn.close()
        target_conn.close()

if __name__ == "__main__":
    migrate()
