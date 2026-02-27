from database.session import SessionLocal
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_junction_pairs():
    session = SessionLocal()
    try:
        # 1. Identify high-traffic junctions
        junctions_query = text("""
            SELECT s.name, s.stop_id, s.id, COUNT(st.id) as dep_count
            FROM stops s
            JOIN stop_times st ON s.id = st.stop_id
            WHERE s.is_major_junction = true
            GROUP BY s.name, s.stop_id, s.id
            ORDER BY dep_count DESC
            LIMIT 5
        """)
        junctions = session.execute(junctions_query).fetchall()
        logger.info("Major Junctions:")
        for j in junctions:
            logger.info(f"{j.name} ({j.stop_id}) - {j.dep_count} deps")
            
        # 2. Pick a pair that should require a transfer
        # Let's see what lines go through ABU ROAD (ABR) and another junction
        abr_id = 3 # Found earlier
        
        # Find stations on trips through ABR
        dest_query = text("""
            SELECT DISTINCT s.stop_id, s.name, r.long_name
            FROM stop_times st1
            JOIN stop_times st2 ON st1.trip_id = st2.trip_id AND st1.stop_sequence < st2.stop_sequence
            JOIN stops s ON st2.stop_id = s.id
            JOIN trips t ON st1.trip_id = t.id
            JOIN gtfs_routes r ON t.route_id = r.id
            WHERE st1.stop_id = :sid
            LIMIT 10
        """)
        dests = session.execute(dest_query, {"sid": abr_id}).fetchall()
        logger.info(f"Direct destinations from ABR (sid={abr_id}):")
        for d in dests:
            logger.info(f"{d.name} ({d.stop_id}) via {d.long_name}")

        # Let's try to find a destination that is NOT in the above list but is a junction
        # This would require a transfer.
        
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    find_junction_pairs()
