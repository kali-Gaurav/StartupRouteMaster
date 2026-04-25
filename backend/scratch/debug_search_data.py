
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

from database.session import initialize_database_pools, SessionTransit
from sqlalchemy import text

async def debug():
    await initialize_database_pools()
    s = SessionTransit()
    try:
        # 1. Check Stations
        stations = s.execute(text("SELECT id, stop_id, code, name FROM stops WHERE code IN ('NDLS', 'HWH')")).fetchall()
        print(f"Stations: {stations}")
        
        if not stations:
            print("❌ NDLS or HWH not found in stops table!")
            return
            
        station_ids = [row[0] for row in stations]
        
        # 2. Check Trips connecting these stations
        query = """
            SELECT DISTINCT st1.trip_id
            FROM stop_times st1
            JOIN stop_times st2 ON st1.trip_id = st2.trip_id
            WHERE st1.stop_id = :s1 AND st2.stop_id = :s2
            AND st1.stop_sequence < st2.stop_sequence
        """
        # We don't know which is NDLS and which is HWH ID yet
        ndls_id = next((r[0] for r in stations if r[2] == 'NDLS'), None)
        hwh_id = next((r[0] for r in stations if r[2] == 'HWH'), None)
        
        if ndls_id and hwh_id:
            trips = s.execute(text(query), {"s1": ndls_id, "s2": hwh_id}).fetchall()
            print(f"Direct Trips NDLS -> HWH: {len(trips)}")
            
            if trips:
                sample_trip = trips[0][0]
                service_id = s.execute(text("SELECT service_id FROM trips WHERE id = :tid"), {"tid": sample_trip}).scalar()
                print(f"Sample Trip {sample_trip} has service_id: {service_id}")
                
                calendar = s.execute(text("SELECT * FROM calendar WHERE service_id = :sid"), {"sid": service_id}).fetchone()
                print(f"Calendar for service {service_id}: {calendar}")
        
    finally:
        s.close()

if __name__ == "__main__":
    asyncio.run(debug())
