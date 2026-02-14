import sqlite3
import uuid
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import os
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from geoalchemy2.functions import ST_MakePoint # Import ST_MakePoint function

# Import models directly to avoid circular dependency issues with app-level modules
from backend.models import Base, Station, Segment, Vehicle 

# Add imports for Redis and Config
import redis
import json
from backend.config import Config 


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "railway_manager.db")
REDIS_PUB_SUB_CHANNEL = "route_engine_update" # Define a channel name for updates

class OperatingDaysBitmask:
    """Utility to build a 7-character operating days string (Mon-Sun).

    Example: OperatingDaysBitmask.create(True, True, True, True, True, False, False) -> "1111100"
    """
    @staticmethod
    def create(mon: bool=False, tue: bool=False, wed: bool=False, thu: bool=False, fri: bool=False, sat: bool=False, sun: bool=False) -> str:
        return ''.join('1' if v else '0' for v in (mon, tue, wed, thu, fri, sat, sun))


def _parse_time_flexible(tstr: str) -> datetime:
    """Parse time strings like 'HH:MM' or 'HH:MM:SS' into a datetime object.

    - Tries common formats, strips trailing seconds if necessary.
    - Raises ValueError for unrecognized formats so caller can skip bad rows.
    """
    if tstr is None:
        raise ValueError("time string is None")
    s = str(tstr).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # last-resort: if there are extra fractional/garbage seconds, try to truncate to HH:MM
    if s.count(":") >= 2:
        parts = s.split(":")
        s2 = ":".join(parts[:2])
        try:
            return datetime.strptime(s2, "%H:%M")
        except ValueError:
            pass
    raise ValueError(f"Unrecognized time format: {tstr!r}")


def calculate_duration(departure_time: str, arrival_time: str) -> int:
    """Calculate duration in minutes between two time strings; handles overnight and seconds."""
    d = _parse_time_flexible(departure_time)
    a = _parse_time_flexible(arrival_time)
    delta = a - d
    if delta.total_seconds() < 0:
        # arrival is next day
        delta = (a.replace(day=a.day + 1) - d)
    return int(delta.total_seconds() // 60)


class SQLiteReader:
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
        """Reads train schedule data to generate segments with accurate timings and operating days."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Fetch all train schedules and group them
        cursor.execute("""
            SELECT train_no, seq_no, station_code, arrival_time, departure_time, day_offset
            FROM train_schedule
            ORDER BY train_no, seq_no
        """)
        schedule_data = [dict(row) for row in cursor.fetchall()]
        
        train_schedules = {}
        for row in schedule_data:
            train_schedules.setdefault(row['train_no'], []).append(row)

        # Fetch train running days
        cursor.execute("SELECT train_no, mon, tue, wed, thu, fri, sat, sun FROM train_running_days")
        running_days_data = {row['train_no']: OperatingDaysBitmask.create(
            mon=row['mon'], tue=row['tue'], wed=row['wed'], thu=row['thu'], fri=row['fri'], sat=row['sat'], sun=row['sun']
        ) for row in cursor.fetchall()}
        
        # Fetch distances from train_routes for segments (this can be considered static for now)
        # Assuming distance is a property of the physical segment, not the schedule entry
        cursor.execute("""
            SELECT train_no, source_station_code, dest_station_code, distance_km
            FROM (
                SELECT
                    tr.train_no,
                    tr.station_code AS source_station_code,
                    LEAD(tr.station_code, 1) OVER (PARTITION BY tr.train_no ORDER BY tr.seq_no) AS dest_station_code,
                    LEAD(tr.distance_from_source, 1) OVER (PARTITION BY tr.train_no ORDER BY tr.seq_no) - tr.distance_from_source AS distance_km
                FROM train_routes tr
            )
            WHERE dest_station_code IS NOT NULL
        """)
        segment_distances = {}
        for row in cursor.fetchall():
            segment_distances[(row['train_no'], row['source_station_code'], row['dest_station_code'])] = row['distance_km']

        segments = []
        for train_no, stops in train_schedules.items():
            if train_no not in running_days_data:
                logger.warning(f"Skipping train {train_no}: no running days data found.")
                continue

            operating_days = running_days_data[train_no]
            
            # Sort stops by sequence number to ensure correct order
            stops.sort(key=lambda x: x['seq_no'])

            for i in range(len(stops) - 1):
                current_stop = stops[i]
                next_stop = stops[i + 1]

                source_station_code = current_stop['station_code']
                dest_station_code = next_stop['station_code']
                
                # Use arrival_time of next_stop and departure_time of current_stop for segment
                departure_time_str = current_stop['departure_time']
                arrival_time_str = next_stop['arrival_time']
                
                # Calculate duration considering day offsets
                try:
                    # parse flexible time formats and normalize stored times to HH:MM
                    departure_dt = _parse_time_flexible(departure_time_str)
                    arrival_dt = _parse_time_flexible(arrival_time_str)
                    departure_time_norm = departure_dt.strftime("%H:%M")
                    arrival_time_norm = arrival_dt.strftime("%H:%M")

                    # Adjust arrival_dt for day offset
                    effective_arrival_dt = arrival_dt + timedelta(days=next_stop['day_offset'])
                    effective_departure_dt = departure_dt + timedelta(days=current_stop['day_offset'])

                    # compute duration and validate
                    duration_delta = effective_arrival_dt - effective_departure_dt
                    duration_minutes = int(duration_delta.total_seconds() // 60)

                    if duration_minutes <= 0:
                        logger.warning(f"Skipping segment for train {train_no} from {source_station_code} to {dest_station_code}: non-positive duration ({duration_minutes} minutes).")
                        continue

                    distance_km = segment_distances.get((train_no, source_station_code, dest_station_code), 0)
                    if distance_km == 0:
                        logger.warning(f"No distance found for segment {train_no}-{source_station_code}-{dest_station_code}. Setting to 0.")

                    segments.append({
                        'train_no': train_no,
                        'source_station_code': source_station_code,
                        'dest_station_code': dest_station_code,
                        'departure_time': departure_time_norm,
                        'arrival_time': arrival_time_norm,
                        'duration_minutes': duration_minutes,
                        'distance_km': distance_km,
                        'arrival_day_offset': next_stop['day_offset'], # Day offset relative to train's departure day
                        'operator': 'Indian Railways', # Assuming all trains are Indian Railways for now
                        'operating_days': operating_days,
                        'cost': 150.0 # Placeholder cost, should be derived from train_fares table
                    })
                except (TypeError, ValueError) as e:
                    logger.warning(f"Skipping segment for train {train_no} from {source_station_code} to {dest_station_code} due to data error: {e}")
                    continue
        
        conn.close()
        logger.info(f"Generated {len(segments)} segments from schedule data.")
        return segments

class PostgresLoader:
    """Loads data into the PostgreSQL database."""
    def __init__(self, db_url: str | None = None):
        # Allow callers to omit db_url and fall back to Config.DATABASE_URL
        from backend.config import Config as _Config
        db_url = db_url or _Config.DATABASE_URL or "sqlite:///:memory:"
        engine = create_engine(db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db: Session = self.SessionLocal()
        self.vehicle_cache: Dict[str, str] = {}
        Base.metadata.drop_all(engine) # Drop all existing tables
        Base.metadata.create_all(engine) # Ensure tables exist with the latest schema
        
        try:
            # Try enabling PostGIS where available; ignore when not supported (e.g. sqlite tests)
            self.db.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            self.db.commit()
            logger.info("PostGIS extension enabled.")
        except Exception:
            self.db.rollback()

        logger.info(f"Connected to PostgreSQL and ensured tables exist.")

    # ... (rest of the class is largely unchanged, but uses self.db)
    def get_or_create_station(self, code: str, name: str, city: str, lat: Optional[float], lon: Optional[float]) -> Optional[str]:
        station = self.db.query(Station).filter(Station.name == name, Station.city == city).first()
        if station:
            return station.id
        
        geom = None
        if lat is not None and lon is not None:
            geom = ST_MakePoint(lon, lat)

        new_station = Station(
            id=str(uuid.uuid4()), 
            name=name, 
            city=city, 
            latitude=lat or 0.0, 
            longitude=lon or 0.0,
            geom=geom # Populate the geom column
        )
        self.db.add(new_station)
        self.db.commit()
        self.db.refresh(new_station) # Refresh to get the generated geom value if any
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

def validate_etl_data(db: Session, station_code_to_id: Dict[str, str], segments_created: int) -> Dict[str, int]:
    """
    Validate data integrity after ETL completion.
    Returns dict with validation results.
    """
    validation_results = {
        'validation_errors': 0,
        'orphaned_segments': 0,
        'invalid_durations': 0,
        'duplicate_segments': 0
    }

    try:
        # Check for orphaned segments (segments with invalid station references)
        orphaned_query = db.execute("""
            SELECT COUNT(*) FROM segments s
            WHERE NOT EXISTS (SELECT 1 FROM stations st WHERE st.id = s.source_station_id)
            OR NOT EXISTS (SELECT 1 FROM stations st WHERE st.id = s.dest_station_id)
        """)
        validation_results['orphaned_segments'] = orphaned_query.scalar() or 0

        # Check for segments with invalid durations
        invalid_duration_query = db.execute("""
            SELECT COUNT(*) FROM segments WHERE duration_minutes <= 0 OR duration_minutes > 1440
        """)
        validation_results['invalid_durations'] = invalid_duration_query.scalar() or 0

        # Check for duplicate segments (same source, dest, vehicle, departure time)
        duplicate_query = db.execute("""
            SELECT COUNT(*) FROM (
                SELECT source_station_id, dest_station_id, vehicle_id, departure_time, COUNT(*)
                FROM segments
                GROUP BY source_station_id, dest_station_id, vehicle_id, departure_time
                HAVING COUNT(*) > 1
            ) duplicates
        """)
        validation_results['duplicate_segments'] = duplicate_query.scalar() or 0

        # Total validation errors
        validation_results['validation_errors'] = (
            validation_results['orphaned_segments'] +
            validation_results['invalid_durations'] +
            validation_results['duplicate_segments']
        )

        logger.info(f"ETL Validation Results:")
        logger.info(f"  - Orphaned segments: {validation_results['orphaned_segments']}")
        logger.info(f"  - Invalid durations: {validation_results['invalid_durations']}")
        logger.info(f"  - Duplicate segments: {validation_results['duplicate_segments']}")
        logger.info(f"  - Total validation errors: {validation_results['validation_errors']}")

    except Exception as e:
        logger.error(f"ETL validation failed: {e}")
        validation_results['validation_errors'] = -1  # Indicate validation failure

    return validation_results


def run_etl(sqlite_path: str = DEFAULT_SQLITE_PATH, db_url: str | None = None):
    """Run ETL from SQLite -> PostgreSQL (or DB configured via db_url).

    Returns a dict with counts: stations_synced, segments_created, errors
    """
    logger.info("="*60)
    logger.info(f"Starting ETL: {sqlite_path} -> {db_url or 'Config.DATABASE_URL'}")
    logger.info("="*60)

    reader = SQLiteReader(sqlite_path)
    loader = PostgresLoader(db_url)

    results = {
        'stations_synced': 0,
        'segments_created': 0,
        'errors': 0,
    }

    try:
        stations = reader.read_stations_master()
        station_code_to_id = {}
        for s in stations:
            sid = loader.get_or_create_station(s['station_code'], s['station_name'], s['city'], s.get('latitude'), s.get('longitude'))
            if sid:
                station_code_to_id[s['station_code']] = sid
        results['stations_synced'] = len(station_code_to_id)
        logger.info(f"Synced {len(station_code_to_id)} stations.")

        segments_data = reader.read_segment_data()
        created = 0
        for seg_dict in segments_data:
            try:
                vehicle_id = loader.get_or_create_vehicle(seg_dict['train_no'], seg_dict['operator'])
                source_id = station_code_to_id.get(seg_dict['source_station_code'])
                dest_id = station_code_to_id.get(seg_dict['dest_station_code'])

                if not all([vehicle_id, source_id, dest_id]):
                    results['errors'] += 1
                    continue

                if loader.create_segment({
                    "id": str(uuid.uuid4()), "source_station_id": source_id, "dest_station_id": dest_id,
                    "vehicle_id": vehicle_id, "transport_mode": "train", "departure_time": seg_dict['departure_time'],
                    "arrival_time": seg_dict['arrival_time'], "duration_minutes": seg_dict['duration_minutes'],
                    "distance_km": seg_dict['distance_km'], "arrival_day_offset": seg_dict['arrival_day_offset'],
                    "cost": seg_dict['cost'], "operating_days": seg_dict['operating_days'],
                }):
                    created += 1
            except Exception:
                results['errors'] += 1
                continue

        loader.db.commit()
        results['segments_created'] = created
        logger.info(f"✅ Committed all segments. Created {created} segments.")

        # Validate data integrity after ETL
        validation_results = validate_etl_data(loader.db, station_code_to_id, created)
        results.update(validation_results)

        if validation_results['validation_errors'] > 0:
            logger.warning(f"ETL completed with {validation_results['validation_errors']} validation errors")
        else:
            logger.info("✅ ETL validation passed - all data integrity checks successful")

        # After successful update, publish a message to Redis Pub/Sub
        try:
            redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
            message = {"event": "graph_updated", "timestamp": datetime.utcnow().isoformat()}
            redis_client.publish(REDIS_PUB_SUB_CHANNEL, json.dumps(message))
            logger.info(f"Published Redis Pub/Sub message to '{REDIS_PUB_SUB_CHANNEL}': {message}")
        except Exception as pub_sub_e:
            logger.error(f"Failed to publish Redis Pub/Sub message: {pub_sub_e}")

    except Exception as e:
        logger.error(f"ETL failed: {e}", exc_info=True)
        loader.db.rollback()
        results['errors'] += 1
    finally:
        loader.close()
        logger.info("ETL process finished.")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL script to load data from SQLite to PostgreSQL.")
    parser.add_argument("--source", default=DEFAULT_SQLITE_PATH, help="Path to the source SQLite database file.")
    parser.add_argument("--db-url", required=False, help="URL for the target PostgreSQL database. If omitted, uses DATABASE_URL from Config.")
    args = parser.parse_args()
    
    run_etl(sqlite_path=args.source, db_url=args.db_url)