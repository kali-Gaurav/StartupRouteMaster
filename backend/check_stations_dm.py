import asyncio
from database.session import SessionTransit, initialize_database_pools
from sqlalchemy import text

async def list_stations():
    await initialize_database_pools()
    s = SessionTransit()
    res = s.execute(text("SELECT id, code, name FROM stops WHERE name LIKE '%DELHI%' OR name LIKE '%MUMBAI%' LIMIT 20"))
    for r in res:
        print(f"{r[0]:6} | {r[1]:8} | {r[2]}")
    s.close()

if __name__ == "__main__":
    asyncio.run(list_stations())
