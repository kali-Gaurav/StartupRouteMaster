import sqlite3
import uuid
import argparse
from datetime import datetime
from typing import Dict, List, Optional
import logging
import os
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker

# Import models directly to avoid circular dependency issues with app-level modules
from models import Base, Station, Segment, Vehicle 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "railway_manager.db")

class OperatingDaysBitmask:
    """Utility to build a 7-character operating days string (Mon-Sun).

    Example: OperatingDaysBitmask.create(True, True, True, True, True, False, False) -> "1111100"
    """
    @staticmethod
    def create(mon: bool=False, tue: bool=False, wed: bool=False, thu: bool=False, fri: bool=False, sat: bool=False, sun: bool=False) -> str:
        return ''.join('1' if v else '0' for v in (mon, tue, wed, thu, fri, sat, sun))


def calculate_duration(departure_time: str, arrival_time: str) -> int:
    """Calculate duration in minutes between two HH:MM strings; handles overnight."""
    fmt = "%H:%M"
    d = datetime.strptime(departure_time, fmt)
    a = datetime.strptime(arrival_time, fmt)
    delta = a - d
    if delta.total_seconds() < 0:
        # arrival is next day
        delta = (a.replace(day=a.day + 1) - d)
    return int(delta.total_seconds() // 60)


class SQLiteReader:
    # ... (rest of the class is unchanged)
    """Reads data from the SQLite railway_manager.db."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"SQLite DB not found: {db_path}")
        logger.info(f"Connected to SQLite: {db_path}")

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def read_stations_master(self) -> List[Dict]:
        """Reads all stations from the stations_master table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT station_code, station_name, city, state, latitude, longitude FROM stations_master ORDER BY station_code")
        stations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        logger.info(f"Read {len(stations)} stations from SQLite.")
        return stations

    def read_segment_data(self) -> List[Dict]:
        """Reads train route data to generate segments."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT train_no, seq_no, station_code, departure_time, arrival_time,
                   distance_from_source, cumulative_travel_minutes, day_offset
            FROM train_routes
            WHERE departure_time IS NOT NULL AND arrival_time IS NOT NULL
            ORDER BY train_no, seq_no
        """)
        routes_data = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        trains = {}
        for row in routes_data:
            trains.setdefault(row['train_no'], []).append(row)

        segments = []
        for train_no, stops in trains.items():
            stops.sort(key=lambda x: x['seq_no'])
            for i in range(len(stops) - 1):
                current_stop = stops[i]
                next_stop = stops[i + 1]
                try:
                    duration = next_stop['cumulative_travel_minutes'] - current_stop['cumulative_travel_minutes']
                    distance = next_stop['distance_from_source'] - current_stop['distance_from_source']
                    
                    if duration <= 0:
                        continue

                    segments.append({
                        'train_no': train_no,
                        'source_station_code': current_stop['station_code'],
                        'dest_station_code': next_stop['station_code'],
                        'departure_time': current_stop['departure_time'],
                        'arrival_time': next_stop['arrival_time'],
                        'duration_minutes': duration,
                        'distance_km': distance,
                        'arrival_day_offset': next_stop['day_offset'] - current_stop['day_offset'],
                        'operator': 'Indian Railways',
                        'operating_days': '1111111',
                        'cost': 150.0
                    })
                except (TypeError, ValueError) as e:
                    logger.warning(f"Skipping segment for train {train_no} due to data error: {e}")
                    continue
        logger.info(f"Generated {len(segments)} segments from {len(trains)} trains.")
        return segments

class PostgresLoader:
    """Loads data into the PostgreSQL database."""
    def __init__(self, db_url: str):
        engine = create_engine(db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db: Session = self.SessionLocal()
        self.vehicle_cache: Dict[str, str] = {}
        Base.metadata.drop_all(engine) # Drop all existing tables
        Base.metadata.create_all(engine) # Ensure tables exist with the latest schema
        logger.info(f"Connected to PostgreSQL and ensured tables exist.")

    # ... (rest of the class is largely unchanged, but uses self.db)
    def get_or_create_station(self, code: str, name: str, city: str, lat: Optional[float], lon: Optional[float]) -> Optional[str]:
        station = self.db.query(Station).filter(Station.name == name, Station.city == city).first()
        if station:
            return station.id
        new_station = Station(id=str(uuid.uuid4()), name=name, city=city, latitude=lat or 0.0, longitude=lon or 0.0)
        self.db.add(new_station)
        self.db.commit()
        return new_station.id

    def get_or_create_vehicle(self, train_no: str, operator: str) -> Optional[str]:
        """Gets or creates a vehicle and returns its UUID."""
        train_no_str = str(train_no) # Explicitly cast to string
        if train_no_str in self.vehicle_cache:
            return self.vehicle_cache[train_no_str]
            
        vehicle = self.db.query(Vehicle).filter(Vehicle.vehicle_number == train_no_str).first()
        if vehicle:
            self.vehicle_cache[train_no_str] = vehicle.id
            return vehicle.id

        new_vehicle = Vehicle(id=str(uuid.uuid4()), vehicle_number=train_no_str, type='train', operator=operator)
        self.db.add(new_vehicle)
        self.db.commit()
        self.vehicle_cache[train_no_str] = new_vehicle.id
        return new_vehicle.id

    def create_segment(self, segment_data: Dict) -> bool:
        existing = self.db.query(Segment).filter(
            and_(
                Segment.source_station_id == segment_data["source_station_id"],
                Segment.dest_station_id == segment_data["dest_station_id"],
                Segment.vehicle_id == segment_data["vehicle_id"],
                Segment.departure_time == segment_data["departure_time"],
            )
        ).first()
        if not existing:
            self.db.add(Segment(**segment_data))
            return True
        return False

    def close(self):
        self.db.close()

def run_etl(sqlite_path: str, db_url: str):
    logger.info("="*60)
    logger.info(f"Starting ETL: {sqlite_path} -> PostgreSQL")
    logger.info("="*60)

    reader = SQLiteReader(sqlite_path)
    loader = PostgresLoader(db_url)

    try:
        stations = reader.read_stations_master()
        station_code_to_id = {s['station_code']: loader.get_or_create_station(s['station_code'], s['station_name'], s['city'], s.get('latitude'), s.get('longitude')) for s in stations}
        logger.info(f"Synced {len(station_code_to_id)} stations.")

        segments_data = reader.read_segment_data()
        for seg_dict in segments_data:
            vehicle_id = loader.get_or_create_vehicle(seg_dict['train_no'], seg_dict['operator'])
            source_id = station_code_to_id.get(seg_dict['source_station_code'])
            dest_id = station_code_to_id.get(seg_dict['dest_station_code'])

            if not all([vehicle_id, source_id, dest_id]):
                continue
            
            loader.create_segment({
                "id": str(uuid.uuid4()), "source_station_id": source_id, "dest_station_id": dest_id,
                "vehicle_id": vehicle_id, "transport_mode": "train", "departure_time": seg_dict['departure_time'],
                "arrival_time": seg_dict['arrival_time'], "duration_minutes": seg_dict['duration_minutes'],
                "distance_km": seg_dict['distance_km'], "arrival_day_offset": seg_dict['arrival_day_offset'],
                "cost": seg_dict['cost'], "operating_days": seg_dict['operating_days'],
            })
        
        loader.db.commit()
        logger.info(f"✅ Committed all segments.")

    except Exception as e:
        logger.error(f"ETL failed: {e}", exc_info=True)
        loader.db.rollback()
    finally:
        loader.close()
        logger.info("ETL process finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL script to load data from SQLite to PostgreSQL.")
    parser.add_argument("--source", default=DEFAULT_SQLITE_PATH, help="Path to the source SQLite database file.")
    parser.add_argument("--db-url", required=True, help="URL for the target PostgreSQL database.")
    args = parser.parse_args()
    
    run_etl(sqlite_path=args.source, db_url=args.db_url)