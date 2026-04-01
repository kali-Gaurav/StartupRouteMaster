import asyncio
from database.session import initialize_database_pools, get_raw_transit_conn
from sqlalchemy import text

async def test():
    await initialize_database_pools()
    async with get_raw_transit_conn() as conn:
        res = await conn.execute(text("PRAGMA table_info(trips)"))
        print(f"Trips columns: {res.fetchall()}")
        
        # Check first row of trips
        res = await conn.execute(text("SELECT * FROM trips LIMIT 1"))
        print(f"Trips sample: {res.fetchone()}")

if __name__ == "__main__":
    asyncio.run(test())
