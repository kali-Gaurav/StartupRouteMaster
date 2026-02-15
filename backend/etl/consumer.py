import json
import uuid
from kafka import KafkaConsumer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.models import Stop, Agency, Route, Calendar, Trip, StopTime
from geoalchemy2.functions import ST_MakePoint
from sqlalchemy.exc import IntegrityError
import logging
from datetime import datetime, time, date, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = "postgresql://postgres:postgres@db:5432/postgres"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Kafka setup
consumer = KafkaConsumer(
    'scraped_data',
    bootstrap_servers=['kafka:9092'],
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='etl_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

def get_or_create_agency(db, name="Indian Railways"):
    """Get or create a default agency."""
    agency_id = str(uuid.uuid4())
    agency = db.query(Agency).filter(Agency.name == name).first()
    if not agency:
        agency = Agency(
            agency_id=agency_id,
            name=name,
            url="http://indianrailways.gov.in", # Placeholder
            timezone="Asia/Kolkata" # Placeholder
        )
        db.add(agency)
        db.flush() # Flush to get the ID
    return agency

def get_or_create_calendar(db, service_id_prefix="daily_service_", default_start_date=date(2023, 1, 1), default_end_date=date(2024, 12, 31)):
    """Get or create a generic daily calendar."""
    # This simplified version does not depend on specific scraped dates,
    # but rather ensures a general daily service calendar exists.
    service_id = service_id_prefix + default_start_date.strftime('%Y%m%d') # Example service_id
    calendar = db.query(Calendar).filter(Calendar.service_id == service_id).first()
    if not calendar:
        calendar = Calendar(
            service_id=service_id,
            monday=True, tuesday=True, wednesday=True, thursday=True,
            friday=True, saturday=True, sunday=True, # Assuming daily for simplicity
            start_date=default_start_date,
            end_date=default_end_date
        )
        db.add(calendar)
        db.flush() # Flush to get the ID
    return calendar

def process_train_schedule(data):
    """Process scraped train schedule data and map to GTFS models."""
    db = SessionLocal()
    try:
        # 1. Handle Agency
        agency = get_or_create_agency(db)

        # 2. Handle Route (gtfs_routes)
        train_number = data['train_number']
        train_name = data['train_name']

        route = db.query(Route).filter(Route.route_id == train_number).first()
        if not route:
            route = Route(
                route_id=train_number,
                agency_id=agency.id,
                short_name=train_number,
                long_name=train_name,
                route_type=2 # 2 for Rail
            )
            db.add(route)
            db.flush()

        # 3. Handle Calendar
        # For simplicity, using a generic daily calendar that exists.
        # In real-world, operating days are crucial and would be scraped,
        # leading to specific calendar entries.
        calendar = get_or_create_calendar(db) # Use the generic daily calendar

        # 4. Handle Trip
        # Generate a unique trip_id for this specific run of the train
        # Assuming scraped_at gives us the context of the day the schedule is valid for.
        scraped_datetime_str = data.get('scraped_at') # e.g., '2026-02-15T19:40:41.234567'
        scraped_date = datetime.fromisoformat(scraped_datetime_str).date() if scraped_datetime_str else datetime.utcnow().date()
        
        # trip_id needs to be unique. Using train_number + date + source + destination
        trip_id = f"{train_number}_{scraped_date.strftime('%Y%m%d')}_{data['source_station']}-{data['destination_station']}"
        trip = db.query(Trip).filter(Trip.trip_id == trip_id).first()
        if not trip:
            trip = Trip(
                trip_id=trip_id,
                route_id=route.id,
                service_id=calendar.id, # Link to the generic daily calendar
                headsign=data['destination_station'],
                direction_id=0 # 0 for outbound, 1 for inbound (default)
            )
            db.add(trip)
            db.flush() # Flush to get trip.id

            # 5. Handle StopTimes
            for stop_sequence_idx, stop_data in enumerate(data['stops']):
                stop_sequence = stop_sequence_idx + 1 # Scrapy item gives 0-indexed list
                station_code = stop_data['station']

                stop_obj = db.query(Stop).filter(Stop.stop_id == station_code).first()
                if not stop_obj:
                    # If stop is not found, it means process_station failed or hasn't run.
                    # Create a minimal placeholder stop to allow the trip to be saved.
                    logger.warning(f"Stop {station_code} not found during train schedule processing. Creating placeholder.")
                    stop_obj = Stop(
                        stop_id=station_code,
                        name=station_code,
                        code=station_code,
                        latitude=0.0,
                        longitude=0.0,
                        geom=ST_MakePoint(0.0, 0.0, 4326) # Default to (0,0)
                    )
                    db.add(stop_obj)
                    db.flush()

                # Parse times. Scraped times are strings, need to convert to datetime.time objects
                # Assuming times are in HH:MM:SS or HH:MM format
                try:
                    arrival_time_str = stop_data.get('arrival_time')
                    arrival_time_obj = datetime.strptime(arrival_time_str, '%H:%M:%S').time() if arrival_time_str else None
                except ValueError:
                    try:
                        arrival_time_obj = datetime.strptime(arrival_time_str, '%H:%M').time() if arrival_time_str else None
                    except ValueError:
                        arrival_time_obj = time(0,0) # Default or log error
                        logger.warning(f"Could not parse arrival_time {arrival_time_str} for stop {station_code}")
                
                try:
                    departure_time_str = stop_data.get('departure_time')
                    departure_time_obj = datetime.strptime(departure_time_str, '%H:%M:%S').time() if departure_time_str else None
                except ValueError:
                    try:
                        departure_time_obj = datetime.strptime(departure_time_str, '%H:%M').time() if departure_time_str else None
                    except ValueError:
                        departure_time_obj = time(0,0) # Default or log error
                        logger.warning(f"Could not parse departure_time {departure_time_str} for stop {station_code}")

                # Ensure non-null times, even if defaulted
                if arrival_time_obj is None: arrival_time_obj = time(0,0)
                if departure_time_obj is None: departure_time_obj = time(0,0)


                stop_time = StopTime(
                    trip_id=trip.id,
                    stop_id=stop_obj.id,
                    arrival_time=arrival_time_obj,
                    departure_time=departure_time_obj,
                    stop_sequence=stop_sequence,
                    cost=0.0 # Cost per segment not available from scraper, default to 0.0
                )
                db.add(stop_time)
        
        db.commit()
        logger.info(f"Processed train schedule for {train_number} on {scraped_date}")
    except IntegrityError as e:
        db.rollback()
        logger.warning(f"Integrity error for train schedule {train_number} (trip_id: {trip_id if 'trip_id' in locals() else 'N/A'}): {e}. Skipping due to duplicate.")
    except Exception as e:
        db.error(f"Error processing train schedule {train_number}: {e}")
        db.rollback()
    finally:
        db.close()

def process_station(data):
    """Process scraped station data and map to the Stop model."""
    db = SessionLocal()
    try:
        station_code = data['station_code']

        existing_stop = db.query(Stop).filter(Stop.stop_id == station_code).first()

        if existing_stop:
            logger.info(f"Updating existing station: {station_code}")
            existing_stop.name = data['station_name']
            existing_stop.city = data.get('city')
            existing_stop.state = data.get('state')
            existing_stop.latitude = data.get('latitude')
            existing_stop.longitude = data.get('longitude')
            if data.get('latitude') is not None and data.get('longitude') is not None:
                existing_stop.geom = ST_MakePoint(data['longitude'], data['latitude'], 4326)
        else:
            logger.info(f"Adding new station: {station_code}")
            new_stop = Stop(
                stop_id=station_code,
                name=data['station_name'],
                code=station_code,
                city=data.get('state'), # Mapping Scrapy Item's `state` to `Stop.city` for now, adjust later if city data is available.
                state=data.get('state'), # Mapping Scrapy Item's `state` to `Stop.state`
                latitude=data.get('latitude'),
                longitude=data.get('longitude'),
            )
            if data.get('latitude') is not None and data.get('longitude') is not None:
                new_stop.geom = ST_MakePoint(data['longitude'], data['latitude'], 4326)
            
            db.add(new_stop)
        
        db.commit()
        logger.info(f"Processed station: {station_code}")
    except IntegrityError as e:
        db.rollback()
        logger.warning(f"Integrity error for station {station_code}: {e}. Skipping due to duplicate.")
    except Exception as e:
        logger.error(f"Error processing station {station_code}: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    logger.info("Starting ETL consumer...")
    for message in consumer:
        data = message.value
        logger.info(f"Received: {data}")

        if 'train_number' in data:
            process_train_schedule(data)
        elif 'station_code' in data:
            process_station(data)
        else:
            logger.warning(f"Unknown data type: {data}")

if __name__ == "__main__":
    main()