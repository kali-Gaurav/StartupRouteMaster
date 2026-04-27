
import asyncio
import sys
import os
from pathlib import Path
from sqlalchemy import text

# Add backend to path
backend_root = Path(os.getcwd())
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from database.session import SessionTransit, initialize_database_pools
from database.models import Stop, StopTime, Calendar, Trip

async def test():
    try:
        await initialize_database_pools()
        db = SessionTransit()
        
        stops_count = db.query(Stop).count()
        print(f"Stops (Stations) count: {stops_count}")
        
        stop_times_count = db.query(StopTime).count()
        print(f"StopTimes (Schedules) count: {stop_times_count}")
        
        trips_count = db.query(Trip).count()
        print(f"Trips count: {trips_count}")
        
        calendar_count = db.query(Calendar).count()
        print(f"Calendar entries: {calendar_count}")
        
        # Check if there's any trip operating on 2026-05-01 (Friday)
        # 1st May 2026 is a Friday.
        friday_trips = db.query(Calendar).filter(Calendar.friday == True).count()
        print(f"Trips operating on Fridays: {friday_trips}")
        
        db.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
