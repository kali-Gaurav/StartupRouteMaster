import sqlite3
import logging
import os
import uuid
import gc
from typing import Dict, Any, List
from datetime import datetime, time, date
from contextlib import contextmanager

from sqlalchemy.orm import Session
from sqlalchemy import text
from database.session import SessionLocal
from database.models import Stop, Trip, Route, Agency, Calendar, StopTime, Segment, Vehicle, StationSchedule, TrainPath

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("etl-atomic")

class SQLiteAtomicReader:
    """[Task 107] High-Concurrency SQLite Handover with WAL support."""
    def __init__(self, db_path: str):
        if not os.path.exists(db_path):
             # Try relative to parent if in backend/
             p1 = os.path.join('backend', 'database', 'railway_data.db')
             db_path = p1 if os.path.exists(p1) else db_path
             
        self.db_path = db_path
        self._conn = None

    @contextmanager
    def session(self):
        if not self._conn:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            # Enable WAL mode for performance/locking
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            
        try:
            yield self._conn.cursor()
        except Exception as e:
            self._conn.rollback()
            raise e

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

def parse_time(t_str):
    if not t_str: return time(12,0)
    try:
        if ' ' in t_str: t_str = t_str.split(' ')[1] 
        parts = t_str.split(':')
        return time(int(parts[0]) % 24, int(parts[1]))
    except: return time(12,0)

async def run_etl():
    """[Task 107] Elite Atomic Ingestion."""
    db_path = os.path.join('database', 'railway_data.db')
    reader = SQLiteAtomicReader(db_path)
    session = SessionLocal()
    
    DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    try:
        logger.info("🎬 Starting Atomic Relational Handover...")
        
        # 1. Base Setup
        agency = session.query(Agency).filter(Agency.agency_id == "IR").first()
        if not agency:
            agency = Agency(agency_id="IR", name="Indian Railways", url="https://enquiry.indianrail.gov.in", timezone="Asia/Kolkata")
            session.add(agency); session.flush()

        # 2. Sync Stations
        with reader.session() as cur:
            cur.execute("SELECT * FROM stations_master")
            stations = [dict(r) for r in cur.fetchall()]
            
        existing_stop_ids = {s[0] for s in session.query(Stop.stop_id).all()}
        new_stops = []
        for s in stations:
            if s['station_code'] not in existing_stop_ids:
                new_stops.append({
                    "stop_id": s['station_code'], "code": s['station_code'], "name": s['station_name'], 
                    "city": s.get('city', ''), "latitude": s.get('latitude', 0.0), "longitude": s.get('longitude', 0.0),
                    "location_type": 1
                })
        
        if new_stops:
            logger.info(f"Syncing {len(new_stops)} new stations...")
            session.bulk_insert_mappings(Stop, new_stops)
            session.commit()

        station_mapping = {s.stop_id: s.id for s in session.query(Stop).all()}

        # 3. Sync Trains
        with reader.session() as cur:
            cur.execute("SELECT * FROM trains_master")
            trains = [dict(r) for r in cur.fetchall()]
            
        existing_trips = {t[0] for t in session.query(Trip.trip_id).all()}
        
        for k, t in enumerate(trains):
            train_no = str(t['train_no'])
            if train_no in existing_trips: continue

            # Route/Service
            gr = Route(route_id=train_no, agency_id=agency.id, short_name=train_no, long_name=t['train_name'], route_type=2)
            session.add(gr); session.flush()

            # Running Days (Using persistent reader)
            with reader.session() as cur:
                cur.execute("SELECT * FROM train_running_days WHERE train_no = ?", (train_no,))
                running = cur.fetchone()
                
            service_id = f"S_{train_no}" if running else "DAILY"
            if running:
                exists = session.query(Calendar).filter(Calendar.service_id == service_id).first()
                if not exists:
                    cal = Calendar(service_id=service_id, monday=bool(running['mon']), tuesday=bool(running['tue']), 
                                  wednesday=bool(running['wed']), thursday=bool(running['thu']),
                                  friday=bool(running['fri']), saturday=bool(running['sat']), sunday=bool(running['sun']),
                                  start_date=date(2020,1,1), end_date=date(2030,12,31))
                    session.add(cal); session.flush()

            trip = Trip(trip_id=train_no, route_id=gr.id, service_id=service_id)
            session.add(trip); session.flush()
            
            vid = str(uuid.uuid4())
            session.add(Vehicle(id=vid, vehicle_number=train_no, type='train', operator='IR'))

            # Route Rows
            with reader.session() as cur:
                cur.execute("SELECT * FROM train_routes WHERE train_no = ? ORDER BY seq_no", (train_no,))
                route_rows = [dict(r) for r in cur.fetchall()]
            
            st_batch, seg_batch, sched_batch = [], [], []
            for i, curr in enumerate(route_rows):
                if curr['station_code'] not in station_mapping: continue
                sid = station_mapping[curr['station_code']]
                arr, dep = parse_time(curr['arrival_time']), parse_time(curr['departure_time'])
                
                st_batch.append({"trip_id": trip.id, "stop_id": sid, "arrival_time": arr, "departure_time": dep, "stop_sequence": curr['seq_no']})
                for day in DAYS_OF_WEEK:
                    sched_batch.append({"station_id": sid, "trip_id": trip.id, "arrival": arr, "departure": dep, "day_of_week": day, "stop_seq": curr['seq_no']})

                if i < len(route_rows) - 1:
                    nxt = route_rows[i+1]
                    if nxt['station_code'] in station_mapping:
                        dur = (nxt['cumulative_travel_minutes'] or 0) - (curr['cumulative_travel_minutes'] or 0)
                        seg_batch.append({
                            "id": str(uuid.uuid4()), "source_station_id": str(sid), "dest_station_id": str(station_mapping[nxt['station_code']]),
                            "trip_id": trip.id, "vehicle_id": vid, "transport_mode": 'train',
                            "departure_time": dep, "arrival_time": parse_time(nxt['arrival_time']),
                            "arrival_day_offset": nxt['day_offset'] or 0, "duration_minutes": dur if dur > 0 else 60,
                            "distance_km": float((nxt['distance_from_source'] or 0) - (curr['distance_from_source'] or 0)),
                            "cost": float((nxt['distance_from_source'] or 0) - (curr['distance_from_source'] or 0)) * 1.2,
                            "operating_days": "1111111"
                        })

            session.bulk_insert_mappings(StopTime, st_batch)
            session.bulk_insert_mappings(StationSchedule, sched_batch)
            session.bulk_insert_mappings(Segment, seg_batch)

            if k % 50 == 0:
                session.commit()
                logger.info(f"Ingested {k} trains...")
                gc.collect()

        session.commit()
        logger.info("✅ Atomic Handover Complete.")
        
    finally:
        session.close()
        reader.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_etl())
