import sqlite3
import logging
from typing import Dict, Any, List
from datetime import datetime, time, date
import os
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import text
from database.session import SessionLocal
from database.config import Config
from database.models import Stop, Trip, Route, Agency, Calendar, StopTime, Segment, Vehicle

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("etl")

class SQLiteReader:
    def __init__(self, db_path: str):
        self.db_path = db_path
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"SQLite database not found at {self.db_path}")

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def read_stations_master(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stations_master")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def read_trains_master(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trains_master")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def read_train_routes(self, train_no: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM train_routes WHERE train_no = ? ORDER BY seq_no", (train_no,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

def parse_time(t_str):
    if not t_str: return time(0,0)
    try:
        if ' ' in t_str: t_str = t_str.split(' ')[1] 
        parts = t_str.split(':')
        return time(int(parts[0]), int(parts[1]))
    except:
        return time(0,0)

def run_etl():
    db_path = os.path.join('backend', 'database', 'railway_data.db')
    reader = SQLiteReader(db_path)
    session = SessionLocal()
    
    try:
        # 1. Base Setup
        agency = session.query(Agency).filter(Agency.agency_id == "IR").first()
        if not agency:
            agency = Agency(agency_id="IR", name="Indian Railways", url="https://enquiry.indianrail.gov.in", timezone="Asia/Kolkata")
            session.add(agency)
            session.flush()
            
        calendar = session.query(Calendar).filter(Calendar.service_id == "DAILY").first()
        if not calendar:
            calendar = Calendar(
                service_id="DAILY", 
                monday=True, tuesday=True, wednesday=True, thursday=True, friday=True, saturday=True, sunday=True,
                start_date=date(2020, 1, 1), end_date=date(2030, 12, 31)
            )
            session.add(calendar)
            session.flush()

        # 2. Sync Stations (Bulk)
        stations = reader.read_stations_master()
        logger.info(f"Syncing {len(stations)} stations...")
        
        # Get existing stops to avoid duplicates
        existing_stop_ids = {s[0] for s in session.query(Stop.stop_id).all()}
        
        new_stops = []
        for s in stations:
            code = s['station_code']
            if code not in existing_stop_ids:
                new_stops.append({
                    "stop_id": code, 
                    "code": code, 
                    "name": s['station_name'], 
                    "city": s.get('city') or '',
                    "latitude": s.get('latitude') or 0.0, 
                    "longitude": s.get('longitude') or 0.0,
                    "location_type": 1
                })
        
        if new_stops:
            logger.info(f"Inserting {len(new_stops)} new stations...")
            session.bulk_insert_mappings(Stop, new_stops)
            session.commit()

        # Re-fetch mapping for FKs
        station_mapping = {s.stop_id: s.id for s in session.query(Stop).all()}

        # 3. Sync Trains & Routes (and StopTimes)
        trains = reader.read_trains_master()
        logger.info(f"Syncing {len(trains)} trains...")
        
        # Pre-fetch existing data to speed up
        existing_trips = {t[0] for t in session.query(Trip.trip_id).all()}
        
        train_count = 0
        segment_count = 0
        
        for t in trains:
            train_no = str(t['train_no'])
            if train_no in existing_trips:
                train_count += 1
                continue

            gtfs_route = Route(route_id=train_no, agency_id=agency.id, short_name=train_no, long_name=t['train_name'], route_type=2)
            session.add(gtfs_route)
            session.flush()
            
            trip = Trip(trip_id=train_no, route_id=gtfs_route.id, service_id=calendar.service_id)
            session.add(trip)
            session.flush()
            
            vehicle = Vehicle(id=str(uuid.uuid4()), vehicle_number=train_no, type='train', operator='IR')
            session.add(vehicle)
            session.flush()

            route_rows = reader.read_train_routes(train_no)
            
            stop_times_to_add = []
            segments_to_add = []

            for i, curr in enumerate(route_rows):
                code = curr['station_code']
                if code in station_mapping:
                    arr_time = parse_time(curr['arrival_time'])
                    dep_time = parse_time(curr['departure_time'])
                    if arr_time > dep_time: arr_time = dep_time

                    stop_times_to_add.append({
                        "trip_id": trip.id,
                        "stop_id": station_mapping[code],
                        "arrival_time": arr_time,
                        "departure_time": dep_time,
                        "stop_sequence": curr['seq_no'],
                        "cost": 0.0
                    })

                # Sync Segment (link current to next)
                if i < len(route_rows) - 1:
                    nxt = route_rows[i+1]
                    src_code = curr['station_code']
                    dst_code = nxt['station_code']
                    
                    if src_code in station_mapping and dst_code in station_mapping:
                        dur = (nxt['cumulative_travel_minutes'] or 0) - (curr['cumulative_travel_minutes'] or 0)
                        if dur <= 0: dur = 60
                            
                        segments_to_add.append({
                            "id": str(uuid.uuid4()),
                            "source_station_id": str(station_mapping[src_code]),
                            "dest_station_id": str(station_mapping[dst_code]),
                            "trip_id": trip.id,
                            "vehicle_id": vehicle.id,
                            "transport_mode": 'train',
                            "departure_time": parse_time(curr['departure_time']),
                            "arrival_time": parse_time(nxt['arrival_time']),
                            "arrival_day_offset": nxt['day_offset'] or 0,
                            "duration_minutes": dur,
                            "distance_km": float((nxt['distance_from_source'] or 0) - (curr['distance_from_source'] or 0)),
                            "cost": float((nxt['distance_from_source'] or 0) - (curr['distance_from_source'] or 0)) * 1.2,
                            "operating_days": "1111111"
                        })

            if stop_times_to_add:
                session.bulk_insert_mappings(StopTime, stop_times_to_add)
            if segments_to_add:
                session.bulk_insert_mappings(Segment, segments_to_add)
                segment_count += len(segments_to_add)

            train_count += 1
            if train_count % 50 == 0:
                session.commit()
                logger.info(f"Processed {train_count} trains... (Total Segments: {segment_count})")

        session.commit()
        logger.info(f"ETL Finished. Synced {train_count} trains, {segment_count} segments.")
        
    except Exception as e:
        logger.error(f"ETL Failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    run_etl()
