import asyncio
from sqlalchemy import text
import database.session as ds

async def check():
    await ds.initialize_database_pools()
    with ds.engine_transit.connect() as conn:
        for table in ["segments", "trips", "transfers", "station_schedule", "stops"]:
            try:
                res = conn.execute(text(f"SELECT * FROM {table} LIMIT 0"))
                print(f"{table.capitalize()} Columns: {res.keys()}")
            except Exception as e:
                print(f"Error checking {table}: {e}")

if __name__ == "__main__":
    asyncio.run(check())
