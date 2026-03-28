import asyncio
from database.session import SessionTransit, initialize_database_pools
from sqlalchemy import text

async def check():
    await initialize_database_pools()
    s = SessionTransit()
    res = s.execute(text("SELECT MIN(start_date), MAX(end_date) FROM calendar")).fetchone()
    print(f"Active Service Schedule Range: {res[0]} to {res[1]}")
    
    res2 = s.execute(text("SELECT date FROM calendar_dates LIMIT 5")).fetchall()
    print(f"Sample Exception Dates: {res2}")
    s.close()

if __name__ == "__main__":
    asyncio.run(check())
