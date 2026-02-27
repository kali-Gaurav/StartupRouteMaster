import asyncio
import logging
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, text
from collections import defaultdict
from datetime import time

from database.config import Config
from database import Base
from database.models import (
    Agency, Stop, Route as GtfsRoute, Calendar, Trip, StopTime,
    User, Booking, Review, Payment, UnlockedRoute, CommissionTracking, Disruption,
    SeatInventory, PrecalculatedRoute,
)
from geoalchemy2.shape import from_shape
from shapely.geometry import Point


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- In-memory maps for migrating Foreign Keys ---
# Maps old string IDs to new integer IDs
stop_id_map = {} # old_station_uuid -> new_stop_int_id
agency_id_map = {} # agency_name -> new_agency_int_id
route_id_map = {} # old_vehicle_id -> new_route_int_id
service_id_map = {} # service_name -> new_calendar_int_id

def get_db_session():
    """Provides a database session for the script."""
    engine = create_engine(Config.DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def clear_new_tables(db: Session):
    """Clears all data from the new GTFS tables to ensure a clean migration."""
    logger.info("Disabling constraints and clearing new GTFS tables...")
    
    table_names = [
        StopTime.__tablename__,
        Trip.__tablename__,
        Calendar.__tablename__,
        GtfsRoute.__tablename__,
        Stop.__tablename__,
        Agency.__tablename__,
    ]
    
    # Using CASCADE to handle foreign key dependencies
    for table in table_names:
        try:
            db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
            logger.info(f"Cleared table: {table}")
        except Exception as e:
            logger.error(f"Error clearing table {table}: {e}")
            db.rollback()
            raise

    db.commit()
    logger.info("Finished clearing tables.")


def migrate_stops(db: Session):
    """Migrates data from old 'stations' to the new 'stops' table."""
    logger.info("Migrating stops from old 'stations' table...")
    
    try:
        # Fetch all stations from the old table
        old_stations = db.execute(text("SELECT id, name, city, latitude, longitude FROM stations;")).fetchall()
        
        new_stops = []
        for station in old_stations:
            new_stop = Stop(
                stop_id=station.id,  # Store old UUID in the public-facing ID
                name=station.name,
                city=station.city,
                latitude=station.latitude,
                longitude=station.longitude,
                geom=from_shape(Point(station.longitude, station.latitude), srid=4326),
                location_type=1 # Assuming all old stations are parent stations
            )
            new_stops.append(new_stop)
        
        db.add_all(new_stops)
        db.commit()

        # Populate the stop_id_map
        for stop in new_stops:
            stop_id_map[stop.stop_id] = stop.id # stop_id has the old UUID

        logger.info(f"Successfully migrated {len(new_stops)} stops.")
    except Exception as e:
        logger.error(f"Error during stop migration: {e}")
        db.rollback()
        raise

def migrate_agencies_and_routes(db: Session):
    """Migrates data to new 'agency' and 'gtfs_routes' tables."""
    logger.info("Migrating agencies and routes...")
    try:
        # 1. Migrate Agencies from old 'vehicles' table
        operators = db.execute(text("SELECT DISTINCT operator FROM vehicles;")).fetchall()
        new_agencies = [Agency(name=op.operator, url="http://example.com", timezone="UTC", agency_id=op.operator) for op in operators]
        db.add_all(new_agencies)
        db.commit()
        
        for agency in new_agencies:
            agency_id_map[agency.name] = agency.id
        logger.info(f"Migrated {len(new_agencies)} agencies.")

        # 2. Migrate Routes from old 'segments' and 'vehicles'
        # We create one route per vehicle to mimic the old logic.
        vehicle_routes = db.execute(text("""
            SELECT DISTINCT v.id as vehicle_id, v.operator, v.type
            FROM vehicles v JOIN segments s ON v.id = s.vehicle_id;
        """)).fetchall()

        new_routes = []
        route_type_map = {'train': 2, 'bus': 3, 'flight': 4}
        for vr in vehicle_routes:
            agency_id = agency_id_map.get(vr.operator)
            if not agency_id:
                logger.warning(f"Could not find agency_id for operator: {vr.operator}")
                continue
            
            new_route = GtfsRoute(
                route_id=vr.vehicle_id, # Use vehicle_id as the public route identifier
                agency_id=agency_id,
                short_name=vr.vehicle_id[:8],
                long_name=f"{vr.type.capitalize()} service for vehicle {vr.vehicle_id}",
                route_type=route_type_map.get(vr.type, 3) # Default to bus
            )
            new_routes.append(new_route)

        db.add_all(new_routes)
        db.commit()

        for route in new_routes:
            route_id_map[route.route_id] = route.id # route.route_id has the vehicle_id
        logger.info(f"Migrated {len(new_routes)} routes.")

    except Exception as e:
        logger.error(f"Error during agency/route migration: {e}")
        db.rollback()
        raise

def migrate_trips_and_stop_times(db: Session):
    """Infers trips from old 'segments' table and populates Trips and StopTimes."""
    logger.info("Migrating trips and stop_times...")
    try:
        # 1. Create a default Calendar service
        default_service_name = "daily_service"
        daily_service = Calendar(
            service_id=default_service_name,
            monday=True, tuesday=True, wednesday=True, thursday=True, friday=True,
            saturday=True, sunday=True,
            start_date=datetime(2020, 1, 1).date(),
            end_date=datetime(2030, 12, 31).date()
        )
        db.add(daily_service)
        db.commit()
        service_id_map[default_service_name] = daily_service.id
        logger.info("Created default daily service calendar.")

        # 2. Fetch all segments, ordered to reconstruct trips
        segments = db.execute(text("""
            SELECT vehicle_id, source_station_id, dest_station_id, departure_time, arrival_time, cost
            FROM segments
            WHERE vehicle_id IS NOT NULL
            ORDER BY vehicle_id, departure_time, arrival_time;
        """)).fetchall()
        
        segments_by_trip = defaultdict(list)
        for seg in segments:
            segments_by_trip[seg.vehicle_id].append(seg)

        logger.info(f"Found {len(segments_by_trip)} potential trips to migrate.")

        new_trips = []
        new_stop_times = []
        for vehicle_id, trip_segments in segments_by_trip.items():
            if not trip_segments:
                continue

            gtfs_route_id = route_id_map.get(vehicle_id)
            if not gtfs_route_id:
                logger.warning(f"Skipping trip for vehicle_id {vehicle_id} as it has no corresponding route.")
                continue

            # Create one Trip for this group of segments
            new_trip = Trip(
                trip_id=f"trip_{vehicle_id}",
                route_id=gtfs_route_id,
                service_id=daily_service.id,
                headsign=f"Service for {vehicle_id}"
            )
            new_trips.append(new_trip)
        
        db.add_all(new_trips)
        db.commit() # Commit trips to get their generated integer IDs

        trip_map = {trip.trip_id: trip.id for trip in new_trips}

        for trip in new_trips:
            vehicle_id = trip.trip_id.replace("trip_", "")
            trip_segments = segments_by_trip[vehicle_id]
            
            # Create the first stop time from the source of the first segment
            first_segment = trip_segments[0]
            source_stop_id = stop_id_map.get(first_segment.source_station_id)
            if not source_stop_id: continue

            # Accept either a string ("HH:MM") or a time object returned by the DB
            dep_val = first_segment.departure_time
            try:
                if isinstance(dep_val, str):
                    dep_time_obj = time.fromisoformat(dep_val)
                else:
                    dep_time_obj = dep_val
            except Exception:
                logger.warning(f"Invalid time format '{dep_val}' for vehicle {vehicle_id}. Skipping first stop.")
                continue

            new_stop_times.append(StopTime(
                trip_id=trip.id,
                stop_id=source_stop_id,
                arrival_time=dep_time_obj, # Arrival and departure are the same for the first stop
                departure_time=dep_time_obj,
                stop_sequence=1,
                cost=0
            ))

            # Create subsequent stop times from the destination of each segment
            for i, segment in enumerate(trip_segments):
                dest_stop_id = stop_id_map.get(segment.dest_station_id)
                if not dest_stop_id: continue

                # Accept string or time object for arrival/departure times
                try:
                    arr_val = segment.arrival_time
                    if isinstance(arr_val, str):
                        arr_time_obj = time.fromisoformat(arr_val)
                    else:
                        arr_time_obj = arr_val

                    if i + 1 < len(trip_segments):
                        next_dep_val = trip_segments[i+1].departure_time
                        dep_time_obj_next = time.fromisoformat(next_dep_val) if isinstance(next_dep_val, str) else next_dep_val
                    else:
                        dep_time_obj_next = arr_time_obj
                except Exception:
                    logger.warning(f"Invalid time format in segment for vehicle {vehicle_id}. Skipping stop.")
                    continue

                new_stop_times.append(StopTime(
                    trip_id=trip.id,
                    stop_id=dest_stop_id,
                    arrival_time=arr_time_obj,
                    departure_time=dep_time_obj_next, # Departure time is from the *next* segment, or same as arrival if last stop
                    stop_sequence=i + 2,
                    cost=segment.cost
                ))
        
        db.add_all(new_stop_times)
        db.commit()
        logger.info(f"Successfully migrated {len(new_trips)} trips and {len(new_stop_times)} stop times.")

    except Exception as e:
        logger.error(f"Error during trip/stop_time migration: {e}", exc_info=True)
        db.rollback()
        raise


def main():
    """Main function to run the migration."""
    db: Session = get_db_session()
    
    try:
        clear_new_tables(db)
        migrate_stops(db)
        migrate_agencies_and_routes(db)
        migrate_trips_and_stop_times(db)
        logger.info("Data migration script finished successfully!")
    except Exception as e:
        logger.error(f"A critical error occurred during migration: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()

