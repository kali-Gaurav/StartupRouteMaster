import asyncio
from sqlalchemy import text
import database.session as ds

async def find_test_data():
    await ds.initialize_database_pools()
    with ds.engine_transit.connect() as conn:
        query = text("""
            SELECT t.service_id, s.source_station_id, s.dest_station_id, t.trip_id
            FROM segments s
            JOIN trips t ON s.trip_id = t.id
            WHERE t.service_id = 'WKD_001'
            LIMIT 10
        """)
        res = conn.execute(query).fetchall()
        for row in res:
            print(f"Service: {row[0]}, Source: {row[1]}, Dest: {row[2]}, Trip: {row[3]}")

if __name__ == "__main__":
    asyncio.run(find_test_data())
