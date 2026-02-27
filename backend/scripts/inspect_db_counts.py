from database.session import SessionLocal
from database.models import Station, Stop
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def inspect_counts():
    session = SessionLocal()
    try:
        station_count = session.query(Station).count()
        stop_count = session.query(Stop).count()
        logger.info(f"Table 'stations' (deprecated) count: {station_count}")
        logger.info(f"Table 'stops' (GTFS) count: {stop_count}")
        
        if stop_count > 0:
            sample_stop = session.query(Stop).first()
            logger.info(f"Sample Stop: {sample_stop.name} ({sample_stop.code}) ID={sample_stop.id} StopID={sample_stop.stop_id}")
            
        if station_count > 0:
            sample_station = session.query(Station).first()
            logger.info(f"Sample Station: {sample_station.name} ({sample_station.code}) ID={sample_station.id}")
            
    except Exception as e:
        logger.error(f"Error inspecting counts: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    inspect_counts()
