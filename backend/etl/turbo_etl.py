import sqlite3
import logging
from datetime import datetime, time, date
import os
import uuid
import sys

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlalchemy import text, insert
from database.session import SessionTransit as SessionLocal, engine_transit as engine
from database.models import (
    Stop, Trip, Route, Agency, Calendar, StopTime, Segment, 
    Vehicle, StationSchedule, TrainPath, ETLMetadata
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("turbo-etl")

def parse_time(t_str):
    if not t_str: return time(0,0)
    try:
        if ' ' in t_str: t_str = t_str.split(' ')[1] 
        parts = t_str.split(':')
        return time(int(parts[0]), int(parts[1]))
    except:
        return time(0,0)

def run_turbo_etl():
    db_path = os.path.join('backend', 'database', 'railway_data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    session = SessionLocal()
    run_id = f"run_{int(datetime.utcnow().timestamp())}"
    
    etl_meta = ETLMetadata(run_id=run_id, status="running", source_version="v1.0")
    session.add(etl_meta)
    session.commit()
    
    try:
        logger.info(f"Starting Optimized ETL Run: {run_id}")
        agency = session.query(Agency).filter(Agency.agency_id == "IR").first()
        if not agency:
            agency = Agency(agency_id="IR", name="Indian Railways", url="https://enquiry.indianrail.gov.in", timezone="Asia/Kolkata")
            session.add(agency)
            session.flush()
        
        station_mapping = {s.stop_id: s.id for s in session.query(Stop.id, Stop.stop_id).all()}
        existing_trips = {t[0] for t in session.query(Trip.trip_id).all()}
        existing_calendars = {c[0] for c in session.query(Calendar.service_id).all()}
        existing_routes = {r[0]: r[1] for r in session.query(Route.route_id, Route.id).all()}
        
        trains = [dict(r) for r in conn.execute("SELECT * FROM trains_master").fetchall()]
        running_days_map = {r['train_no']: dict(r) for r in conn.execute("SELECT * FROM train_running_days").fetchall()}
        
        new_trains = [t for t in trains if str(t['train_no']) not in existing_trips]
        logger.info(f"Found {len(new_trains)} new trains to sync.")
        
        if not new_trains:
            etl_meta.status = "success"
            etl_meta.end_time = datetime.utcnow()
            session.commit()
            return

        # Buffers
        vehicles_to_add = []
        stop_times_to_add = []
        segments_to_add = []
        station_schedules_to_add = []
        train_paths_to_add = []
        
        DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        # Process in smaller batches of trains to keep memory and DB transactions manageable
        BATCH_SIZE = 50
        for i in range(0, len(new_trains), BATCH_SIZE):
            batch = new_trains[i:i+BATCH_SIZE]
            logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(new_trains)-1)//BATCH_SIZE + 1}...")
            
            for t in batch:
                train_no = str(t['train_no'])
                
                # Ensure Route exists
                if train_no not in existing_routes:
                    gtfs_route = Route(route_id=train_no, agency_id=agency.id, short_name=train_no, long_name=t['train_name'], route_type=2)
                    session.add(gtfs_route)
                    session.flush() # Need this ID
                    existing_routes[train_no] = gtfs_route.id
                
                route_id_internal = existing_routes[train_no]

                # Service
                running = running_days_map.get(train_no)
                service_id = "DAILY"
                if running:
                    service_id = f"S_{train_no}"
                    if service_id not in existing_calendars:
                        cal = Calendar(
                            service_id=service_id,
                            monday=bool(running['mon']), tuesday=bool(running['tue']), 
                            wednesday=bool(running['wed']), thursday=bool(running['thu']),
                            friday=bool(running['fri']), saturday=bool(running['sat']), 
                            sunday=bool(running['sun']),
                            start_date=date(2020, 1, 1), end_date=date(2030, 12, 31)
                        )
                        session.add(cal)
                        existing_calendars.add(service_id)

                # Trip
                trip = Trip(trip_id=train_no, route_id=route_id_internal, service_id=service_id)
                session.add(trip)
                session.flush() # Need this ID for StopTimes
                
                etl_meta.trips_synced += 1
                vehicle_id = str(uuid.uuid4())
                vehicles_to_add.append({"id": vehicle_id, "vehicle_number": train_no, "type": 'train', "operator": 'IR'})

                # Route Detail
                route_rows = conn.execute("SELECT * FROM train_routes WHERE train_no = ? ORDER BY seq_no", (train_no,)).fetchall()
                for j, curr in enumerate(route_rows):
                    code = curr['station_code']
                    if code in station_mapping:
                        stop_id_int = station_mapping[code]
                        arr_time, dep_time = parse_time(curr['arrival_time']), parse_time(curr['departure_time'])
                        if arr_time > dep_time: arr_time = dep_time

                        stop_times_to_add.append({
                            "trip_id": trip.id, "stop_id": stop_id_int,
                            "arrival_time": arr_time, "departure_time": dep_time,
                            "stop_sequence": curr['seq_no']
                        })
                        etl_meta.stop_times_synced += 1

                        for day in DAYS_OF_WEEK:
                            station_schedules_to_add.append({
                                "station_id": stop_id_int, "trip_id": trip.id,
                                "arrival": arr_time, "departure": dep_time,
                                "day_of_week": day, "stop_seq": curr['seq_no']
                            })
                            train_paths_to_add.append({
                                "trip_id": trip.id, "station_id": stop_id_int,
                                "arrival": arr_time, "departure": dep_time,
                                "stop_seq": curr['seq_no'], "day_of_week": day
                            })

                    if j < len(route_rows) - 1:
                        nxt = route_rows[j+1]
                        src_code, dst_code = curr['station_code'], nxt['station_code']
                        if src_code in station_mapping and dst_code in station_mapping:
                            dur = (nxt['cumulative_travel_minutes'] or 0) - (curr['cumulative_travel_minutes'] or 0)
                            segments_to_add.append({
                                "id": str(uuid.uuid4()),
                                "source_station_id": station_mapping[src_code],
                                "dest_station_id": station_mapping[dst_code],
                                "trip_id": trip.id, "vehicle_id": vehicle_id,
                                "transport_mode": 'train',
                                "departure_time": parse_time(curr['departure_time']),
                                "arrival_time": parse_time(nxt['arrival_time']),
                                "arrival_day_offset": nxt['day_offset'] or 0,
                                "duration_minutes": dur if dur > 0 else 60,
                                "distance_km": float((nxt['distance_from_source'] or 0) - (curr['distance_from_source'] or 0)),
                                "cost": float((nxt['distance_from_source'] or 0) - (curr['distance_from_source'] or 0)) * 1.2,
                                "operating_days": "1111111"
                            })

            # Commit batch
            session.bulk_insert_mappings(Vehicle, vehicles_to_add)
            session.bulk_insert_mappings(StopTime, stop_times_to_add)
            session.bulk_insert_mappings(Segment, segments_to_add)
            session.bulk_insert_mappings(StationSchedule, station_schedules_to_add)
            session.bulk_insert_mappings(TrainPath, train_paths_to_add)
            session.commit()
            
            # Clear buffers
            vehicles_to_add, stop_times_to_add, segments_to_add = [], [], []
            station_schedules_to_add, train_paths_to_add = [], []
            
        etl_meta.status = "success"
        etl_meta.end_time = datetime.utcnow()
        session.commit()
        logger.info(f"🚀 Turbo ETL Finished. {etl_meta.trips_synced} trips synced.")

    except Exception as e:
        logger.error(f"Turbo ETL Failed: {e}")
        session.rollback()
        etl_meta.status = "failed"
        etl_meta.end_time = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()
        conn.close()

if __name__ == "__main__":
    run_turbo_etl()
