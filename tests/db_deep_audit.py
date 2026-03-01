import asyncio
import os
import sys
from sqlalchemy import text

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def audit_database():
    logger.info("Deep-diving into Database Table Stats...")
    db = SessionLocal()
    
    tables = [
        "users", "profiles", "stops", "trips", "stop_times", 
        "station_schedule", "train_path", "stop_departures",
        "station_departures_indexed", "gtfs_routes"
    ]
    
    stats = {}
    try:
        for table in tables:
            try:
                # Check if table exists and get count
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                stats[table] = result
            except Exception as e:
                stats[table] = f"ERROR: {str(e).splitlines()[0]}"
        
        logger.info("\nTable Counts:")
        for table, count in stats.items():
            logger.info(f" - {table:30}: {count}")
            
        # Check for sample data in station_schedule if it exists
        if isinstance(stats.get("station_schedule"), int) and stats["station_schedule"] > 0:
            logger.info("\nSample from station_schedule:")
            sample = db.execute(text("SELECT * FROM station_schedule LIMIT 3")).fetchall()
            for row in sample:
                logger.info(f"   {row}")
        else:
            logger.warning("\nstation_schedule is EMPTY or missing. Route engine might be slow!")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(audit_database())
