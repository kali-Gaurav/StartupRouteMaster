import asyncio
from sqlalchemy import text
import database.session as ds

async def check_segments():
    await ds.initialize_database_pools()
    with ds.engine_transit.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM segments")).scalar()
        print(f"Segments Total: {count}")
        
        if count > 0:
            res = conn.execute(text("SELECT trip_id, source_station_id, dest_station_id FROM segments LIMIT 5")).fetchall()
            for row in res:
                print(f"Trip ID: {row[0]}, Source: {row[1]}, Dest: {row[2]}")

if __name__ == "__main__":
    asyncio.run(check_segments())
