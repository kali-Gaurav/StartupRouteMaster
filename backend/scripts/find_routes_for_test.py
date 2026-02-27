from database.session import SessionLocal
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_routes():
    session = SessionLocal()
    try:
        # Step 1: Find trips passing through 'ABU ROAD' (ABR)
        query = text("""
            SELECT s1.stop_id as src, s2.stop_id as dst, t.trip_id, t.route_id, r.long_name
            FROM stop_times st1
            JOIN stop_times st2 ON st1.trip_id = st2.trip_id AND st1.stop_sequence < st2.stop_sequence
            JOIN stops s1 ON st1.stop_id = s1.id
            JOIN stops s2 ON st2.stop_id = s2.id
            JOIN trips t ON st1.trip_id = t.id
            JOIN gtfs_routes r ON t.route_id = r.id
            WHERE s1.stop_id = 'ABR'
            LIMIT 5
        """)
        res = session.execute(query)
        logger.info("Found routes from ABR:")
        for row in res:
            logger.info(row)
            
    except Exception as e:
        logger.error(f"Error finding routes: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    find_routes()
