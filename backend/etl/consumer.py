import json
import uuid
from kafka import KafkaConsumer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

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

def process_train_schedule(data):
    """Process scraped train schedule data"""
    db = SessionLocal()
    try:
        # Insert into trains table if not exists
        train_query = text("""
            INSERT INTO trains (id, train_number, train_name, created_at, updated_at)
            VALUES (:id, :train_number, :train_name, NOW(), NOW())
            ON CONFLICT (train_number) DO NOTHING
        """)
        db.execute(train_query, {
            'id': str(uuid.uuid4()),
            'train_number': data['train_number'],
            'train_name': data['train_name']
        })

        # Insert schedule
        schedule_query = text("""
            INSERT INTO schedules (id, train_id, created_at, updated_at)
            SELECT :id, id, NOW(), NOW()
            FROM trains WHERE train_number = :train_number
            ON CONFLICT DO NOTHING
        """)
        db.execute(schedule_query, {
            'id': str(uuid.uuid4()),
            'train_number': data['train_number']
        })

        db.commit()
        logger.info(f"Processed train: {data['train_number']}")
    except Exception as e:
        logger.error(f"Error processing train: {e}")
        db.rollback()
    finally:
        db.close()

def process_station(data):
    """Process scraped station data"""
    db = SessionLocal()
    try:
        query = text("""
            INSERT INTO stations (id, station_code, station_name, latitude, longitude, created_at, updated_at)
            VALUES (:id, :station_code, :station_name, :latitude, :longitude, NOW(), NOW())
            ON CONFLICT (station_code) DO NOTHING
        """)
        db.execute(query, {
            'id': str(uuid.uuid4()),
            'station_code': data['station_code'],
            'station_name': data['station_name'],
            'latitude': data.get('latitude'),
            'longitude': data.get('longitude')
        })
        db.commit()
        logger.info(f"Processed station: {data['station_code']}")
    except Exception as e:
        logger.error(f"Error processing station: {e}")
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