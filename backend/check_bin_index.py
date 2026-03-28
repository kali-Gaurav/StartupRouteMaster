import asyncio
from database.session import SessionTransit, initialize_database_pools
from sqlalchemy import text

async def check():
    await initialize_database_pools()
    s = SessionTransit()
    res = s.execute(text("SELECT station_code FROM station_transit_index_bin LIMIT 5")).fetchall()
    print("Binary Index Station Codes:")
    for r in res:
        print(f"  - {r[0]}")
    s.close()

if __name__ == "__main__":
    asyncio.run(check())
